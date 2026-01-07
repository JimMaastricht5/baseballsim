"""
--- Copyright Notice ---
Copyright (c) 2024 Jim Maastricht

PRIMARY FUNCTION:
- main(): Initializes the tkinter root window and instantiates the
  SeasonMainWindow class to launch the application.

USAGE:
    python bbseason_ui.py

OPTIONAL COMMAND-LINE ARGUMENTS (Future Enhancement):
    --seasons 2023,2024,2025    Years to load stats from
    --new-season 2026           Season to simulate
    --follow NYM,LAD            Teams to follow in detail
    --random                    Use random data (appends "random" to file name)
Contact: JimMaastricht5@gmail.com
"""

import tkinter as tk
import datetime

from ui.main_window_tk import SeasonMainWindow
from bblogger import logger


def main(load_seasons=[2023, 2024, 2025], new_season = 2026, season_length = 162, series_length = 3,
         rotation_len = 5, season_chatty = False, season_print_lineup_b = False,
         season_print_box_score_b = False, season_team_to_follow = None):
    """
    Main entry point for the UI application.

    Creates the tkinter root window, instantiates the main window,
    and starts the tkinter event loop.
    """
    logger.info("Starting Baseball Season Simulator UI (tkinter)")

    # Create root window
    root = tk.Tk()

    # Create main window
    window = SeasonMainWindow(root, load_seasons, new_season, season_length, series_length, rotation_len,
                              season_chatty,season_print_lineup_b, season_print_box_score_b,
                              season_team_to_follow)

    # Handle window close
    root.protocol("WM_DELETE_WINDOW", window.on_close)

    logger.info("Main window displayed, entering event loop")

    # Start event loop
    root.mainloop()


if __name__ == "__main__":
    start_time = datetime.datetime.now()
    main(load_seasons = [2023, 2024, 2025],
         new_season = 2026,
         season_length = 162,
         series_length = 3,
         rotation_len = 5,
         season_chatty = True,
         season_print_lineup_b = True,
         season_print_box_score_b = True,
         season_team_to_follow = 'MIL'  # Single team string (defaults to 'MIL' if None)
         )

    # how long did that take?
    end_time = datetime.datetime.now()
    run_time = end_time - start_time
    total_seconds = run_time.total_seconds()  # Get the total run time in seconds
    minutes = int(total_seconds // 60)
    seconds = int(total_seconds % 60)
    print(f'Total run time: {minutes} minutes, {seconds} seconds')

