#!/usr/bin/env python
"""Data refresh pipeline for the baseball simulator.

Runs the data preparation scripts in order, so the simulator has current inputs:
  1. download_stats.py          - download player stats from RotoWire (Selenium)
  2. download_il.py             - download the current injured list (FanGraphs)
  3. download_schedule.py       - download the season schedule
  4. bbplayer_projections.py    - build projected/historical/new-season files from the downloads

The order matters: the projections step consumes the files produced by the downloads.
The pipeline stops at the first failure. Any command line arguments are ignored.
"""

import subprocess
import sys
import time
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent

# (script, what it does, what it produces)
STEPS = [
    (
        "download_stats.py",
        "Downloading the latest player batting and pitching stats from RotoWire.",
        "raw '{year} player-stats-*.csv' files",
    ),
    (
        "download_il.py",
        "Downloading the current injured list (IL) report from FanGraphs.",
        "an il_report_YYYY.csv file used to model injuries",
    ),
    (
        "download_schedule.py",
        "Downloading the season schedule.",
        "the schedule file used by the season simulation",
    ),
    (
        "bbplayer_projections.py",
        "Preprocessing the downloaded stats into age-adjusted projections, historical files, "
        "and the new-season placeholder, then running integrity checks.",
        "player-projected, historical, and New-Season CSV files used by the simulator",
    ),
]


def run_step(number: int, total: int, script: str, description: str, produces: str) -> None:
    """Run one script with the current interpreter, printing commentary before and after."""
    print("=" * 90)
    print(f"STEP {number}/{total}: {script}")
    print("=" * 90)
    print(description)
    print(f"Output: {produces}")
    print(f"Starting {script}...\n")

    start = time.perf_counter()
    result = subprocess.run([sys.executable, script], cwd=SCRIPT_DIR)
    elapsed = time.perf_counter() - start

    print()
    if result.returncode != 0:
        print(f"FAILED: {script} exited with code {result.returncode} after {elapsed:.1f}s.")
        print("Stopping the pipeline; later steps depend on this one.")
        sys.exit(result.returncode)
    print(f"Finished {script} successfully in {elapsed:.1f}s.\n")


def main() -> None:
    print("*" * 90)
    print("BASEBALL SIM DATA REFRESH")
    print(f"Running {len(STEPS)} steps: downloads first, then projection preprocessing.")
    print("*" * 90 + "\n")

    start = time.perf_counter()
    for i, (script, description, produces) in enumerate(STEPS, start=1):
        run_step(i, len(STEPS), script, description, produces)

    print("*" * 90)
    print(f"DATA REFRESH COMPLETE in {time.perf_counter() - start:.1f}s")
    print("The simulator can now be launched with run.py.")
    print("*" * 90)


if __name__ == "__main__":
    main()
