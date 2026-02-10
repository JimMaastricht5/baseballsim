"""
--- Copyright Notice ---
Copyright (c) 2024 Jim Maastricht

Games Played widget for baseball season simulation UI.

Displays historical play-by-play for followed team games.
"""

import tkinter as tk
from tkinter import ttk, scrolledtext
from typing import Dict, List, Tuple
from bblogger import logger


class GamesPlayedWidget:
    """
    Games Played widget showing play-by-play history for followed team.

    Features:
    - Day dropdown to select which day to view
    - Displays full play-by-play recap for followed games
    - Formatted display with game headers and score highlights
    """

    def __init__(self, parent: tk.Widget):
        """
        Initialize games played widget.

        Args:
            parent: Parent tkinter widget (notebook or frame)
        """
        self.frame = tk.Frame(parent)

        # Storage for play-by-play data by day
        self.pbp_by_day = {}  # Dict: {day_num: [(away, home, game_recap), ...]}

        # Control frame with day dropdown
        pbp_control_frame = tk.Frame(self.frame)
        pbp_control_frame.pack(fill=tk.X, padx=10, pady=5)

        tk.Label(pbp_control_frame, text="Day:", font=("Arial", 10, "bold")).pack(side=tk.LEFT, padx=5)
        self.pbp_day_var = tk.StringVar(value="Select Day")
        self.pbp_day_combo = ttk.Combobox(
            pbp_control_frame,
            textvariable=self.pbp_day_var,
            width=15,
            state="readonly"
        )
        self.pbp_day_combo['values'] = ['Select Day']
        self.pbp_day_combo.bind('<<ComboboxSelected>>', self._on_day_changed)
        self.pbp_day_combo.pack(side=tk.LEFT, padx=5)

        # Info label
        self.pbp_info_label = tk.Label(
            pbp_control_frame,
            text="Select a day to view play-by-play for followed games",
            font=("Arial", 9),
            fg="#666666"
        )
        self.pbp_info_label.pack(side=tk.LEFT, padx=20)

        # ScrolledText for play-by-play
        self.pbp_text = scrolledtext.ScrolledText(
            self.frame, wrap=tk.WORD, font=("Courier", 9), state=tk.DISABLED
        )

        # Configure text tags for formatting
        self.pbp_text.tag_configure("game_header", font=("Arial", 11, "bold"),
                                   foreground="#1a3d6b", spacing1=10, spacing3=5)
        self.pbp_text.tag_configure("play", font=("Courier", 9))
        self.pbp_text.tag_configure("score_update", font=("Courier", 9, "bold"),
                                   foreground="#006600")

        self.pbp_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    def add_game_recap(self, day_num: int, away_team: str, home_team: str, game_recap: str):
        """
        Add a game recap to the play-by-play storage.

        Args:
            day_num: Day number (0-indexed)
            away_team: Away team abbreviation
            home_team: Home team abbreviation
            game_recap: Full game play-by-play text
        """
        if day_num not in self.pbp_by_day:
            self.pbp_by_day[day_num] = []

        self.pbp_by_day[day_num].append((away_team, home_team, game_recap))

        # Update dropdown with new day
        current_days = [f"Day {d+1}" for d in sorted(self.pbp_by_day.keys())]
        self.pbp_day_combo['values'] = ['Select Day'] + current_days

        logger.debug(f"Added game recap for Day {day_num + 1}: {away_team} @ {home_team}")

    def _on_day_changed(self, event=None):
        """Handle day dropdown change."""
        selected = self.pbp_day_var.get()

        if selected == "Select Day":
            return

        # Extract day number from "Day X" format
        try:
            day_num = int(selected.split()[1]) - 1  # Convert back to 0-indexed
        except (ValueError, IndexError):
            logger.error(f"Invalid day selection: {selected}")
            return

        # Get games for this day
        games = self.pbp_by_day.get(day_num, [])

        if not games:
            self.pbp_text.config(state=tk.NORMAL)
            self.pbp_text.delete(1.0, tk.END)
            self.pbp_text.insert(tk.END, f"No followed games on {selected}\n")
            self.pbp_text.config(state=tk.DISABLED)
            return

        # Display all games for this day
        self.pbp_text.config(state=tk.NORMAL)
        self.pbp_text.delete(1.0, tk.END)

        for away, home, game_recap in games:
            # Add game header
            header = f"▼ {away} @ {home} ▼\n"
            self.pbp_text.insert(tk.END, "\n" if self.pbp_text.get(1.0, tk.END).strip() else "")
            self.pbp_text.insert(tk.END, header, "game_header")

            # Add game recap (already formatted with play-by-play)
            # Apply simple formatting: highlight score lines
            for line in game_recap.split('\n'):
                if "Scored" in line or "score is" in line:
                    self.pbp_text.insert(tk.END, line + '\n', "score_update")
                else:
                    self.pbp_text.insert(tk.END, line + '\n', "play")

            # Add separator between games
            self.pbp_text.insert(tk.END, "\n" + "="*80 + "\n")

        self.pbp_text.see(1.0)  # Scroll to top of day's games
        self.pbp_text.config(state=tk.DISABLED)

        logger.debug(f"Displayed {len(games)} games for Day {day_num + 1}")

    def get_frame(self) -> tk.Frame:
        """Get the main frame for adding to parent container."""
        return self.frame
