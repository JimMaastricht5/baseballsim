import pandas as pd
import bbstats
import numpy as np


class TeamBoxScore:
    def __init__(self, lineup, pitching, team_name):
        # self.rnd = lambda: np.random.default_rng().uniform(low=0.0, high=1.001)  # random generator between 0 and 1
        self.box_pitching = pitching.copy()
        self.box_pitching[['G', 'GS']] = 1
        self.box_pitching[['CG', 'SHO', 'IP', 'AB', 'H', '2B', '3B', 'ER', 'K', 'BB', 'HR', 'W', 'L', 'SV', 'BS',
                           'HLD', 'ERA', 'WHIP',
                           'OBP', 'SLG', 'OPS', 'Total_Outs']] = 0
        # self.box_pitching.drop(['Season', 'Total_OB', 'Total_Outs'], axis=1, inplace=True)
        self.box_pitching = bbstats.remove_non_print_cols(self.box_pitching)
        self.team_box_pitching = None
        self.game_pitching_stats = None

        self.box_batting = lineup.copy()
        self.box_batting[['G']] = 1
        self.box_batting[['AB', 'R', 'H', '2B', '3B', 'HR', 'RBI', 'SB', 'CS', 'BB', 'SO', 'SH', 'SF', 'HBP', 'AVG',
                          'OBP', 'SLG', 'OPS']] = 0
        self.box_batting = bbstats.remove_non_print_cols(self.box_batting)
        self.team_box_batting = None
        self.game_batting_stats = None

        self.team_name = team_name
        self.total_hits = 0
        self.total_errors = 0

        self.condition_change_per_day = 20
        self.rnd_condition_chg = lambda: abs(np.random.normal(loc=self.condition_change_per_day,
                                                              scale=self.condition_change_per_day / 2, size=1)[0])
        return

    def batters_faced(self, pitcher_index):
        pitcher_stats = self.box_pitching.loc[pitcher_index]  # Store the result of .loc[] in a variable
        return pitcher_stats.H + pitcher_stats.BB + pitcher_stats.IP * 3  # total batters faced

    def pitching_result(self, pitcher_index, outcomes, condition):
        outcomes.convert_k()
        row = self.box_pitching.loc[pitcher_index]
        if outcomes.score_book_cd != 'BB':  # Handle walks
            row['AB'] += 1
        if not outcomes.on_base_b:  # Handle outs
            row['Total_Outs'] += outcomes.outs_on_play
            row['IP'] = float(row['Total_Outs'] / 3)
        if outcomes.score_book_cd in ['H', '2B', '3B', 'HR', 'K', 'BB', 'HBP']:  # Handle plate appearance
            row[outcomes.score_book_cd] += 1
        # Increment hit count if OB, not a walk, and not a single
        if outcomes.score_book_cd not in ['BB', 'H'] and outcomes.on_base_b:
            row['H'] += 1
        # Update runs scored and condition
        row['ER'] += outcomes.runs_scored
        row['Condition'] = condition
        # Write the row back to the DataFrame
        self.box_pitching.loc[pitcher_index] = row
        # print(f'teamgameboxstats pitching_results {self.box_pitching.loc[pitcher_index]}')
        return

    def add_pitcher_to_box(self, new_pitcher):
        new_pitcher = new_pitcher if isinstance(new_pitcher, pd.DataFrame) else new_pitcher.to_frame().T
        new_pitcher = new_pitcher.assign(G=1, GS=0, CG=0, SHO=0, IP=0, AB=0, H=0, ER=0, K=0, BB=0, HR=0,
                                         W=0, L=0, SV=0, BS=0, HLD=0, ERA=0,
                                         WHIP=0, OBP=0, SLG=0, OPS=0, Total_Outs=0, Condition=100)  # ?? ISSUE!!!
        self.box_pitching = pd.concat([self.box_pitching, new_pitcher], ignore_index=False)
        return

    def pitching_win_loss_save(self, pitcher_index, win_b, save_b):
        # set win loss records and save if applicable
        if win_b:  # win boolean, did this pitcher win or lose?
            self.box_pitching.loc[pitcher_index, ['W']] += 1
        else:
            self.box_pitching.loc[pitcher_index, ['L']] += 1
        if save_b:  # add one to save col for last row in box for team is save boolean is true
            self.box_pitching.loc[self.box_pitching.index[-1], ['SV']] += 1
            if float(self.box_pitching.loc[self.box_pitching.index[-1], ['IP']]) < 2.0 and \
                    float(self.box_pitching.loc[self.box_pitching.index[-2], ['IP']]) > 0:  # if save was not 2 innings
                self.box_pitching.loc[self.box_pitching.index[-2], ['HLD']] += 1,
        return

    def pitching_blown_save(self, pitcher_index):
        self.box_pitching.loc[pitcher_index, ['BS']] = 1
        return

    def steal_result(self, runner_index, steal=True):
        runner_stats = self.box_batting.loc[runner_index].copy()
        if steal:
            runner_stats['SB'] += 1
        else:  # caught stealing
            runner_stats['CS'] += 1
        self.box_batting.loc[runner_index] = runner_stats
        return

    def batting_result(self, batter_index, outcomes, players_scored_list):
        outcomes.convert_k()
        batter_stats = self.box_batting.loc[batter_index].copy()  # Store the row in a variable
        if outcomes.score_book_cd != 'BB':  # handle walks
            batter_stats['AB'] += 1
        outcome_cd = outcomes.score_book_cd if outcomes.score_book_cd != 'K' else 'SO'  # translate K to SO for batter
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

    def set_box_batting_condition(self):
        self.box_batting['Condition'] = self.box_batting. \
            apply(lambda row: row['Condition'] - self.rnd_condition_chg(), axis=1)
        self.box_batting['Condition'] = self.box_batting['Condition'].clip(lower=0, upper=100)
        return

    def totals(self):
        self.game_batting_stats = self.box_batting.copy()  # make a copy w/o totals for season accumulations
        self.game_pitching_stats = self.box_pitching.copy()  # make a copy w/o totals for season accumulations
        self.box_batting = bbstats.team_batting_totals(self.box_batting, team_name=self.team_name, concat=True)
        self.box_pitching = bbstats.team_pitching_totals(self.box_pitching, team_name=self.team_name, concat=True)
        return

    def print_boxes(self):
        df = self.box_batting[['Player', 'Team', 'Pos', 'Age', 'G', 'AB', 'R', 'H', '2B', '3B', 'HR', 'RBI',
                               'SB', 'CS', 'BB', 'SO', 'SH', 'SF', 'HBP']]
        # , 'AVG', 'OBP', 'SLG', 'OPS', 'Condition', 'Status']]
        # df = df.apply(bbstats.condition_txt_f)  # throws a conversion error, col not int
        print(df.to_string(index=False, justify='right'))
        print('')
        df = self.box_pitching[['Player', 'Team', 'Age', 'G', 'GS', 'CG', 'SHO', 'IP', 'H', '2B', '3B',
                                'ER', 'K', 'BB', 'HR', 'W', 'L', 'SV', 'BS', 'HLD']]  #
        # , 'ERA', 'WHIP', 'AVG', 'OBP', 'SLG', 'OPS', 'Condition', 'Status']]
        # df = df.apply(bbstats.condition_txt_f)
        print(df.to_string(index=False, justify='right'))
        print('')
        return

    def get_batter_game_stats(self):
        return self.game_batting_stats

    def get_pitcher_game_stats(self):
        return self.game_pitching_stats
