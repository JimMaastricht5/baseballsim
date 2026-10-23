#!/usr/bin/env python
"""Run the MIL vs TBR playoff series many times and tally how often each team wins.

Uses bbplayoff_series.BaseballPlayoffSeries: the games, home/away order and dates come from the schedule, each series
starts from freshly loaded data, and only a line per series, the final record and the average games to win are
printed. Prints the start time, end time and elapsed time of the whole run.
"""

from datetime import datetime

from bblogger import configure_logger
from bbplayoff_series import BaseballPlayoffSeries

TEAM_A = "MIL"
TEAM_B = "TBR"
ROTATION_LEN = 4
NUM_SERIES = 10


def main() -> None:
    configure_logger("INFO", console_level="WARNING")  # INFO still goes to the log file, not the console

    start_time = datetime.now()
    print(f"Start time:   {start_time:%Y-%m-%d %H:%M:%S}")
    print(f"Running {NUM_SERIES} series: {TEAM_A} vs {TEAM_B}, {ROTATION_LEN} man rotation\n")

    BaseballPlayoffSeries(TEAM_A, TEAM_B, rotation_len=ROTATION_LEN, num_series=NUM_SERIES).run_all()

    end_time = datetime.now()
    print(f"\nStart time:   {start_time:%Y-%m-%d %H:%M:%S}")
    print(f"End time:     {end_time:%Y-%m-%d %H:%M:%S}")
    print(f"Elapsed time: {end_time - start_time}")


if __name__ == "__main__":
    main()
