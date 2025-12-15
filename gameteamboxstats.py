"""
--- Copyright Notice ---
Copyright (c) 2024 Jim Maastricht

--- File Context and Purpose ---
Team box score tracking and accumulation for baseball game simulation.

This module manages in-game statistics for both batting and pitching, tracking
individual player performance throughout a game. Box scores are accumulated from
at-bat outcomes and later aggregated into season-long statistics. Handles player
condition tracking, runs scored, and pitching statistics.

Contact: JimMaastricht5@gmail.com
"""
import pandas as pd
import bbstats
import numpy as np
from at_bat import OutCome
from numpy import float64, int32, int64
from pandas.core.frame import DataFrame
from pandas.core.series import Series
from typing import Dict, Union


class TeamBoxScore:
    """
    Tracks and accumulates in-game statistics for a team's batters and pitchers.

    Creates box score DataFrames for both batting and pitching that start at zero
    and accumulate throughout the game. After the game, these are aggregated into
    season statistics. Also tracks player condition changes and total hits/errors.

    Attributes:
        box_batting: DataFrame of batting statistics for the game
        box_pitching: DataFrame of pitching statistics for the game
        team_name: Three-letter team abbreviation
        total_hits: Running total of team hits in game
        total_errors: Running total of team errors in game
        condition_change_per_day: Base condition change for fatigue (default 20)
        game_batting_stats: Copy of box_batting without totals row
        game_pitching_stats: Copy of box_pitching without totals row
    """
    def __init__(self, lineup: DataFrame, pitching: DataFrame, team_name: str) -> None:
        """
        Initialize box score with team lineup and starting pitcher.

        Args:
            lineup: DataFrame of batting lineup with historical stats
            pitching: DataFrame with starting pitcher stats
            team_name: Three-letter team abbreviation
        """
        # self.rnd = lambda: np.random.default_rng().uniform(low=0.0, high=1.001)  # random generator between 0 and 1
        self.box_printed = ''
        self.box_pitching = pitching.copy()
        self.box_pitching[['G', 'GS']] = 1
        self.box_pitching[['CG', 'SHO', 'AB', 'H', '2B', '3B', 'ER', 'SO', 'BB', 'HR', 'W', 'L', 'SV', 'BS',
                           'HLD']] = 0
        self.box_pitching[['IP', 'ERA', 'WHIP', 'OBP', 'SLG', 'OPS', 'Total_Outs']] = 0.0
        pcols_to_convert = ['IP', 'ERA', 'WHIP', 'OBP', 'SLG', 'OPS', 'Total_Outs', 'Condition',
                            'AVG_faced', 'Game_Fatigue_Factor']  # make sure these are floats
        self.box_pitching[pcols_to_convert] = self.box_pitching[pcols_to_convert].astype(float)
        # self.box_pitching = bbstats.remove_non_print_cols(self.box_pitching)
        self.team_box_pitching = None
        self.game_pitching_stats = None

        self.box_batting = lineup.copy()
        self.box_batting[['G']] = 1
        self.box_batting[['AB', 'R', 'H', '2B', '3B', 'HR', 'RBI', 'SB', 'CS', 'BB', 'SO', 'SH', 'SF', 'HBP']] = 0
        self.box_batting[['AVG', 'OBP', 'SLG', 'OPS']] = 0.0
        self.box_batting['Condition'] = self.box_batting['Condition'].astype(float)
        # self.box_batting = bbstats.remove_non_print_cols(self.box_batting)
        self.team_box_batting = None
        self.game_batting_stats = None
        self.box_batting_totals = None
        self.box_pitching_totals = None

        self.team_name = team_name
        self.total_hits = 0
        self.total_errors = 0

        self.condition_change_per_day = 20
        self.rnd_condition_chg = lambda: abs(np.random.normal(loc=self.condition_change_per_day,
                                                              scale=self.condition_change_per_day / 2, size=1)[0])
        return

    def batters_faced(self, pitcher_index: int64) -> Union[int64, float64]:
        """
        Calculate total batters faced by a pitcher in this game.

        Args:
            pitcher_index: Player hashcode for the pitcher

        Returns:
            Union[int64, float64]: Total batters faced (H + BB + IP*3)
        """
        pitcher_stats = self.box_pitching.loc[pitcher_index]  # Store the result of .loc[] in a variable
        return pitcher_stats.H + pitcher_stats.BB + pitcher_stats.IP * 3  # total batters faced

    def pitching_result(self, pitcher_index: int64, outcomes: OutCome, condition: Union[float64, int]) -> None:
        """
        Update pitcher's box score stats based on at-bat outcome.

        Args:
            pitcher_index: Player hashcode for the pitcher
            outcomes: OutCome object with at-bat results
            condition: Current pitcher condition (0-100)
        """
        row = self.box_pitching.loc[pitcher_index]
        row['AB'] += (outcomes.score_book_cd != 'BB')  # add 1 if true
        if not outcomes.on_base_b:  # Handle outs
            row['Total_Outs'] += outcomes.outs_on_play
            row['IP'] = float(row['Total_Outs'] / 3)
        if outcomes.score_book_cd in ['H', '2B', '3B', 'HR', 'SO', 'BB', 'HBP']:  # Handle plate appearance
            row[outcomes.score_book_cd] += 1
        row['H'] += (outcomes.score_book_cd not in ['BB', 'H'] and outcomes.on_base_b)  # add 1 if true else 0
        row['ER'] += outcomes.runs_scored
        row['Condition'] = float(condition)
        self.box_pitching.loc[pitcher_index] = row  # Write the row back to the DataFrame
        return

    def add_pitcher_to_box(self, new_pitcher: Series) -> None:
        """
        Add a relief pitcher to the box score when they enter the game.

        Args:
            new_pitcher: Series or DataFrame with pitcher's historical stats
        """
        new_pitcher = new_pitcher if isinstance(new_pitcher, pd.DataFrame) else new_pitcher.to_frame().T
        new_pitcher = new_pitcher.assign(G=1, GS=0, CG=0, SHO=0, IP=0, AB=0, H=0, ER=0, SO=0, BB=0, HR=0,
                                         W=0, L=0, SV=0, BS=0, HLD=0, ERA=0,
                                         WHIP=0, OBP=0, SLG=0, OPS=0, Total_Outs=0, Condition=100.0)  # ?? ISSUE!!!
        self.box_pitching = pd.concat([self.box_pitching, new_pitcher], ignore_index=False)
        return

    def pitching_win_loss_save(self, pitcher_index: int64, win_b: bool, save_b: bool) -> None:
        """
        Record win/loss and save for pitcher(s) at end of game.

        Awards win or loss to specified pitcher. If save situation, credits
        save to last pitcher and hold to second-to-last if they pitched <2 innings.

        Args:
            pitcher_index: Hashcode of pitcher to credit with win/loss
            win_b: True if win, False if loss
            save_b: True if save situation (close game, winning team)
        """
        # set win loss records and save if applicable
        if win_b:  # win boolean, did this pitcher win or lose?
            self.box_pitching.loc[pitcher_index, ['W']] += 1
        else:
            self.box_pitching.loc[pitcher_index, ['L']] += 1
        if save_b:  # add one to save col for last row in box for team is save boolean is true
            self.box_pitching.loc[self.box_pitching.index[-1], ['SV']] += 1
            # ip_last_pitcher = self.box_pitching.loc[self.box_pitching.index[-1], ['IP']]
            # ip_second_to_last_pitcher = self.box_pitching.loc[self.box_pitching.index[-2], ['IP']]
            # print(f'pitching_win_loss_save {ip_last_pitcher}')
            if (float(self.box_pitching.loc[self.box_pitching.index[-1], 'IP']) < 2.0 and
                    float(self.box_pitching.loc[self.box_pitching.index[-2], 'IP']) > 0):  # if save was not 2 innings
                self.box_pitching.loc[self.box_pitching.index[-2], 'HLD'] += 1
        return

    def pitching_blown_save(self, pitcher_index):
        """
        Record a blown save for the pitcher.

        Args:
            pitcher_index: Hashcode of pitcher who blew the save
        """
        self.box_pitching.loc[pitcher_index, ['BS']] = 1
        return

    def steal_result(self, runner_index: int32, steal: bool = True) -> None:
        """
        Record stolen base or caught stealing for runner.

        Args:
            runner_index: Hashcode of runner attempting steal
            steal: True if successful steal, False if caught stealing
        """
        runner_stats = self.box_batting.loc[runner_index].copy()
        if steal:
            runner_stats['SB'] += 1
        else:  # caught stealing
            runner_stats['CS'] += 1
        self.box_batting.loc[runner_index] = runner_stats
        return

    def batting_result(self, batter_index: int, outcomes: OutCome, players_scored_list: Dict[int32, str]) -> None:
        """
        Update batter's box score stats based on at-bat outcome.

        Records AB, hits, RBIs, and other stats. Also credits runs to players who scored.

        Args:
            batter_index: Hashcode of batter
            outcomes: OutCome object with at-bat results
            players_scored_list: Dictionary of player hashcodes who scored this at-bat

        Raises:
            ValueError: If a player with hashcode 0 is in scoring list
        """
        batter_stats = self.box_batting.loc[batter_index].copy()  # Store the row in a variable
        if outcomes.score_book_cd != 'BB':  # handle walks
            batter_stats['AB'] += 1
        outcome_cd = outcomes.score_book_cd # if outcomes.score_book_cd != 'SO' else 'SO'  # translate K SO for batter
        if outcome_cd in ['H', '2B', '3B', 'HR', 'BB', 'SO', 'SF', 'HBP']:  # record  plate appearance
            batter_stats[outcome_cd] += 1
        if outcomes.score_book_cd != 'BB' and outcomes.score_book_cd != 'H' and outcomes.on_base_b is True:
            batter_stats['H'] += 1
        batter_stats['RBI'] += outcomes.runs_scored
        self.box_batting.loc[batter_index] = batter_stats  # Update the DataFrame
        self.total_hits = self.box_batting['H'].sum()
        scored_indices = list(players_scored_list.keys())
        if 0 in scored_indices:
            print(f'teamgameboxstats.py batting result runners scored with zero index.')
            raise ValueError('Player with zero index value causes problems accumulating runs')
        self.box_batting.loc[scored_indices, 'R'] += 1
        return

    def set_box_batting_condition(self) -> None:
        """
        Decrease player condition for all batters after the game.

        Applies random condition decrease (normal distribution around condition_change_per_day)
        and clips values between 0 and 100.
        """
        self.box_batting['Condition'] = self.box_batting. \
            apply(lambda row: row['Condition'] - self.rnd_condition_chg(), axis=1)
        self.box_batting['Condition'] = self.box_batting['Condition'].clip(lower=0, upper=100)
        return

    def totals(self) -> None:
        """
        Calculate team totals for batting and pitching box scores.

        Creates copies of box scores without totals (for season accumulation)
        and generates team total rows for display.
        """
        self.game_batting_stats = self.box_batting.copy()  # make a copy w/o totals for season accumulations
        self.game_pitching_stats = self.box_pitching.copy()  # make a copy w/o totals for season accumulations
        self.box_batting_totals = bbstats.team_batting_totals(self.box_batting)
        self.box_pitching_totals = bbstats.team_pitching_totals(self.box_pitching)
        return

    def print_boxes(self) -> str:
        """
        Format and return box scores as printable string.

        Creates formatted strings for both batting and pitching box scores
        with team totals row appended.

        Returns:
            str: Formatted box score text with batting and pitching stats
        """
        batting_cols = ['Player', 'Team', 'Pos', 'Age', 'G', 'AB', 'R', 'H', '2B', '3B', 'HR', 'RBI',
                        'SB', 'CS', 'BB', 'SO', 'SH', 'SF', 'HBP']
        pitching_cols = ['Player', 'Team', 'Age', 'G', 'GS', 'CG', 'SHO', 'IP', 'H', '2B', '3B',
                         'ER', 'SO', 'BB', 'HR', 'W', 'L', 'SV', 'BS', 'HLD']
        df = self.box_batting[batting_cols]
        df = pd.concat([df, self.box_batting_totals.assign(Player='Totals', Team='', Pos='', Age='')[batting_cols]])
        self.box_printed += df.to_string(index=False, justify='right') + '\n\n'
        # print(df.to_string(index=False, justify='right'))
        # print('')
        df = self.box_pitching[pitching_cols]
        df = pd.concat([df, self.box_pitching_totals.assign(Player='Totals', Team='', Pos='', Age='')[pitching_cols]])
        self.box_printed += df.to_string(index=False, justify='right') + '\n\n'
        # print(df.to_string(index=False, justify='right'))
        # print('')
        return self.box_printed

    def get_batter_game_stats(self):
        """
        Get batting statistics for accumulation into season stats.

        Returns:
            DataFrame: Copy of box_batting without totals row
        """
        return self.game_batting_stats

    def get_pitcher_game_stats(self):
        """
        Get pitching statistics for accumulation into season stats.

        Ensures 2B and 3B columns are integers before returning.

        Returns:
            DataFrame: Copy of box_pitching without totals row
        """
        # 2b and 3b slide toward object types, make sure they are ints
        self.game_pitching_stats[['2B', '3B']] = self.game_pitching_stats[['2B', '3B']].astype(int)
        return self.game_pitching_stats
