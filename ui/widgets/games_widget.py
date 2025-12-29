"""
--- Copyright Notice ---
Copyright (c) 2024 Jim Maastricht

Games widget for baseball season simulation UI.

Displays today's games in a formatted grid view with progressive updates.
"""

import tkinter as tk
from tkinter import scrolledtext
from typing import List, Tuple, Dict, Any


class GamesWidget:
    """
    Games widget showing today's schedule and results.

    Features:
    - Grid display of games (5 per row)
    - Progressive updates as games complete
    - Shows R H E (Runs, Hits, Errors) for each team
    - Displays yesterday's results and today's schedule
    - Handles paused state display
    """

    def __init__(self, parent: tk.Widget):
        """
        Initialize games widget.

        Args:
            parent: Parent tkinter widget (notebook or frame)
        """
        self.frame = tk.Frame(parent)

        # Create ScrolledText widget for games display
        self.games_text = scrolledtext.ScrolledText(
            self.frame, wrap=tk.WORD, font=("Courier", 9), state=tk.DISABLED
        )

        # Configure text tags for formatting
        self.games_text.tag_configure("header", font=("Arial", 12, "bold"), foreground="#2e5090")
        self.games_text.tag_configure("day_header", font=("Arial", 12, "bold"),
                                     foreground="#1a3d6b", spacing3=10)
        self.games_text.tag_configure("followed_game", background="#ffffcc",
                                     spacing1=5, spacing3=5)
        self.games_text.tag_configure("separator", foreground="#888888")

        self.games_text.pack(fill=tk.BOTH, expand=True)

        # Track games for progressive display
        self.current_day_schedule = []  # List of (away_team, home_team) tuples
        self.current_day_results = {}   # Dict: {(away, home): game_data}
        self.previous_day_results = {}  # Dict: {(away, home): game_data} from previous day
        self.current_day_num = 0  # Track current day number for header

    def on_day_started(self, day_num: int, schedule: List[Tuple[str, str]]):
        """
        Handle day started event.

        Args:
            day_num: Current day number (0-indexed)
            schedule: List of (away_team, home_team) tuples for today's games
        """
        # Move current results to previous
        self.previous_day_results = self.current_day_results.copy()

        # Reset for new day
        self.current_day_num = day_num
        self.current_day_schedule = schedule
        self.current_day_results = {}

        # Clear and display
        self.games_text.config(state=tk.NORMAL)
        self.games_text.delete(1.0, tk.END)

        # Show yesterday's results if available
        if day_num > 0 and self.previous_day_results:
            self.games_text.insert(tk.END, f"═══ Day {day_num} Results ═══\n\n", "day_header")
            self._display_yesterday_results()
            self.games_text.insert(tk.END, "\n\n")

        # Show today's schedule
        self.games_text.insert(tk.END, f"═══ Day {day_num + 1} Schedule ═══\n\n", "day_header")
        self._display_games_grid()

        self.games_text.see(tk.END)
        self.games_text.config(state=tk.DISABLED)

    def on_game_completed(self, game_data: Dict[str, Any]):
        """
        Handle individual game completion (progressive update).

        Args:
            game_data: Dict with keys: away_team, home_team, away_r, home_r,
                      away_h, home_h, away_e, home_e, game_recap
        """
        game_key = (game_data['away_team'], game_data['home_team'])
        self.current_day_results[game_key] = game_data

        # Rebuild display with updated results
        self._rebuild_games_display()

    def on_day_completed(self, game_results: List[Dict], standings_data: Dict):
        """
        Handle day completed event (batch update for non-followed games).

        Args:
            game_results: List of game result dicts for non-followed games
            standings_data: Current standings (not used in this widget)
        """
        # Add non-followed games to results
        for game in game_results:
            game_key = (game['away_team'], game['home_team'])
            self.current_day_results[game_key] = game

        # Rebuild display with all results
        self._rebuild_games_display()

    def display_paused_state(self, season_schedule: List[List[Tuple]]):
        """
        Display completed day results and next day schedule when paused.

        Args:
            season_schedule: Full season schedule for looking up next day
        """
        self.games_text.config(state=tk.NORMAL)
        self.games_text.delete(1.0, tk.END)

        # Show completed day's results
        completed_day = self.current_day_num + 1  # Display number (1-indexed)
        self.games_text.insert(tk.END, f"═══ Day {completed_day} Results ═══\n\n", "day_header")

        if self.current_day_results:
            self._display_completed_day_results()
        else:
            self.games_text.insert(tk.END, "No games played today\n\n")

        self.games_text.insert(tk.END, "\n\n")

        # Show next day's schedule if available
        next_day_num = self.current_day_num + 1  # 0-indexed for lookup
        if next_day_num < len(season_schedule):
            self.games_text.insert(tk.END, f"═══ Day {next_day_num + 1} Schedule ═══\n\n", "day_header")
            self._display_next_day_schedule(season_schedule[next_day_num])
        else:
            self.games_text.insert(tk.END, "═══ Season Complete ═══\n", "day_header")

        self.games_text.see(1.0)  # Scroll to top
        self.games_text.config(state=tk.DISABLED)

    def _display_games_grid(self):
        """
        Display all games for the day in columnar format with R H E headers.

        Shows actual R H E values for completed games, dashes for pending games.
        """
        if not self.current_day_schedule:
            self.games_text.insert(tk.END, "No games scheduled today\n\n")
            return

        games_per_row = 5
        game_separator = '     '  # 5 spaces between games

        for row_start in range(0, len(self.current_day_schedule), games_per_row):
            row_games = self.current_day_schedule[row_start:row_start + games_per_row]

            # Header row: "     R   H   E"
            header_parts = ['     R   H   E'] * len(row_games)
            self.games_text.insert(tk.END, game_separator.join(header_parts) + "\n")

            # Away team row
            away_parts = []
            for away, home in row_games:
                game_key = (away, home)
                if game_key in self.current_day_results:
                    data = self.current_day_results[game_key]
                    # Format: Team(3) Space R(2) 2spaces H(2) 3spaces E(1)
                    away_parts.append(f"{away:>3} {data['away_r']:>2}  {data['away_h']:>2}   {data['away_e']:>1}")
                else:
                    # Use same spacing but with dashes
                    away_parts.append(f"{away:>3}  -   -    -")
            self.games_text.insert(tk.END, game_separator.join(away_parts) + "\n")

            # Home team row
            home_parts = []
            for away, home in row_games:
                game_key = (away, home)
                if game_key in self.current_day_results:
                    data = self.current_day_results[game_key]
                    # Format: Team(3) Space R(2) 2spaces H(2) 3spaces E(1)
                    home_parts.append(f"{home:>3} {data['home_r']:>2}  {data['home_h']:>2}   {data['home_e']:>1}")
                else:
                    # Use same spacing but with dashes
                    home_parts.append(f"{home:>3}  -   -    -")
            self.games_text.insert(tk.END, game_separator.join(home_parts) + "\n\n")

    def _rebuild_games_display(self):
        """Rebuild the entire games display with current results."""
        self.games_text.config(state=tk.NORMAL)
        self.games_text.delete(1.0, tk.END)

        # Show yesterday's results if available
        if self.current_day_num > 0 and self.previous_day_results:
            self.games_text.insert(tk.END, f"═══ Day {self.current_day_num} Results ═══\n\n", "day_header")
            self._display_yesterday_results()
            self.games_text.insert(tk.END, "\n\n")

        # Show today's schedule header
        self.games_text.insert(tk.END, f"═══ Day {self.current_day_num + 1} Schedule ═══\n\n", "day_header")

        # Display updated grid
        self._display_games_grid()

        self.games_text.see(tk.END)  # Auto-scroll
        self.games_text.config(state=tk.DISABLED)

    def _display_yesterday_results(self):
        """Display yesterday's results in compact grid format."""
        if not self.previous_day_results:
            return

        games = sorted(self.previous_day_results.keys())
        games_per_row = 5
        game_separator = '     '

        for row_start in range(0, len(games), games_per_row):
            row_games = games[row_start:row_start + games_per_row]

            # Header row
            header_parts = ['     R   H   E'] * len(row_games)
            self.games_text.insert(tk.END, game_separator.join(header_parts) + "\n")

            # Away team row
            away_parts = []
            for game_key in row_games:
                data = self.previous_day_results[game_key]
                away_parts.append(f"{data['away_team']:>3} {data['away_r']:>2}  {data['away_h']:>2}   {data['away_e']:>1}")
            self.games_text.insert(tk.END, game_separator.join(away_parts) + "\n")

            # Home team row
            home_parts = []
            for game_key in row_games:
                data = self.previous_day_results[game_key]
                home_parts.append(f"{data['home_team']:>3} {data['home_r']:>2}  {data['home_h']:>2}   {data['home_e']:>1}")
            self.games_text.insert(tk.END, game_separator.join(home_parts) + "\n\n")

    def _display_completed_day_results(self):
        """Display the completed day's results in compact grid format."""
        games = sorted(self.current_day_results.keys())
        games_per_row = 5
        game_separator = '     '

        for row_start in range(0, len(games), games_per_row):
            row_games = games[row_start:row_start + games_per_row]

            # Header row
            header_parts = ['     R   H   E'] * len(row_games)
            self.games_text.insert(tk.END, game_separator.join(header_parts) + "\n")

            # Away team row
            away_parts = []
            for game_key in row_games:
                data = self.current_day_results[game_key]
                away_parts.append(f"{data['away_team']:>3} {data['away_r']:>2}  {data['away_h']:>2}   {data['away_e']:>1}")
            self.games_text.insert(tk.END, game_separator.join(away_parts) + "\n")

            # Home team row
            home_parts = []
            for game_key in row_games:
                data = self.current_day_results[game_key]
                home_parts.append(f"{data['home_team']:>3} {data['home_r']:>2}  {data['home_h']:>2}   {data['home_e']:>1}")
            self.games_text.insert(tk.END, game_separator.join(home_parts) + "\n\n")

    def _display_next_day_schedule(self, next_day_games: List[Tuple[str, str]]):
        """
        Display the next day's schedule.

        Args:
            next_day_games: List of (away, home) tuples for next day
        """
        # Filter out OFF DAY entries
        matchups = [(m[0], m[1]) for m in next_day_games if 'OFF DAY' not in m]

        if not matchups:
            self.games_text.insert(tk.END, "No games scheduled\n\n")
            return

        games_per_row = 5
        game_separator = '     '

        for row_start in range(0, len(matchups), games_per_row):
            row_games = matchups[row_start:row_start + games_per_row]

            # Header row
            header_parts = ['     R   H   E'] * len(row_games)
            self.games_text.insert(tk.END, game_separator.join(header_parts) + "\n")

            # Away team row (with dashes for unplayed games)
            away_parts = []
            for away, home in row_games:
                away_parts.append(f"{away:>3}  -   -    -")
            self.games_text.insert(tk.END, game_separator.join(away_parts) + "\n")

            # Home team row (with dashes for unplayed games)
            home_parts = []
            for away, home in row_games:
                home_parts.append(f"{home:>3}  -   -    -")
            self.games_text.insert(tk.END, game_separator.join(home_parts) + "\n\n")

    def get_frame(self) -> tk.Frame:
        """Get the main frame for adding to parent container."""
        return self.frame
