"""
Entry point for the baseball season simulation UI.

Launches the tkinter application with the main window.

Usage:
    python bbseason_ui.py

Optional command-line arguments (for future enhancement):
    --seasons 2023,2024,2025    Years to load stats from
    --new-season 2026           Season to simulate
    --follow NYM,LAD            Teams to follow in detail
    --random                    Use random data
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
