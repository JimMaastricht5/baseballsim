"""
--- Copyright Notice ---
Copyright (c) 2024 Jim Maastricht

Games widget for baseball season simulation UI.

Displays today's schedule and results in a scrolling list format.
"""

import tkinter as tk
from datetime import datetime
from tkinter import scrolledtext
from typing import List, Tuple, Dict, Any

from ui.theme import BG_PANEL, BG_WIDGET, TEXT_PRIMARY, TEXT_HEADING, ACCENT_GOLD
from bblogger import logger


class GamesWidget:
    """
    Games widget showing schedule and results.

    Features:
    - Scrolling list of 16 days (past 3 + current + next 13)
    - Today's games highlighted with ◄ CURRENT
    - Scoreboard format: R  H  E grid per game
    - 4 games per line layout
    - Keeps past days visible as simulation progresses
    """

    def __init__(self, parent: tk.Widget, followed_team: str = None):
        """Initialize games widget."""
        self.frame = tk.Frame(parent, bg=BG_PANEL)
        self.followed_team = followed_team

        # Header
        header = tk.Label(
            self.frame, text="Today's Games (Past + Current + Next)",
            font=("Segoe UI", 11, "bold"), pady=5, bg=BG_PANEL, fg=TEXT_HEADING
        )
        header.pack()

        # Single scrolling text widget
        self.schedule_text = scrolledtext.ScrolledText(
            self.frame,
            wrap=tk.NONE,
            font=("Consolas", 9),
            state=tk.DISABLED,
            bg=BG_WIDGET,
            fg=TEXT_PRIMARY,
            insertbackground=TEXT_PRIMARY
        )
        self.schedule_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Configure text tags for formatting
        self.schedule_text.tag_configure("day_header", font=("Segoe UI", 12, "bold"),
                                         foreground=ACCENT_GOLD, spacing1=8, spacing3=3)
        self.schedule_text.tag_configure("current_day", background="#1f3010",
                                         font=("Segoe UI", 12, "bold"), foreground=ACCENT_GOLD,
                                         spacing1=8, spacing3=3)
        self.schedule_text.tag_configure("upcoming_header", font=("Segoe UI", 11, "bold"),
                                         foreground=ACCENT_GOLD, spacing1=8, spacing3=3)
        self.schedule_text.tag_configure("matchup", font=("Consolas", 9),
                                         lmargin1=20, lmargin2=20)
        self.schedule_text.tag_configure("time", font=("Consolas", 9),
                                         foreground="#888888")
        self.schedule_text.tag_configure("off_day", font=("Consolas", 9),
                                         foreground="#666666")

        # State
        self.season_schedule = []
        self.completed_games = {}  # {(day, away, home): {away_r, home_r, away_h, home_h, away_e, home_e}}
        self.schedule_dates = []
        self._current_day = 0
        self._batch_update_day = None  # Day number being batched - suppress individual redraws

    def set_season_schedule(self, schedule: List):
        """Set the full season schedule."""
        self.season_schedule = schedule
        # Sync completed games from schedule (in case games were loaded as completed from CSV)
        # Note: CSV only has scores, not hits/errors, so we default H and E to 0
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

    def update_schedule(self, current_day: int, schedule=None, schedule_times=None, schedule_dates=None):
        """Update the display to show past + current + upcoming days."""
        if schedule_dates:
            self.schedule_dates = schedule_dates

        self._current_day = current_day

        self.schedule_text.config(state=tk.NORMAL)
        self.schedule_text.delete(1.0, tk.END)

        total_days = len(self.season_schedule)

        # Show past 3 days + current + next 13 days = 16 days total
        start_day = max(0, current_day - 3)
        days_to_show = min(16, total_days - start_day)

        for i in range(days_to_show):
            day_index = start_day + i
            if day_index >= total_days:
                break

            day_obj = self.season_schedule[day_index]
            day_games = day_obj.games if hasattr(day_obj, 'games') else []

            date_str = self._get_date_for_day(day_index)

            # Mark the actual current day with ◄ CURRENT
            if day_index == current_day:
                day_label = f"{date_str} ◄ CURRENT"
                self.schedule_text.insert(tk.END, day_label + "\n", "current_day")
            else:
                self.schedule_text.insert(tk.END, date_str + "\n", "day_header")

            if not day_games:
                self.schedule_text.insert(tk.END, "  No games\n", "matchup")
            else:
                # Categorize games
                completed_rows = []  # [(game, result)]
                pending_rows = []   # [game]

                for game in day_games:
                    if game.is_off_day:
                        off_team = game.home if game.home != "OFF DAY" else game.away
                        self.schedule_text.insert(tk.END, f"  {off_team} OFF\n", "off_day")
                    else:
                        game_key = (day_index, game.away, game.home)
                        if game_key in self.completed_games:
                            completed_rows.append((game, self.completed_games[game_key]))
                        else:
                            pending_rows.append(game)

                # === Completed Games Section (3 columns) ===
                if completed_rows:
                    # Process in chunks of 3
                    for chunk_idx in range(0, len(completed_rows), 3):
                        chunk = completed_rows[chunk_idx:chunk_idx + 3]

                        # Pad to 3 if needed
                        while len(chunk) < 3:
                            chunk.append((None, None))  # Placeholder

                        # Row 1: RHE header
                        for game, result in chunk:
                            if game:
                                self.schedule_text.insert(tk.END, "    R  H  E", "rhe_header")
                            else:
                                self.schedule_text.insert(tk.END, f"{'':15}", "placeholder")
                        self.schedule_text.insert(tk.END, "\n", "matchup")

                        # Row 2: Away team stats
                        for game, result in chunk:
                            if game and result:
                                away = game.away
                                away_r = result.get('away_r', 0)
                                away_h = result.get('away_h', 0)
                                away_e = result.get('away_e', 0)
                                entry = f"{away} {away_r} {away_h} {away_e}"
                                self.schedule_text.insert(tk.END, f"{entry:<15}", "score")
                            else:
                                self.schedule_text.insert(tk.END, f"{'':15}", "placeholder")
                        self.schedule_text.insert(tk.END, "\n", "matchup")

                        # Row 3: Home team stats
                        for game, result in chunk:
                            if game and result:
                                home = game.home
                                home_r = result.get('home_r', 0)
                                home_h = result.get('home_h', 0)
                                home_e = result.get('home_e', 0)
                                entry = f"{home} {home_r} {home_h} {home_e}"
                                self.schedule_text.insert(tk.END, f"{entry:<15}", "score")
                            else:
                                self.schedule_text.insert(tk.END, f"{'':15}", "placeholder")
                        self.schedule_text.insert(tk.END, "\n", "matchup")

                # === Pending Games Section (4 per line, like schedule) ===
                if pending_rows:
                    self.schedule_text.insert(tk.END, "Upcoming Games\n", "upcoming_header")

                    matchups_per_line = 4
                    matchup_count = 0

                    for game in pending_rows:
                        if matchup_count % matchups_per_line == 0:
                            self.schedule_text.insert(tk.END, "  ", "matchup")
                        else:
                            self.schedule_text.insert(tk.END, "   ", "matchup")

                        away, home = game.away, game.home
                        if self.followed_team and away == self.followed_team:
                            self.schedule_text.insert(tk.END, f"{away:3s}", "score")
                        else:
                            self.schedule_text.insert(tk.END, f"{away:3s}", "matchup")
                        self.schedule_text.insert(tk.END, " @ ", "matchup")
                        if self.followed_team and home == self.followed_team:
                            self.schedule_text.insert(tk.END, f"{home:3s}", "score")
                        else:
                            self.schedule_text.insert(tk.END, f"{home:3s}", "matchup")

                        if game.time:
                            self.schedule_text.insert(tk.END, f" {game.time}", "time")

                        matchup_count += 1

                        if matchup_count % matchups_per_line == 0:
                            self.schedule_text.insert(tk.END, "\n", "matchup")

                    # Final line break if needed
                    if matchup_count % matchups_per_line != 0:
                        self.schedule_text.insert(tk.END, "\n", "matchup")

                # Extra spacing between days
                self.schedule_text.insert(tk.END, "\n", "matchup")

        self.schedule_text.config(state=tk.DISABLED)
        self.schedule_text.see("1.0")

    def _get_date_for_day(self, day_index: int) -> str:
        """Return formatted date for display."""
        if day_index < len(self.schedule_dates):
            try:
                dt = datetime.strptime(self.schedule_dates[day_index], "%Y-%m-%d")
                return dt.strftime("%B %d, %Y")
            except:
                pass
        return f"Day {day_index + 1}"

    def on_day_started(self, day_num: int, schedule: List[Tuple[str, str]], date_str: str = None):
        """Handle day started - update display."""
        self._batch_update_day = day_num
        self.update_schedule(day_num)

    def on_game_completed(self, game_data: Dict[str, Any]):
        """Handle game completion - store result, skip redraw during batch."""
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
        logger.debug(f"GamesWidget stored: Day {day_num} {away}@{home}, total: {len(self.completed_games)}")
        if day_num != self._batch_update_day:
            self.update_schedule(day_num)

    def on_day_completed(self, game_results: List[Dict], standings_data: Dict, day_number: int = None):
        """Handle day completed - update all scores and redraw once."""
        update_day = day_number if day_number is not None else self._current_day
        logger.debug(f"on_day_completed: Day {update_day}, receiving {len(game_results)} games")
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
            logger.debug(f"  batch: Day {day_num} {away}@{home}")
        logger.debug(f"on_day_completed: total stored after: {len(self.completed_games)}")
        self._batch_update_day = None
        self.update_schedule(update_day)

    def get_frame(self) -> tk.Frame:
        """Get the main frame."""
        return self.frame
