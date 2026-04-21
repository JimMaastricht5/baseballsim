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
        self.completed_games = {}     # {(away, home): True} for completed games
        
        # Playoff schedule (separate from regular season)
        self._playoff_schedule = []   # List[ScheduleDay] for playoff games
        self._playoff_dates = []      # ["2026-10-01", ...] for playoffs
        self._series_winners = {}     # {(away, home): winner_team} for completed series

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
        1. Find the first day that has games NOT yet completed
        2. Calculate team position: wins + losses for followed team
        3. Use MAX of both to ensure we start at or after actual position

        Args:
            team_win_loss: Dict mapping team to [wins, losses]
            team_to_follow: List of teams to follow

        Returns:
            Day number (index) to start simulation
        """
        # Find the first day that has upcoming (not completed) games
        start_day = 0

        for idx, day in enumerate(self.schedule):
            if day.has_upcoming_games():
                start_day = idx
                break
        else:
            # All games completed, start from last day
            start_day = len(self.schedule) - 1

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

    def clear_playoffs(self):
        """Clear all playoff data."""
        self._playoff_schedule = []
        self._playoff_dates = []
        self._series_winners = {}

    def get_playoff_date(self, day_offset: int) -> str:
        """Calculate date for playoff day N (0 = first playoff day).
        
        Args:
            day_offset: Days from start of playoffs (0-21 for full playoffs)
            
        Returns:
            Date string in "YYYY-MM-DD" format
        """
        if not self._schedule_dates:
            # Default to October 1 if no regular season dates
            base_date = datetime.datetime(2026, 10, 1)
        else:
            # Start from end of regular season
            last_date = self._schedule_dates[-1]
            base_date = datetime.datetime.strptime(last_date, "%Y-%m-%d")
        
        # First playoff day is the first Monday on or after Oct 1
        # Find first Monday in October
        oct_1 = datetime.datetime(base_date.year, 10, 1)
        # Days until next Monday (0=Monday, so Monday=0)
        days_until_monday = (7 - oct_1.weekday()) % 7
        if days_until_monday == 0 and oct_1.weekday() != 0:
            days_until_monday = 7
        first_playoff_monday = oct_1 + datetime.timedelta(days=days_until_monday)
        
        playoff_date = first_playoff_monday + datetime.timedelta(days=day_offset)
        return playoff_date.strftime("%Y-%m-%d")

    def is_playoff_day(self, day_index: int) -> bool:
        """Check if day index is in playoffs.
        
        Args:
            day_index: Day index relative to start of playoffs
            
        Returns:
            True if day_index is within playoff schedule
        """
        return 0 <= day_index < len(self._playoff_schedule)

    def get_playoff_games_for_day(self, day_index: int) -> List[GameMatchup]:
        """Get games for a specific playoff day.
        
        Args:
            day_index: Day index relative to start of playoffs (0 = first playoff day)
            
        Returns:
            List of GameMatchup objects for that day
        """
        if 0 <= day_index < len(self._playoff_schedule):
            return self._playoff_schedule[day_index].games
        return []

    def get_series_games(self, away: str, home: str) -> List[PlayoffMatchup]:
        """Get all games for a playoff series.
        
        Args:
            away: Away team abbreviation
            home: Home team abbreviation
            
        Returns:
            List of PlayoffMatchup objects for this series, sorted by game_num
        """
        series_games = []
        for day in self._playoff_schedule:
            for game in day.games:
                if isinstance(game, PlayoffMatchup):
                    if (game.away == away and game.home == home):
                        series_games.append(game)
        return sorted(series_games, key=lambda g: g.game_num)

    def set_series_winner(self, away: str, home: str, winner: str):
        """Mark series as complete with winner.
        
        Args:
            away: Away team abbreviation
            home: Home team abbreviation  
            winner: Winning team abbreviation
        """
        self._series_winners[(away, home)] = winner
        for game in self.get_series_games(away, home):
            game.series_winner = winner

    def get_series_winner(self, away: str, home: str) -> Optional[str]:
        """Get winner of completed series.
        
        Args:
            away: Away team abbreviation
            home: Home team abbreviation
            
        Returns:
            Winner team abbreviation or None if not complete
        """
        return self._series_winners.get((away, home))

    def build_full_playoff_bracket(self, al_seeds: List[str], nl_seeds: List[str]):
        """Build entire playoff schedule at start of playoffs.
        
        Creates all playoff games upfront with correct home/away based on MLB format:
        - Wild Card: Best of 3, all games at higher seed
        - Division Series: Best of 5, 2-2-1 format
        - LCS: Best of 7, 2-3-2 format
        - World Series: Best of 7, 2-3-2 format
        
        Args:
            al_seeds: List of 6 AL team abbreviations in seed order (1-6)
            nl_seeds: List of 6 NL team abbreviations in seed order (1-6)
        """
        self.clear_playoffs()
        
        # Day offset tracker
        day_offset = 0
        
        def add_series_games(home: str, away: str, best_of: int, round_name: str):
            """Add all games for a series."""
            nonlocal day_offset
            games_to_add = []
            
            for game_num in range(1, best_of + 1):
                # Determine home team based on MLB format
                if best_of == 3:  # WC: all at higher seed
                    current_home, current_away = home, away
                elif best_of == 5:  # DS: 2-2-1
                    current_home, current_away = (home, away) if game_num in [1, 2, 5] else (away, home)
                else:  # LCS/WS: 2-3-2
                    current_home, current_away = (home, away) if game_num in [1, 2, 6, 7] else (away, home)
                
                game = PlayoffMatchup(
                    home=current_home,
                    away=current_away,
                    round_name=round_name,
                    game_num=game_num,
                    series_game_index=game_num
                )
                games_to_add.append(game)
            
            # Add games to schedule (one day per game for playoffs)
            for game in games_to_add:
                date_str = self.get_playoff_date(day_offset)
                day = ScheduleDay(date_str, [game])
                self._playoff_schedule.append(day)
                self._playoff_dates.append(date_str)
                day_offset += 1
            
            return games_to_add
        
        # Build Wild Card Round (2 days - 3 games each league)
        # AL: Seed 6 @ Seed 3 (WC1), Seed 5 @ Seed 4 (WC2)
        # Note: Using seeds as placeholders - actual winners determined after games
        add_series_games(al_seeds[2], al_seeds[5], 3, "AL Wild Card A")
        add_series_games(al_seeds[3], al_seeds[4], 3, "AL Wild Card B")
        # NL: Seed 6 @ Seed 3 (WC1), Seed 5 @ Seed 4 (WC2)
        add_series_games(nl_seeds[2], nl_seeds[5], 3, "NL Wild Card A")
        add_series_games(nl_seeds[3], nl_seeds[4], 3, "NL Wild Card B")
        
        # Division Series (4 series per league = 20 games max)
        # DS1: Seed 1 vs WC2 Winner, DS2: Seed 2 vs WC1 Winner
        # Using seed numbers as placeholders - will be replaced with actual winners
        add_series_games(al_seeds[0], al_seeds[4], 5, "ALDS A")  # Seed 1 vs WC2 (placeholder)
        add_series_games(al_seeds[1], al_seeds[5], 5, "ALDS B")  # Seed 2 vs WC1 (placeholder)
        add_series_games(nl_seeds[0], nl_seeds[4], 5, "NLDS A")
        add_series_games(nl_seeds[1], nl_seeds[5], 5, "NLDS B")
        
        # League Championship Series (2 series per league = 14 games max)
        add_series_games(al_seeds[0], al_seeds[1], 7, "ALCS")  # Placeholders
        add_series_games(nl_seeds[0], nl_seeds[1], 7, "NLCS")
        
        # World Series (7 games max)
        add_series_games("AL", "NL", 7, "World Series")
        
        logger.info(f"Built playoff schedule: {day_offset} days, {sum(len(d.games) for d in self._playoff_schedule)} games")


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


class PlayoffMatchup(GameMatchup):
    """Represents a single playoff game matchup."""
    
    def __init__(self, home: str, away: str, round_name: str, game_num: int, series_game_index: int):
        super().__init__(home, away, time=None)
        self.round_name = round_name        # "AL Wild Card A", "ALDS A", "NLCS", "World Series"
        self.game_num = game_num            # 1-7 (which game in series)
        self.series_game_index = series_game_index  # 1 of N games in round
        self.series_winner = None           # Set after series completes
        
    @property
    def is_off_day(self) -> bool:
        return False  # Playoff games are never off days
    
    def mark_series_complete(self, winner: str):
        """Mark the entire series as complete with winner."""
        self.series_winner = winner


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