#!/usr/bin/env python3
"""Tests for the generated OrcaSlicer plugin using a stub `orca` module.

This checks the plugin's logic and return codes only. It does NOT run inside OrcaSlicer.
Run: python3 -m unittest -v test_plugin_stub.py
"""

import enum
import importlib.util
import os
import sys
import tempfile
import types
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
PLUGIN = os.path.join(HERE, "plugin", "orca_nonplanar_gcode_check_plugin.py")


def _make_orca_stub():
    orca = types.ModuleType("orca")

    class PluginResult(enum.Enum):
        Success = 0
        Skipped = 1
        RecoverableError = 2
        FatalError = 3

    class ExecutionResult:
        def __init__(self, status, message=""):
            self.status = status
            self.message = message

        @staticmethod
        def success(message=""):
            return ExecutionResult(PluginResult.Success, message)

        @staticmethod
        def failure(status, message):
            return ExecutionResult(status, message)

    class Step:
        psGCodePostProcess = "psGCodePostProcess"

    class SlicingPipelineCapabilityBase:
        def get_config(self):
            return "{}"

    orca.PluginResult = PluginResult
    orca.ExecutionResult = ExecutionResult
    orca.slicing = types.SimpleNamespace(Step=Step, SlicingPipelineCapabilityBase=SlicingPipelineCapabilityBase)
    orca.base = object
    orca.plugin = lambda cls: cls
    orca.register_capability = lambda cls: None
    return orca


class _Ctx:
    pass


class PluginLogicTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        sys.modules["orca"] = _make_orca_stub()
        spec = importlib.util.spec_from_file_location("plugin_under_test", PLUGIN)
        cls.plugin = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.plugin)
        cls.tmp = tempfile.mkdtemp()

    def _run(self, text, step="psGCodePostProcess"):
        path = os.path.join(self.tmp, "t.gcode")
        with open(path, "w") as f:
            f.write(text)
        ctx = _Ctx()
        ctx.step = step
        ctx.gcode_path = path
        ctx.host = "File"
        ctx.output_name = "t"
        return self.plugin.NonplanarGCodeCheck().execute(ctx)

    def test_clean_file_succeeds(self):
        res = self._run("G90\nG1 X0 Y0 Z1\nG1 X10 Y0 E1\n")
        self.assertEqual(res.status.name, "Success")

    def test_steep_extrusion_fails_export(self):
        res = self._run("G90\nG1 X0 Y0 Z1\nG1 X1 Y0 Z2 E1\n")
        self.assertEqual(res.status.name, "FatalError")
        self.assertIn("SLOPE", res.message)

    def test_other_steps_are_noop(self):
        res = self._run("G90\nG1 X1 Y0 Z2 E1\n", step="posSlice")
        self.assertEqual(res.status.name, "Success")

    def test_file_is_not_modified(self):
        text = "G90\nG1 X0 Y0 Z1\nG1 X1 Y0 Z2 E1\n"
        self._run(text)
        with open(os.path.join(self.tmp, "t.gcode")) as f:
            self.assertEqual(f.read(), text)


if __name__ == "__main__":
    unittest.main()
