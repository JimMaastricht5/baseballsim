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
import pandas as pd
import numpy as np
from numpy import ndarray
from pandas.core.frame import DataFrame
from pandas.core.series import Series
from typing import List, Optional, Union
import threading


class BaseballStats:
    def __init__(self, load_seasons: List[int], new_season: int, include_leagues: list = None,
                 load_batter_file: str = 'stats-pp-Batting.csv',
                 load_pitcher_file: str = 'stats-pp-Pitching.csv',
                 debug: bool = False) -> None:
        """
        :param load_seasons: list of seasons to load, each season is an integer year
        :param new_season: integer value of year for new season
        :param include_leagues: list of leagues to include in season
        :param load_batter_file: file name of the batting stats, year will be added as a prefix
        :param load_pitcher_file: file name of the pitching stats, year will be added as a prefix
        :param debug: boolean to control extra printing
        """
        self.semaphore = threading.Semaphore(1)  # one thread can update games stats at a time
        self.rnd = lambda: np.random.default_rng().uniform(low=0.0, high=1.001)  # random generator between 0 and 1
        # self.create_hash = lambda text: int(hashlib.sha256(text.encode('utf-8')).hexdigest()[:5], 16)

        self.numeric_bcols = ['G', 'AB', 'R', 'H', '2B', '3B', 'HR', 'RBI', 'SB', 'CS', 'BB', 'SO', 'SH', 'SF',
                              'HBP', 'Condition']  # these cols will get added to running season total
        self.numeric_bcols_to_print = ['G', 'AB', 'R', 'H', '2B', '3B', 'HR', 'RBI', 'SB', 'CS', 'BB', 'SO', 'SH', 'SF',
                                       'HBP', 'AVG', 'OBP', 'SLG', 'OPS']
        self.numeric_pcols = ['G', 'GS', 'CG', 'SHO', 'IP', 'AB', 'H', '2B', '3B', 'HR', 'ER', 'SO', 'BB', 'W', 'L',
                              'SV', 'BS', 'HLD', 'Total_Outs', 'Condition']  # cols will add to running season total
        self.numeric_pcols_to_print = ['G', 'GS', 'CG', 'SHO', 'IP', 'H', '2B', '3B', 'HR', 'ER', 'SO', 'BB',
                                       'W', 'L', 'SV', 'BS', 'HLD', 'ERA', 'WHIP', 'AVG', 'OBP', 'SLG', 'OPS']
        self.pcols_to_print = ['Player', 'League', 'Team', 'Age', 'G', 'GS', 'CG', 'SHO', 'IP', 'H', '2B', '3B', 'ER',
                               'SO', 'BB', 'HR', 'W', 'L', 'SV', 'BS', 'HLD', 'ERA', 'WHIP', 'AVG', 'OBP', 'SLG', 'OPS',
                               'Status', 'Injured Days', 'Condition']
        self.bcols_to_print = ['Player', 'League', 'Team', 'Pos', 'Age', 'G', 'AB', 'R', 'H', '2B', '3B', 'HR', 'RBI',
                               'SB', 'CS', 'BB', 'SO', 'SH', 'SF', 'HBP', 'AVG', 'OBP', 'SLG',
                               'OPS', 'Status', 'Injured Days', 'Condition']
        self.injury_cols_to_print = ['Player', 'Team', 'Age', 'Status', 'Days Remaining']  # Days Remaining to see time
        self.include_leagues = include_leagues
        self.debug = debug
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

        # ***************** game to game stats and settings for injury and rest
        # condition and injury odds
        # 64% of injuries are to pitchers (188 of 684); 26% position players (87 of 634)
        # 27.5% of pitchers w > 5 in will spend time on IL per season (188 out of 684)
        # 26.3% of pitching injuries affect the throwing elbow results in avg of 74 days lost
        # position player (non-pitcher) longevitiy: https://www.nytimes.com/2007/07/15/sports/baseball/15careers.html
        self.condition_change_per_day = 20  # improve with rest, mid-point of normal dist for recovery
        self.fatigue_start_perc = 70  # 85% of way to avg max is where fatigue starts, adjust factor to inc outing lgth
        self.fatigue_rate = .001  # at 85% of avg max pitchers have a .014 increase in OBP.  using .001 as proxy
        self.fatigue_pitching_change_limit = 5  # change pitcher at # or below out of 100
        self.fatigue_unavailable = 33  # condition must be 33 or higher for a pitcher or pos player to be available
        self.pitching_injury_rate = .275  # 27.5 out of 100 players injured per season-> per game
        # self.pitching_injury_odds_for_season = 1 - (1 - self.pitching_injury_rate) ** (1/162)
        self.pitching_injury_avg_len = 32  # according to mlb avg len is 74 but that cant be a normal dist
        self.batting_injury_rate = .137  # 2022 87 out of 634 injured per season .137 avg age 27
        # self.batting_injury_odds_for_season = 1 - (1 - self.batting_injury_rate) ** (1/162)
        self.injury_odds_adjustment_for_age = .000328  # 3.28% inc injury per season above 20 w/ .90 survival
        self.batting_injury_avg_len = 15  # made this up
        self.pitcher_injury_odds_for_season = lambda age: 1 - (1 - (self.pitching_injury_rate + ((age - 20)
                                                                    * self.injury_odds_adjustment_for_age))) ** (1/162)
        self.batter_injury_odds_for_season = lambda age: 1 - (1 - (self.batting_injury_rate + ((age - 20)
                                                                   * self.injury_odds_adjustment_for_age))) ** (1 / 162)
        self.rnd_condition_chg = lambda age: abs(np.random.normal(loc=(self.condition_change_per_day - (age - 20) / 100
                                                                       * self.condition_change_per_day),
                                                                  scale=self.condition_change_per_day / 3, size=1)[0])
        self.rnd_p_inj = lambda age: abs(np.random.normal(loc=self.pitching_injury_avg_len,
                                                          scale=self.pitching_injury_avg_len / 2, size=1)[0])
        self.rnd_b_inj = lambda age: abs(np.random.normal(loc=self.batting_injury_avg_len,
                                                          scale=self.batting_injury_avg_len / 2, size=1)[0])
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
        if self.debug:
            print('bbstats.py get batting data')
            print(team_name)
            print(self.new_season_batting_data.head(5).to_string())
            print(self.new_season_batting_data['Team'].unique())
            print(df.head(5).to_string())
            print('bbstats.py done getting batting data')

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
        df = team_pitching_stats(df)
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
        new_pitcher_file = 'New-Season-' + pitcher_file
        new_batter_file = 'New-Season-' + batter_file
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
            print(e)
            print(f'file was not found, correct spelling or try running bbstats_preprocess.py to setup the data')
            exit(1)  # stop the program

        # limit the league if include leagues is not none and at least one league is in the list
        if self.debug:
            print('bbstats.py in get_seasons')
            print(self.pitching_data.head(5).to_string())
            print(self.new_season_pitching_data.head(5).to_string())
            print('')
        if self.include_leagues is not None and any(self.pitching_data['League'].isin(self.include_leagues)):
            self.pitching_data = self.pitching_data[self.pitching_data['League'].isin(self.include_leagues)]
            self.batting_data = self.batting_data[self.batting_data['League'].isin(self.include_leagues)]

        # cast cols to float, may not be needed, best to be certain
        pcols_to_convert = ['Condition', 'IP', 'ERA', 'WHIP', 'OBP', 'AVG_faced', 'Game_Fatigue_Factor']
        self.pitching_data[pcols_to_convert] = self.pitching_data[pcols_to_convert].astype(float)
        self.batting_data['Condition'] = self.batting_data['Condition'].astype(float)
        self.new_season_pitching_data[pcols_to_convert] = self.new_season_pitching_data[pcols_to_convert].astype(float)
        self.new_season_batting_data['Condition'] = self.new_season_batting_data['Condition'].astype(float)
        return

    def game_results_to_season(self, box_score_class) -> None:
        """
        adds the game results to a season df to accumulate stats, thread safe for shared df across game threads
        :param box_score_class: box score from game to add to season stats
        :return: None
        """
        with self.semaphore:
            # print(f'bbstats.py game_results_to_season, got the semaphore')
            batting_box_score = box_score_class.get_batter_game_stats()
            pitching_box_score = box_score_class.get_pitcher_game_stats()

            # add results to season accumulation, double brackets after box score keep data as df not series
            for index, row in batting_box_score.iterrows():
                self.new_season_batting_data.loc[index, self.numeric_bcols] = (
                        batting_box_score.loc[index, self.numeric_bcols] +
                        self.new_season_batting_data.loc[index, self.numeric_bcols])
                self.new_season_batting_data.loc[index, 'Condition'] = batting_box_score.loc[index, 'Condition']
                self.new_season_batting_data.loc[index, 'Injured Days'] = batting_box_score.loc[index, 'Injured Days']

            # print(pitching_box_score[self.numeric_pcols].to_string())
            # print(pitching_box_score[self.numeric_pcols].dtypes)
            # print(self.new_season_pitching_data[self.numeric_pcols].dtypes)
            for index, row in pitching_box_score.iterrows():
                self.new_season_pitching_data.loc[index, self.numeric_pcols] = (
                        pitching_box_score.loc[index, self.numeric_pcols] +
                        self.new_season_pitching_data.loc[index, self.numeric_pcols])
                self.new_season_pitching_data.loc[index, 'Condition'] = pitching_box_score.loc[index, 'Condition']
                self.new_season_pitching_data.loc[index, 'Injured Days'] = pitching_box_score.loc[index, 'Injured Days']
            # print(f'bbstats.py game_results_to_season, critical section completed')
        return

    def is_injured(self) -> None:
        """
        determine if a pitcher or hitter is injured and severity.  older players get injured more often
        add that data to the active seasons df
        ??? should condition be a factor
        :return: None
        """
        self.new_season_pitching_data['Injured Days'] = self.new_season_pitching_data.\
            apply(lambda row: 0 if self.rnd() > self.pitcher_injury_odds_for_season(row['Age']) and
                  row['Injured Days'] == 0 else
                  row['Injured Days'] - 1 if row['Injured Days'] > 0 else
                  int(self.rnd_p_inj(row['Age'])), axis=1)
        self.new_season_batting_data['Injured Days'] = self.new_season_batting_data.\
            apply(lambda row: 0 if self.rnd() > self.batter_injury_odds_for_season(row['Age']) and
                  row['Injured Days'] == 0 else
                  row['Injured Days'] - 1 if row['Injured Days'] > 0 else
                  int(self.rnd_b_inj(row['Age'])), axis=1)

        self.new_season_pitching_data['Status'] = \
            self.new_season_pitching_data['Injured Days'].apply(injured_list_f)  # apply injured list static func
        self.new_season_batting_data['Status'] = \
            self.new_season_batting_data['Injured Days'].apply(injured_list_f)  # apply injured list static func

        print(f'Season Disabled Lists:')
        if self.new_season_pitching_data[self.new_season_pitching_data["Injured Days"] > 0].shape[0] > 0:
            df = self.new_season_pitching_data[self.new_season_pitching_data["Injured Days"] > 0]
            df = df.rename(columns={'Injured Days': 'Days Remaining'})
            print(f'{df[self.injury_cols_to_print].to_string(justify="right")}\n')
        if self.new_season_batting_data[self.new_season_batting_data["Injured Days"] > 0].shape[0] > 0:
            df = self.new_season_batting_data[self.new_season_batting_data["Injured Days"] > 0]
            df = df.rename(columns={'Injured Days': 'Days Remaining'})
            print(f'{df[self.injury_cols_to_print].to_string(justify="right")}\n')
        return

    def new_game_day(self) -> None:
        """
        Set up the next day, check if injured and reduce number of days on dl.  improve player condition
        make thread safe, should only be called by season controller once
        :return: None
        """
        with self.semaphore:
            # print(f'bbstats.py in new_game_day, got semaphore')
            self.is_injured()
            self.new_season_pitching_data['Condition'] = self.new_season_pitching_data.\
                apply(lambda row: self.rnd_condition_chg(row['Age']) + row['Condition'], axis=1)
            self.new_season_pitching_data['Condition'] = self.new_season_pitching_data['Condition'].clip(lower=0, upper=100)
            self.new_season_batting_data['Condition'] = self.new_season_batting_data.\
                apply(lambda row: self.rnd_condition_chg(row['Age']) + row['Condition'], axis=1)
            self.new_season_batting_data['Condition'] = self.new_season_batting_data['Condition'].clip(lower=0, upper=100)

            # copy over results in new season to prior season for game management
            self.pitching_data.loc[:, 'Condition'] = self.new_season_pitching_data.loc[:, 'Condition']
            # self.pitching_data.loc[:, 'Injured Days'] = self.new_season_pitching_data.loc[:, 'Injured Days']
            self.pitching_data = update_column_with_other_df(self.pitching_data, 'Injured Days',
                                                             self.new_season_pitching_data, 'Injured Days')
            self.batting_data.loc[:, 'Condition'] = self.new_season_batting_data.loc[:, 'Condition']
            self.batting_data = update_column_with_other_df(self.batting_data, 'Injured Days',
                                                            self.new_season_batting_data, 'Injured Days')
            # print(f'bbstats.py in new_game_day, released semaphore')
        return

    def update_season_stats(self) -> None:
        """
        fill na with zeros for players with no IP or AB from the df and update season stats
        make thread safe, should only be called by season controller once
        :return: None
        """
        with self.semaphore:
            print(f'bbstats.py in update_season_stats, got semaphore')
            self.new_season_pitching_data = \
                team_pitching_stats(self.new_season_pitching_data[self.new_season_pitching_data['IP'] > 0].fillna(0))
            self.new_season_batting_data = \
                team_batting_stats(self.new_season_batting_data[self.new_season_batting_data['AB'] > 0].fillna(0))
            if self.debug:
                print(f'bbstats update season stats {self.new_season_pitching_data.to_string(justify="right")}')
            print(f'bbstats.py in update_season_stats, release semaphore')
        return

    def move_a_player_between_teams(self, player_index, new_team):
        is_batter, is_pitcher = self.is_batter_or_pitcher(player_index)
        if is_batter:
            self.batting_data.loc[player_index, 'Team'] = new_team
            self.batting_data.loc[player_index, 'Teams'].append(new_team)  # should inplace modify row
        if is_pitcher:
            self.pitching_data.loc[player_index, 'Team'] = new_team
            self.pitching_data.loc[player_index, 'Teams'].append(new_team)  # should inplace modify row
        return

    def is_batter_or_pitcher(self, player_index):
        is_batter, is_pitcher = False, False
        try:
            batter_row = self.batting_data.loc(player_index)
            is_batter = True
        except ValueError:
            pass
        try:
            pitcher_row = self.pitching_data.loc(player_index)
            is_pitcher = True
        except ValueError:
            print(f'pitcher not found {player_index}')
            pass
        print(is_batter, is_pitcher)
        return is_batter, is_pitcher

    def print_current_season(self, teams: Optional[List[str]] = None, summary_only_b: bool = False) -> None:
        """
        prints the current season being played
        :param teams: option list of team names
        :param summary_only_b: print team totals or entire roster stats
        :return: None
        """
        if self.debug:
            print('in bbstats.py print current season')
            print(f'teams: {teams}')
            print(self.new_season_batting_data.head(5).to_string())
            print(team_batting_stats(self.new_season_batting_data).head(5).to_string())
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
        df = df_p[df_p['Team'].isin(teams)]
        df_totals = team_pitching_totals(df)
        if summary_only_b is False:
            print(df[self.pcols_to_print].to_string(justify='right'))  # print entire team

        print('\nTeam Pitching Totals:')
        print(df_totals[self.numeric_pcols_to_print].to_string(justify='right', index=False))
        print('\n\n')

        df = df_b[df_b['Team'].isin(teams)]
        df_totals = team_batting_totals(df)
        if summary_only_b is False:
            print(df[self.bcols_to_print].to_string(justify='right'))  # print entire team

        print('\nTeam Batting Totals:')
        print(df_totals[self.numeric_bcols_to_print].to_string(justify='right', index=False))
        print('\n\n')
        return


def injured_list_f(idays: int) -> str:
    """
    generate text for dl list if player is injured
    :param idays: number of day that player is injured
    :return: string with name of the DL list player should be placed on
    """
    # mlb is 10 for pos min, 15 for pitcher min, and 60 day
    return 'Active' if idays == 0 else \
        '10 Day DL' if idays <= 10 else '15 Day DL' if idays <= 15 else '60 Day DL'


def condition_txt_f(condition: int) -> str:
    """
    generate text to describe players health
    :param condition: condition level, 100 is perfect, 0 is dead tired
    :return:
    """
    return 'Peak' if condition > 75 else \
        'Healthy' if condition > 51 else \
        'Tired' if condition > 33 else \
        'Exhausted'


def remove_non_print_cols(df: DataFrame, debug: bool=False) -> DataFrame:
    """
    Remove df columns that are for internal use only
    :param df: df to clean
    :return: df cleaned up
    """
    if debug:
        print(df.head(5).to_string())
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
    if filter_stats:
        df = df[df['AB'] > 0]
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
    if filter_stats:
        df = df[(df['IP'] > 0) & (df['AB'] > 0)]
    df['AB'] = trunc_col(df['AB'], 0)
    df['IP'] = trunc_col(df['IP'], 2)
    df['AVG'] = trunc_col(df['H'] / df['AB'], 3)
    df['OBP'] = trunc_col((df['H'] + df['BB']) / (df['AB'] + df['BB']), 3)

    # Calculate 'SLG' column
    slg_numerator = (df['H'] - df['2B'] - df['3B'] - df['HR']) + df['2B'] * 2 + df['3B'] * 3 + df['HR'] * 4
    df['SLG'] = trunc_col(slg_numerator / df['AB'], 3)
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
    df = team_pitching_stats(df, filter_stats=False)
    return df


def update_column_with_other_df(df1, col1, df2, col2):
    """
    Updates a column in df1 with values from df2 based on the index.
    :param df1: The DataFrame containing the column to update.
    :param col1: The name of the column in df1 to update.
    :param df2: The DataFrame containing the reference values.
    :param col2: The name of the column in df2 to use for updates.
    :return: The updated DataFrame with the modified column.
    """
    df1.loc[df1.index, col1] = df1[col1].apply(lambda x: df2.loc[x, col2] if x in df2.index else 0)
    return df1

def fill_nan_with_value(df, column_name, value=0):
    df[column_name] = np.where((df[column_name] == 0) | df[column_name].isnull(), value, df[column_name])
    return df


if __name__ == '__main__':
    my_teams = []
    baseball_data = BaseballStats(load_seasons=[2024], new_season=2025,  include_leagues=['ACB', 'NBL'],
                                  load_batter_file='stats-pp-Batting.csv',
                                  load_pitcher_file='stats-pp-Pitching.csv',
                                  debug=True)
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
