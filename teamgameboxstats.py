import pandas as pd
import bbstats
# import numpy as np


class TeamBoxScore:
    def __init__(self, lineup, pitching, team_name):
        # self.rnd = lambda: np.random.default_rng().uniform(low=0.0, high=1.001)  # random generator between 0 and 1
        self.box_pitching = pitching.copy()
        self.box_pitching[['G', 'GS']] = 1
        self.box_pitching[['CG', 'SHO', 'IP', 'H', '2B', '3B', 'ER', 'K', 'BB', 'HR', 'W', 'L', 'SV', 'BS',
                           'HLD', 'ERA', 'WHIP',
                           'OBP', 'SLG', 'OPS', 'Total_Outs']] = 0
        # self.box_pitching.drop(['Season', 'Total_OB', 'Total_Outs'], axis=1, inplace=True)
        self.box_pitching = bbstats.remove_non_print_cols(self.box_pitching, True)
        self.team_box_pitching = None
        self.game_pitching_stats = None

        self.box_batting = lineup.copy()
        self.box_batting[['G']] = 1
        self.box_batting[['AB', 'R', 'H', '2B', '3B', 'HR', 'RBI', 'SB', 'CS', 'BB', 'SO', 'SH', 'SF', 'HBP', 'AVG',
                          'OBP', 'SLG', 'OPS']] = 0
        self.box_batting = bbstats.remove_non_print_cols(self.box_batting, False)
        self.team_box_batting = None
        self.game_batting_stats = None

        self.team_name = team_name
        self.total_hits = 0
        self.total_errors = 0

        return

    def batters_faced(self, pitcher_index):
        total_faced = self.box_pitching.loc[pitcher_index].H + self.box_pitching.loc[pitcher_index].BB + \
                      self.box_pitching.loc[pitcher_index].IP * 3
        return total_faced

    def pitching_result(self, pitcher_index, outcome, outs, condition):
        outcome[1] = 'K' if outcome[1] == 'SO' else outcome[1]  # handle stat translation from pitcher SO to batter K
        if outcome[1] != 'BB':  # handle walks
            self.box_pitching.loc[pitcher_index, ['AB']] = self.box_pitching.loc[pitcher_index, ['AB']] + 1

        if outcome[0] == 'OUT':
            self.box_pitching.loc[pitcher_index, ['Total_Outs']] = \
                self.box_pitching.loc[pitcher_index, ['Total_Outs']] + outs
            self.box_pitching.loc[pitcher_index, ['IP']] = \
                float(self.box_pitching.loc[pitcher_index, ['Total_Outs']] / 3)

        if outcome[1] in ['H', '2B', '3B', 'HR', 'K', 'BB', 'HBP']:  # handle plate appearance
            self.box_pitching.loc[pitcher_index, [outcome[1]]] = self.box_pitching.loc[pitcher_index, [outcome[1]]] + 1

        # increment hit count if OB, not a walk, and not a single
        self.box_pitching.loc[pitcher_index, ['H']] = self.box_pitching.loc[pitcher_index, ['H']] + 1 \
            if outcome[1] != 'BB' and outcome[1] != 'H' and outcome[0] == 'OB' \
            else self.box_pitching.loc[pitcher_index, ['H']]

        # add runs
        self.box_pitching.loc[pitcher_index, ['ER']] = self.box_pitching.loc[pitcher_index, ['ER']] + outcome[3]  # rbis
        self.box_pitching.loc[pitcher_index, ['Condition']] = condition
        return

    def add_pitcher_to_box(self, new_pitcher):
        new_pitcher = new_pitcher if isinstance(new_pitcher, pd.DataFrame) else new_pitcher.to_frame().T
        new_pitcher[['G']] = 1
        new_pitcher[['GS', 'CG', 'SHO', 'IP', 'H', 'ER', 'K', 'BB', 'HR', 'W', 'L', 'SV', 'BS', 'HLD', 'ERA', 'WHIP',
                           'OBP', 'SLG', 'OPS', 'Total_Outs']] = 0
        new_pitcher[['Condition']] = 100
        self.box_pitching = pd.concat([self.box_pitching, new_pitcher], ignore_index=False)
        self.box_pitching = bbstats.remove_non_print_cols(self.box_pitching, True)
        return

    def pitching_win_loss_save(self, pitcher_index, win_b, save_b):
        # set win loss records and save if applicable
        if win_b:  # win boolean, did this pitcher win or lose?
            self.box_pitching.loc[pitcher_index, ['W']] = self.box_pitching.loc[pitcher_index, ['W']] + 1
        else:
            self.box_pitching.loc[pitcher_index, ['L']] = self.box_pitching.loc[pitcher_index, ['L']] + 1

        if save_b:  # add one to save col for last row in box for team is save boolean is true
            self.box_pitching.loc[self.box_pitching.index[-1], ['SV']] = \
                self.box_pitching.loc[self.box_pitching.index[-1], ['SV']] + 1
        return

    def batting_result(self, batter_index, outcome, players_scored_list):
        outcome[1] = 'SO' if outcome[1] == 'K' else outcome[1]  # handle stat translation from pitcher SO to batter K
        if outcome[1] != 'BB':  # handle walks
            self.box_batting.loc[batter_index, ['AB']] = self.box_batting.loc[batter_index, ['AB']] + 1

        if outcome[1] in ['H', '2B', '3B', 'HR', 'BB', 'SO', 'SF', 'HBP']:  # record result of plate appearance
            self.box_batting.loc[batter_index, [outcome[1]]] = self.box_batting.loc[batter_index, [outcome[1]]] + 1

        # increment hit count if OB, not a walk, and not a single
        self.box_batting.loc[batter_index, ['H']] = self.box_batting.loc[batter_index, ['H']] + 1 \
            if outcome[1] != 'BB' and outcome[1] != 'H' and outcome[0] == 'OB' \
            else self.box_batting.loc[batter_index, ['H']]
        self.total_hits = self.box_batting['H'].sum()
        self.box_batting.loc[batter_index, ['RBI']] = self.box_batting.loc[batter_index, ['RBI']] + outcome[3]  # rbis

        for scored_index in players_scored_list.keys():
            self.box_batting.loc[scored_index, ['R']] = self.box_batting.loc[scored_index, ['R']] + 1
        return

    def totals(self):
        self.game_batting_stats = self.box_batting.copy()  # make a copy w/o totals for season accumulations
        self.game_pitching_stats = self.box_pitching.copy()  # make a copy w/o totals for season accumulations
        self.box_batting = bbstats.team_batting_totals(self.box_batting, team_name=self.team_name, concat=True)
        self.box_pitching = bbstats.team_pitching_totals(self.box_pitching, team_name=self.team_name, concat=True)
        return

    def print_boxes(self):
        df = self.box_batting.reindex(['Player', 'Team', 'Pos', 'Age', 'G', 'AB', 'R', 'H', '2B', '3B', 'HR', 'RBI',
                                       'SB', 'CS', 'BB', 'SO', 'SH', 'SF', 'HBP', 'AVG', 'OBP', 'SLG', 'OPS',
                                       'Condition', 'Injured'], axis=1)
        print(df.to_string(index=False, justify='center'))
        print('')
        df = self.box_pitching.reindex(['Player', 'Team', 'Age', 'G', 'GS', 'CG', 'SHO', 'IP', 'AB', 'H', '2B', '3B',
                                        'ER', 'K', 'BB',
                                        'HR', 'W', 'L', 'SV', 'BS', 'HLD', 'ERA', 'WHIP', 'AVG', 'OBP', 'SLG', 'OPS',
                                        'Condition', 'Injured'], axis=1)
        # print(df.drop(['Total_Outs'], axis=1, inplace=False).to_string(index=False, justify='center'))
        print(df.to_string(index=False, justify='center'))
        print('')
        return

    def get_batter_game_stats(self):
        return self.game_batting_stats

    def get_pitcher_game_stats(self):
        return self.game_pitching_stats
