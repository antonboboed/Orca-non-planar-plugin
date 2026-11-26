#!/usr/bin/env python3
"""Build the single-file OrcaSlicer plugin from gcode_check.py.

The plugin loader takes one entry file, so the checker code is copied into it here.
Run: python3 plugin/build_plugin.py  ->  plugin/orca_nonplanar_gcode_check_plugin_win_x86_64.py
"""
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

with open(os.path.join(ROOT, "gcode_check.py"), encoding="utf-8") as f:
    checker = f.read()

# Keep only the checker definitions: drop the module docstring, the future import and the CLI.
body = checker.split('"""', 2)[2]          # text after the module docstring
body = body.replace("from __future__ import annotations\n", "")
body = body.split("\ndef main(", 1)[0]     # drop CLI
body = body.replace("import sys\n", "").replace("import argparse\n", "")

with open(os.path.join(HERE, "plugin_header.py"), encoding="utf-8") as f:
    header = f.read()

# Header imports come after the docstring; checker imports go right after them.
head, rest = header.split("import json\n", 1)
out = head + "import json\n" + "\n# ---- checker (generated from gcode_check.py; edit that file) ----\n" + body.rstrip() + "\n\n" \
    + "import orca" + rest.split("import orca", 1)[1]

target = os.path.join(HERE, "orca_nonplanar_gcode_check_plugin_win_x86_64.py")
with open(target, "w", encoding="utf-8") as f:
    f.write(out)
print("wrote", target)
