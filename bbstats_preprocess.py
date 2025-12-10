# MIT License
#
# 2024 Jim Maastricht
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
#
# JimMaastricht5@gmail.com
"""
Baseball statistics preprocessing and data standardization.

This module handles the cleaning, transformation, and aggregation of raw MLB player
statistics downloaded from RotoWire/Baseball-Reference. Creates two types of output files:

1. **Aggregated Files** (for simulation):
   - Career totals: `{seasons} aggr-stats-pp-Batting.csv`
   - Career totals: `{seasons} aggr-stats-pp-Pitching.csv`
   - One row per player with cumulative stats across all loaded seasons
   - Indexed by player Hashcode

2. **Historical Files** (for year-by-year analysis):
   - Year-by-year: `{seasons} historical-Batting.csv`
   - Year-by-year: `{seasons} historical-Pitching.csv`
   - One row per player per season
   - Indexed by Player_Season_Key (Hashcode_Year)

3. **New Season Files** (for starting a new season):
   - Projected stats: `{new_season} New-Season-stats-pp-Batting.csv`
   - Projected stats: `{new_season} New-Season-stats-pp-Pitching.csv`
   - Based on age-adjusted performance projections

Key Features:
- Handles multi-season data aggregation and de-duplication
- Removes unwanted columns from raw data
- Calculates derived statistics (OBP, SLG, OPS, ERA, WHIP, etc.)
- Supports random league/team/player name generation for testing
- Age-adjusted performance projections for future seasons
- Merges salary data from historical records
- Filters players by minimum playing time (AB >= 10, IP >= 5)
- Team name remapping (e.g., OAK → ATH)

Random Data Generation:
- Randomizes team cities, mascots, and player names
- Jiggers stats with normal distribution (±10% with scale=2)
- Creates fictional leagues (ACB, NBL)
- Maintains statistical relationships and distributions

Age-Adjusted Projections:
- Peak performance age: 29
- Young players (21-25): Improvement curve (coeff=0.0008)
- Declining players (30+): Decline curve (coeff=-0.0059)
- Applies parabolic adjustment to OBP/OPS
"""
# data clean up and standardization for stats.  handles random generation if requested
# data imported from https://www.rotowire.com/baseball/stats.php
import pandas as pd
import random
import city_names as city
import hashlib
import salary
import numpy as np
from numpy import ndarray
from pandas.core.frame import DataFrame
from typing import List, Optional


class BaseballStatsPreProcess:
    def __init__(self, load_seasons: List[int], new_season: Optional[int] = None, generate_random_data: bool = False,
                 load_batter_file: str = 'player-stats-Batters.csv',
                 load_pitcher_file: str = 'player-stats-Pitching.csv') -> None:
        self.create_hash = lambda text: int(hashlib.sha256(text.encode('utf-8')).hexdigest()[:5], 16)
        self.jigger_data = lambda x: x + int(np.abs(np.random.normal(loc=x * .10, scale=2, size=1)))

        self.numeric_bcols = ['G', 'AB', 'R', 'H', '2B', '3B', 'HR', 'RBI', 'SB', 'CS', 'BB', 'SO', 'SH', 'SF',
                              'BA', 'GIDP', 'HBP', 'Condition']  # these cols will get added to running season total
        self.numeric_pcols = ['G', 'GS', 'CG', 'SHO', 'IP', 'AB', 'H', '2B', '3B', 'HR', 'ER', 'R', 'SO', 'BB', 'W',
                              'L', 'SV', 'WP', 'Total_Outs', 'Condition']  # cols will add to running season total
        self.nl = ['CHC', 'CIN', 'MIL', 'PIT', 'STL', 'ATL', 'MIA', 'NYM', 'PHI', 'WAS', 'WSN', 'COL', 'LAD', 'ARI',
                   'SDP', 'SFG']
        self.al = ['ATH', 'BOS', 'TEX', 'NYY', 'KCR', 'BAL', 'CLE', 'TOR', 'LAA', 'CWS', 'SEA', 'MIN', 'DET', 'TBR',
                   'HOU']
        self.digit_pos_map = {'1': 'P', '2': 'C', '3': '1B', '4': '2B', '5': '3B', '6': 'SS',
                                               '7': 'LF', '8': 'CF', '9': 'RF'}
        # Team remapping dictionary - maps old team names to new team names
        self.team_remapping = {'OAK': 'ATH'}

        # constants for age adjusted performance
        # key assumptions about year over year performance changes
        # 1. A young player (21-25) will show significant improvement from year to year
        #    assuming the peak is at age 29 at an avg OBP of .325, OBP = -0.0008 * (Age - 29)^2 + 0.325
        # 2. a player in their late 20s (27-29) is typically at their stable peak
        # 3. a player entering their 30s (30+) will begin to show a slight year-over-year decline.
        #    assuming the peak is at age 29 at an avg OBP of 0.325, OBP = -0.00059 * (Age - 29)^2 + 0.325
        # 4. The decline often becomes more rapid after Age 34
        self.coeff_age_improvement = 0.0008
        self.coeff_age_decline = -0.0059
        self.peak_perf_age = 29

        # load seasons
        self.load_seasons = [load_seasons] if not isinstance(load_seasons, list) else load_seasons  # convert to list
        self.new_season = new_season
        self.pitching_data = None
        self.batting_data = None
        self.pitching_data_historical = None
        self.batting_data_historical = None
        self.new_season_pitching_data = None
        self.new_season_batting_data = None
        self.generate_random_data = generate_random_data

        self.df_salary = salary.retrieve_salary('mlb-salaries-2000-24.csv', self.create_hash)
        self.get_seasons(load_batter_file, load_pitcher_file)  # get existing data file
        self.apply_team_remapping()  # apply team name remapping before other processing
        self.calculate_def_war()  # calculate defensive WAR from prior season
        self.generate_random_data = generate_random_data
        if self.generate_random_data:  # generate new data from existing
            self.randomize_data()  # generate random data
        if new_season is not None:
            self.create_new_season_from_existing(load_batter_file, load_pitcher_file)
        self.save_data()
        return

    def save_data(self) -> None:
        # Aggregated files now include 'aggr' in name
        f_pname_aggr = 'random-aggr-stats-pp-Pitching.csv' if self.generate_random_data else 'aggr-stats-pp-Pitching.csv'
        f_bname_aggr = 'random-aggr-stats-pp-Batting.csv' if self.generate_random_data else 'aggr-stats-pp-Batting.csv'
        # New season files do NOT include 'aggr' since they are not aggregated
        f_pname_new = 'random-stats-pp-Pitching.csv' if self.generate_random_data else 'stats-pp-Pitching.csv'
        f_bname_new = 'random-stats-pp-Batting.csv' if self.generate_random_data else 'stats-pp-Batting.csv'
        seasons_str = " ".join(str(season) for season in self.load_seasons)

        # Save aggregated data (with 'aggr' in filename - for bbstats.py)
        self.pitching_data.to_csv(f'{seasons_str} {f_pname_aggr}', index=True, header=True)
        self.batting_data.to_csv(f'{seasons_str} {f_bname_aggr}', index=True, header=True)
        print(f'Saved aggregated files: {seasons_str} {f_pname_aggr} and {f_bname_aggr}')

        # Save historical year-by-year data (new)
        if self.pitching_data_historical is not None:
            f_hist_pname = 'random-historical-Pitching.csv' if self.generate_random_data else 'historical-Pitching.csv'
            self.pitching_data_historical.to_csv(f'{seasons_str} {f_hist_pname}', index=True, header=True)
            print(f'Saved historical pitching data: {seasons_str} {f_hist_pname}')

        if self.batting_data_historical is not None:
            f_hist_bname = 'random-historical-Batting.csv' if self.generate_random_data else 'historical-Batting.csv'
            self.batting_data_historical.to_csv(f'{seasons_str} {f_hist_bname}', index=True, header=True)
            print(f'Saved historical batting data: {seasons_str} {f_hist_bname}')

        # Save new season data (no 'aggr' prefix - this is single season data, not aggregated)
        if self.new_season is not None:
            self.new_season_pitching_data.to_csv(f'{self.new_season} New-Season-{f_pname_new}', index=True, header=True)
            self.new_season_batting_data.to_csv(f'{self.new_season} New-Season-{f_bname_new}', index=True, header=True)
        return

    @staticmethod
    def group_col_to_list(df: DataFrame, key_col: str, col: str, new_col: str) -> DataFrame:
        # Groups unique values in a column by a key column
        # Args: df (pd.DataFrame): The dataframe containing the columns.
        #    key_col (str): The name of the column containing the key.
        #    col (str): The name of the column to find unique values in.
        #    new_col (str): The name of the new column to contain the data
        # Returns: list: A list of dictionaries containing unique values grouped by key.
        groups = {}
        for i, row in df.iterrows():
            key = row[key_col]
            val = row[col]
            if key not in groups:
                groups[key] = set()

            # Handle both string and list values
            if isinstance(val, list):
                # If val is already a list, add each non-empty item
                for item in val:
                    if item and str(item).strip():
                        groups[key].add(item)
            elif val and isinstance(val, str) and val.strip():
                # If val is a non-empty string
                groups[key].add(val)
            elif val and not isinstance(val, str):
                # Handle other types (int, float, etc.)
                groups[key].add(val)

        df[new_col] = df[key_col].map(groups)  # Create a new column to store grouped unique values
        df[new_col] = df[new_col].apply(list)  # Convert sets to lists for easier handling in DataFrame
        return df

    @staticmethod
    def find_duplicate_rows(df: DataFrame, column_names: str) -> DataFrame:
        #  This function finds duplicate rows in a DataFrame based on a specified column.
        # Args: df (pandas.DataFrame): The DataFrame to analyze.
        #   column_names (list): The name of the column containing strings for comparison.
        # Returns: pandas.DataFrame: A new DataFrame containing only the rows with duplicate string values.
        filtered_df = df[column_names].dropna()
        duplicates = filtered_df.duplicated(keep=False)  # keep both rows
        return df[duplicates]

    @staticmethod
    def remove_non_numeric(text):
        return ''.join(char for char in text if char.isdigit())

    def translate_pos(self, digit_string):
        return ''.join(self.digit_pos_map.get(digit, digit) + ',' for digit in digit_string).rstrip(',')

    def de_dup_df(self, df: DataFrame, key_name: str, dup_column_names: str,
                  stats_cols_to_sum: List[str], drop_dups: bool = False) -> DataFrame:
        dup_hashcodes = self.find_duplicate_rows(df=df, column_names=dup_column_names)
        for dfrow_key in dup_hashcodes[key_name].unique():
            df_rows = df.loc[df[key_name] == dfrow_key]
            for dfcol_name in stats_cols_to_sum:
                df.loc[df[key_name] == dfrow_key, dfcol_name] = df_rows[dfcol_name].sum()
        if drop_dups:
            df = df.drop_duplicates(subset='Hashcode', keep='last')
        return df

    def get_pitching_seasons(self, pitcher_file: str, load_seasons: List[int]) -> tuple:
        # Returns tuple of (aggregated_df, historical_df)
        # caution war and salary cols will get aggregated across multiple seasons
        pitching_data = None
        stats_pcols_sum = ['G', 'GS', 'CG', 'SHO', 'IP', 'H', 'ER', 'SO', 'BB', 'HR', 'W', 'L', 'SV', 'HBP', 'BK',
                           'WP']
        for season in load_seasons:
            df = pd.read_csv(str(season) + f" {pitcher_file}")
            df['Season'] = season  # Add season before concatenating
            pitching_data = pd.concat([pitching_data, df], axis=0)

        # drop unwanted cols
        # print(pitching_data.columns)
        pitching_data.drop(['Rk', 'Lg', 'W-L%', 'GF', 'IBB', 'ERA+', 'FIP', 'H9', 'BB9', 'SO9', 'SO/BB',
                            'HR9', 'Awards', 'Player-additional', 'BF'],inplace=True, axis=1)
        pitching_data['Player'] = pitching_data['Player'].str.replace('*', '').str.replace('#', '')
        pitching_data['Hashcode'] = pitching_data['Player'].apply(self.create_hash)

        pitching_data = pd.merge(pitching_data, self.df_salary, on='Hashcode', how='left')  # war and salary cols
        pitching_data = salary.fill_nan_salary(pitching_data, 'Salary')  # set league min for missing data
        pitching_data = salary.fill_nan_salary(pitching_data, 'MLS', 0)  # set min for missing data
        pitching_data['Team'] = pitching_data['Team'].apply(lambda x: x if x in self.nl + self.al else '')
        # players with multiple teams have a 2TM or 3TM line that is the total of all stats.  Drop rows since we total
        pitching_data = pitching_data[pitching_data['Team'] != '']  # drop rows without a formal team name
        pitching_data['League'] = pitching_data['Team'].apply(
                lambda x: 'NL' if x in self.nl else ('AL' if x in self.al else '') )
        # Create Player_Season_Key BEFORE de-duplication
        pitching_data['Player_Season_Key'] = (
            pitching_data['Hashcode'].astype(str) + '_' +
            pitching_data['Season'].astype(str)
        )

        # *** Create HISTORICAL data (year-by-year) - one row per player per season ***
        historical_data = pitching_data.copy()
        historical_data = self.group_col_to_list(df=historical_data, key_col='Player_Season_Key', col='Team', new_col='Teams')
        historical_data = self.group_col_to_list(df=historical_data, key_col='Player_Season_Key', col='League', new_col='Leagues')
        # For historical, only de-dup within same season (mid-season trades)
        historical_data = self.de_dup_df(df=historical_data, key_name='Player_Season_Key',
                                        dup_column_names='Player_Season_Key',
                                        stats_cols_to_sum=stats_pcols_sum, drop_dups=True)
        historical_data = historical_data.set_index('Player_Season_Key')

        # *** Create AGGREGATED data (career totals) - one row per player ***
        pitching_data = self.group_col_to_list(df=pitching_data, key_col='Hashcode', col='Team', new_col='Teams')
        pitching_data = self.group_col_to_list(df=pitching_data, key_col='Hashcode', col='League', new_col='Leagues')
        # Create Years_Included column - list of seasons this player appeared in
        pitching_data = self.group_col_to_list(df=pitching_data, key_col='Hashcode', col='Season', new_col='Years_Included')
        # Sort by Season to ensure most recent year's Team/League are kept during de-duplication
        pitching_data = pitching_data.sort_values('Season', ascending=True)
        pitching_data = self.de_dup_df(df=pitching_data, key_name='Hashcode', dup_column_names='Hashcode',
                                       stats_cols_to_sum=stats_pcols_sum, drop_dups=True)
        pitching_data = pitching_data.set_index('Hashcode')

        # Apply random data jigger if needed (to both datasets)
        if self.generate_random_data:
            for stats_col in stats_pcols_sum:
                pitching_data[stats_col] = pitching_data[stats_col].apply(self.jigger_data)
                historical_data[stats_col] = historical_data[stats_col].apply(self.jigger_data)

        # Calculate derived stats for AGGREGATED data
        pitching_data['AB'] = pitching_data['IP'] * 3 + pitching_data['H']
        pitching_data['2B'] = 0
        pitching_data['3B'] = 0
        pitching_data['HBP'] = 0
        pitching_data['Season'] = str(load_seasons)  # List of all seasons
        pitching_data['OBP'] = pitching_data['WHIP'] / (3 + pitching_data['WHIP'])  # bat reached / number faced
        pitching_data['Total_OB'] = pitching_data['H'] + pitching_data['BB']  # + pitching_data['HBP']
        pitching_data['Total_Outs'] = pitching_data['IP'] * 3  # 3 outs per inning
        pitching_data = pitching_data[pitching_data['IP'] >= 5]  # drop pitchers without enough innings
        pitching_data['AVG_faced'] = (pitching_data['Total_OB'] + pitching_data['Total_Outs']) / pitching_data.G
        pitching_data['Game_Fatigue_Factor'] = 0
        pitching_data['Condition'] = 100
        pitching_data['Status'] = 'Active'  # DL or active
        pitching_data['Injured Days'] = 0  # days to spend in IL
        pitching_data['BS'] = 0
        pitching_data['HLD'] = 0
        pitching_data['E'] = 0
        pitching_data['Age_Adjustment'] = 0.0  # adjust performance based on age change
        if 'Injury_Rate_Adj' not in pitching_data.columns:
            pitching_data['Injury_Rate_Adj'] = 0
            pitching_data['Injury_Perf_Adj'] = 0
        if 'Streak_Adjustment' not in pitching_data.columns:
            pitching_data['Streak_Adjustment'] = 0.0  # Always 0 for aggregated data

        # Calculate derived stats for HISTORICAL data
        historical_data['AB'] = historical_data['IP'] * 3 + historical_data['H']
        historical_data['2B'] = 0
        historical_data['3B'] = 0
        historical_data['HBP'] = 0
        # Season is already set per row from the loop
        historical_data['OBP'] = historical_data['WHIP'] / (3 + historical_data['WHIP'])
        historical_data['Total_OB'] = historical_data['H'] + historical_data['BB']
        historical_data['Total_Outs'] = historical_data['IP'] * 3
        historical_data = historical_data[historical_data['IP'] >= 5]
        historical_data['AVG_faced'] = (historical_data['Total_OB'] + historical_data['Total_Outs']) / historical_data.G
        historical_data['Game_Fatigue_Factor'] = 0
        historical_data['Condition'] = 100
        historical_data['Status'] = 'Active'
        historical_data['Injured Days'] = 0
        historical_data['BS'] = 0
        historical_data['HLD'] = 0
        historical_data['E'] = 0
        historical_data['Age_Adjustment'] = 0.0
        if 'Injury_Rate_Adj' not in historical_data.columns:
            historical_data['Injury_Rate_Adj'] = 0
            historical_data['Injury_Perf_Adj'] = 0
        if 'Streak_Adjustment' not in historical_data.columns:
            historical_data['Streak_Adjustment'] = 0.0  # Always 0 for historical data

        return pitching_data, historical_data

    def get_batting_seasons(self, batter_file: str, load_seasons: List[int]) -> tuple:
        # Returns tuple of (aggregated_df, historical_df)
        batting_data = None
        stats_bcols_sum = ['G', 'AB', 'R', 'H', '2B', '3B', 'HR', 'RBI', 'SB', 'CS', 'BB', 'SO', 'SH', 'SF', 'HBP',
                           'GIDP']
        for season in load_seasons:
            df = pd.read_csv(str(season) + f" {batter_file}")
            df['Season'] = season  # Add season before concatenating
            batting_data = pd.concat([batting_data, df], axis=0)

        # drop unwanted cols
        batting_data.drop(['Rk', 'PA', 'Lg', 'OPS+', 'rOBA', 'Rbat+', 'TB', 'IBB', 'Awards',
                           'Player-additional'],inplace=True, axis=1)
        batting_data['Player'] = batting_data['Player'].str.replace('#', '').str.replace('*', '')
        batting_data['Hashcode'] = batting_data['Player'].apply(self.create_hash)

        batting_data = pd.merge(batting_data, self.df_salary, on='Hashcode', how='left')  # war and salary cols
        batting_data = salary.fill_nan_salary(batting_data, 'Salary')  # set league min for missing data
        batting_data = salary.fill_nan_salary(batting_data, 'MLS', 0)  # set min for missing data
        batting_data['Pos'] = batting_data['Pos'].apply(self.remove_non_numeric).apply(self.translate_pos)
        batting_data = self.group_col_to_list(df=batting_data, key_col='Hashcode', col='Pos', new_col='Pos')
        batting_data['Team'] = batting_data['Team'].apply(lambda x: x if x in self.nl + self.al else '' )
        batting_data['League'] = batting_data['Team'].apply(
                lambda x: 'NL' if x in self.nl else ('AL' if x in self.al else '') )
        # players with multiple teams have a 2TM or 3TM line that is the total of all stats.  Drop rows since we total
        batting_data = batting_data[batting_data['Team'] != '']  # drop rows without a formal team name
        # Create Player_Season_Key BEFORE de-duplication
        batting_data['Player_Season_Key'] = (
            batting_data['Hashcode'].astype(str) + '_' +
            batting_data['Season'].astype(str)
        )

        # *** Create HISTORICAL data (year-by-year) - one row per player per season ***
        historical_data = batting_data.copy()
        historical_data = self.group_col_to_list(df=historical_data, key_col='Player_Season_Key', col='Pos', new_col='Pos')
        historical_data = self.group_col_to_list(df=historical_data, key_col='Player_Season_Key', col='Team', new_col='Teams')
        historical_data = self.group_col_to_list(df=historical_data, key_col='Player_Season_Key', col='League', new_col='Leagues')
        # For historical, only de-dup within same season (mid-season trades)
        historical_data = self.de_dup_df(df=historical_data, key_name='Player_Season_Key',
                                        dup_column_names='Player_Season_Key',
                                        stats_cols_to_sum=stats_bcols_sum, drop_dups=True)
        historical_data = historical_data.set_index('Player_Season_Key')

        # *** Create AGGREGATED data (career totals) - one row per player ***
        batting_data = self.group_col_to_list(df=batting_data, key_col='Hashcode', col='Pos', new_col='Pos')
        batting_data = self.group_col_to_list(df=batting_data, key_col='Hashcode', col='Team', new_col='Teams')
        batting_data = self.group_col_to_list(df=batting_data, key_col='Hashcode', col='League', new_col='Leagues')
        # Create Years_Included column - list of seasons this player appeared in
        batting_data = self.group_col_to_list(df=batting_data, key_col='Hashcode', col='Season', new_col='Years_Included')
        # Sort by Season to ensure most recent year's Team/League are kept during de-duplication
        batting_data = batting_data.sort_values('Season', ascending=True)
        batting_data = self.de_dup_df(df=batting_data, key_name='Hashcode', dup_column_names='Hashcode',
                                      stats_cols_to_sum=stats_bcols_sum, drop_dups=True)
        batting_data = batting_data.set_index('Hashcode')

        # Apply random data jigger if needed (to both datasets)
        if self.generate_random_data:
            for stats_col in stats_bcols_sum:
                batting_data[stats_col] = batting_data[stats_col].apply(self.jigger_data)
                historical_data[stats_col] = historical_data[stats_col].apply(self.jigger_data)

        # Calculate derived stats for AGGREGATED data
        batting_data['Season'] = str(load_seasons)  # List of all seasons
        batting_data['OBP'] = self.trunc_col(np.nan_to_num(np.divide(batting_data['H'] + batting_data['BB'] +
                                                                     batting_data['HBP'], batting_data['AB'] +
                                                                     batting_data['BB'] + batting_data['HBP']),
                                                           nan=0.0, posinf=0.0), 3)
        batting_data['SLG'] = self.trunc_col(np.nan_to_num(np.divide((batting_data['H'] - batting_data['2B'] -
                                                                      batting_data['3B'] - batting_data['HR']) +
                                                                     batting_data['2B'] * 2 +
                                                                     batting_data['3B'] * 3 + batting_data['HR'] * 4,
                                                                     batting_data['AB']), nan=0.0, posinf=0.0), 3)
        batting_data['OPS'] = self.trunc_col(np.nan_to_num(batting_data['OBP'] + batting_data['SLG'],
                                                           nan=0.0, posinf=0.0), 3)
        batting_data['Total_OB'] = batting_data['H'] + batting_data['BB'] + batting_data['HBP']
        batting_data['Total_Outs'] = batting_data['AB'] - batting_data['H'] + batting_data['HBP']
        batting_data = batting_data[batting_data['AB'] >= 10]  # drop players without enough AB
        batting_data['E'] = 0
        batting_data['Game_Fatigue_Factor'] = 0
        batting_data['Condition'] = 100
        batting_data['Status'] = 'Active'  # DL or active
        batting_data['Injured Days'] = 0
        batting_data['Age_Adjustment'] = 0.0  # adjust performance based on age change
        if 'Injury_Rate_Adj' not in batting_data.columns:
            batting_data['Injury_Rate_Adj'] = 0
            batting_data['Injury_Perf_Adj'] = 0
        if 'Streak_Adjustment' not in batting_data.columns:
            batting_data['Streak_Adjustment'] = 0.0  # Always 0 for aggregated data

        # Calculate derived stats for HISTORICAL data
        # Season is already set per row from the loop
        historical_data['OBP'] = self.trunc_col(np.nan_to_num(np.divide(historical_data['H'] + historical_data['BB'] +
                                                                        historical_data['HBP'], historical_data['AB'] +
                                                                        historical_data['BB'] + historical_data['HBP']),
                                                              nan=0.0, posinf=0.0), 3)
        historical_data['SLG'] = self.trunc_col(np.nan_to_num(np.divide((historical_data['H'] - historical_data['2B'] -
                                                                         historical_data['3B'] - historical_data['HR']) +
                                                                        historical_data['2B'] * 2 +
                                                                        historical_data['3B'] * 3 + historical_data['HR'] * 4,
                                                                        historical_data['AB']), nan=0.0, posinf=0.0), 3)
        historical_data['OPS'] = self.trunc_col(np.nan_to_num(historical_data['OBP'] + historical_data['SLG'],
                                                              nan=0.0, posinf=0.0), 3)
        historical_data['Total_OB'] = historical_data['H'] + historical_data['BB'] + historical_data['HBP']
        historical_data['Total_Outs'] = historical_data['AB'] - historical_data['H'] + historical_data['HBP']
        historical_data = historical_data[historical_data['AB'] >= 10]
        historical_data['E'] = 0
        historical_data['Game_Fatigue_Factor'] = 0
        historical_data['Condition'] = 100
        historical_data['Status'] = 'Active'
        historical_data['Injured Days'] = 0
        historical_data['Age_Adjustment'] = 0.0
        if 'Injury_Rate_Adj' not in historical_data.columns:
            historical_data['Injury_Rate_Adj'] = 0
            historical_data['Injury_Perf_Adj'] = 0
        if 'Streak_Adjustment' not in historical_data.columns:
            historical_data['Streak_Adjustment'] = 0.0  # Always 0 for historical data

        return batting_data, historical_data

    def get_seasons(self, batter_file: str, pitcher_file: str) -> None:
        self.pitching_data, self.pitching_data_historical = self.get_pitching_seasons(pitcher_file, self.load_seasons)
        self.batting_data, self.batting_data_historical = self.get_batting_seasons(batter_file, self.load_seasons)
        return

    def apply_team_remapping(self) -> None:
        """
        Apply team name remapping based on self.team_remapping dictionary.
        This remaps old team names to new team names in both pitching and batting data.
        """
        if not self.team_remapping:
            return  # No remapping needed if dictionary is empty

        remapped_teams = []

        # Apply remapping to pitching data (aggregated)
        for old_team, new_team in self.team_remapping.items():
            if old_team in self.pitching_data['Team'].values:
                self.pitching_data['Team'] = self.pitching_data['Team'].replace(old_team, new_team)
                remapped_teams.append(f"Pitching: {old_team} → {new_team}")

        # Apply remapping to batting data (aggregated)
        for old_team, new_team in self.team_remapping.items():
            if old_team in self.batting_data['Team'].values:
                self.batting_data['Team'] = self.batting_data['Team'].replace(old_team, new_team)
                if f"Pitching: {old_team} → {new_team}" not in remapped_teams:
                    remapped_teams.append(f"Batting: {old_team} → {new_team}")

        # Apply remapping to historical data as well
        if self.pitching_data_historical is not None:
            for old_team, new_team in self.team_remapping.items():
                if old_team in self.pitching_data_historical['Team'].values:
                    self.pitching_data_historical['Team'] = self.pitching_data_historical['Team'].replace(old_team, new_team)

        if self.batting_data_historical is not None:
            for old_team, new_team in self.team_remapping.items():
                if old_team in self.batting_data_historical['Team'].values:
                    self.batting_data_historical['Team'] = self.batting_data_historical['Team'].replace(old_team, new_team)

        # Log the remappings that were applied
        if remapped_teams:
            print(f"Applied team remappings: {', '.join(remapped_teams)}")

        return

    def calculate_def_war(self) -> None:
        """
        Calculate Def_WAR (defensive/baserunning value) from prior season data.

        Def_WAR = Real_2025_WAR - Calculated_Sim_WAR_2025

        This captures the defensive and baserunning contributions that aren't
        measured by our offensive/pitching Sim_WAR calculations.
        """
        if not self.load_seasons or len(self.load_seasons) == 0:
            print("No seasons loaded, skipping Def_WAR calculation")
            return

        # Use the most recent season as the prior season
        prior_season = max(self.load_seasons)
        print(f"Calculating Def_WAR from {prior_season} season data...")

        # === PITCHERS ===
        if self.pitching_data_historical is not None:
            # Filter for prior season only
            prior_p = self.pitching_data_historical[
                self.pitching_data_historical['Season'] == prior_season
            ].copy()

            # Filter for meaningful playing time
            prior_p = prior_p[prior_p['IP'] >= 5].copy()

            if len(prior_p) > 0:
                # Calculate FIP for each pitcher
                prior_p['FIP'] = ((13 * prior_p['HR'] + 3 * prior_p['BB'] - 2 * prior_p['SO']) / prior_p['IP']) + 3.10

                # Calculate league average FIP
                league_fip = prior_p['FIP'].mean()
                replacement_fip = league_fip + 1.0

                # Calculate Sim_WAR using our formula
                prior_p['Calculated_Sim_WAR'] = ((replacement_fip - prior_p['FIP']) / 9.0) * prior_p['IP'] / 10.0

                # Calculate Def_WAR = Real_WAR - Sim_WAR
                prior_p['Def_WAR'] = prior_p['WAR'] - prior_p['Calculated_Sim_WAR']

                # Merge Def_WAR into aggregated data by Hashcode
                def_war_p = prior_p[['Hashcode', 'Def_WAR']].copy()
                def_war_p = def_war_p.set_index('Hashcode')

                # Add Def_WAR column to aggregated pitching data
                self.pitching_data = self.pitching_data.join(def_war_p[['Def_WAR']], how='left')

                # Fill NaN with 0.0 for players without prior season data
                self.pitching_data['Def_WAR'] = self.pitching_data['Def_WAR'].fillna(0.0)

                # Also update WAR column to use prior season value
                prior_war_p = prior_p[['Hashcode', 'WAR']].copy()
                prior_war_p = prior_war_p.rename(columns={'WAR': 'Prior_Season_WAR'})
                prior_war_p = prior_war_p.set_index('Hashcode')
                self.pitching_data = self.pitching_data.join(prior_war_p[['Prior_Season_WAR']], how='left')
                self.pitching_data['WAR'] = self.pitching_data['Prior_Season_WAR'].fillna(self.pitching_data['WAR'])
                self.pitching_data.drop('Prior_Season_WAR', axis=1, inplace=True)

                print(f"  Pitchers: Added Def_WAR for {(self.pitching_data['Def_WAR'] != 0).sum()} players")
                print(f"  Pitchers: Def_WAR range: {self.pitching_data['Def_WAR'].min():.2f} to {self.pitching_data['Def_WAR'].max():.2f}")
            else:
                self.pitching_data['Def_WAR'] = 0.0
                print("  Pitchers: No players with IP >= 5 in prior season")

        # === BATTERS ===
        if self.batting_data_historical is not None:
            # Filter for prior season only
            prior_b = self.batting_data_historical[
                self.batting_data_historical['Season'] == prior_season
            ].copy()

            # Filter for meaningful playing time
            prior_b = prior_b[prior_b['AB'] >= 100].copy()

            if len(prior_b) > 0:
                # Calculate wOBA
                singles = prior_b['H'] - prior_b['2B'] - prior_b['3B'] - prior_b['HR']
                woba_numerator = (0.69 * prior_b['BB'] + 0.72 * prior_b['HBP'] + 0.88 * singles +
                                  1.24 * prior_b['2B'] + 1.56 * prior_b['3B'] + 1.95 * prior_b['HR'])
                prior_b['PA'] = prior_b['AB'] + prior_b['BB'] + prior_b['HBP'] + prior_b['SF']
                prior_b['wOBA'] = woba_numerator / prior_b['PA']

                # Calculate league average wOBA
                league_woba = prior_b['wOBA'].mean()
                replacement_woba = league_woba - 0.020

                # Calculate Sim_WAR using our formula
                prior_b['Calculated_Sim_WAR'] = ((prior_b['wOBA'] - replacement_woba) / 1.15) * prior_b['PA'] / 10.0

                # Calculate Def_WAR = Real_WAR - Sim_WAR
                prior_b['Def_WAR'] = prior_b['WAR'] - prior_b['Calculated_Sim_WAR']

                # Merge Def_WAR into aggregated data by Hashcode
                def_war_b = prior_b[['Hashcode', 'Def_WAR']].copy()
                def_war_b = def_war_b.set_index('Hashcode')

                # Add Def_WAR column to aggregated batting data
                self.batting_data = self.batting_data.join(def_war_b[['Def_WAR']], how='left')

                # Fill NaN with 0.0 for players without prior season data
                self.batting_data['Def_WAR'] = self.batting_data['Def_WAR'].fillna(0.0)

                # Also update WAR column to use prior season value
                prior_war_b = prior_b[['Hashcode', 'WAR']].copy()
                prior_war_b = prior_war_b.rename(columns={'WAR': 'Prior_Season_WAR'})
                prior_war_b = prior_war_b.set_index('Hashcode')
                self.batting_data = self.batting_data.join(prior_war_b[['Prior_Season_WAR']], how='left')
                self.batting_data['WAR'] = self.batting_data['Prior_Season_WAR'].fillna(self.batting_data['WAR'])
                self.batting_data.drop('Prior_Season_WAR', axis=1, inplace=True)

                print(f"  Batters: Added Def_WAR for {(self.batting_data['Def_WAR'] != 0).sum()} players")
                print(f"  Batters: Def_WAR range: {self.batting_data['Def_WAR'].min():.2f} to {self.batting_data['Def_WAR'].max():.2f}")
            else:
                self.batting_data['Def_WAR'] = 0.0
                print("  Batters: No players with AB >= 100 in prior season")

        return

    def randomize_data(self):
        self.create_leagues()
        self.randomize_city_names()
        self.randomize_player_names()
        if np.min(self.batting_data.index) == 0 or np.min(self.pitching_data.index) == 0:  # last ditch check key error
            raise Exception('Index value cannot be zero')  # screws up bases where 0 is no runner
        return

    def create_leagues(self):
        # replace AL and NL with random league names, set leagues column to match
        league_names = ['ACB', 'NBL']  # Armchair Baseball and Nerd Baseball, Some Other League SOL, No Name NNL
        # league_names = random.sample(league_list, 2)
        # print(self.pitching_data[['League', 'Team']].drop_duplicates())

        # Update aggregated data
        self.pitching_data.loc[self.pitching_data['League'] == 'AL', 'League'] = league_names[0]
        self.pitching_data.loc[self.pitching_data['League'] == 'NL', 'League'] = league_names[1]
        self.pitching_data['Leagues'] = self.pitching_data['League'].apply(lambda x: [x])
        self.batting_data.loc[self.batting_data['League'] == 'AL', 'League'] = league_names[0]
        self.batting_data.loc[self.batting_data['League'] == 'NL', 'League'] = league_names[1]
        self.batting_data['Leagues'] = self.batting_data['League'].apply(lambda x: [x])

        # Update historical data
        if self.pitching_data_historical is not None:
            self.pitching_data_historical.loc[self.pitching_data_historical['League'] == 'AL', 'League'] = league_names[0]
            self.pitching_data_historical.loc[self.pitching_data_historical['League'] == 'NL', 'League'] = league_names[1]
            self.pitching_data_historical['Leagues'] = self.pitching_data_historical['League'].apply(lambda x: [x])

        if self.batting_data_historical is not None:
            self.batting_data_historical.loc[self.batting_data_historical['League'] == 'AL', 'League'] = league_names[0]
            self.batting_data_historical.loc[self.batting_data_historical['League'] == 'NL', 'League'] = league_names[1]
            self.batting_data_historical['Leagues'] = self.batting_data_historical['League'].apply(lambda x: [x])

        return

    def randomize_city_names(self):
        # create team name and mascots, set teams column to match
        city_dict = {}
        current_team_names = self.batting_data.Team.unique()  # get list of current team names
        city_abbrev = [str(name[:3]).upper() for name in city.names]  # city names are imported
        mascots = self.randomize_mascots(len(city.names))
        for ii, team_abbrev in enumerate(city_abbrev):
            city_dict.update({city_abbrev[ii]: [city.names[ii], mascots[ii]]})  # update will use the last unique abbrev

        new_teams = list(random.sample(city_abbrev, len(current_team_names)))
        for ii, team in enumerate(current_team_names):  # do not use a df merge here resets the index, that is bad
            new_team = new_teams[ii]
            mascot = city_dict[new_team][1]
            city_name = city_dict[new_team][0]

            # Update aggregated data
            self.pitching_data.replace([team], [new_team], inplace=True)
            self.pitching_data.loc[self.pitching_data['Team'] == new_team, 'City'] = city_name
            self.pitching_data['Teams'] = self.pitching_data['Team'].apply(lambda x: [x])
            self.pitching_data.loc[self.pitching_data['Team'] == new_team, 'Mascot'] = mascot
            self.batting_data.replace([team], [new_team], inplace=True)
            self.batting_data.loc[self.batting_data['Team'] == new_team, 'City'] = city_name
            self.batting_data['Teams'] = self.batting_data['Team'].apply(lambda x: [x])
            self.batting_data.loc[self.batting_data['Team'] == new_team, 'Mascot'] = mascot

            # Update historical data
            if self.pitching_data_historical is not None:
                self.pitching_data_historical.replace([team], [new_team], inplace=True)
                self.pitching_data_historical.loc[self.pitching_data_historical['Team'] == new_team, 'City'] = city_name
                self.pitching_data_historical['Teams'] = self.pitching_data_historical['Team'].apply(lambda x: [x])
                self.pitching_data_historical.loc[self.pitching_data_historical['Team'] == new_team, 'Mascot'] = mascot

            if self.batting_data_historical is not None:
                self.batting_data_historical.replace([team], [new_team], inplace=True)
                self.batting_data_historical.loc[self.batting_data_historical['Team'] == new_team, 'City'] = city_name
                self.batting_data_historical['Teams'] = self.batting_data_historical['Team'].apply(lambda x: [x])
                self.batting_data_historical.loc[self.batting_data_historical['Team'] == new_team, 'Mascot'] = mascot

        return

    @staticmethod
    def randomize_mascots(length):
        with open('animals.txt', 'r') as f:
            animals = f.readlines()
        animals = [animal.strip() for animal in animals]
        mascots = random.sample(animals, length)
        return mascots

    def randomize_player_names(self):
        # change pitching_data and batting data names, team name, etc
        df = pd.concat([self.batting_data.Player.str.split(pat=' ', n=1, expand=True),
                        self.pitching_data.Player.str.split(pat=' ', n=1, expand=True)])
        first_names = df[0].values.tolist()
        last_names = df[1].values.tolist()
        random_names = []
        for ii in range(1, (df.shape[0] + 1) * 2):  # generate twice as many random names as needed
            random_names.append(random.choice(first_names) + ' ' + random.choice(last_names))
        random_names = list(set(random_names))  # drop non-unique names
        random_names = random.sample(random_names, self.batting_data.shape[0] + self.pitching_data.shape[0])

        # load new names and reset hashcode index for AGGREGATED data
        self.batting_data['Player'] = random_names[: len(self.batting_data)]  # grab first x rows of list
        self.batting_data = self.batting_data.reset_index()
        self.batting_data['Hashcode'] = self.batting_data['Player'].apply(self.create_hash)
        self.batting_data = self.batting_data.set_index('Hashcode')

        self.pitching_data['Player'] = random_names[-len(self.pitching_data):]  # next x rows list
        self.pitching_data = self.pitching_data.reset_index()
        self.pitching_data['Hashcode'] = self.pitching_data['Player'].apply(self.create_hash)
        self.pitching_data = self.pitching_data.set_index('Hashcode')

        # Update HISTORICAL data with same player names (need to map old hashcode to new)
        # Create mapping from old hashcode to new player name
        if self.batting_data_historical is not None:
            # Extract hashcode from Player_Season_Key (format: hashcode_season)
            self.batting_data_historical = self.batting_data_historical.reset_index()
            self.batting_data_historical['Old_Hashcode'] = self.batting_data_historical['Player_Season_Key'].str.split('_').str[0].astype(int)
            # Map old hashcode to new player name from aggregated data
            old_to_new_player = dict(zip(self.batting_data.reset_index()['Hashcode'], self.batting_data.reset_index()['Player']))
            self.batting_data_historical['Player'] = self.batting_data_historical['Old_Hashcode'].map(old_to_new_player)
            # Recalculate hashcode and Player_Season_Key
            self.batting_data_historical['Hashcode'] = self.batting_data_historical['Player'].apply(self.create_hash)
            self.batting_data_historical['Player_Season_Key'] = (
                self.batting_data_historical['Hashcode'].astype(str) + '_' +
                self.batting_data_historical['Season'].astype(str)
            )
            self.batting_data_historical = self.batting_data_historical.drop('Old_Hashcode', axis=1)
            self.batting_data_historical = self.batting_data_historical.set_index('Player_Season_Key')

        if self.pitching_data_historical is not None:
            self.pitching_data_historical = self.pitching_data_historical.reset_index()
            self.pitching_data_historical['Old_Hashcode'] = self.pitching_data_historical['Player_Season_Key'].str.split('_').str[0].astype(int)
            old_to_new_player = dict(zip(self.pitching_data.reset_index()['Hashcode'], self.pitching_data.reset_index()['Player']))
            self.pitching_data_historical['Player'] = self.pitching_data_historical['Old_Hashcode'].map(old_to_new_player)
            self.pitching_data_historical['Hashcode'] = self.pitching_data_historical['Player'].apply(self.create_hash)
            self.pitching_data_historical['Player_Season_Key'] = (
                self.pitching_data_historical['Hashcode'].astype(str) + '_' +
                self.pitching_data_historical['Season'].astype(str)
            )
            self.pitching_data_historical = self.pitching_data_historical.drop('Old_Hashcode', axis=1)
            self.pitching_data_historical = self.pitching_data_historical.set_index('Player_Season_Key')

        return

    def calc_age_adjustment(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculates and applies a parabolic age-based adjustment to a specified performance column in a DataFrame.
        Args: df: The DataFrame to modify (e.g., batting or pitching data).
        Returns: The modified DataFrame with the adjustment applied and a new 'Age_Adjustment' column created.
        """
        # Calculate the Age Adjustment using the stored self. coefficients
        df['Age_Adjustment'] = np.where(
            df['Age'] <= self.peak_perf_age,
            self.coeff_age_improvement * (df['Age'] - self.peak_perf_age) ** 2,
            self.coeff_age_decline * (df['Age'] - self.peak_perf_age) ** 2
        )
        return df

    def create_new_season_from_existing(self, load_batter_file: str, load_pitcher_file: str) -> None:
        if self.pitching_data is None or self.batting_data is None:
            raise Exception('load at least one season of pitching and batting')
        # blend of actual partial season, load org new season from file
        if self.load_seasons[-1] == self.new_season and self.generate_random_data is False:
            self.new_season_pitching_data = self.get_pitching_seasons(load_pitcher_file, [self.new_season])
            self.new_season_batting_data = self.get_batting_seasons(load_batter_file, [self.new_season])
        else:  # handle random league data and or consecutive seasons
            self.new_season_pitching_data = self.pitching_data.copy()
            self.new_season_pitching_data[self.numeric_pcols] = \
                self.new_season_pitching_data[self.numeric_pcols].astype('int')
            self.new_season_pitching_data[self.numeric_pcols] = 0
            self.new_season_pitching_data[['ERA', 'WHIP', 'OBP', 'AVG_faced', 'Total_OB', 'Total_Outs', 'AB',
                                           'HLD', 'BS', 'Injured Days']] = 0
            self.new_season_pitching_data['Condition'] = 100
            self.new_season_pitching_data['Streak_Adjustment'] = 0.0  # All players start season with no streak
            self.new_season_pitching_data.drop(['Total_OB', 'Total_Outs'], axis=1)
            self.new_season_pitching_data['Season'] = str(self.new_season)
            if self.new_season not in self.load_seasons:  # add a year to age if it is the next year
                self.new_season_pitching_data['Age'] = self.new_season_pitching_data['Age'] + 1  # everyone a year older
                self.new_season_pitching_data = self.calc_age_adjustment(df=self.new_season_pitching_data)

            self.new_season_batting_data = self.batting_data.copy()
            self.new_season_batting_data[self.numeric_bcols] = 0
            self.new_season_batting_data[['AVG', 'OBP', 'SLG', 'OPS', 'Total_OB', 'Total_Outs', 'Injured Days']] = 0
            self.new_season_batting_data['Condition'] = 100
            self.new_season_batting_data['Streak_Adjustment'] = 0.0  # All players start season with no streak
            self.new_season_batting_data.drop(['Total_OB', 'Total_Outs'], axis=1)
            self.new_season_batting_data['Season'] = str(self.new_season)
            if self.new_season not in self.load_seasons:  # add a year to age if it is the next year
                self.new_season_batting_data['Age'] = self.new_season_batting_data['Age'] + 1  # everyone a year older
                self.new_season_batting_data = self.calc_age_adjustment(df=self.new_season_batting_data)

        return

    @staticmethod
    def trunc_col(df_n: ndarray, d: int = 3) -> ndarray:
        return (df_n * 10 ** d).astype(int) / 10 ** d


if __name__ == '__main__':
    baseball_data = BaseballStatsPreProcess(load_seasons=[2023, 2024, 2025], new_season=2026,
                                            generate_random_data=False,
                                            load_batter_file='player-stats-Batters.csv',
                                            load_pitcher_file='player-stats-Pitching.csv')
    # print(*baseball_data.pitching_data.columns)
    # print(*baseball_data.batting_data.columns)
    # print(baseball_data.batting_data.Team.unique())
    # print(baseball_data.batting_data[baseball_data.batting_data['Team'] == 'MIL'].to_string())
    # print(baseball_data.pitching_data[baseball_data.pitching_data['Team'] == 'MIL'].to_string())
    # print(baseball_data.batting_data.Mascot.unique())
    # print(baseball_data.pitching_data.sort_values('Hashcode').to_string())
    # print(baseball_data.batting_data.sort_values('Hashcode').to_string())
    # print(baseball_data.new_season_pitching_data.sort_values('Hashcode').to_string())
