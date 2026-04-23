"""
--- Copyright Notice ---
Copyright (c) 2024 Jim Maastricht

Games widget for baseball season simulation UI.

Displays completed game results in a scrollable list (newest first).
"""

import tkinter as tk
from datetime import datetime
from tkinter import scrolledtext
from typing import List, Dict, Any

from ui.theme import BG_PANEL, BG_WIDGET, TEXT_PRIMARY, TEXT_HEADING, ACCENT_GOLD


class GamesWidget:
    """
    Games widget showing completed results in scrollable list.

    Features:
    - Only completed games shown
    - Newest results at top
    - Vertical scrollbar for navigation
    """

    def __init__(self, parent: tk.Widget, followed_team: str = None):
        """Initialize games widget."""
        self.frame = tk.Frame(parent, bg=BG_PANEL)
        self.followed_team = followed_team

        # Header
        header = tk.Label(
            self.frame, text="Game Results",
            font=("Segoe UI", 11, "bold"), pady=5, bg=BG_PANEL, fg=TEXT_HEADING
        )
        header.pack()

        # Use ScrolledText for results (matches Schedule tab style)
        self.results_text = scrolledtext.ScrolledText(
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

        # Configure text tags (matches Schedule widget style)
        self.results_text.tag_configure("day_header", font=("Segoe UI", 12, "bold"),
                                        foreground=ACCENT_GOLD, spacing1=5, spacing3=3)
        self.results_text.tag_configure("rhe_header", font=("Consolas", 9),
                                        foreground="#888888", lmargin1=10)
        self.results_text.tag_configure("score", font=("Consolas", 9),
                                        foreground=TEXT_PRIMARY, lmargin1=5)
        self.results_text.tag_configure("score_followed", font=("Consolas", 9),
                                        foreground=ACCENT_GOLD, lmargin1=5)
        self.results_text.tag_configure("placeholder", font=("Consolas", 9),
                                        foreground="#666666", lmargin1=5)
        self.results_text.tag_configure("off_day", font=("Consolas", 9),
                                        foreground="#666666", lmargin1=5)

        self.results_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # State
        self.completed_games = {}
        self.schedule_dates = []
        self._current_day = 0
        self._batch_update_day = None

    def set_season_schedule(self, schedule: List):
        """Set the full season schedule."""
        self.season_schedule = schedule
        self.completed_games = {}
        for day_idx, day in enumerate(schedule):
            for game in day.games:
                if game.completed:
                    key = (day_idx, game.away, game.home)
                    self.completed_games[key] = {
                        'away_r': game.away_score if game.away_score else 0,
                        'home_r': game.home_score if game.home_score else 0,
                        'away_h': 0,
                        'home_h': 0,
                        'away_e': 0,
                        'home_e': 0,
                    }

    def set_schedule_dates(self, dates: List[str]):
        """Set the schedule dates."""
        self.schedule_dates = dates

    def _get_date_for_day(self, day_index: int) -> str:
        """Return formatted date for display."""
        if day_index < len(self.schedule_dates):
            try:
                dt = datetime.strptime(self.schedule_dates[day_index], "%Y-%m-%d")
                return dt.strftime("%B %d, %Y")
            except ValueError:
                pass
        return f"Day {day_index + 1}"

    def _build_day_content(self, day_index: int) -> list:
        """Build formatted content for a single day as list of (tag, text) tuples."""
        # Configuration constants
        GAMES_PER_ROW = 6
        COLUMN_WIDTH = 15

        if day_index >= len(self.season_schedule) if hasattr(self, 'season_schedule') else True:
            return []

        day_obj = self.season_schedule[day_index]
        day_games = day_obj.games if hasattr(day_obj, 'games') else []

        date_str = self._get_date_for_day(day_index)
        lines = [("day_header", f"{date_str}\n")]

        if not day_games:
            return lines

        completed_rows = []
        for game in day_games:
            if game.is_off_day:
                off_team = game.home if game.home != "OFF DAY" else game.away
                lines.append(("off_day", f"  {off_team} OFF\n"))
                continue

            game_key = (day_index, game.away, game.home)
            if game_key in self.completed_games:
                completed_rows.append((game, self.completed_games[game_key]))

        if not completed_rows:
            return lines

        # Process games in chunks
        for chunk_idx in range(0, len(completed_rows), GAMES_PER_ROW):
            chunk = completed_rows[chunk_idx:chunk_idx + GAMES_PER_ROW]

            while len(chunk) < GAMES_PER_ROW:
                chunk.append((None, None))

            # --- Row 1: RHE Header (Always neutral) ---
            for game, result in chunk:
                if game:
                    # Always use 'rhe_header' tag to avoid highlighting the column titles
                    lines.append(("rhe_header", "    R  H  E    "))
                else:
                    lines.append(("rhe_header", " " * COLUMN_WIDTH))
            lines.append(("rhe_header", "\n"))

            # --- Row 2: Away Team ---
            for game, result in chunk:
                if game and result:
                    away = game.away
                    entry = f"{away:<3} {result['away_r']:>2} {result['away_h']:>2} {result['away_e']:>2}"
                    tag = "score_followed" if away == self.followed_team else "score"
                    lines.append((tag, f"{entry:<{COLUMN_WIDTH}}"))
                else:
                    lines.append(("score", " " * COLUMN_WIDTH))
            lines.append(("score", "\n"))

            # --- Row 3: Home Team ---
            for game, result in chunk:
                if game and result:
                    home = game.home
                    entry = f"{home:<3} {result['home_r']:>2} {result['home_h']:>2} {result['home_e']:>2}"
                    tag = "score_followed" if home == self.followed_team else "score"
                    lines.append((tag, f"{entry:<{COLUMN_WIDTH}}"))
                else:
                    lines.append(("score", " " * COLUMN_WIDTH))
            lines.append(("score", "\n"))

            # Spacer between rows of box scores
            lines.append(("score", "\n"))

        return list(reversed(lines))

    # def _build_day_content(self, day_index: int) -> list:
    #     """Build formatted content for a single day as list of (tag, text) tuples."""
    #     if day_index >= len(self.season_schedule) if hasattr(self, 'season_schedule') else True:
    #         return []
    #
    #     day_obj = self.season_schedule[day_index]
    #     day_games = day_obj.games if hasattr(day_obj, 'games') else []
    #
    #     date_str = self._get_date_for_day(day_index)
    #     lines = [("day_header", f"{date_str}\n")]
    #
    #     if not day_games:
    #         return []
    #
    #     completed_rows = []
    #     for game in day_games:
    #         if game.is_off_day:
    #             off_team = game.home if game.home != "OFF DAY" else game.away
    #             lines.append(("off_day", f"  {off_team} OFF\n"))
    #             continue
    #
    #         game_key = (day_index, game.away, game.home)
    #         if game_key in self.completed_games:
    #             completed_rows.append((game, self.completed_games[game_key]))
    #
    #     if not completed_rows:
    #         return []
    #
    #     # 7 games per row
    #     for chunk_idx in range(0, len(completed_rows), 3):
    #         chunk = completed_rows[chunk_idx:chunk_idx + 3]
    #         while len(chunk) < 3:
    #             chunk.append((None, None))
    #
    #         # Check if any game involves the followed team
    #         followed_in_chunk = any(
    #             game and (game.away == self.followed_team or game.home == self.followed_team)
    #             for game, result in chunk
    #             if game and result
    #         )
    #         row_tag = "score_followed" if followed_in_chunk else "score"
    #
    #         # Row 1: RHE header
    #         for col_idx in range(3):
    #             game = chunk[col_idx][0] if chunk[col_idx][0] else None
    #             if game:
    #                 tag = "score_followed" if self.followed_team and (
    #                         game.away == self.followed_team or game.home == self.followed_team) else "rhe_header"
    #                 lines.append((tag, "    R  H  E    "))
    #             else:
    #                 lines.append(("rhe_header", f"{'':15}"))
    #         lines.append(("rhe_header", "\n"))
    #
    #         # Row 2: Away
    #         for col_idx in range(3):
    #             game, result = chunk[col_idx]
    #             if game and result:
    #                 away = game.away
    #                 entry = f"{away} {result['away_r']:>2} {result['away_h']:>2} {result['away_e']:>2}"
    #                 tag = "score_followed" if self.followed_team and away == self.followed_team else "score"
    #                 lines.append((tag, f"{entry:<15}"))
    #
    #         # Row 3: Home
    #         for col_idx in range(3):
    #             game, result = chunk[col_idx]
    #             if game and result:
    #                 home = game.home
    #                 entry = f"{home} {result['home_r']:>2} {result['home_h']:>2} {result['home_e']:>2}"
    #                 tag = "score_followed" if self.followed_team and home == self.followed_team else "score"
    #                 lines.append((tag, f"{entry:<15}"))
    #
    #     return list(reversed(lines))  # need to be reversed since newest lines stay on top of screen

    def update_schedule(self, current_day: int, schedule=None, schedule_times=None, schedule_dates=None):
        """Update the display."""
        if schedule_dates:
            self.schedule_dates = schedule_dates
        self._current_day = current_day

        if schedule:
            self.season_schedule = schedule

    def on_day_started(self, day_num: int, schedule: List, date_str: str = None):
        """Handle day started."""
        self._batch_update_day = day_num
        self._current_day = day_num

    def on_game_completed(self, game_data: Dict[str, Any]):
        """Handle game completion."""
        day_num = game_data.get('day_num')
        if day_num is None:
            day_num = self._current_day
        away = game_data['away_team']
        home = game_data['home_team']
        game_key = (day_num, away, home)

        self.completed_games[game_key] = {
            'away_r': game_data.get('away_r', 0),
            'home_r': game_data.get('home_r', 0),
            'away_h': game_data.get('away_h', 0),
            'home_h': game_data.get('home_h', 0),
            'away_e': game_data.get('away_e', 0),
            'home_e': game_data.get('home_e', 0),
        }

    def on_day_completed(self, game_results: List[Dict], standings_data: Dict, day_number: int = None):
        """Handle day completed - add results at top."""
        update_day = day_number if day_number is not None else self._current_day

        # Store all game results
        for game in game_results:
            day_num = game.get('day_num', update_day)
            away = game['away_team']
            home = game['home_team']
            game_key = (day_num, away, home)
            self.completed_games[game_key] = {
                'away_r': game.get('away_r', 0),
                'home_r': game.get('home_r', 0),
                'away_h': game.get('away_h', 0),
                'home_h': game.get('home_h', 0),
                'away_e': game.get('away_e', 0),
                'home_e': game.get('home_e', 0),
            }
        self._batch_update_day = None

        # Build and insert content at top with tags
        content_lines = self._build_day_content(update_day)
        if content_lines:
            self.results_text.config(state=tk.NORMAL)
            insert_pos = 1.0
            for tag, text in content_lines:
                self.results_text.insert(insert_pos, text, tag)
            self.results_text.config(state=tk.DISABLED)

    def get_frame(self) -> tk.Frame:
        """Get the main frame."""
        return self.frame
