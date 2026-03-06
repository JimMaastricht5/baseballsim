"""
--- Copyright Notice ---
Copyright (c) 2024 Jim Maastricht

Schedule widget for baseball season simulation UI.

Displays upcoming games in a formatted text view.
"""

import tkinter as tk
from tkinter import scrolledtext
from typing import List, Tuple

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

        self.schedule_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    def update_schedule(self, current_day: int, schedule: List[List[Tuple]]):
        """
        Update the schedule display to show upcoming games.

        Args:
            current_day: Current day number (0-indexed)
            schedule: Full season schedule (list of days, each day is list of matchups)
        """
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

            day_games = schedule[day_index]

            # Day header (highlight current day)
            day_label = f"Day {day_index + 1}"
            if i == 0:
                day_label += " ◄ CURRENT"
                self.schedule_text.insert(tk.END, day_label + "\n", "current_day")
            else:
                self.schedule_text.insert(tk.END, day_label + "\n", "day_header")

            # Format matchups - show 4 per line for better readability
            # Insert matchups with bold for followed team names
            matchups_per_line = 4
            matchup_count = 0

            for matchup in day_games:
                # Add line break and indent after every 4 matchups
                if matchup_count % matchups_per_line == 0:
                    self.schedule_text.insert(tk.END, "  ", "matchup")  # Indent
                else:
                    self.schedule_text.insert(tk.END, "   ", "matchup")  # Separator between matchups

                if 'OFF DAY' in matchup:
                    off_team = matchup[0] if matchup[0] != 'OFF DAY' else matchup[1]
                    # Insert team name with bold if it's the followed team
                    if self.followed_team and off_team == self.followed_team:
                        self.schedule_text.insert(tk.END, f"{off_team:4s}", "bold_team")
                    else:
                        self.schedule_text.insert(tk.END, f"{off_team:4s}", "matchup")
                    self.schedule_text.insert(tk.END, " OFF", "matchup")
                else:
                    away, home = matchup[0], matchup[1]
                    # Insert away team with bold if it's the followed team
                    if self.followed_team and away == self.followed_team:
                        self.schedule_text.insert(tk.END, f"{away:3s}", "bold_team")
                    else:
                        self.schedule_text.insert(tk.END, f"{away:3s}", "matchup")

                    self.schedule_text.insert(tk.END, " @ ", "matchup")

                    # Insert home team with bold if it's the followed team
                    if self.followed_team and home == self.followed_team:
                        self.schedule_text.insert(tk.END, f"{home:3s}", "bold_team")
                    else:
                        self.schedule_text.insert(tk.END, f"{home:3s}", "matchup")

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

    def get_frame(self) -> tk.Frame:
        """Get the main frame for adding to parent container."""
        return self.frame
