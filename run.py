#!/usr/bin/env python
"""Convenience wrapper that launches bbseason_ui.py via uv with sane defaults."""

import subprocess
import sys

defaults = ["--team", "MIL", "--games", "162", "--seasons", "2020, 2021, 2022, 2023,2024,2025,2026", "--new-season",
            "2026"]

args = defaults + sys.argv[1:]
result = subprocess.run(["uv", "run", "--python", "3.14.0", "bbseason_ui.py"] + args)
sys.exit(result.returncode)
