"""
--- Copyright Notice ---
Copyright (c) 2024 Jim Maastricht

Games widget for baseball season simulation UI.

Displays today's schedule and results in a scrolling list format.
"""

import tkinter as tk
from tkinter import scrolledtext
from datetime import datetime
from typing import List, Tuple, Dict, Any

from ui.theme import BG_PANEL, BG_WIDGET, TEXT_PRIMARY, TEXT_HEADING, ACCENT_GOLD


class GamesWidget:
    """
    Games widget showing schedule and results.

    Features:
    - Scrolling list of 14 days
    - Today's games highlighted with ◄ CURRENT
    - Progressive score updates as games complete
    - Shows times for upcoming games
    """

    def __init__(self, parent: tk.Widget, followed_team: str = None):
        """Initialize games widget."""
        self.frame = tk.Frame(parent, bg=BG_PANEL)
        self.followed_team = followed_team

        # Single scrolling text widget
        self.schedule_text = scrolledtext.ScrolledText(
            self.frame,
            wrap=tk.WORD,
            font=("Consolas", 9),
            state=tk.DISABLED,
            bg=BG_WIDGET,
            fg=TEXT_PRIMARY,
            insertbackground=TEXT_PRIMARY
        )
        self.schedule_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

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
                                        foreground="#888888")
        self.schedule_text.tag_configure("score", font=("Consolas", 9, "bold"),
                                        foreground=ACCENT_GOLD)
        self.schedule_text.tag_configure("off_day", font=("Consolas", 9),
                                        foreground="#666666")

        # State
        self.season_schedule = []
        self.completed_games = {}  # {(away, home): {away_r, home_r, away_h, home_h, away_e, home_e}}
        self.schedule_dates = []
        self._current_day = 0

    def set_season_schedule(self, schedule: List):
        """Set the full season schedule."""
        self.season_schedule = schedule

    def set_schedule_dates(self, dates: List[str]):
        """Set the schedule dates."""
        self.schedule_dates = dates

    def update_schedule(self, current_day: int, schedule=None, schedule_times=None, schedule_dates=None):
        """Update the display to show 14 days starting from current_day."""
        if schedule_dates:
            self.schedule_dates = schedule_dates
            
        self._current_day = current_day
        
        self.schedule_text.config(state=tk.NORMAL)
        self.schedule_text.delete(1.0, tk.END)
        
        total_days = len(self.season_schedule)
        
        # Show previous day + current + next 13 days (total 14 days)
        start_day = max(0, current_day - 1)
        days_to_show = min(14, total_days - start_day)
        
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
                for game in day_games:
                    if game.is_off_day:
                        off_team = game.home if game.home != "OFF DAY" else game.away
                        self.schedule_text.insert(tk.END, f"  {off_team} OFF\n", "off_day")
                    else:
                        away, home = game.away, game.home
                        # Use day_index in key to look up correct game
                        game_key = (day_index, away, home)
                        
                        if game_key in self.completed_games:
                            game_result = self.completed_games[game_key]
                            away_r = game_result.get('away_r', 0)
                            home_r = game_result.get('home_r', 0)
                            away_h = game_result.get('away_h', 0)
                            home_h = game_result.get('home_h', 0)
                            away_e = game_result.get('away_e', 0)
                            home_e = game_result.get('home_e', 0)
                            
                            # Bold winner on score line
                            if away_r > home_r:
                                self.schedule_text.insert(tk.END, f"  {away:3s}", "bold_team")
                            else:
                                self.schedule_text.insert(tk.END, f"  {away:3s}", "matchup")
                            self.schedule_text.insert(tk.END, " @ ", "matchup")
                            if home_r > away_r:
                                self.schedule_text.insert(tk.END, f"{home:3s}", "bold_team")
                            else:
                                self.schedule_text.insert(tk.END, f"{home:3s}", "matchup")
                            # Score on its own line
                            self.schedule_text.insert(tk.END, f"  {away_r}-{home_r}\n", "score")
                            # R H E on separate lines
                            self.schedule_text.insert(tk.END, f"        H:{away_h} E:{away_e}\n", "matchup")
                            self.schedule_text.insert(tk.END, f"        H:{home_h} E:{home_e}\n", "matchup")
                        elif game.time:
                            self.schedule_text.insert(tk.END, f"  {away:3s}", "matchup")
                            self.schedule_text.insert(tk.END, " @ ", "matchup")
                            self.schedule_text.insert(tk.END, f"{home:3s}", "matchup")
                            self.schedule_text.insert(tk.END, f"  {game.time}\n", "time")
                        else:
                            self.schedule_text.insert(tk.END, f"  {away:3s}", "matchup")
                            self.schedule_text.insert(tk.END, " @ ", "matchup")
                            self.schedule_text.insert(tk.END, f"{home:3s}\n", "matchup")
            
            self.schedule_text.insert(tk.END, "\n")
        
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
        self.update_schedule(day_num)

    def on_game_completed(self, game_data: Dict[str, Any]):
        """Handle game completion - update score with R H E."""
        # Key must include day to avoid team collision across different days
        day_num = game_data.get('day_num', self._current_day)
        away = game_data['away_team']
        home = game_data['home_team']
        game_key = (day_num, away, home)  # Include day in key
        
        self.completed_games[game_key] = {
            'away_r': game_data.get('away_r', 0),
            'home_r': game_data.get('home_r', 0),
            'away_h': game_data.get('away_h', 0),
            'home_h': game_data.get('home_h', 0),
            'away_e': game_data.get('away_e', 0),
            'home_e': game_data.get('home_e', 0),
        }
        self.update_schedule(self._current_day)

    def on_day_completed(self, game_results: List[Dict], standings_data: Dict):
        """Handle day completed - update scores."""
        for game in game_results:
            day_num = game.get('day_num', self._current_day)
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
        self.update_schedule(self._current_day)

    def get_frame(self) -> tk.Frame:
        """Get the main frame."""
        return self.frame