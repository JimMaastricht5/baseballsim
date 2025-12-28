"""
--- Copyright Notice ---
Copyright (c) 2024 Jim Maastricht

UI-aware subclass of BaseballSeason that uses queue-based signals instead of printing.

This class overrides specific methods from BaseballSeason to emit queue-based signals
for UI updates while preserving all simulation logic.
"""

import pandas as pd
from typing import List, Optional
import queue
import threading

import bbseason
import bbgame
from ui.signals import SeasonSignals
from bblogger import logger


class UIBaseballSeason(bbseason.BaseballSeason):
    """
    BaseballSeason subclass that emits queue-based signals instead of printing to console.

    Overrides:
    - _process_and_print_game_results(): Emits game_completed and day_completed signals via queues
    - check_gm_assessments(): Emits gm_assessment_ready signal for followed teams via queues
    - print_standings(): Suppressed (standings emitted with day_completed)

    All other simulation logic remains unchanged from BaseballSeason.
    """

    def __init__(self, signals: SeasonSignals, *args, **kwargs):
        """
        Initialize UIBaseballSeason with signal emitter.

        Args:
            signals (SeasonSignals): Signal emitter for UI updates
            *args, **kwargs: Passed to BaseballSeason.__init__()
        """
        super().__init__(*args, **kwargs)
        self.signals = signals
        logger.info("UIBaseballSeason initialized with signal emitter")

    def _create_play_by_play_callback(self, away_team: str, home_team: str, day_num: int):
        """
        Create a callback function for emitting play-by-play during game simulation.

        Args:
            away_team (str): Away team abbreviation
            home_team (str): Home team abbreviation
            day_num (int): Current day number

        Returns:
            callable: Callback function that accepts text string
        """
        def callback(text: str):
            # Only emit if this involves a followed team
            if not self.team_to_follow or any(team in self.team_to_follow for team in [away_team, home_team]):
                self.signals.emit_play_by_play({
                    'away_team': away_team,
                    'home_team': home_team,
                    'text': text,
                    'day_num': day_num
                })
        return callback

    def _process_and_print_game_results(self, game_results: List[tuple], season_day_num: int = 0) -> None:
        """
        Override to emit signals instead of printing.

        Processes game results and emits:
        - game_completed signal for each followed team game (immediate)
        - day_completed signal with batch of non-followed games and standings

        Args:
            game_results: List of tuples (match_up, score, game_recap, away_box_score, home_box_score)
            season_day_num: Day number (0-indexed)
        """
        compact_summaries = []

        for match_up, score, game_recap, away_box_score, home_box_score in game_results:
            # Check if this was a followed game
            is_followed = any(team in self.team_to_follow for team in match_up) if self.team_to_follow else False

            # Build game data dict
            game_data = {
                'away_team': match_up[0],
                'home_team': match_up[1],
                'away_r': score[0],
                'home_r': score[1],
                'away_h': away_box_score.total_hits,
                'home_h': home_box_score.total_hits,
                'away_e': away_box_score.total_errors,
                'home_e': home_box_score.total_errors,
                'game_recap': game_recap if is_followed else '',  # Full recap for followed games (display in Play-by-Play tab)
                'day_num': season_day_num if is_followed else None
            }

            if is_followed:
                # Emit immediately for followed teams
                self.signals.emit_game_completed(game_data)
                logger.debug(f"Emitted game_completed for {match_up[0]} @ {match_up[1]}")
            else:
                # Collect for batch emission
                compact_summaries.append({
                    'away_team': match_up[0],
                    'home_team': match_up[1],
                    'away_r': score[0],
                    'home_r': score[1],
                    'away_h': away_box_score.total_hits,
                    'home_h': home_box_score.total_hits,
                    'away_e': away_box_score.total_errors,
                    'home_e': home_box_score.total_errors
                })

        # Emit batch update with standings
        standings_data = self.extract_standings()
        self.signals.emit_day_completed(compact_summaries, standings_data)
        logger.debug(f"Emitted day_completed with {len(compact_summaries)} games and standings")

    def check_gm_assessments(self, force: bool = False) -> None:
        """
        Override to emit signals for GM assessments of followed teams.

        Runs the standard GM assessment logic but emits gm_assessment_ready
        signal instead of printing to console.

        Args:
            force: If True, force assessments for all teams regardless of schedule
        """
        # Skip GM assessments after game 150 milestone (last assessment)
        if self.team_games_played:
            max_games = max(self.team_games_played.values())
            if max_games > 150:
                return

        # Calculate current Sim WAR values before assessments
        with self.baseball_data.semaphore:
            self.baseball_data.calculate_sim_war()

        # Determine which teams to print (or in our case, emit)
        teams_to_print = self._get_teams_to_print()

        for team_name, gm in self.gm_managers.items():
            games_played = self.team_games_played[team_name]

            # Check if assessment is due (or force if requested)
            if force or gm.should_assess(games_played):
                # Get team record
                record = self.team_win_loss[team_name]
                wins, losses = record[0], record[1]

                # Calculate games back
                games_back = self.calculate_games_back(team_name)

                # Determine if this team should be reported
                should_report = teams_to_print is None or team_name in teams_to_print

                # Run GM assessment (with should_print=False to suppress console output)
                logger.info(f"Running GM assessment for {team_name} after {games_played} games")
                assessment = gm.assess_roster(
                    baseball_stats=self.baseball_data,
                    team_record=(wins, losses),
                    games_back=games_back,
                    games_played=games_played,
                    should_print=False  # Suppress console output
                )

                # Emit signal if this is a followed team
                if should_report:
                    assessment_data = {
                        'team': team_name,
                        'games_played': games_played,
                        'wins': wins,
                        'losses': losses,
                        'games_back': games_back,
                        'assessment': assessment
                    }
                    self.signals.emit_gm_assessment_ready(assessment_data)
                    logger.info(f"Emitted gm_assessment_ready for {team_name}")

    def sim_day_threaded(self, season_day_num: int) -> None:
        """
        Override to emit day_started signal and inject play-by-play callbacks.

        Args:
            season_day_num (int): Day number (0-indexed)
        """
        # Emit day_started signal with schedule
        schedule_text = self.print_day_schedule(season_day_num)
        self.signals.emit_day_started(season_day_num, schedule_text)
        logger.debug(f"Emitted day_started for day {season_day_num + 1}")

        # Run game simulation (adapted from parent's sim_day_threaded)
        threads = []
        queues = []
        match_ups = []
        todays_games = self.schedule[season_day_num]
        teams_list = self.team_to_follow if len(self.team_to_follow) > 0 else None
        self.baseball_data.new_game_day(teams_to_follow=teams_list)

        for match_up in todays_games:
            if 'OFF DAY' not in match_up:
                # Create play-by-play callback for this game
                pbp_callback = self._create_play_by_play_callback(
                    match_up[0], match_up[1], season_day_num
                )

                game = bbgame.Game(
                    away_team_name=match_up[0],
                    home_team_name=match_up[1],
                    baseball_data=self.baseball_data,
                    game_num=season_day_num,
                    rotation_len=self.rotation_len,
                    print_lineup=self.print_lineup_b,
                    chatty=self.season_chatty,
                    print_box_score_b=self.print_box_score_b,
                    team_to_follow=self.team_to_follow,
                    interactive=self.interactive,
                    play_by_play_callback=pbp_callback  # NEW: Inject callback
                )
                q = queue.Queue()
                thread = threading.Thread(target=game.sim_game_threaded, args=(q,))
                threads.append(thread)
                queues.append(q)
                match_ups.append(match_up)
                thread.start()

        # Collect game results
        game_results = []
        for ii, thread in enumerate(threads):
            thread.join()
            (score, inning, win_loss_list, away_box_score, home_box_score, game_recap) = queues[ii].get()
            match_up = match_ups[ii]
            self.update_win_loss(away_team_name=match_up[0], home_team_name=match_up[1],
                                win_loss=win_loss_list)
            self.baseball_data.game_results_to_season(box_score_class=away_box_score)
            self.baseball_data.game_results_to_season(box_score_class=home_box_score)
            game_results.append((match_up, score, game_recap, away_box_score, home_box_score))

        # Process and emit signals (existing code)
        self._process_and_print_game_results(game_results, season_day_num)

        # Extract and emit injury update
        injuries = self.extract_injuries()
        self.signals.emit_injury_update(injuries)
        logger.debug(f"Emitted injury_update with {len(injuries)} injuries")

    def print_standings(self) -> None:
        """
        Override to suppress printing.

        Standings are emitted as part of day_completed signal,
        so we don't need to print them separately.
        """
        # Standings already emitted via day_completed signal
        pass

    def sim_start(self) -> None:
        """
        Override to suppress printing start info.

        The UI doesn't need this console output.
        """
        logger.info(f"Starting {self.new_season} season with {len(self.schedule)} games per team")
        # Suppress the print statements from parent
        pass

    def sim_end(self) -> None:
        """
        Override to suppress printing end info.

        The UI will show its own completion message.
        """
        logger.info(f"Ending {self.new_season} season")
        # Update season stats
        self.baseball_data.update_season_stats()
        # Suppress the print statements from parent
        pass

    def extract_standings(self) -> dict:
        """
        Extract standings data from team_win_loss dictionary, separated by league.

        Replicates the logic from print_standings() but returns data
        instead of printing, with separate AL and NL standings.

        Returns:
            dict: Standings data with keys:
                - al (dict): AL standings with 'teams', 'wins', 'losses', 'pct', 'gb'
                - nl (dict): NL standings with 'teams', 'wins', 'losses', 'pct', 'gb'
        """
        teaml, winl, lossl, leaguel = [], [], [], []

        # Get team-to-league mapping from baseball_data
        team_league_map = {}
        if hasattr(self.baseball_data, 'batting_data') and 'League' in self.baseball_data.batting_data.columns:
            # Create a mapping of team to league
            team_league_df = self.baseball_data.batting_data[['Team', 'League']].drop_duplicates()
            team_league_map = dict(zip(team_league_df['Team'], team_league_df['League']))

        for team in self.team_win_loss:
            if team != 'OFF DAY':
                win_loss = self.team_win_loss[team]
                teaml.append(team)
                winl.append(win_loss[0])
                lossl.append(win_loss[1])
                # Get league from mapping, default to 'AL' if not found
                leaguel.append(team_league_map.get(team, 'AL'))

        # Create DataFrame and calculate stats
        df = pd.DataFrame({'Team': teaml, 'W': winl, 'L': lossl, 'League': leaguel})
        df['Pct'] = df['W'] / (df['W'] + df['L'])
        df['Pct'] = df['Pct'].fillna(0.0)  # Handle 0-0 teams

        # Separate by league and calculate GB separately
        al_df = df[df['League'] == 'AL'].copy()
        nl_df = df[df['League'] == 'NL'].copy()

        def calculate_gb(league_df):
            """Calculate games back for a league."""
            if len(league_df) == 0:
                return league_df

            # Sort by wins descending
            league_df = league_df.sort_values('W', ascending=False).reset_index(drop=True)

            # Calculate Games Back from league leader
            max_wins = league_df['W'].iloc[0]
            leader_losses = league_df['L'].iloc[0]
            league_df['GB'] = ((max_wins - league_df['W']) + (league_df['L'] - leader_losses)) / 2.0
            league_df['GB'] = league_df['GB'].apply(lambda x: '-' if x == 0 else f'{x:.1f}')

            return league_df

        al_df = calculate_gb(al_df)
        nl_df = calculate_gb(nl_df)

        return {
            'al': {
                'teams': al_df['Team'].tolist(),
                'wins': al_df['W'].tolist(),
                'losses': al_df['L'].tolist(),
                'pct': al_df['Pct'].tolist(),
                'gb': al_df['GB'].tolist()
            },
            'nl': {
                'teams': nl_df['Team'].tolist(),
                'wins': nl_df['W'].tolist(),
                'losses': nl_df['L'].tolist(),
                'pct': nl_df['Pct'].tolist(),
                'gb': nl_df['GB'].tolist()
            }
        }

    def extract_injuries(self) -> list:
        """
        Extract all injured players from current season data.

        Reads injury information from baseball_data.new_season_batting_data
        and new_season_pitching_data DataFrames.

        Returns:
            list: List of injury dicts with keys:
                - player (str): Player name
                - team (str): Team abbreviation
                - position (str): Position (e.g., '1B', 'P')
                - injury (str): Injury description
                - days_remaining (int): Estimated days until return
                - status (str): 'IL' (≥10 days) or 'Day-to-Day' (<10 days)
        """
        injuries = []

        # Check batters
        try:
            injured_batters = self.baseball_data.new_season_batting_data[
                self.baseball_data.new_season_batting_data['Injured Days'] > 0
            ]

            for idx, row in injured_batters.iterrows():
                days = int(row['Injured Days'])
                injuries.append({
                    'player': row['Player'],
                    'team': row['Team'],
                    'position': row.get('Pos', 'Unknown'),
                    'injury': row.get('Injury Description', 'Undisclosed'),
                    'days_remaining': days,
                    'status': 'IL' if days >= 10 else 'Day-to-Day'
                })
        except Exception as e:
            logger.warning(f"Error extracting batter injuries: {e}")

        # Check pitchers
        try:
            injured_pitchers = self.baseball_data.new_season_pitching_data[
                self.baseball_data.new_season_pitching_data['Injured Days'] > 0
            ]

            for idx, row in injured_pitchers.iterrows():
                days = int(row['Injured Days'])
                injuries.append({
                    'player': row['Player'],
                    'team': row['Team'],
                    'position': 'P',
                    'injury': row.get('Injury Description', 'Undisclosed'),
                    'days_remaining': days,
                    'status': 'IL' if days >= 10 else 'Day-to-Day'
                })
        except Exception as e:
            logger.warning(f"Error extracting pitcher injuries: {e}")

        logger.debug(f"Extracted {len(injuries)} injuries")
        return injuries

    def print_day_schedule(self, day: int) -> str:
        """
        Override to return schedule text instead of printing.

        This method is called by sim_day_threaded() to print the schedule,
        but we want to capture the text for signaling instead.

        Args:
            day (int): Day number (0-indexed)

        Returns:
            str: Formatted schedule text
        """
        # Call parent to get the formatted text
        # Note: The parent method prints, so we need to suppress that
        # For now, we'll replicate the logic to avoid printing
        todays_games = self.schedule[day]
        schedule_lines = []

        for match_up in todays_games:
            if 'OFF DAY' in match_up:
                off_team = match_up[0] if match_up[0] != 'OFF DAY' else match_up[1]
                schedule_lines.append(f"{off_team} has an OFF DAY")
            else:
                schedule_lines.append(f"{match_up[0]} @ {match_up[1]}")

        return f"Day {day + 1}: " + ", ".join(schedule_lines)
