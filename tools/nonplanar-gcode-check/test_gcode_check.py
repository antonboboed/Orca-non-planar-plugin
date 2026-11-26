#!/usr/bin/env python3
"""Unit tests for gcode_check.py. Run: python3 -m unittest -v test_gcode_check.py"""

import math
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gcode_check as gc  # noqa: E402


def run(lines):
    return gc.Checker().run(lines)


def codes(report, level="error"):
    return [i.code for i in report.issues if i.level == level]


class PlanarTests(unittest.TestCase):
    def test_planar_square_is_clean(self):
        g = [
            "G90", "M83", "G1 Z0.2 F600",
            "G1 X10 Y0 E1.0 F1200", "G1 X10 Y10 E2.0", "G1 X0 Y10 E3.0", "G1 X0 Y0 E4.0",
            "G1 Z0.4", "G1 X5 Y5 F9000",   # travel above printed layer
        ]
        r = run(g)
        self.assertEqual(codes(r), [])
        self.assertEqual(r.counts.get("nonplanar_extrusion_moves", 0), 0)

    def test_extrusion_below_bed_is_error(self):
        r = run(["G90", "M83", "G1 X0 Y0 Z-0.1", "G1 X5 Y0 E1"])
        self.assertIn("Z_NEGATIVE", codes(r))

    def test_calibration_touch_below_bed_is_not_error(self):
        # Bambu startup: nozzle pressed on the exposed steel below Z=0 with no extrusion.
        r = run(["G90", "M83", "G1 X0 Y0 Z0.5", "G1 X128 Y261 Z-1.5", "G1 X125 Y259 Z-1.01"])
        self.assertNotIn("Z_NEGATIVE", codes(r))
        self.assertEqual(codes(r), [])


class SlopeTests(unittest.TestCase):
    def test_extrusion_below_limit_is_info_not_error(self):
        # 10 degrees over 5 mm: tan(10) * 5 = 0.88 mm
        dz = 5 * math.tan(math.radians(10))
        r = run(["G90", "M83", "G1 X0 Y0 Z1.0", f"G1 X5 Y0 Z{1.0 + dz:.4f} E1.0"])
        self.assertEqual(codes(r), [])
        self.assertEqual(r.counts.get("nonplanar_extrusion_moves"), 1)
        self.assertLess(r.max_slope_deg, 12.0)

    def test_extrusion_above_limit_is_error(self):
        dz = 5 * math.tan(math.radians(15))
        r = run(["G90", "M83", "G1 X0 Y0 Z1.0", f"G1 X5 Y0 Z{1.0 + dz:.4f} E1.0"])
        self.assertIn("SLOPE", codes(r))

    def test_vertical_z_hop_is_not_slope_error(self):
        r = run(["G90", "G1 X0 Y0 Z1.0", "G1 Z1.4", "G1 X0.2 Y0 Z1.4"])
        self.assertNotIn("SLOPE", codes(r))

    def test_relative_xyz_mode(self):
        dz = 5 * math.tan(math.radians(15))
        r = run(["G90", "G1 Z1.0", "G91", f"G1 X5 Z{dz:.4f} E1", "G90"])
        self.assertIn("SLOPE", codes(r))


class CollisionTests(unittest.TestCase):
    def _wall(self, z):
        # Material at height z, along y=0 from x=0..20 (bead written as extrusion).
        return ["G90", "M83", f"G1 X0 Y0 Z{z:.3f}", f"G1 X20 Y0 E5"]

    def test_travel_into_taller_material_collides(self):
        # Material top at 5.0; nozzle passes at z=4.5, 0.2 mm off the bead -> inside the cone.
        g = self._wall(5.0) + ["G1 Z8.0", "G1 X10 Y5", "G1 Z4.5", "G1 Y0.2"]
        r = run(g)
        self.assertIn("COLLISION", codes(r))

    def test_travel_far_from_material_is_clear(self):
        g = self._wall(5.0) + ["G1 Z8.0", "G1 X10 Y5", "G1 Z4.5", "G1 X15 Y5"]
        r = run(g)
        self.assertNotIn("COLLISION", codes(r))

    def test_travel_above_material_is_clear(self):
        g = self._wall(5.0) + ["G1 Z8.0", "G1 X10 Y0.2"]
        r = run(g)
        self.assertNotIn("COLLISION", codes(r))

    def test_material_at_nozzle_height_is_allowed(self):
        # Printing the next bead next to the one at the same height must not be a collision.
        g = ["G90", "M83", "G1 X0 Y0 Z1.0", "G1 X20 Y0 E5", "G1 X20 Y0.4 E5.2"]
        r = run(g)
        self.assertNotIn("COLLISION", codes(r))

    def test_high_material_is_flagged_as_unchecked(self):
        # Material 4 mm above the nozzle: heater-block zone, must be reported, not silently passed.
        g = self._wall(5.0) + ["G1 Z1.0", "G1 X10 Y20"]
        r = run(g)
        self.assertIn("UNCHECKED_HIGH", codes(r, level="warning"))


class RegressionTests(unittest.TestCase):
    def test_own_bead_is_not_material_for_next_move(self):
        # Nonplanar bead descending along its own path: the nozzle is always at the bead's end.
        g = ["G90", "M83", "G1 X0 Y0 Z0.5", "G1 X1 Y0 Z0.45 E0.1", "G1 X2 Y0 Z0.40 E0.2",
             "G1 X3 Y0 Z0.35 E0.3", "G1 X4 Y0 Z0.30 E0.4"]
        r = run(g)
        self.assertNotIn("COLLISION", codes(r))

    def test_travel_slope_down_is_warning_not_error(self):
        r = run(["G90", "G1 X0 Y0 Z2.0", "G1 X3 Y0 Z1.0"])
        self.assertNotIn("SLOPE", codes(r))
        self.assertIn("SLOPE", codes(r, level="warning"))

    def test_z_hop_up_is_not_slope_warning(self):
        r = run(["G90", "G1 X0 Y0 Z1.2", "G1 X0.5 Y0 Z1.6 F30000"])
        self.assertEqual(codes(r, level="warning"), [])


class HomingAndArcTests(unittest.TestCase):
    def test_arc_is_analysed_not_skipped(self):
        r = run(["G90", "M83", "G1 X0 Y0 Z1", "G2 X5 Y0 I2.5 J0 E1"])
        self.assertNotIn("ARC", codes(r, level="warning"))
        self.assertEqual(r.counts.get("arc_moves"), 1)
        self.assertGreater(r.counts.get("moves_extrude", 0), 1)   # split into chords

    def test_arc_extrusion_deposits_material(self):
        # A fully extruded arc at Z=5 must leave material that blocks a nozzle passing underneath.
        g = ["G90", "M83", "G1 X0 Y0 Z5", "G2 X10 Y0 I5 J0 E5", "G1 Z8", "G1 X5 Y20",
             "G1 Z4.5", "G1 X5 Y0.2"]
        r = run(g)
        self.assertIn("COLLISION", codes(r))

    def test_arc_clear_of_material_is_ok(self):
        g = ["G90", "M83", "G1 X0 Y0 Z1", "G2 X10 Y0 I5 J0 E5", "G1 Z1.2 F600", "G1 X20 Y20"]
        r = run(g)
        self.assertNotIn("COLLISION", codes(r))

    def test_homing_is_warning(self):
        r = run(["G28", "G1 Z1 F100"])
        self.assertIn("HOME", codes(r, level="warning"))


class ModelTests(unittest.TestCase):
    def test_rings_match_reference_tip(self):
        self.assertAlmostEqual(gc.RINGS[0][0], 0.12)
        self.assertAlmostEqual(gc.RINGS[0][1], 0.5504)

    def test_obstruction_radius_is_monotonic(self):
        radii = [gc.obstruction_radius(dz) for dz in (0.13, 0.5, 1.0, 2.0, 2.5)]
        self.assertEqual(radii, sorted(radii))
        self.assertEqual(gc.obstruction_radius(0.05), 0.0)


if __name__ == "__main__":
    unittest.main()
