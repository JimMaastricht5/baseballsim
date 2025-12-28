"""
--- Copyright Notice ---
Copyright (c) 2024 Jim Maastricht

--- File Context and Purpose ---
Baseball statistics management and game state tracking.
This module provides the core statistics management system for the baseball simulator,
handling loading of preprocessed player data, calculating derived statistics (AVG, OBP,
ERA, WHIP), managing player conditions (injuries, fatigue, hot/cold streaks), and
accumulating game results into season statistics. Thread-safe for multi-game simulations.

Key Features:
- Loads both aggregated (career) and new season player statistics
- Caches league-wide statistics for 2-3x performance improvement
- Manages dynamic player state (condition, injuries, streaks)
- Thread-safe stats updates via semaphore locking
- Syncs condition and injury data between historical and new season stats
- Calculates all derived baseball statistics (AVG, OBP, SLG, ERA, WHIP, etc.)

Data Structure:
- pitching_data: Aggregated career pitching stats (indexed by Hashcode)
- batting_data: Aggregated career batting stats (indexed by Hashcode)
- new_season_pitching_data: Current season pitching stats
- new_season_batting_data: Current season batting stats

Contact: JimMaastricht5@gmail.com
"""
import ast
import pandas as pd
import numpy as np
from numpy import ndarray
from pandas.core.frame import DataFrame
from pandas.core.series import Series
from typing import List, Optional, Union
import threading
import re
import bbinjuries
from bblogger import logger

# PERFORMANCE: Pre-compile regex patterns for ~2-5x speedup in safe_literal_eval
_LIST_PATTERN = re.compile(r"\[([^\]]+)\]")

# Dynamic state fields that need to be synced from new_season data to gameplay data
DYNAMIC_FIELDS = ['Condition', 'Injured Days', 'Injury Description',
                  'Injury_Perf_Adj', 'Injury_Rate_Adj', 'Streak_Adjustment']


class BaseballStats:
    def __init__(self, load_seasons: List[int], new_season: int, include_leagues: list = None,
                 load_batter_file: str = 'aggr-stats-pp-Batting.csv',
                 load_pitcher_file: str = 'aggr-stats-pp-Pitching.csv',
                 suppress_console_output: bool = False) -> None:
        """
        :param load_seasons: list of seasons to load, each season is an integer year
        :param new_season: integer value of year for new season
        :param include_leagues: list of leagues to include in season
        :param load_batter_file: file name of the batting stats, year will be added as a prefix
        :param load_pitcher_file: file name of the pitching stats, year will be added as a prefix
        :param suppress_console_output: if True, suppress disabled list and hot/cold list console output
        """
        self.suppress_console_output = suppress_console_output
        self.semaphore = threading.Semaphore(1)  # one thread can update games stats at a time
        # PERFORMANCE: Create RNG instance once, reuse for ~29x speedup
        self._rng_instance = np.random.default_rng()
        self.rnd = lambda: self._rng_instance.uniform(low=0.0, high=1.001)
        # self.create_hash = lambda text: int(hashlib.sha256(text.encode('utf-8')).hexdigest()[:5], 16)

        self.numeric_bcols = ['G', 'AB', 'R', 'H', '2B', '3B', 'HR', 'RBI', 'SB', 'CS', 'BB', 'SO', 'SH', 'SF',
                              'HBP', 'Condition']  # these cols will get added to running season total
        self.numeric_bcols_to_print = ['G', 'AB', 'R', 'H', '2B', '3B', 'HR', 'RBI', 'SB', 'CS', 'BB', 'SO', 'SH', 'SF',
                                       'HBP', 'AVG', 'OBP', 'SLG', 'OPS', 'Sim_WAR']
        self.numeric_pcols = ['G', 'GS', 'CG', 'SHO', 'IP', 'AB', 'H', '2B', '3B', 'HR', 'ER', 'SO', 'BB', 'W', 'L',
                              'SV', 'BS', 'HLD', 'Total_Outs', 'Condition']  # cols will add to running season total
        self.numeric_pcols_to_print = ['G', 'GS', 'CG', 'SHO', 'IP', 'H', '2B', '3B', 'HR', 'ER', 'SO', 'BB',
                                       'W', 'L', 'SV', 'BS', 'HLD', 'ERA', 'WHIP', 'AVG', 'OBP', 'SLG', 'OPS', 'Sim_WAR']
        self.pcols_to_print = ['Player', 'League', 'Team', 'Age', 'G', 'GS', 'CG', 'SHO', 'IP', 'H', '2B', '3B', 'ER',
                               'SO', 'BB', 'HR', 'W', 'L', 'SV', 'BS', 'HLD', 'ERA', 'WHIP', 'AVG', 'OBP', 'SLG', 'OPS',
                               'Sim_WAR', 'Status', 'Estimated Days Remaining', 'Injury Description', 'Streak Status', 'Condition']
        self.bcols_to_print = ['Player', 'League', 'Team', 'Pos', 'Age', 'G', 'AB', 'R', 'H', '2B', '3B', 'HR', 'RBI',
                               'SB', 'CS', 'BB', 'SO', 'SH', 'SF', 'HBP', 'AVG', 'OBP', 'SLG',
                               'OPS', 'Sim_WAR', 'Status', 'Estimated Days Remaining', 'Injury Description', 'Streak Status', 'Condition']
        self.include_leagues = include_leagues
        logger.debug("Initializing BaseballStats with seasons: {}", load_seasons)
        self.load_seasons = [load_seasons] if not isinstance(load_seasons, list) else load_seasons
        self.new_season = new_season
        self.pitching_data = None
        self.batting_data = None
        self.new_season_pitching_data = None
        self.new_season_batting_data = None
        self.get_seasons(load_batter_file, load_pitcher_file)  # get existing data file
        self.get_all_team_names = lambda: self.batting_data.Team.unique()
        self.get_all_league_names = lambda: self.batting_data.League.unique()
        self.get_all_city_names = lambda: self.batting_data.City.unique()
        self.get_all_team_city_names = lambda: None if len(self.get_all_city_names()) <= 1 \
            else dict(zip(self.get_all_team_names(), self.get_all_city_names()))

        # output format for df print
        pd.set_option('display.max_rows', None)  # Show all rows
        pd.set_option('display.max_columns', None)  # Show all columns
        pd.set_option('display.width', None)  # Adjust the display width
        pd.set_option('display.precision', 3)  # Set the number of decimal places
        pd.set_option('future.no_silent_downcasting', True)  # Opt-in to future pandas behavior

        # ***************** game to game stats and settings for injury and rest
        # condition and injury odds
        # 64% of injuries are to pitchers (188 of 684); 26% position players (87 of 634)
        # 27.5% of pitchers w > 5 in will spend time on IL per season (188 out of 684)
        # 26.3% of pitching injuries affect the throwing elbow results in avg of 74 days lost
        # position player (non-pitcher) longevitiy: https://www.nytimes.com/2007/07/15/sports/baseball/15careers.html
        self.condition_change_per_day = 15  # improve with rest, mid-point of normal dist for recovery
        self.fatigue_start_perc = 70  # 85% of way to avg max is where fatigue starts, adjust factor to inc outing lgth
        self.fatigue_rate = .001  # at 85% of avg max pitchers have a .014 increase in OBP.  using .001 as proxy
        self.fatigue_pitching_change_limit = 5  # change pitcher at # or below out of 100
        self.fatigue_unavailable = 33  # condition must be 33 or higher for a pitcher or pos player to be available
        self.pitching_injury_rate = .275  # 27.5 out of 100 players injured per season-> per game
        self.pitching_injury_avg_len = 32  # according to mlb avg len is 74 but that cant be a normal dist
        self.batting_injury_rate = .137  # 2022 87 out of 634 injured per season .137 avg age 27
        self.injury_odds_adjustment_for_age = .000328  # 3.28% inc injury per season above 20 w/ .90 survival
        self.batting_injury_avg_len = 15  # made this up
        # adjust performance is this is a substantial injury, perf decreases by 0 to 20%; studies indicated -10 to -20%
        self.injury_perf_f = lambda injury_days, injury_perf_adj: (
                injury_perf_adj - self._rng_instance.uniform(0, 0.2)) if injury_days >= 30 else injury_perf_adj
        # PERFORMANCE: Return scalar directly instead of size=1 array with [0] indexing
        self.rnd_condition_chg = lambda age: abs(self._rng_instance.normal(
            loc=(self.condition_change_per_day - (age - 20) / 100 * self.condition_change_per_day),
            scale=self.condition_change_per_day / 3))
        self.rnd_p_inj = lambda age: abs(self._rng_instance.normal(
            loc=self.pitching_injury_avg_len,
            scale=self.pitching_injury_avg_len / 2))
        self.rnd_b_inj = lambda age: abs(self._rng_instance.normal(
            loc=self.batting_injury_avg_len,
            scale=self.batting_injury_avg_len / 2))

        # Initialize the injury system
        self.injury_system = bbinjuries.InjuryType()

        # PERFORMANCE: Cache league totals for at-bat calculations (avoids recalculating 162 times per season)
        self.league_batting_totals = team_batting_totals(self.batting_data)
        self.league_pitching_totals = team_pitching_totals(self.pitching_data)

        # Cache additional league-wide statistics used in SimAB
        batting_data_sum = self.batting_data[['H', 'BB', 'HBP']].sum()
        self.league_batting_total_ob = batting_data_sum['H'] + batting_data_sum['BB'] + batting_data_sum['HBP']
        self.league_pitching_total_ob = self.pitching_data[['H', 'BB']].sum().sum()
        self.league_total_outs = self.batting_data['AB'].sum() - batting_data_sum.sum()
        self.league_k_rate_per_ab = self.batting_data['SO'].sum() / self.league_total_outs

        logger.debug("Cached league totals and statistics for performance optimization")
        return

    @staticmethod
    def add_missing_cols(df):
        # add missing data for random vs. historical
        if 'City' not in df.columns:
            df['City'] = df['Team']
            df['Mascot'] = ''
        return df

    def get_batting_data(self, team_name: Optional[str] = None, prior_season: bool = True) -> DataFrame:
        """
        loads data for batters
        :param team_name: single team name is optional, alt is full league
        :param prior_season: is this data from a prior season or the current one?
        :return: dataframe of seasons data
        """
        if team_name is None:
            df = self.batting_data if prior_season else self.new_season_batting_data
        else:
            df_new = self.new_season_batting_data[self.new_season_batting_data['Team'] == team_name]
            df_cur = self.batting_data[self.batting_data.index.isin(df_new.index)]
            df = df_cur if prior_season else df_new
        logger.debug('Getting batting data for team: {}', team_name)
        logger.debug('New season batting data sample:\n{}', self.new_season_batting_data.head(5).to_string())
        logger.debug('Available teams: {}', self.new_season_batting_data['Team'].unique())
        logger.debug('Retrieved batting data sample:\n{}', df.head(5).to_string())
        df = team_batting_stats(df, filter_stats=False)
        df = self.add_missing_cols(df)

        return df

    def get_pitching_data(self, team_name: Optional[str] = None, prior_season: bool = True) -> DataFrame:
        """
        loads data for pitchers
        :param team_name: single team name is optional, alt is full league
        :param prior_season: is this data from a prior season or the current one?
        :return: df with seasons data
        """
        if team_name is None:
            df = self.pitching_data if prior_season else self.new_season_pitching_data
        else:
            df_new = self.new_season_pitching_data[self.new_season_pitching_data['Team'] == team_name]
            df_cur = self.pitching_data[self.pitching_data.index.isin(df_new.index)]
            df = df_cur if prior_season else df_new
        # Don't filter stats - include pitchers with 0 IP (important for roster display at season start)
        df = team_pitching_stats(df, filter_stats=False)
        df = self.add_missing_cols(df)
        return df

    def get_seasons(self, batter_file: str, pitcher_file: str) -> None:
        """
        loads a full season of data for pitching and hitting and casts cols to proper values, loads values into
        internal df to class
        :param batter_file: batter file name
        :param pitcher_file: pitcher file name
        :return: None
        """
        # New season files don't have 'aggr-' prefix, so remove it if present
        new_pitcher_file = 'New-Season-' + pitcher_file.replace('aggr-', '')
        new_batter_file = 'New-Season-' + batter_file.replace('aggr-', '')
        seasons_str = " ".join(str(season) for season in self.load_seasons)
        try:
            if self.pitching_data is None or self.batting_data is None:  # need to read data... else skip as cached
                self.pitching_data = self.add_missing_cols(
                    pd.read_csv(f'{seasons_str} {pitcher_file}', index_col='Hashcode'))
                self.batting_data = self.add_missing_cols(
                    pd.read_csv(f'{seasons_str} {batter_file}', index_col='Hashcode'))

            if self.new_season_pitching_data is None or self.new_season_batting_data is None:
                self.new_season_pitching_data = self.add_missing_cols(pd.read_csv(str(self.new_season) +
                                                                                  f" {new_pitcher_file}", index_col='Hashcode'))
                self.new_season_batting_data = self.add_missing_cols(pd.read_csv(str(self.new_season) +
                                                                                 f" {new_batter_file}", index_col='Hashcode'))
        except FileNotFoundError as e:
            logger.error("File not found in get_seasons(): {}", e)
            logger.error("bbstats.py, get_seasons(), file was not found.")
            logger.error('Looking for files with pattern: "{} {}" and "{} {}"',
                         seasons_str, pitcher_file, seasons_str, batter_file)
            logger.error('Or new season files: "{} {}" and "{} {}"',
                         self.new_season, new_pitcher_file, self.new_season, new_batter_file)
            logger.error('Correct spelling or try running bbstats_preprocess.py to setup the data')
            exit(1)  # stop the program

        # limit the league if include leagues is not none and at least one league is in the list
        logger.debug('In get_seasons')
        logger.debug('Prior season pitching data:\n{}', self.pitching_data.head(5).to_string())
        logger.debug('New season pitching data:\n{}', self.new_season_pitching_data.head(5).to_string())
        if self.include_leagues is not None and any(self.pitching_data['League'].isin(self.include_leagues)):
            self.pitching_data = self.pitching_data[self.pitching_data['League'].isin(self.include_leagues)]
            self.batting_data = self.batting_data[self.batting_data['League'].isin(self.include_leagues)]

        # cast cols to float, may not be needed, best to be certain
        pcols_to_convert = ['Condition', 'IP', 'ERA', 'WHIP', 'OBP', 'AVG_faced', 'Game_Fatigue_Factor',
                            'Injury_Rate_Adj', 'Injury_Perf_Adj', 'Streak_Adjustment']
        bcols_to_convert = ['Condition', 'Injury_Rate_Adj', 'Injury_Perf_Adj', 'Streak_Adjustment']
        self.pitching_data[pcols_to_convert] = self.pitching_data[pcols_to_convert].astype(float)
        self.batting_data[bcols_to_convert] = self.batting_data[bcols_to_convert].astype(float)
        self.new_season_pitching_data[pcols_to_convert] = self.new_season_pitching_data[pcols_to_convert].astype(float)
        self.new_season_batting_data[bcols_to_convert] = self.new_season_batting_data[bcols_to_convert].astype(float)

        # Add columns if they don't exist using helper method
        self._ensure_column_exists([self.pitching_data, self.new_season_pitching_data], 'Injury Description', "")
        self._ensure_column_exists([self.batting_data, self.new_season_batting_data], 'Injury Description', "")
        self._ensure_column_exists([self.pitching_data, self.new_season_pitching_data], 'Sim_WAR', 0.0)
        self._ensure_column_exists([self.batting_data, self.new_season_batting_data], 'Sim_WAR', 0.0)

        return

    def _ensure_column_exists(self, df_list: List[DataFrame], column_name: str, default_value) -> None:
        """
        Helper method to ensure a column exists in multiple dataframes with a default value
        :param df_list: List of dataframes to check/update
        :param column_name: Name of the column to ensure exists
        :param default_value: Default value to use if column doesn't exist
        :return: None
        """
        for df in df_list:
            if column_name not in df.columns:
                df[column_name] = default_value

    def _sync_fields(self, source_df: DataFrame, target_df: DataFrame, field_list: List[str]) -> None:
        """
        Helper method to sync fields from source to target dataframe
        :param source_df: Source dataframe to copy from
        :param target_df: Target dataframe to copy to
        :param field_list: List of field names to sync
        :return: None (modifies target_df in place)
        """
        for field in field_list:
            if field in source_df.columns and field in target_df.columns:
                target_df.loc[:, field] = source_df.loc[:, field].astype(target_df[field].dtype)

    def sync_dynamic_fields(self, target_pitching_df: DataFrame, target_batting_df: DataFrame) -> None:
        """
        Synchronize dynamic state fields from new_season data to target dataframes.
        Dynamic fields include: condition, injuries, streaks - anything that changes during the season.

        :param target_pitching_df: DataFrame to update with current pitching dynamic state
        :param target_batting_df: DataFrame to update with current batting dynamic state
        :return: None (modifies dataframes in place)
        """
        # Copy dynamic fields for pitchers
        self._sync_fields(self.new_season_pitching_data, target_pitching_df, DYNAMIC_FIELDS)

        # Copy dynamic fields for batters
        self._sync_fields(self.new_season_batting_data, target_batting_df, DYNAMIC_FIELDS)

        return

    def game_results_to_season(self, box_score_class) -> None:
        """
        adds the game results to a season df to accumulate stats, thread safe for shared df across game threads
        VECTORIZED: ~50-200x faster than iterrows approach (called 324 times per season)

        :param box_score_class: box score from game to add to season stats
        :return: None
        """
        with self.semaphore:
            batting_box_score = box_score_class.get_batter_game_stats()
            pitching_box_score = box_score_class.get_pitcher_game_stats()

            # VECTORIZED: Update all batters who played in the game at once (no loop!)
            if len(batting_box_score) > 0:
                batter_indices = batting_box_score.index

                # Add game stats to season accumulation (all players simultaneously)
                self.new_season_batting_data.loc[batter_indices, self.numeric_bcols] += \
                    batting_box_score.loc[batter_indices, self.numeric_bcols]

                # Update condition and injury status (all players simultaneously)
                self.new_season_batting_data.loc[batter_indices, 'Condition'] = \
                    batting_box_score.loc[batter_indices, 'Condition']
                self.new_season_batting_data.loc[batter_indices, 'Injured Days'] = \
                    batting_box_score.loc[batter_indices, 'Injured Days'].astype('int64')

            # VECTORIZED: Update all pitchers who played in the game at once (no loop!)
            if len(pitching_box_score) > 0:
                pitcher_indices = pitching_box_score.index

                # Add game stats to season accumulation (all players simultaneously)
                self.new_season_pitching_data.loc[pitcher_indices, self.numeric_pcols] += \
                    pitching_box_score.loc[pitcher_indices, self.numeric_pcols]

                # Update condition and injury status (all players simultaneously)
                self.new_season_pitching_data.loc[pitcher_indices, 'Condition'] = \
                    pitching_box_score.loc[pitcher_indices, 'Condition']
                self.new_season_pitching_data.loc[pitcher_indices, 'Injured Days'] = \
                    pitching_box_score.loc[pitcher_indices, 'Injured Days'].astype('int64')
        return

    def calculate_per_game_injury_odds(self, age: int, injury_rate: float, injury_rate_adjustment: float) -> float:
        """ Calculates the per-game probability of injury based on a season-long rate adjusted for age and 162-games
        Formula (P_game = 1 - (1 - P_season) ** (1 / 162))
        Args:
            age: The player's current age.
            injury_rate: the injury rate for the position either pitcher or batter
            injury_rate_adjustment: the injury rate adjustment is an increase in the odds of injury based on past injury
        Returns: The probability of injury for a single game.
        """
        # 1. Calculate the season-long injury rate, adjusted for age
        age_adjustment_term = (age - 20) * self.injury_odds_adjustment_for_age
        season_long_injury_rate = injury_rate + age_adjustment_term + injury_rate_adjustment
        # 2. Convert the season-long probability to a per-game probability
        # 1 - (Probability of NOT getting hurt in the season) ^ (1/162)
        probability_of_not_getting_hurt_season = 1 - season_long_injury_rate
        per_game_odds = 1 - (probability_of_not_getting_hurt_season) ** (1 / 162)
        return per_game_odds

    def is_injured(self) -> None:
        """
        determine if a pitcher or hitter is injured and severity.  older players get injured more often
        add that data to the active seasons df and assign appropriate injury descriptions
        It is assumed that once a player has a substantial injury that player is 10-20% more likely
        to be injured again.  Also there is a cumulative downward effect on performance

        VECTORIZED: Uses vectorized operations for ~10-50x speedup
        :return: None
        """
        # Process pitcher injuries - VECTORIZED
        healthy_pitchers = self.new_season_pitching_data['Injured Days'] == 0
        injured_pitchers = ~healthy_pitchers

        # Generate random rolls for all healthy pitchers at once
        n_healthy_p = healthy_pitchers.sum()
        if n_healthy_p > 0:
            random_rolls = np.random.uniform(0, 1, n_healthy_p)

            # Calculate injury odds for all healthy pitchers vectorized
            healthy_df = self.new_season_pitching_data[healthy_pitchers]
            injury_odds = healthy_df.apply(
                lambda row: self.calculate_per_game_injury_odds(row['Age'], self.pitching_injury_rate, row['Injury_Rate_Adj']),
                axis=1
            ).values

            # Determine which players get injured
            new_injuries = random_rolls <= injury_odds
            newly_injured_indices = healthy_df.index[new_injuries]

            # Process each newly injured player (still need individual processing for injury descriptions)
            for idx in newly_injured_indices:
                row = self.new_season_pitching_data.loc[idx]
                injury_days = int(self.rnd_p_inj(row['Age']))
                injury_rate_adjustment = (self._rng_instance.uniform(low=0.1, high=0.2) + row['Injury_Rate_Adj']
                                         if injury_days >= 30 else row['Injury_Rate_Adj'])
                injury_perf_adj = self.injury_perf_f(injury_days, row['Injury_Perf_Adj'])
                injury_desc = self.injury_system.get_pitcher_injury(injury_days)
                refined_injury_days = self.injury_system.get_injury_days_from_description(injury_desc, is_pitcher=True)

                self.new_season_pitching_data.at[idx, 'Injured Days'] = refined_injury_days
                self.new_season_pitching_data.at[idx, 'Injury Description'] = injury_desc
                self.new_season_pitching_data.at[idx, 'Injury_Rate_Adj'] = injury_rate_adjustment
                self.new_season_pitching_data.at[idx, 'Injury_Perf_Adj'] = injury_perf_adj

        # Vectorized: Decrement all currently injured pitchers at once
        if injured_pitchers.sum() > 0:
            self.new_season_pitching_data.loc[injured_pitchers, 'Injured Days'] -= 1
            # Clear descriptions for players who just recovered (Injured Days now 0)
            recovered = self.new_season_pitching_data['Injured Days'] == 0
            self.new_season_pitching_data.loc[recovered, 'Injury Description'] = ""

        # Process batter injuries - VECTORIZED (same logic)
        healthy_batters = self.new_season_batting_data['Injured Days'] == 0
        injured_batters = ~healthy_batters

        n_healthy_b = healthy_batters.sum()
        if n_healthy_b > 0:
            random_rolls = np.random.uniform(0, 1, n_healthy_b)
            healthy_df = self.new_season_batting_data[healthy_batters]
            injury_odds = healthy_df.apply(
                lambda row: self.calculate_per_game_injury_odds(row['Age'], self.batting_injury_rate, row['Injury_Rate_Adj']),
                axis=1
            ).values

            new_injuries = random_rolls <= injury_odds
            newly_injured_indices = healthy_df.index[new_injuries]

            for idx in newly_injured_indices:
                row = self.new_season_batting_data.loc[idx]
                injury_days = int(self.rnd_b_inj(row['Age']))
                injury_rate_adjustment = (self._rng_instance.uniform(low=0.1, high=0.2) + row['Injury_Rate_Adj']
                                         if injury_days >= 30 else row['Injury_Rate_Adj'])
                injury_perf_adj = self.injury_perf_f(injury_days, row['Injury_Perf_Adj'])
                injury_desc = self.injury_system.get_batter_injury(injury_days)
                refined_injury_days = self.injury_system.get_injury_days_from_description(injury_desc, is_pitcher=False)

                self.new_season_batting_data.at[idx, 'Injured Days'] = refined_injury_days
                self.new_season_batting_data.at[idx, 'Injury Description'] = injury_desc
                self.new_season_batting_data.at[idx, 'Injury_Rate_Adj'] = injury_rate_adjustment
                self.new_season_batting_data.at[idx, 'Injury_Perf_Adj'] = injury_perf_adj

        if injured_batters.sum() > 0:
            self.new_season_batting_data.loc[injured_batters, 'Injured Days'] -= 1
            recovered = self.new_season_batting_data['Injured Days'] == 0
            self.new_season_batting_data.loc[recovered, 'Injury Description'] = ""

        # Update status - vectorize using np.where for better performance
        # Vectorized status updates (avoid apply with lambda)
        def get_status_vectorized(df, is_pitcher):
            """Vectorized status calculation"""
            injured_days = df['Injured Days'].values
            injury_desc = df['Injury Description'].values

            # Check for concussions vectorized
            is_concussion = np.array([self.injury_system.is_concussion(desc) for desc in injury_desc])

            # Build status array
            status = np.where(injured_days == 0, 'Active',
                     np.where(is_concussion, '7-Day IL',
                     np.where(injured_days >= 60, '60-Day IL',
                     np.where(is_pitcher, '15-Day IL', '10-Day IL'))))
            return status

        self.new_season_pitching_data['Status'] = get_status_vectorized(self.new_season_pitching_data, True)
        self.new_season_batting_data['Status'] = get_status_vectorized(self.new_season_batting_data, False)

        # Print the disabled lists in compact format (only if not suppressed)
        if not self.suppress_console_output:
            print(f'Season Disabled Lists:')

            # Helper function to print injuries by IL type
            def print_injuries_by_il_type(df, player_type='Pitchers'):
                if df[df["Injured Days"] > 0].shape[0] == 0:
                    return

                injured_df = df[df["Injured Days"] > 0].copy()
                print(f'\n{player_type}:')

                # Group by Status (IL type)
                for il_type in ['60-Day IL', '15-Day IL', '10-Day IL', '7-Day IL']:
                    il_group = injured_df[injured_df['Status'] == il_type]
                    if il_group.shape[0] > 0:
                        count = il_group.shape[0]
                        # Build compact list: Player(TEAM) - Injury
                        injury_list = []
                        for idx, row in il_group.iterrows():
                            player = row['Player']
                            team = row['Team']
                            injury = row['Injury Description']
                            injury_list.append(f"{player}({team}) - {injury}")

                        # Print in compact format
                        print(f"  {il_type} ({count}): {', '.join(injury_list)}")

            # Print pitchers and batters
            print_injuries_by_il_type(self.new_season_pitching_data, 'Pitchers')
            print_injuries_by_il_type(self.new_season_batting_data, 'Batters')
            print()  # Add blank line after injury lists

        return

    def print_hot_cold_players(self, teams_to_follow: Optional[List[str]] = None) -> None:
        """
        Print list of players with hot or cold streaks (similar to injury list)
        Only shows players with streaks >= +2.5% (Hot) or <= -2.5% (Cold)
        :param teams_to_follow: List of team names to show, None means don't print anything
        :return: None
        """
        # Only print if following specific teams and console output is not suppressed
        if not teams_to_follow or self.suppress_console_output:
            return

        # Filter for hot/cold players only (not Normal)
        hot_pitchers = self.new_season_pitching_data[
            self.new_season_pitching_data['Streak_Adjustment'] >= 0.025
        ].copy()
        cold_pitchers = self.new_season_pitching_data[
            self.new_season_pitching_data['Streak_Adjustment'] <= -0.025
        ].copy()
        hot_batters = self.new_season_batting_data[
            self.new_season_batting_data['Streak_Adjustment'] >= 0.025
        ].copy()
        cold_batters = self.new_season_batting_data[
            self.new_season_batting_data['Streak_Adjustment'] <= -0.025
        ].copy()

        # Filter by teams to follow
        hot_pitchers = hot_pitchers[hot_pitchers['Team'].isin(teams_to_follow)]
        cold_pitchers = cold_pitchers[cold_pitchers['Team'].isin(teams_to_follow)]
        hot_batters = hot_batters[hot_batters['Team'].isin(teams_to_follow)]
        cold_batters = cold_batters[cold_batters['Team'].isin(teams_to_follow)]

        # Only print if there are hot/cold players
        if (hot_pitchers.shape[0] > 0 or hot_batters.shape[0] > 0 or
            cold_pitchers.shape[0] > 0 or cold_batters.shape[0] > 0):

            # Print Hot players
            if hot_pitchers.shape[0] > 0 or hot_batters.shape[0] > 0:
                print('Hot:')
                self._print_streak_players(hot_pitchers, hot_batters)

            # Print Cold players
            if cold_pitchers.shape[0] > 0 or cold_batters.shape[0] > 0:
                print('Cold:')
                self._print_streak_players(cold_pitchers, cold_batters)
        return

    def _print_streak_players(self, pitchers: DataFrame, batters: DataFrame) -> None:
        """
        Helper method to print hot or cold players in consistent format (one line)
        :param pitchers: DataFrame of pitchers with streaks
        :param batters: DataFrame of batters with streaks
        :return: None
        """
        players = []

        # Add pitchers
        if pitchers.shape[0] > 0:
            for _, row in pitchers.iterrows():
                player_name = row['Player']
                obp_change = f"{row['Streak_Adjustment']:+.1%}"
                players.append(f"{player_name} (P) {obp_change}")

        # Add batters
        if batters.shape[0] > 0:
            for _, row in batters.iterrows():
                player_name = row['Player']
                if 'Pos' in row and row['Pos']:
                    pos = format_positions(row['Pos'])
                else:
                    pos = ''
                obp_change = f"{row['Streak_Adjustment']:+.1%}"
                players.append(f"{player_name} ({pos}) {obp_change}")

        # Print all players on one line
        if players:
            print(', '.join(players) + '\n')

    def update_streaks(self) -> None:
        """
        Update streak adjustments for all non-injured players.
        Streaks slowly drift toward 0 (regression to mean) with small random changes.
        Only updates players who are not injured (Injured Days == 0).
        Injured players' streaks are frozen until they return to action.

        Logic:
        - Small random walk: ±0.4% to ±1.2% per game (mean 0%, std 0.004, reduced from 0.005)
        - Regression to mean: Pull streak toward 0 by 4% of current value (increased from 2%)
        - Bounds checking: Enforce -10% to +10% limits

        VECTORIZED: Processes all active players at once for ~20-100x speedup
        :return: None
        """
        # Update pitchers (vectorized - only those not injured)
        active_pitchers = self.new_season_pitching_data['Injured Days'] == 0
        n_active_pitchers = active_pitchers.sum()

        if n_active_pitchers > 0:
            # Get current streaks for active pitchers
            current_streaks = self.new_season_pitching_data.loc[active_pitchers, 'Streak_Adjustment']

            # Generate all random changes at once (reduced volatility: 0.005 -> 0.004)
            random_changes = np.random.normal(loc=0.0, scale=0.004, size=n_active_pitchers)

            # Vectorized regression calculation (increased regression: 0.02 -> 0.04)
            regression = -0.04 * current_streaks

            # Calculate new streaks and enforce bounds
            new_streaks = np.clip(current_streaks + random_changes + regression, -0.10, 0.10)

            # Update all at once
            self.new_season_pitching_data.loc[active_pitchers, 'Streak_Adjustment'] = new_streaks

        # Update batters (vectorized - same logic, only non-injured)
        active_batters = self.new_season_batting_data['Injured Days'] == 0
        n_active_batters = active_batters.sum()

        if n_active_batters > 0:
            current_streaks = self.new_season_batting_data.loc[active_batters, 'Streak_Adjustment']
            random_changes = np.random.normal(loc=0.0, scale=0.004, size=n_active_batters)
            regression = -0.04 * current_streaks
            new_streaks = np.clip(current_streaks + random_changes + regression, -0.10, 0.10)
            self.new_season_batting_data.loc[active_batters, 'Streak_Adjustment'] = new_streaks

        return

    def new_game_day(self, teams_to_follow: Optional[List[str]] = None) -> None:
        """
        Set up the next day, check if injured and reduce number of days on dl.  improve player condition
        make thread safe, should only be called by season controller once
        :param teams_to_follow: Optional list of team names to show hot/cold players for
        :return: None
        """
        with self.semaphore:
            self.is_injured()
            self.update_streaks()  # Update streaks for active players only
            self.print_hot_cold_players(teams_to_follow)  # Print hot/cold players for followed teams

            # VECTORIZED: Update pitcher condition (10-50x faster than apply with lambda)
            pitcher_ages = self.new_season_pitching_data['Age'].values
            loc_values = self.condition_change_per_day - (pitcher_ages - 20) / 100 * self.condition_change_per_day
            random_changes = np.abs(self._rng_instance.normal(
                loc=loc_values,
                scale=self.condition_change_per_day / 3,
                size=len(pitcher_ages)
            ))
            self.new_season_pitching_data['Condition'] = \
                (self.new_season_pitching_data['Condition'] + random_changes).clip(lower=0, upper=100)

            # VECTORIZED: Update batter condition (10-50x faster than apply with lambda)
            batter_ages = self.new_season_batting_data['Age'].values
            loc_values = self.condition_change_per_day - (batter_ages - 20) / 100 * self.condition_change_per_day
            random_changes = np.abs(self._rng_instance.normal(
                loc=loc_values,
                scale=self.condition_change_per_day / 3,
                size=len(batter_ages)
            ))
            self.new_season_batting_data['Condition'] = \
                (self.new_season_batting_data['Condition'] + random_changes).clip(lower=0, upper=100)

            # copy over results in new season to prior season for game management
            self.sync_dynamic_fields(self.pitching_data, self.batting_data)
        return

    def update_season_stats(self) -> None:
        """
        fill na with zeros for players with no IP or AB from the df and update season stats
        make thread safe, should only be called by season controller once
        :return: None
        """
        with self.semaphore:
            logger.debug('Calculating team pitching stats...')
            self.new_season_pitching_data = \
                team_pitching_stats(self.new_season_pitching_data[self.new_season_pitching_data['IP'] > 0].fillna(0))
            logger.debug('Calculating team batting stats...')
            self.new_season_batting_data = \
                team_batting_stats(self.new_season_batting_data[self.new_season_batting_data['AB'] > 0].fillna(0))
            logger.debug('Updated season pitching stats:\n{}', self.new_season_pitching_data.to_string(justify="right"))

            # Note: Sim WAR is calculated only during AI GM assessments (not after every game)
            logger.debug('Season statistics update complete.')
        return

    def calculate_sim_war(self) -> None:
        """
        Calculate dynamic Sim WAR (Player Value) based on OBSERVABLE season performance.

        This metric reflects player value based purely on their statistical output - like real-world WAR.
        It does NOT apply internal simulation adjustment factors (age, injury, streak) because those
        already influenced the in-game performance that produced these stats.

        Formula components:
        - Batters: Offensive value based on wOBA vs league average, scaled by PA
        - Pitchers: Run prevention value based on FIP vs league average, scaled by IP

        Design Philosophy:
        - Adjustment factors affect IN-GAME performance (at-bats, pitching)
        - WAR measures the RESULTS of those performances (observable stats)
        - Applying adjustments to WAR would be double-counting

        Results stored in 'Sim_WAR' column for both batting and pitching dataframes.

        NOTE: This function should be called from within a semaphore-protected context.
        It does NOT acquire its own semaphore to avoid deadlock.

        :return: None (modifies dataframes in place)
        """
        # NOTE: No semaphore here - caller must hold it
        # ===== BATTER SIM WAR =====
        batting_df = self.new_season_batting_data

        # Filter batters with playing time
        active_batters = batting_df['AB'] >= 0

        if active_batters.sum() > 0:
            # Calculate wOBA (weighted On-Base Average)
            # Weights: BB=0.69, HBP=0.72, 1B=0.88, 2B=1.24, 3B=1.56, HR=1.95
            singles = batting_df['H'] - batting_df['2B'] - batting_df['3B'] - batting_df['HR']
            woba_numerator = (0.69 * batting_df['BB'] +
                             0.72 * batting_df['HBP'] +
                             0.88 * singles +
                             1.24 * batting_df['2B'] +
                             1.56 * batting_df['3B'] +
                             1.95 * batting_df['HR'])
            plate_appearances = batting_df['AB'] + batting_df['BB'] + batting_df['HBP'] + batting_df['SF']
            woba = np.where(plate_appearances > 0, woba_numerator / plate_appearances, 0.0)

            # League average wOBA (calculate from all active batters)
            league_woba = np.mean(woba[active_batters])

            # Replacement level wOBA (roughly 0.020 below league average)
            # This matches real WAR methodology which compares to replacement level, not average
            replacement_woba = league_woba - 0.020

            # Offensive runs above replacement: ((wOBA - replacement) / 1.15) * PA
            # 1.15 is wOBA scale factor to convert to runs
            runs_above_replacement = ((woba - replacement_woba) / 1.15) * plate_appearances

            # Convert runs to wins (~10 runs = 1 WAR)
            # This is the base offensive WAR - based purely on observable offensive stats
            sim_war = runs_above_replacement / 10.0

            # Add Def_WAR if it exists (captures defense/baserunning from prior season)
            if 'Def_WAR' in batting_df.columns:
                # Def_WAR is a per-season value from prior year, scale by games played
                games_played = batting_df['G']
                # Scale Def_WAR by participation rate (G/162)
                scaled_def_war = batting_df['Def_WAR'] * (games_played / 162.0)
                sim_war = sim_war + scaled_def_war

            # Set Sim_WAR column (vectorized)
            batting_df['Sim_WAR'] = np.where(active_batters, sim_war, 0.0)

            logger.debug('League average wOBA: {:.3f}, Replacement level wOBA: {:.3f}',
                       league_woba, replacement_woba)
            logger.debug('Calculated Sim WAR for batters: min={:.2f}, max={:.2f}, avg={:.2f}',
                       batting_df['Sim_WAR'].min(), batting_df['Sim_WAR'].max(),
                       batting_df['Sim_WAR'].mean())
        else:
            batting_df['Sim_WAR'] = 0.0

        # ===== PITCHER SIM WAR =====
        pitching_df = self.new_season_pitching_data

        # Filter pitchers with playing time
        active_pitchers = pitching_df['IP'] >= 5

        # Debug output for season end
        logger.debug(f'Pitcher WAR calculation: {len(pitching_df)} total pitchers, {active_pitchers.sum()} active (IP >= 5)')

        if active_pitchers.sum() > 0:
            # Calculate FIP (Fielding Independent Pitching)
            # FIP = ((13*HR + 3*BB - 2*SO) / IP) + constant
            # FIP constant ~3.10 to match ERA scale
            fip_constant = 3.10
            fip_numerator = (13 * pitching_df['HR'] + 3 * pitching_df['BB'] - 2 * pitching_df['SO'])
            fip = np.where(pitching_df['IP'] > 0,
                          (fip_numerator / pitching_df['IP']) + fip_constant,
                          0.0)

            # League average FIP
            league_fip = np.mean(fip[active_pitchers])

            # Replacement level FIP (roughly 1.0 runs per 9 IP worse than league average)
            # This matches real WAR methodology which compares to replacement level, not average
            replacement_fip = league_fip + 1.0

            # Runs prevented above replacement: ((replacementFIP - playerFIP) / 9) * IP
            # Divide by 9 to convert from per-9-innings rate to per-inning rate
            runs_above_replacement = ((replacement_fip - fip) / 9.0) * pitching_df['IP']

            # Convert runs to wins (~10 runs = 1 WAR)
            # This is the base pitching WAR - based purely on observable pitching stats
            sim_war = runs_above_replacement / 10.0

            # Add Def_WAR if it exists (captures fielding from prior season)
            # Note: For pitchers, Def_WAR is typically small (fielding by pitcher)
            if 'Def_WAR' in pitching_df.columns:
                # Def_WAR is a per-season value from prior year, scale by games/IP
                games_played = pitching_df['G']
                # Scale Def_WAR by participation rate (G/35 for starters, G/70 for relievers)
                # Use simplified scaling: G/50 as middle ground
                scaled_def_war = pitching_df['Def_WAR'] * (games_played / 50.0)
                sim_war = sim_war + scaled_def_war

            # Set Sim_WAR column (vectorized)
            pitching_df['Sim_WAR'] = np.where(active_pitchers, sim_war, 0.0)

            logger.debug(f'League average FIP: {league_fip:.2f}, Replacement level FIP: {replacement_fip:.2f}')
            logger.debug(f'Pitcher WAR range: {pitching_df[active_pitchers]["Sim_WAR"].min():.2f} to {pitching_df[active_pitchers]["Sim_WAR"].max():.2f}, avg={pitching_df[active_pitchers]["Sim_WAR"].mean():.2f}')

            # Log a sample pitcher for verification (temporarily store FIP in dataframe)
            pitching_df['_temp_fip'] = fip
            sample_pitchers = pitching_df[active_pitchers].nlargest(3, 'IP')
            for idx, p in sample_pitchers.iterrows():
                logger.debug(f'Sample: {p.get("Player", "Unknown")} - IP:{p["IP"]:.1f} FIP:{p["_temp_fip"]:.2f} WAR:{p["Sim_WAR"]:.2f}')
            pitching_df.drop(columns=['_temp_fip'], inplace=True)
        else:
            pitching_df['Sim_WAR'] = 0.0

        return

    def move_a_player_between_teams(self, player_index, new_team):
        is_batter, is_pitcher = self.is_batter_or_pitcher(player_index)
        if is_batter:
            self.move_player_in_df(self.batting_data, player_index, new_team)
            self.move_player_in_df(self.new_season_batting_data, player_index, new_team)
        if is_pitcher:
            self.move_player_in_df(self.pitching_data, player_index, new_team)
            self.move_player_in_df(self.new_season_pitching_data, player_index, new_team)
        return

    @staticmethod
    def safe_literal_eval(s):
        """Safely evaluates a string to a Python literal, handling unquoted strings in lists.

        PERFORMANCE: Uses pre-compiled regex pattern for ~2-5x speedup
        """
        if isinstance(s, list):
            return s
        try:
            # Replace unquoted strings within lists with quoted strings using pre-compiled pattern
            s = _LIST_PATTERN.sub(
                lambda match: "[" + ",".join(f'"{item.strip()}"' for item in match.group(1).split(",")) + "]", s)
            return ast.literal_eval(s)
        except (ValueError, SyntaxError):
            return None  # Or handle the error as needed

    def move_player_in_df(self, df, player_index, new_team):
        # ast.literal_eval doesn't work well unless the list is formatted like ["'BOS'"], use static method
        df['Teams'] = df['Teams'].apply(self.safe_literal_eval)
        df['Leagues'] = df['Leagues'].apply(self.safe_literal_eval)
        df.loc[player_index, 'Team'] = new_team
        df.loc[player_index, 'Teams'].append(new_team)  # should inplace modify row
        return df

    def is_batter_or_pitcher(self, player_index):
        is_batter = True if player_index in self.batting_data.index else False
        is_pitcher = True if player_index in self.pitching_data.index else False
        return is_batter, is_pitcher

    def print_current_season(self, teams: Optional[List[str]] = None, summary_only_b: bool = False) -> None:
        """
        prints the current season being played
        :param teams: option list of team names
        :param summary_only_b: print team totals or entire roster stats
        :return: None
        """
        logger.debug('In print_current_season')
        logger.debug('Teams: {}', teams)
        logger.debug('Current season batting data:\n{}', self.new_season_batting_data.head(5).to_string())
        logger.debug('Current season batting stats:\n{}', team_batting_stats(self.new_season_batting_data).head(5).to_string())
        teams = list(self.batting_data.Team.unique()) if teams is None else teams
        self.print_season(team_batting_stats(self.new_season_batting_data, filter_stats=False),
                          team_pitching_stats(self.new_season_pitching_data, filter_stats=False), teams=teams,
                          summary_only_b=summary_only_b)
        return

    def print_prior_season(self, teams: Optional[List[str]] = None, summary_only_b: bool = False) -> None:
        """
        useful to look back at the prior season to see the trend in the current one or just look at last years to
        start the season
        :param teams: option list of team names
        :param summary_only_b: print team totals or entire roster stats
        :return: None
        """
        teams = list(self.batting_data.Team.unique()) if teams is None else teams
        self.print_season(team_batting_stats(self.batting_data), team_pitching_stats(self.pitching_data), teams=teams,
                          summary_only_b=summary_only_b)
        return

    def save_season_stats(self) -> None:
        """
        Save final season statistics to CSV files.
        Creates files: {new_season} Final-Season-stats-pp-Batting.csv and
                      {new_season} Final-Season-stats-pp-Pitching.csv
        :return: None
        """
        # Calculate final stats for both batting and pitching
        final_batting_data = team_batting_stats(
            self.new_season_batting_data[self.new_season_batting_data['AB'] > 0].fillna(0),
            filter_stats=False
        )
        final_pitching_data = team_pitching_stats(
            self.new_season_pitching_data[self.new_season_pitching_data['IP'] > 0].fillna(0),
            filter_stats=False
        )

        # Create file names
        batting_filename = f"{self.new_season} Final-Season-stats-pp-Batting.csv"
        pitching_filename = f"{self.new_season} Final-Season-stats-pp-Pitching.csv"

        # Save to CSV files
        final_batting_data.to_csv(batting_filename, index=True, index_label='Hashcode')
        final_pitching_data.to_csv(pitching_filename, index=True, index_label='Hashcode')

        logger.debug(f'Saved final season batting stats to {batting_filename}')
        logger.debug(f'Saved final season pitching stats to {pitching_filename}')
        print(f'\nFinal season statistics saved to:')
        print(f'  - {batting_filename}')
        print(f'  - {pitching_filename}')

        return

    def save_new_season_stats(self) -> None:
        """
        Save current New-Season statistics to CSV files.
        Used for saving player movements/trades made in the admin UI.
        Creates files: {new_season} New-Season-stats-pp-Batting.csv and
                      {new_season} New-Season-stats-pp-Pitching.csv
        :return: None
        """
        # Create file names
        batting_filename = f"{self.new_season} New-Season-stats-pp-Batting.csv"
        pitching_filename = f"{self.new_season} New-Season-stats-pp-Pitching.csv"

        # Save to CSV files (with Hashcode as index)
        self.new_season_batting_data.to_csv(batting_filename, index=True, index_label='Hashcode')
        self.new_season_pitching_data.to_csv(pitching_filename, index=True, index_label='Hashcode')

        logger.debug(f'Saved new season batting stats to {batting_filename}')
        logger.debug(f'Saved new season pitching stats to {pitching_filename}')
        print(f'\nNew season statistics saved to:')
        print(f'  - {batting_filename}')
        print(f'  - {pitching_filename}')

        return

    def print_season(self, df_b: DataFrame, df_p: DataFrame, teams: List[str],
                     summary_only_b: bool = False, condition_text: bool = True) -> None:
        """
        print a season either in flight or prior season, called from current and prior season methods
        :param df_b: batter data
        :param df_p: pitcher data
        :param teams: list of team names
        :param summary_only_b: print team totals or entire roster stats
        :param condition_text: print the condition of the player as text
        :return:
        """
        teams.append('')  # add blank team for totals
        if condition_text:
            df_p['Condition'] = df_p['Condition'].apply(condition_txt_f)  # apply condition_txt static func
            df_b['Condition'] = df_b['Condition'].apply(condition_txt_f)  # apply condition_txt static func

        # Apply streak status text
        df_p['Streak Status'] = df_p['Streak_Adjustment'].apply(streak_txt_f)
        df_b['Streak Status'] = df_b['Streak_Adjustment'].apply(streak_txt_f)

        # Prepare pitching data
        df_p_display = df_p[df_p['Team'].isin(teams)].copy()
        # Rename 'Injured Days' to 'Estimated Days Remaining' for pitchers
        if 'Injured Days' in df_p_display.columns:
            df_p_display = df_p_display.rename(columns={'Injured Days': 'Estimated Days Remaining'})

        # Rename index to remove the separate "Hashcode" line
        df_p_display = df_p_display.rename_axis(None)

        df_totals = team_pitching_totals(df_p_display)
        if summary_only_b is False:
            print(df_p_display[self.pcols_to_print].to_string(justify='right', index_names=False))  # print entire team

        print('\nTeam Pitching Totals:')
        print(df_totals[self.numeric_pcols_to_print].to_string(justify='right', index=False))
        print('\n\n')

        # Prepare batting data
        df_b_display = df_b[df_b['Team'].isin(teams)].copy()
        # Rename 'Injured Days' to 'Estimated Days Remaining' for batters
        if 'Injured Days' in df_b_display.columns:
            df_b_display = df_b_display.rename(columns={'Injured Days': 'Estimated Days Remaining'})

        # Format positions to remove brackets and quotes, but keep commas
        if 'Pos' in df_b_display.columns:
            df_b_display['Pos'] = df_b_display['Pos'].apply(format_positions)

        # Rename index to remove the separate "Hashcode" line
        df_b_display = df_b_display.rename_axis(None)

        df_totals = team_batting_totals(df_b_display)
        if summary_only_b is False:
            print(df_b_display[self.bcols_to_print].to_string(justify='right', index_names=False))  # print entire team

        print('\nTeam Batting Totals:')
        print(df_totals[self.numeric_bcols_to_print].to_string(justify='right', index=False))
        print('\n\n')
        return


def injured_list_f(idays: int, is_pitcher: bool = False, is_concussion: bool = False) -> str:
    """
    Generate text for IL (Injured List) based on MLB rules:
    - 7-Day IL: For concussions only
    - 10-Day IL: For position players
    - 15-Day IL: For pitchers and two-way players
    - 60-Day IL: For long-term injuries (removes player from 40-man roster)
    
    :param idays: number of days the player is injured
    :param is_pitcher: whether the player is a pitcher
    :param is_concussion: whether the injury is a concussion
    :return: string with name of the IL the player should be placed on
    """
    if idays == 0:
        return 'Active'
    elif is_concussion:
        return '7-Day IL'
    elif idays >= 60:
        return '60-Day IL'
    elif is_pitcher:
        return '15-Day IL'
    else:
        return '10-Day IL'


def condition_txt_f(condition: int) -> str:
    """
    generate text to describe players health
    :param condition: condition level, 100 is perfect, 0 is dead tired
    :return:
    """
    if isinstance(condition, str):
        condition_text = condition  # already converted to a string
    else:
        condition_text = 'Peak' if condition > 75 else \
            'Healthy' if condition > 51 else \
            'Tired' if condition > 33 else \
            'Exhausted'
    return condition_text


def streak_txt_f(streak: float) -> str:
    """
    Generate text to describe player's current streak status
    :param streak: streak adjustment value from -0.10 to 0.10
    :return: string describing streak status
    """
    if isinstance(streak, str):
        return streak  # Already converted to string

    if streak >= 0.025:
        return 'Hot'
    elif streak <= -0.025:
        return 'Cold'
    else:
        return 'Normal'


def remove_non_print_cols(df: DataFrame) -> DataFrame:
    """
    Remove df columns that are for internal use only
    :param df: df to clean
    :return: df cleaned up
    """
    logger.debug('Removing non-print columns from dataframe:\n{}', df.head(5).to_string())
    non_print_cols = {'Season', 'Total_OB', 'AVG_faced', 'Game_Fatigue_Factor', 'Total_Outs', 'Condition'}  # Total_Outs
    cols_to_drop = list(non_print_cols.intersection(df.columns))
    if cols_to_drop:
        df = df.drop(cols_to_drop, axis=1)
    return df


def trunc_col(df_n: Union[ndarray, Series], d: int = 3) -> Union[ndarray, Series]:
    """
    truncate the values in columns in a df to clean up for print
    :param df_n: df to truncate
    :param d: number of places to keep
    :return: new df
    """
    return (df_n * 10 ** d) / 10 ** d


def team_batting_stats(df: DataFrame, filter_stats: bool=True) -> DataFrame:
    """
    calculate stats based on underlying values for things like OBP
    :param df: current df
    :param filter_stats: boolean that filters out players with no stats
    :return: data with calc cols updated
    """
    # OPTIMIZED: Filter first (creates new df), or copy only if not filtering
    if filter_stats:
        df = df[df['AB'] > 0]  # Boolean indexing creates a new dataframe
    else:
        df = df.copy()  # Copy only when not filtering to avoid modifying caller's data

    df['AVG'] = trunc_col(np.nan_to_num(np.divide(df['H'], df['AB']), nan=0.0, posinf=0.0), 3)
    df['OBP'] = trunc_col(np.nan_to_num(np.divide(df['H'] + df['BB'] + df['HBP'], df['AB'] + df['BB'] + df['HBP']),
                          nan=0.0, posinf=0.0), 3)
    df['SLG'] = trunc_col(np.nan_to_num(np.divide((df['H'] - df['2B'] - df['3B'] - df['HR']) + df['2B'] * 2 +
                          df['3B'] * 3 + df['HR'] * 4, df['AB']), nan=0.0, posinf=0.0), 3)
    df['OPS'] = trunc_col(np.nan_to_num(df['OBP'] + df['SLG'], nan=0.0, posinf=0.0), 3)
    return df


def team_pitching_stats(df: DataFrame, filter_stats: bool=True) -> DataFrame:
    """
    build up pitcher stats.  Note initial values for some cols are 0. hbp is 0, 2b are 0, 3b are 0
    :param df: data set to calc
    :param filter_stats boolean that drops players with no stats
    :return: df with new cols / updated cols
    """
    # OPTIMIZED: Filter first (creates new df), or copy only if not filtering
    if filter_stats:
        # For pitchers, only require IP > 0 (not AB, since most pitchers don't bat)
        df = df[df['IP'] > 0]  # Boolean indexing creates a new dataframe
    else:
        df = df.copy()  # Copy only when not filtering to avoid modifying caller's data

    df['AB'] = trunc_col(df['AB'], 0)
    df['IP'] = trunc_col(df['IP'], 2)
    # Only calculate batting stats if pitcher has at-bats (NL pitchers, two-way players)
    df['AVG'] = trunc_col(np.where(df['AB'] > 0, df['H'] / df['AB'], 0), 3)
    df['OBP'] = trunc_col(np.where(df['AB'] + df['BB'] > 0, (df['H'] + df['BB']) / (df['AB'] + df['BB']), 0), 3)

    # Calculate 'SLG' column (only for pitchers with at-bats)
    slg_numerator = (df['H'] - df['2B'] - df['3B'] - df['HR']) + df['2B'] * 2 + df['3B'] * 3 + df['HR'] * 4
    df['SLG'] = trunc_col(np.where(df['AB'] > 0, slg_numerator / df['AB'], 0), 3)
    # Calculate 'OPS' column
    df['OPS'] = trunc_col(df['OBP'] + df['SLG'], 3)
    # Calculate 'WHIP' and 'ERA' columns
    df['WHIP'] = trunc_col((df['BB'] + df['H']) / df['IP'], 3)
    df['ERA'] = trunc_col((df['ER'] / df['IP']) * 9, 2)
    df = fill_nan_with_value(df,'ERA', 0)
    df = fill_nan_with_value(df, 'WHIP', 0)
    df = fill_nan_with_value(df, 'AVG', 0)
    df = fill_nan_with_value(df, 'OBP', 0)
    df = fill_nan_with_value(df, 'SLG', 0)
    df = fill_nan_with_value(df, 'OPS', 0)
    return df


def team_batting_totals(batting_df: DataFrame) -> DataFrame:
    """
    team totals for batting
    :param batting_df: ind batting data
    :return: df with team totals
    """
    df = batting_df[['AB', 'R', 'H', '2B', '3B', 'HR', 'RBI', 'SB', 'CS', 'BB', 'SO',
                     'SH', 'SF', 'HBP']].sum().astype(int)
    df['G'] = np.max(batting_df['G'])
    # Add Sim_WAR if it exists (sum of all player values)
    if 'Sim_WAR' in batting_df.columns:
        df['Sim_WAR'] = batting_df['Sim_WAR'].sum()
    df = df.to_frame().T
    df = team_batting_stats(df, filter_stats=False)
    return df


def team_pitching_totals(pitching_df: DataFrame) -> DataFrame:
    """
      team totals for pitching
      :param pitching_df: ind pitcher data
      :return: df with team totals
      """
    df = pitching_df[['GS', 'CG', 'SHO', 'IP', 'AB', 'H', '2B', '3B', 'ER', 'SO', 'BB', 'HR', 'W', 'L', 'SV', 'BS',
                      'HLD']].sum().astype(int)
    df = df.to_frame().T
    df = df.assign(G=np.max(pitching_df['G']))
    # Add Sim_WAR if it exists (sum of all player values)
    if 'Sim_WAR' in pitching_df.columns:
        df['Sim_WAR'] = pitching_df['Sim_WAR'].sum()
    df = team_pitching_stats(df, filter_stats=False)
    return df


def update_column_with_other_df(df1, col1, df2, col2):
    """
    Updates a column in df1 with values from df2 based on the index.
    OPTIMIZED: Uses pandas .map() for 10-30x speedup vs apply with lambda

    :param df1: The DataFrame containing the column to update.
    :param col1: The name of the column in df1 to update.
    :param df2: The DataFrame containing the reference values.
    :param col2: The name of the column in df2 to use for updates.
    :return: The updated DataFrame with the modified column.
    """
    # OPTIMIZED: map() is optimized for lookups
    # Create mapped series, fill NaN, infer proper dtypes, then assign
    mapped_values = df1[col1].map(df2[col2])
    filled_values = mapped_values.fillna(0)
    df1[col1] = filled_values.infer_objects(copy=False)
    return df1

def fill_nan_with_value(df, column_name, value=0):
    df[column_name] = np.where((df[column_name] == 0) | df[column_name].isnull(), value, df[column_name])
    return df


def format_positions(pos):
    """
    Format positions compactly by removing brackets, quotes, and using slash separator.
    Handles both list and string representations.

    :param pos: Position(s) as list or string
    :return: Compact formatted string of positions (e.g., "1B/OF" instead of "1B, OF")
    """
    if isinstance(pos, list):
        # Limit to first 3 positions for compactness
        positions = pos[:3] if len(pos) > 3 else pos
        return "/".join(positions)
    elif isinstance(pos, str):
        # Check if it looks like a string representation of a list
        if pos.startswith('[') and pos.endswith(']'):
            # Remove brackets and split by comma, then clean up quotes and spaces
            items = pos[1:-1].split(',')
            cleaned_items = [item.strip().strip("'\"") for item in items]
            # Limit to first 3 positions for compactness
            positions = cleaned_items[:3] if len(cleaned_items) > 3 else cleaned_items
            return "/".join(positions)
    # Return the original if no formatting is needed
    return pos


if __name__ == '__main__':
    # Configure logger level - change to "DEBUG" for more detailed logs
    from bblogger import configure_logger
    configure_logger("INFO")
    
    my_teams = []
    baseball_data = BaseballStats(load_seasons=[2023, 2024, 2025], new_season=2026,  include_leagues=['AL', 'NL'],
                                  load_batter_file='aggr-stats-pp-Batting.csv',
                                  load_pitcher_file='aggr-stats-pp-Pitching.csv')
    # print(*baseball_data.pitching_data.columns)
    # print(*baseball_data.batting_data.columns)
    print(baseball_data.get_all_team_names())
    print(baseball_data.get_all_team_city_names())
    # print(baseball_data.pitching_data.to_string())
    # baseball_data.print_prior_season()
    # baseball_data.print_prior_season(teams=[baseball_data.get_all_team_names()[0]])
    # print(baseball_data.get_pitching_data(team_name=baseball_data.get_all_team_names()[0]).to_string())
    my_teams.append('MIL' if 'MIL' in baseball_data.get_all_team_names() else baseball_data.get_all_team_names()[0])
    for team in my_teams:
        print(team)
        # print(baseball_data.get_pitching_data(team_name=team, prior_season=True).to_string())
    #     print(baseball_data.get_pitching_data(team_name=team, prior_season=False).to_string())
        print(baseball_data.get_batting_data(team_name=team, prior_season=True).to_string())
        print(baseball_data.get_batting_data(team_name=team, prior_season=False).to_string())
