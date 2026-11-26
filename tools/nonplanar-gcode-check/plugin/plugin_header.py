# /// script
# requires-python = ">=3.12"
#
# [tool.orcaslicer.plugin]
# name = "Nonplanar G-code Check"
# description = "Checks exported G-code for nonplanar printing: move slope, Z range, and hotend collisions (tip and cone). Blocks the export on errors."
# author = "antonboboed"
# version = "0.1"
# type = "slicing-pipeline"
# ///
"""Nonplanar G-code Check (draft, not validated on the P1S).

Runs at the G-code export/post-process step (Step.psGCodePostProcess). It only READS the
exported G-code file and never edits it. On errors it fails the export so that the file is
not sent to the printer. Warnings are written to the OrcaSlicer log.

This check is NOT a safety certificate. See tools/nonplanar-gcode-check/README.md.
"""
import json

import orca

_DEFAULTS = {
    "max_angle_deg": 12.0,
    "fail_on_error": True,
}


def _config(self):
    try:
        cfg = json.loads(self.get_config())
    except (AttributeError, TypeError, ValueError):
        cfg = {}
    out = dict(_DEFAULTS)
    out.update({k: v for k, v in cfg.items() if k in _DEFAULTS})
    return out


class NonplanarGCodeCheck(orca.slicing.SlicingPipelineCapabilityBase):
    def get_name(self):
        return "Nonplanar G-code Check"

    def get_default_config(self):
        return dict(_DEFAULTS)

    def execute(self, ctx):
        if ctx.step != orca.slicing.Step.psGCodePostProcess:
            return orca.ExecutionResult.success()
        if not ctx.gcode_path:
            return orca.ExecutionResult.success("Nonplanar G-code Check: no gcode_path, nothing to do")

        cfg = _config(self)
        checker = Checker(max_angle_deg=float(cfg["max_angle_deg"]))
        with open(ctx.gcode_path, "r", encoding="utf-8", errors="replace") as f:
            report = checker.run(f)
        text = format_report(ctx.gcode_path, report, float(cfg["max_angle_deg"]))
        for line in text.splitlines():
            print(line)

        if report.errors and cfg["fail_on_error"]:
            first = [i for i in report.issues if i.level == "error"][:3]
            detail = "; ".join(f"{i.code} line {i.line}: {i.message}" for i in first)
            return orca.ExecutionResult.failure(
                orca.PluginResult.FatalError,
                f"Nonplanar G-code Check found {report.errors} error(s), export stopped. {detail}")

        return orca.ExecutionResult.success(
            f"Nonplanar G-code Check: {report.errors} error(s), {len(report.issues) - report.errors} other issue(s)")


@orca.plugin
class NonplanarGCodeCheckPackage(orca.base):
    def register_capabilities(self):
        orca.register_capability(NonplanarGCodeCheck)
