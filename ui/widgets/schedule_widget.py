"""
--- Copyright Notice ---
Copyright (c) 2024 Jim Maastricht

Schedule widget for baseball season simulation UI.

Displays upcoming games in a formatted text view.
"""

import tkinter as tk
from tkinter import scrolledtext
from datetime import datetime
from typing import List, Tuple, Dict, Any

from ui.theme import BG_PANEL, BG_WIDGET, TEXT_PRIMARY, TEXT_HEADING, ACCENT_GOLD


class ScheduleWidget:
    """
    Schedule widget showing upcoming games.

    Displays next 14 days of games in a scrollable text widget with
    current day highlighting and formatted matchups.
    """

    def __init__(self, parent: tk.Widget, followed_team: str = None):
        """
        Initialize schedule widget.

        Args:
            parent: Parent tkinter widget (notebook or frame)
            followed_team: Team abbreviation to highlight (e.g., 'MIL', 'NYM')
        """
        self.frame = tk.Frame(parent, bg=BG_PANEL)
        self.followed_team = followed_team
        self.schedule_times = {}  # {(away, home): "7:10 PM"}
        self.completed_games = {}  # {(away, home): (away_r, home_r)}
        self.schedule_dates = []  # List of date strings for each day

        # Header
        schedule_header = tk.Label(
            self.frame, text="Upcoming Games (Next 14 Days)",
            font=("Segoe UI", 11, "bold"), pady=5, bg=BG_PANEL, fg=TEXT_HEADING
        )
        schedule_header.pack()

        # Create ScrolledText for schedule (supports text wrapping)
        self.schedule_text = scrolledtext.ScrolledText(
            self.frame,
            wrap=tk.WORD,
            font=("Consolas", 9),
            state=tk.DISABLED,
            padx=10,
            pady=5,
            bg=BG_WIDGET,
            fg=TEXT_PRIMARY,
            insertbackground=TEXT_PRIMARY
        )

        # Configure text tags for formatting
        self.schedule_text.tag_configure("day_header", font=("Segoe UI", 12, "bold"),
                                        foreground=ACCENT_GOLD, spacing1=5, spacing3=3)
        self.schedule_text.tag_configure("current_day", background="#1f3010",
                                        font=("Segoe UI", 12, "bold"), foreground=ACCENT_GOLD,
                                        spacing1=5, spacing3=3)
        self.schedule_text.tag_configure("matchup", font=("Consolas", 9),
                                        lmargin1=20, lmargin2=20)
        self.schedule_text.tag_configure("bold_team", font=("Consolas", 10, "bold"),
                                        lmargin1=20, lmargin2=20, foreground=ACCENT_GOLD)
        self.schedule_text.tag_configure("time", font=("Consolas", 9),
                                        foreground="#888888")  # Gray for times
        self.schedule_text.tag_configure("score", font=("Consolas", 9, "bold"),
                                        foreground=ACCENT_GOLD)  # Gold for scores

        self.schedule_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    def update_schedule(self, current_day: int, schedule: List,
                   schedule_times: Dict = None, schedule_dates: List = None):
        """
        Update the schedule display to show upcoming games.

        Args:
            current_day: Current day number (0-indexed)
            schedule: Full season schedule (list of ScheduleDay objects or old list of matchups)
            schedule_times: Optional dict of {(away, home): "7:10 PM"} for game times
            schedule_dates: Optional list of date strings for each day
        """
        # Store schedule times and dates
        if schedule_times:
            self.schedule_times = schedule_times
        if schedule_dates:
            self.schedule_dates = schedule_dates

        # Clear existing schedule
        self.schedule_text.config(state=tk.NORMAL)
        self.schedule_text.delete(1.0, tk.END)

        total_days = len(schedule)

        # Show next 14 days (or until end of season)
        days_to_show = min(14, total_days - current_day)

        for i in range(days_to_show):
            day_index = current_day + i
            if day_index >= total_days:
                break

            # Handle both new format (ScheduleDay objects) and old format (list of tuples)
            day_obj = schedule[day_index]
            if hasattr(day_obj, 'games'):
                # New format: ScheduleDay object
                day_games = day_obj.games
            else:
                # Old format: list of tuples
                day_games = day_obj

            # Day header with date (highlight current day)
            date_str = self._get_date_for_day(day_index)
            day_label = f"{date_str} Day {day_index + 1}" if date_str else f"Day {day_index + 1}"
            if i == 0:
                day_label += " ◄ CURRENT"
                self.schedule_text.insert(tk.END, day_label + "\n", "current_day")
            else:
                self.schedule_text.insert(tk.END, day_label + "\n", "day_header")

            # Format matchups - show 4 per line for better readability
            matchups_per_line = 4
            matchup_count = 0

            for game in day_games:
                # Add line break and indent after every 4 matchups
                if matchup_count % matchups_per_line == 0:
                    self.schedule_text.insert(tk.END, "  ", "matchup")  # Indent
                else:
                    self.schedule_text.insert(tk.END, "   ", "matchup")  # Separator between matchups

                # Handle both new format (GameMatchup objects) and old format (tuple)
                if hasattr(game, 'is_off_day'):
                    # New format: GameMatchup object
                    if game.is_off_day:
                        off_team = game.home if game.home != "OFF DAY" else game.away
                        if self.followed_team and off_team == self.followed_team:
                            self.schedule_text.insert(tk.END, f"{off_team:4s}", "bold_team")
                        else:
                            self.schedule_text.insert(tk.END, f"{off_team:4s}", "matchup")
                        self.schedule_text.insert(tk.END, " OFF", "matchup")
                    else:
                        away, home = game.away, game.home
                        if self.followed_team and away == self.followed_team:
                            self.schedule_text.insert(tk.END, f"{away:3s}", "bold_team")
                        else:
                            self.schedule_text.insert(tk.END, f"{away:3s}", "matchup")
                        self.schedule_text.insert(tk.END, " @ ", "matchup")
                        if self.followed_team and home == self.followed_team:
                            self.schedule_text.insert(tk.END, f"{home:3s}", "bold_team")
                        else:
                            self.schedule_text.insert(tk.END, f"{home:3s}", "matchup")
                        # Show score if completed, time if not
                        if game.completed and game.away_score is not None and game.home_score is not None:
                            self.schedule_text.insert(tk.END, f"  {game.away_score}-{game.home_score}", "score")
                        elif game.time:
                            self.schedule_text.insert(tk.END, f" {game.time}", "time")
                else:
                    # Old format: tuple (away, home) or "OFF DAY"
                    if 'OFF DAY' in game:
                        off_team = game[0] if game[0] != 'OFF DAY' else game[1]
                        if self.followed_team and off_team == self.followed_team:
                            self.schedule_text.insert(tk.END, f"{off_team:4s}", "bold_team")
                        else:
                            self.schedule_text.insert(tk.END, f"{off_team:4s}", "matchup")
                        self.schedule_text.insert(tk.END, " OFF", "matchup")
                    else:
                        away, home = game[0], game[1]
                        if self.followed_team and away == self.followed_team:
                            self.schedule_text.insert(tk.END, f"{away:3s}", "bold_team")
                        else:
                            self.schedule_text.insert(tk.END, f"{away:3s}", "matchup")
                        self.schedule_text.insert(tk.END, " @ ", "matchup")
                        if self.followed_team and home == self.followed_team:
                            self.schedule_text.insert(tk.END, f"{home:3s}", "bold_team")
                        else:
                            self.schedule_text.insert(tk.END, f"{home:3s}", "matchup")
                        # Show time or score from completed_games dict
                        game_key = (away, home)
                        if game_key in self.schedule_times:
                            if game_key in self.completed_games:
                                away_r, home_r = self.completed_games[game_key]
                                self.schedule_text.insert(tk.END, f"  {away_r}-{home_r}", "score")
                            else:
                                time_str = self.schedule_times[game_key]
                                self.schedule_text.insert(tk.END, f" {time_str}", "time")

                matchup_count += 1

                # Add line break after every 4 matchups
                if matchup_count % matchups_per_line == 0:
                    self.schedule_text.insert(tk.END, "\n", "matchup")

            # Add final line break if we didn't just add one
            if matchup_count % matchups_per_line != 0:
                self.schedule_text.insert(tk.END, "\n", "matchup")

            # Add spacing between days
            self.schedule_text.insert(tk.END, "\n")

        self.schedule_text.config(state=tk.DISABLED)

    def _get_date_for_day(self, day_index: int) -> str:
        """Return formatted date for display."""
        if day_index < len(self.schedule_dates):
            dt = datetime.strptime(self.schedule_dates[day_index], "%Y-%m-%d")
            return dt.strftime("%B %d, %Y")
        return ""

    def on_game_completed(self, game_data: Dict[str, Any]):
        """Handle game completion - update schedule display with score."""
        game_key = (game_data["away_team"], game_data["home_team"])
        self.completed_games[game_key] = (game_data["away_r"], game_data["home_r"])

    def get_frame(self) -> tk.Frame:
        """Get the main frame for adding to parent container."""
        return self.frame
