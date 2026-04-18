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
        self._schedule_dates = []     # Date for each day (list of "YYYY-MM-DD" strings)
        self._schedule_times = {}     # {(away, home): "7:10 PM"} for future games
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
        self._schedule_dates = []
        self._schedule_times = {}

        # Load ALL games from CSV
        for date in sorted(df["Date"].unique()):
            day_games = df[df["Date"] == date]
            day_schedule = ScheduleDay(date)

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

                # Get time for future games
                game_time = None
                if not is_completed and pd.notna(row["Time"]) and row["Time"]:
                    game_time = self._convert_time_12hr(str(row["Time"]))
                    self._schedule_times[(away, home)] = game_time

                # Create GameMatchup object
                game = GameMatchup(home=home, away=away, time=game_time)
                if is_completed:
                    game.completed = True
                    game.home_score = row["Home_Score"]
                    game.away_score = row["Away_Score"]
                
                day_schedule.games.append(game)

            if day_schedule.games:
                self.schedule.append(day_schedule)
                self._schedule_dates.append(date)

        logger.info(
            f"Loaded {len(self.schedule)} days from {csv_path}"
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
        from datetime import datetime, timedelta

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
        self._schedule_dates = []
        
        # Start date (today) for random schedule
        start_date = datetime.now()
        
        random.shuffle(teams_list)
        
        day_counter = 0

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
                        round_pairs.append((away, "OFF DAY"))
                    elif away == "OFF":
                        round_pairs.append((home, "OFF DAY"))
                    else:
                        round_pairs.append((home, away))

                for _ in range(series_length):
                    if games_scheduled_for_tracker < target_games:
                        # Create ScheduleDay with GameMatchup objects
                        date_str = (start_date + timedelta(days=day_counter)).strftime("%Y-%m-%d")
                        day = ScheduleDay(date_str)
                        
                        for home, away in round_pairs:
                            game = GameMatchup(home=home, away=away)
                            day.games.append(game)
                        
                        self.schedule.append(day)
                        self._schedule_dates.append(date_str)
                        day_counter += 1
                        
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
        
        for idx, day in enumerate(self.schedule):
            date = day.date
            if date >= today and day.has_upcoming_games():
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
        if idx < len(self._schedule_dates):
            dt = datetime.datetime.strptime(self._schedule_dates[idx], "%Y-%m-%d")
            return dt.strftime("%m/%d/%Y")
        return f"Day {idx + 1}"

    def get_game_counter(self, team_win_loss: Dict, team_to_follow: List[str]) -> int:
        """Get game number from team's wins + losses.

        Args:
            team_win_loss: Dict mapping team to [wins, losses]
            team_to_follow: List of teams to follow

        Returns:
            Game number (wins + losses) for followed team, or 0
        """
        if not team_to_follow:
            return 0
        team = team_to_follow[0]
        if team in team_win_loss:
            wins, losses = team_win_loss[team]
            return wins + losses
        return 0

    def get_time_for_game(self, away: str, home: str) -> str:
        """Get 12-hour time for a game.
        
        Args:
            away: Away team abbreviation
            home: Home team abbreviation
            
        Returns:
            Time string (e.g., "7:10 PM") or empty string
        """
        return self._schedule_times.get((away, home), "")

    def get_games_for_day(self, day_index: int) -> List[GameMatchup]:
        """Get list of GameMatchup objects for a day.
        
        Args:
            day_index: Schedule day index
            
        Returns:
            List of GameMatchup objects
        """
        if 0 <= day_index < len(self.schedule):
            return self.schedule[day_index].games
        return []

    def get_day(self, day_index: int) -> Optional[ScheduleDay]:
        """Get ScheduleDay object for a day index.
        
        Args:
            day_index: Schedule day index
            
        Returns:
            ScheduleDay object or None
        """
        if 0 <= day_index < len(self.schedule):
            return self.schedule[day_index]
        return None

    @property
    def schedule_times(self) -> Dict:
        """Return schedule times dict for compatibility."""
        return self._schedule_times
    
    @property
    def schedule_dates(self) -> List:
        """Return schedule dates list for compatibility."""
        return self._schedule_dates
    
    @property
    def schedule_list(self) -> List:
        """Return schedule list (list of games per day) for compatibility."""
        return self.schedule

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
        for day in self.schedule:
            game = day.get_game(home, away)
            if game:
                return game.completed
        return False

    def mark_game_completed(self, home: str, away: str, home_score: int, away_score: int):
        """Find game and mark completed with scores.
        
        Args:
            home: Home team abbreviation
            away: Away team abbreviation
            home_score: Home team runs scored
            away_score: Away team runs scored
        """
        for day in self.schedule:
            game = day.get_game(home, away)
            if game:
                game.mark_completed(home_score, away_score)
                logger.debug(f"Marked {away} @ {home} as completed: {away_score}-{home_score}")
                return
        logger.warning(f"Could not find game {away} @ {home} to mark completed")


class GameMatchup:
    """Represents a single game matchup in the schedule."""
    
    def __init__(self, home: str, away: str, time: str = None):
        self.home = home                    # "MIL"
        self.away = away                    # "NYY"
        self.time = time                    # "7:10 PM" or None
        self.completed = False              # Game played?
        self.home_score = None
        self.away_score = None
        
    @property
    def is_off_day(self) -> bool:
        return self.home == "OFF DAY" or self.away == "OFF DAY"
    
    def mark_completed(self, home_score: int, away_score: int):
        """Mark game as completed with scores."""
        self.completed = True
        self.home_score = home_score
        self.away_score = away_score


class ScheduleDay:
    """Represents a single day in the schedule with multiple games."""
    
    def __init__(self, date: str, games: List[GameMatchup] = None):
        self.date = date                    # "2026-04-17"
        self.games = games or []          # List[GameMatchup]
        
    @property
    def is_completed(self) -> bool:
        """True if all real games (non-off-days) are completed."""
        real_games = [g for g in self.games if not g.is_off_day]
        if not real_games:
            return False
        return all(g.completed for g in real_games)
    
    @property
    def completed_count(self) -> int:
        return sum(1 for g in self.games if g.completed)
    
    def get_game(self, home: str, away: str) -> GameMatchup:
        """Find game by teams."""
        for g in self.games:
            if g.home == home and g.away == away:
                return g
        return None
    
    def has_upcoming_games(self) -> bool:
        """Check if any games not yet completed."""
        return any(not g.completed and not g.is_off_day for g in self.games)