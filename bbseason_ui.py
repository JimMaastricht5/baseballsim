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

from ui.main_window_tk import SeasonMainWindow
from bblogger import logger


def main():
    """
    Main entry point for the UI application.

    Creates the tkinter root window, instantiates the main window,
    and starts the tkinter event loop.
    """
    logger.info("Starting Baseball Season Simulator UI (tkinter)")

    # Create root window
    root = tk.Tk()

    # Create main window
    window = SeasonMainWindow(root)

    # Handle window close
    root.protocol("WM_DELETE_WINDOW", window.on_close)

    logger.info("Main window displayed, entering event loop")

    # Start event loop
    root.mainloop()


if __name__ == "__main__":
    main()
