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
from tkinter import ttk, messagebox
import datetime

from ui.main_window_tk import SeasonMainWindow
from bblogger import logger


class StartupDialog:
    """
    Startup dialog to select team and number of games before starting the season.
    """

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Baseball Season Setup")
        self.root.geometry("450x220")
        self.root.resizable(False, False)

        # Result variables
        self.selected_team = 'MIL'
        self.num_games = 162
        self.confirmed = False

        # Create UI first
        self._create_widgets()

        # Center the dialog on screen
        self.root.update_idletasks()
        width = self.root.winfo_width()
        height = self.root.winfo_height()
        x = (self.root.winfo_screenwidth() // 2) - (width // 2)
        y = (self.root.winfo_screenheight() // 2) - (height // 2)
        self.root.geometry(f'{width}x{height}+{x}+{y}')

        # Protocol to handle window close button
        self.root.protocol("WM_DELETE_WINDOW", self._on_cancel)

        # Ensure window is visible
        self.root.lift()
        self.root.focus_force()

    def _create_widgets(self):
        """Create dialog widgets."""
        # Main frame
        main_frame = tk.Frame(self.root, padx=20, pady=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Team selection
        team_label = tk.Label(main_frame, text="Select Team to Follow:", font=("Arial", 11, "bold"))
        team_label.grid(row=0, column=0, sticky=tk.W, pady=(0, 5))

        self.team_var = tk.StringVar(value='MIL')
        team_combo = ttk.Combobox(
            main_frame,
            textvariable=self.team_var,
            width=10,
            state="readonly",
            font=("Arial", 10)
        )
        team_combo['values'] = ['ARI', 'ATL', 'BAL', 'BOS', 'CHC', 'CHW', 'CIN', 'CLE',
                                'COL', 'DET', 'HOU', 'KCR', 'LAA', 'LAD', 'MIA', 'MIL',
                                'MIN', 'NYM', 'NYY', 'OAK', 'PHI', 'PIT', 'SDP', 'SEA',
                                'SFG', 'STL', 'TBR', 'TEX', 'TOR', 'WSN']
        team_combo.grid(row=0, column=1, sticky=tk.W, pady=(0, 5))

        # Number of games
        games_label = tk.Label(main_frame, text="Number of Games to Simulate:", font=("Arial", 11, "bold"))
        games_label.grid(row=1, column=0, sticky=tk.W, pady=(15, 5))

        self.games_var = tk.StringVar(value='162')
        games_spinbox = tk.Spinbox(
            main_frame,
            from_=1,
            to=162,
            textvariable=self.games_var,
            width=10,
            font=("Arial", 10)
        )
        games_spinbox.grid(row=1, column=1, sticky=tk.W, pady=(15, 5))

        # Buttons
        button_frame = tk.Frame(main_frame)
        button_frame.grid(row=2, column=0, columnspan=2, pady=(30, 0))

        ok_button = tk.Button(
            button_frame,
            text="Start Season",
            command=self._on_ok,
            width=12,
            bg="green",
            fg="white",
            font=("Arial", 10, "bold")
        )
        ok_button.pack(side=tk.LEFT, padx=5)

        cancel_button = tk.Button(
            button_frame,
            text="Cancel",
            command=self._on_cancel,
            width=12,
            font=("Arial", 10)
        )
        cancel_button.pack(side=tk.LEFT, padx=5)

    def _on_ok(self):
        """Handle OK button click."""
        try:
            self.selected_team = self.team_var.get()
            self.num_games = int(self.games_var.get())

            # Validate inputs
            if not self.selected_team:
                messagebox.showerror("Error", "Please select a team")
                return

            if self.num_games < 1 or self.num_games > 162:
                messagebox.showerror("Error", "Number of games must be between 1 and 162")
                return

            self.confirmed = True
            self.root.quit()
        except ValueError:
            messagebox.showerror("Error", "Invalid number of games")

    def _on_cancel(self):
        """Handle Cancel button click."""
        self.confirmed = False
        self.root.quit()

    def show(self):
        """Show the dialog and wait for user input."""
        self.root.mainloop()
        self.root.destroy()
        return self.confirmed, self.selected_team, self.num_games


def main(load_seasons=[2023, 2024, 2025], new_season = 2026, season_length = 162, series_length = 3,
         rotation_len = 5, season_chatty = False, season_print_lineup_b = False,
         season_print_box_score_b = False, season_team_to_follow = None, show_startup_dialog = True):
    """
    Main entry point for the UI application.

    Creates the tkinter root window, instantiates the main window,
    and starts the tkinter event loop.

    Args:
        show_startup_dialog: If True, shows startup dialog to select team and games (default True)
    """
    logger.info("Starting Baseball Season Simulator UI (tkinter)")

    # Show startup dialog if requested
    if show_startup_dialog:
        try:
            dialog = StartupDialog()
            confirmed, selected_team, num_games = dialog.show()

            if not confirmed:
                logger.info("User cancelled season setup")
                return

            # Use dialog values
            season_team_to_follow = selected_team
            season_length = num_games
            logger.info(f"User selected team: {selected_team}, games: {num_games}")
        except Exception as e:
            logger.error(f"Error in startup dialog: {e}")
            messagebox.showerror("Error", f"Failed to show startup dialog: {e}")
            return

    # Now create the main application window
    root = tk.Tk()

    # Create main window
    try:
        window = SeasonMainWindow(root, load_seasons, new_season, season_length, series_length, rotation_len,
                                  season_chatty, season_print_lineup_b, season_print_box_score_b,
                                  season_team_to_follow)
    except Exception as e:
        logger.error(f"Error creating main window: {e}")
        messagebox.showerror("Error", f"Failed to create main window: {e}")
        root.destroy()
        return

    # Handle window close
    root.protocol("WM_DELETE_WINDOW", window.on_close)

    logger.info("Main window displayed, entering event loop")

    # Start event loop
    root.mainloop()


if __name__ == "__main__":
    start_time = datetime.datetime.now()
    main(load_seasons = [2023, 2024, 2025],
         new_season = 2026,
         season_length = 162,  # Default, will be overridden by startup dialog
         series_length = 3,
         rotation_len = 5,
         season_chatty = True,
         season_print_lineup_b = True,
         season_print_box_score_b = True,
         season_team_to_follow = 'MIL',  # Default, will be overridden by startup dialog
         show_startup_dialog = True  # Set to False to skip dialog and use hardcoded values
         )

    # how long did that take?
    end_time = datetime.datetime.now()
    run_time = end_time - start_time
    total_seconds = run_time.total_seconds()  # Get the total run time in seconds
    minutes = int(total_seconds // 60)
    seconds = int(total_seconds % 60)
    print(f'Total run time: {minutes} minutes, {seconds} seconds')

