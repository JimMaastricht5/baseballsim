#!/usr/bin/env python
"""Convenience wrapper that launches bbseason_ui.py via uv with free-threaded Python 3.14."""

import platform
import subprocess
import sys

# Ensure it runs from a native Windows command line
if sys.platform != "win32" or platform.system() != "Windows":
    print("Error: This script must be run from a native Windows command line.", file=sys.stderr)
    sys.exit(1)

defaults = [
    "--team",
    "MIL",
    "--games",
    "162",
    "--seasons",
    "2020,2021,2022,2023,2024,2025,2026",
    "--new-season",
    "2026",
]

args = defaults + sys.argv[1:]

# Check if we are already running under Python 3.14+ with the GIL disabled (free-threaded)
is_free_threaded = False
try:
    # sys._is_gil_enabled() returns False if running a free-threaded build with the GIL turned off
    is_free_threaded = sys.version_info >= (3, 14) and hasattr(sys, "_is_gil_enabled") and not sys._is_gil_enabled()
except Exception:
    pass

if is_free_threaded:
    # Already running inside the multi-threaded Python 3.14 environment, launch the UI directly
    result = subprocess.run([sys.executable, "bbseason_ui.py"] + args)
    sys.exit(result.returncode)
else:
    # Spin up uv using the free-threaded Python 3.14 specifier (3.14t)
    result = subprocess.run(["uv", "run", "--python", "3.14t", "bbseason_ui.py"] + args)
    sys.exit(result.returncode)
