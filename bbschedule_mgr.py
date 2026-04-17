"""
--- Copyright Notice ---
Copyright (c) 2024 Jim Maastricht

Schedule Manager for baseball season simulation.

Handles schedule loading, parsing, date calculations, and determining
where to start in the schedule based on partial season data.
"""

import os
import datetime
import pandas as pd
from typing import Dict, List, Optional, Tuple

from bblogger import logger


class ScheduleManager:
    """Manages baseball schedule loading, parsing, and date calculations.
    
    Responsibilities:
    - Load schedule from CSV or generate random
    - Track completed games and game times
    - Calculate starting position in schedule
    - Provide date/time lookup for UI
    """

    def __init__(self, baseball_data, new_season: int):
        """Initialize schedule manager.
        
        Args:
            baseball_data: BaseballStats instance for team validation
            new_season: Season year (e.g., 2026)
        """
        self.baseball_data = baseball_data
        self.new_season = new_season
        
        self.schedule = []           # Full schedule (list of days, each day is list of games)
        self.schedule_dates = []     # Date for each day (list of "YYYY-MM-DD" strings)
        self.schedule_times = {}     # {(away, home): "7:10 PM"} for future games
        self.completed_games = {}   # {(away, home): True} for completed games

    def load_from_csv(self, csv_path: str = None) -> bool:
        """Load schedule from downloaded CSV file.

        Priority:
        1. Use provided csv_path parameter
        2. Check for default file "{new_season} MLB Schedule.csv"
        3. Return False if not found

        Returns:
            True if loaded successfully, False otherwise
        """
        if csv_path is None:
            csv_path = f"{self.new_season} MLB Schedule.csv"

        if not os.path.exists(csv_path):
            logger.debug(f"Schedule CSV not found: {csv_path}")
            return False

        df = pd.read_csv(csv_path)
        valid_teams = set(self.baseball_data.get_all_team_names())

        self.schedule = []
        self.schedule_dates = []
        self.schedule_times = {}
        self.completed_games = {}

        # Load ALL games from CSV
        for date in sorted(df["Date"].unique()):
            day_games = df[df["Date"] == date]
            day_schedule = []

            for _, row in day_games.iterrows():
                away, home = row["Away_Team"], row["Home_Team"]

                # Skip if teams don't match sim data
                if away not in valid_teams or home not in valid_teams:
                    logger.warning(f"Skipping game: {away} @ {home} - team not found")
                    continue

                # Check if game already played (has score or no time)
                is_completed = (
                    (pd.isna(row["Time"]) or not row["Time"]) or 
                    (row["Away_Score"] > 0 or row["Home_Score"] > 0)
                )
                if is_completed:
                    self.completed_games[(away, home)] = True

                # Always add to schedule
                day_schedule.append([home, away])

                # Store time only for future games
                if not is_completed and pd.notna(row["Time"]) and row["Time"]:
                    time_12h = self._convert_time_12hr(str(row["Time"]))
                    self.schedule_times[(away, home)] = time_12h

            if day_schedule:
                self.schedule.append(day_schedule)
                self.schedule_dates.append(date)

        logger.info(
            f"Loaded {len(self.schedule)} days from {csv_path}, "
            f"{len(self.completed_games)} completed"
        )
        return True

    def create_random(
        self, 
        teams: List[str], 
        season_length: int = 162, 
        series_length: int = 3
    ) -> None:
        """Generate random round-robin schedule.
        
        Args:
            teams: List of team abbreviations
            season_length: Number of games per team (default 162)
            series_length: Games per series (default 3)
        """
        import random

        teams_list = [t for t in teams if t != "OFF DAY"]
        target_games = season_length

        # Round Robin requires even number
        if len(teams_list) % 2 != 0:
            teams_list.append("OFF")

        num_teams = len(teams_list)
        num_rounds = num_teams - 1

        tracking_team = [t for t in teams_list if t != "OFF"][0]
        games_scheduled_for_tracker = 0

        self.schedule = []
        random.shuffle(teams_list)

        while games_scheduled_for_tracker < target_games:
            for _ in range(num_rounds):
                round_pairs = []
                tracker_has_game = False

                for i in range(num_teams // 2):
                    home = teams_list[i]
                    away = teams_list[num_teams - 1 - i]

                    if tracking_team in (home, away) and "OFF" not in (home, away):
                        tracker_has_game = True

                    if home == "OFF":
                        round_pairs.append([away, "OFF DAY"])
                    elif away == "OFF":
                        round_pairs.append([home, "OFF DAY"])
                    else:
                        round_pairs.append([home, away])

                for _ in range(series_length):
                    if games_scheduled_for_tracker < target_games:
                        self.schedule.append(round_pairs)
                        if tracker_has_game:
                            games_scheduled_for_tracker += 1
                    else:
                        break

                teams_list = [teams_list[0]] + [teams_list[-1]] + teams_list[1:-1]

                if games_scheduled_for_tracker >= target_games:
                    break

    def find_start_day(self, team_win_loss: Dict, team_to_follow: List[str]) -> int:
        """Calculate starting position in schedule.
        
        Logic:
        1. Find today's position: first date >= today in schedule_dates
        2. Calculate team position: wins + losses for followed team
        3. Use MAX of both to ensure we start at or after actual position
        
        Args:
            team_win_loss: Dict mapping team to [wins, losses]
            team_to_follow: List of teams to follow
            
        Returns:
            Day number (index) to start simulation
        """
        # Find today's position in schedule
        today = datetime.datetime.now().strftime("%Y-%m-%d")
        start_day = 0
        
        for idx, date in enumerate(self.schedule_dates):
            if date >= today:
                start_day = idx
                break

        # Calculate team's position (wins + losses)
        team_day = 0
        if team_to_follow:
            team = team_to_follow[0]
            if team in team_win_loss:
                wins, losses = team_win_loss[team]
                team_day = wins + losses

        # Use MAX to ensure we start at or after both positions
        return max(start_day, team_day)

    def get_date_for_index(self, idx: int) -> str:
        """Get formatted date for schedule index.
        
        Args:
            idx: Schedule index
            
        Returns:
            Formatted date (e.g., "04/17/2026") or "Day X" if invalid
        """
        if idx < len(self.schedule_dates):
            dt = datetime.datetime.strptime(self.schedule_dates[idx], "%Y-%m-%d")
            return dt.strftime("%m/%d/%Y")
        return f"Day {idx + 1}"

    def get_time_for_game(self, away: str, home: str) -> str:
        """Get 12-hour time for a game.
        
        Args:
            away: Away team abbreviation
            home: Home team abbreviation
            
        Returns:
            Time string (e.g., "7:10 PM") or empty string
        """
        return self.schedule_times.get((away, home), "")

    def _convert_time_12hr(self, time_24h: str) -> str:
        """Convert '14:10' to '2:10 PM'.
        
        Args:
            time_24h: Time in 24-hour format
            
        Returns:
            Time in 12-hour format
        """
        try:
            dt = datetime.datetime.strptime(time_24h, "%H:%M")
            return dt.strftime("%-I:%M %p").lstrip("0")
        except ValueError:
            return time_24h

    def is_game_completed(self, away: str, home: str) -> bool:
        """Check if a game is already completed.
        
        Args:
            away: Away team abbreviation
            home: Home team abbreviation
            
        Returns:
            True if game was already played
        """
        return (away, home) in self.completed_games