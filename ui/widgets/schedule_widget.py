"""
--- Copyright Notice ---
Copyright (c) 2024 Jim Maastricht

Schedule widget for baseball season simulation UI.

Displays upcoming games in a formatted text view.
"""

import tkinter as tk
from tkinter import scrolledtext
from typing import List, Tuple


class ScheduleWidget:
    """
    Schedule widget showing upcoming games.

    Displays next 14 days of games in a scrollable text widget with
    current day highlighting and formatted matchups.
    """

    def __init__(self, parent: tk.Widget):
        """
        Initialize schedule widget.

        Args:
            parent: Parent tkinter widget (notebook or frame)
        """
        self.frame = tk.Frame(parent)

        # Header
        schedule_header = tk.Label(
            self.frame, text="Upcoming Games (Next 14 Days)",
            font=("Arial", 11, "bold"), pady=5
        )
        schedule_header.pack()

        # Create ScrolledText for schedule (supports text wrapping)
        self.schedule_text = scrolledtext.ScrolledText(
            self.frame,
            wrap=tk.WORD,
            font=("Courier", 9),
            state=tk.DISABLED,
            padx=10,
            pady=5
        )

        # Configure text tags for formatting
        self.schedule_text.tag_configure("day_header", font=("Arial", 12, "bold"),
                                        foreground="#1a3d6b", spacing1=5, spacing3=3)
        self.schedule_text.tag_configure("current_day", background="#ffeecc",
                                        font=("Arial", 12, "bold"), foreground="#1a3d6b",
                                        spacing1=5, spacing3=3)
        self.schedule_text.tag_configure("matchup", font=("Courier", 9),
                                        lmargin1=20, lmargin2=20)

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
            matchup_strings = []
            for matchup in day_games:
                if 'OFF DAY' in matchup:
                    off_team = matchup[0] if matchup[0] != 'OFF DAY' else matchup[1]
                    matchup_strings.append(f"{off_team:4s} OFF")
                else:
                    matchup_strings.append(f"{matchup[0]:3s} @ {matchup[1]:3s}")

            # Display matchups in rows of 4
            for j in range(0, len(matchup_strings), 4):
                row_matchups = matchup_strings[j:j+4]
                matchups_line = "   ".join(row_matchups)
                self.schedule_text.insert(tk.END, "  " + matchups_line + "\n", "matchup")

            # Add spacing between days
            self.schedule_text.insert(tk.END, "\n")

        self.schedule_text.config(state=tk.DISABLED)

    def get_frame(self) -> tk.Frame:
        """Get the main frame for adding to parent container."""
        return self.frame
