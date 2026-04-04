#!/usr/bin/env python
import subprocess
import sys

defaults = [
    "--team",
    "MIL",
    "--games",
    "162",
    "--seasons",
    "2023,2024,2025",
    "--new-season",
    "2026",
]

args = defaults + sys.argv[1:]
result = subprocess.run(["uv", "run", "--python", "3.14.0", "bbseason_ui.py"] + args)
sys.exit(result.returncode)
