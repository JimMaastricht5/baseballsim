import pandas as pd
import bbstats

class TeamBoxScore:
    def __init__(self, lineup, pitching, team_name):
        self.box_pitching = pitching.copy()
        self.box_pitching[['G', 'GS']] = 1
        self.box_pitching[['CG', 'SHO', 'IP', 'H', 'ER', 'K', 'BB', 'HR', 'W', 'L', 'SV', 'BS', 'HLD', 'ERA', 'WHIP',
                           'OBP', 'SLG', 'OPS']] = 0
        self.box_pitching.drop(['Season', 'Total_OB', 'Total_Outs'], axis=1, inplace=True)
        # self.box_pitching = self.box_pitching.reset_index()
        self.team_box_pitching = None

        self.box_batting = lineup.copy()
        self.box_batting[['G']] = 1
        self.box_batting[['AB', 'R', 'H', '2B', '3B', 'HR', 'RBI', 'SB', 'CS', 'BB', 'SO', 'SH', 'SF', 'HBP', 'AVG',
                          'OBP', 'SLG', 'OPS']] = 0
        self.box_batting.drop(['Season', 'Total_OB', 'Total_Outs'], axis=1, inplace=True)
        # self.box_batting = self.box_batting.reset_index()
        self.team_box_batting = None

        self.team_name = team_name
        return
#
#     def pitching_result(self, pitcher_num, outcome):
#         outcome[1] = 'K' if outcome[1] == 'SO' else outcome[1]  # handle stat translation from pitcher SO to batter K
#         if outcome[0] == 'OUT':
#             self.box_pitching.loc[pitcher_num, ['IP']] = self.box_pitching.loc[pitcher_num, ['IP']] + .333333
#
#         if outcome[1] in ['H', 'HR', 'K', 'BB', 'HBP']:  # handle plate appearance
#             self.box_pitching.loc[pitcher_num, [outcome[1]]] = self.box_pitching.loc[pitcher_num, [outcome[1]]] + 1
#
#         # increment hit count if OB, not a walk, and not a single
#         self.box_pitching.loc[pitcher_num, ['H']] = self.box_pitching.loc[pitcher_num, ['H']] + 1 \
#             if outcome[1] != 'BB' and outcome[1] != 'H' and outcome[0] == 'OB' \
#             else self.box_pitching.loc[pitcher_num, ['H']]
#         return
#
#     def batting_result(self, batter_num, outcome):
#         outcome[1] = 'SO' if outcome[1] == 'K' else outcome[1]  # handle stat translation from pitcher SO to batter K
#         if outcome[1] != 'BB':  # handle walks
#             self.box_batting.loc[batter_num, ['AB']] = self.box_batting.loc[batter_num, ['AB']] + 1
#
#         if outcome[1] in ['H', '2B', '3B', 'HR', 'BB', 'SO', 'HBP']:  # record result of plate appearance
#             self.box_batting.loc[batter_num, [outcome[1]]] = self.box_batting.loc[batter_num, [outcome[1]]] + 1
#
#         # increment hit count if OB, not a walk, and not a single
#         self.box_batting.loc[batter_num, ['H']] = self.box_batting.loc[batter_num, ['H']] + 1 \
#             if outcome[1] != 'BB' and outcome[1] != 'H' and outcome[0] == 'OB' \
#             else self.box_batting.loc[batter_num, ['H']]
#
#         self.box_batting.loc[batter_num, ['RBI']] = self.box_batting.loc[batter_num, ['RBI']] + outcome[3]  # add rbis
#         return
#
#     def totals(self):
#         self.team_box_batting = self.box_batting[['AB', 'R', 'H', '2B', '3B', 'HR', 'RBI', 'SB', 'CS', 'BB',
#                                                   'SO', 'SH', 'SF', 'HBP']].sum()
#         self.team_box_batting['Player'] = 'Team Totals'
#         self.team_box_batting['Team'] = self.team_name
#         self.team_box_batting['G'] = 1
#         self.team_box_batting['Age'] = ''
#         self.team_box_batting['Pos'] = ''
#         self.team_box_batting = self.box_batting.append(self.team_box_batting, ignore_index=True)  # totals + indiv
#         self.team_box_batting = bbstats.team_batting_stats(self.team_box_batting)  # calculate stats
#
#         self.team_box_pitching = self.box_pitching[['GS', 'CG', 'SHO', 'IP', 'H', 'ER', 'K', 'BB', 'HR', 'W', 'L',
#                                                     'SV', 'BS', 'HLD', 'ERA', 'WHIP']].sum()
#         self.team_box_pitching['Player'] = 'Team Totals'
#         self.team_box_pitching['Team'] = self.team_name
#         self.team_box_pitching['G'] = 1
#         self.team_box_pitching['Age'] = ''
#         self.team_box_pitching = self.box_pitching.append(self.team_box_pitching, ignore_index=True)
#         self.team_box_pitching = bbstats.team_pitching_stats(self.team_box_pitching)  # calc stats
#         return
#
#     def print(self):
#         print(self.box_batting.to_string(index=False, justify='center'))
#         print('')
#         print(self.box_pitching.to_string(index=False, justify='center'))
#         return

# old code
# class TeamBoxScore:
#     def __init__(self, lineup, pitching, team_name):
#         self.box_pitching = pitching.copy()
#         self.box_pitching[['G', 'GS']] = 1
#         self.box_pitching[['CG', 'SHO', 'IP', 'H', 'ER', 'K', 'BB', 'HR', 'W', 'L', 'SV', 'BS', 'HLD', 'ERA', 'WHIP',
#                            'OBP', 'SLG', 'OPS']] = 0
#         self.box_pitching.drop(['Season', 'Total_OB', 'Total_Outs'], axis=1, inplace=True)
#         self.box_pitching = self.box_pitching.reset_index()
#         self.team_box_pitching = None
#
#         self.box_batting = lineup.copy()
#         self.box_batting[['G']] = 1
#         self.box_batting[['AB', 'R', 'H', '2B', '3B', 'HR', 'RBI', 'SB', 'CS', 'BB', 'SO', 'SH', 'SF', 'HBP', 'AVG',
#                           'OBP', 'SLG', 'OPS']] = 0
#         self.box_batting.drop(['Season', 'Total_OB', 'Total_Outs'], axis=1, inplace=True)
#         self.box_batting = self.box_batting.reset_index()
#         self.team_box_batting = None
#
#         self.team_name = team_name
#         return

    def pitching_result(self, pitcher_index, outcome):
        # print(pitcher_num, outcome)
        # print(self.box_pitching)
        outcome[1] = 'K' if outcome[1] == 'SO' else outcome[1]  # handle stat translation from pitcher SO to batter K
        if outcome[0] == 'OUT':
            self.box_pitching.loc[pitcher_index, ['IP']] = self.box_pitching.loc[pitcher_index, ['IP']] + .333333

        if outcome[1] in ['H', 'HR', 'K', 'BB', 'HBP']:  # handle plate appearance
            self.box_pitching.loc[pitcher_index, [outcome[1]]] = self.box_pitching.loc[pitcher_index, [outcome[1]]] + 1

        # increment hit count if OB, not a walk, and not a single
        self.box_pitching.loc[pitcher_index, ['H']] = self.box_pitching.loc[pitcher_index, ['H']] + 1 \
            if outcome[1] != 'BB' and outcome[1] != 'H' and outcome[0] == 'OB' \
            else self.box_pitching.loc[pitcher_index, ['H']]
        return

    def batting_result(self, batter_index, outcome):
        outcome[1] = 'SO' if outcome[1] == 'K' else outcome[1]  # handle stat translation from pitcher SO to batter K
        if outcome[1] != 'BB':  # handle walks
            self.box_batting.loc[batter_index, ['AB']] = self.box_batting.loc[batter_index, ['AB']] + 1

        if outcome[1] in ['H', '2B', '3B', 'HR', 'BB', 'SO', 'HBP']:  # record result of plate appearance
            self.box_batting.loc[batter_index, [outcome[1]]] = self.box_batting.loc[batter_index, [outcome[1]]] + 1

        # increment hit count if OB, not a walk, and not a single
        self.box_batting.loc[batter_index, ['H']] = self.box_batting.loc[batter_index, ['H']] + 1 \
            if outcome[1] != 'BB' and outcome[1] != 'H' and outcome[0] == 'OB' \
            else self.box_batting.loc[batter_index, ['H']]

        self.box_batting.loc[batter_index, ['RBI']] = self.box_batting.loc[batter_index, ['RBI']] + outcome[3]  # add rbis
        return

    def totals(self):
        self.team_box_batting = self.box_batting[['AB', 'R', 'H', '2B', '3B', 'HR', 'RBI', 'SB', 'CS', 'BB',
                                                  'SO', 'SH', 'SF', 'HBP']].sum()
        self.team_box_batting['Player'] = 'Team Totals'
        self.team_box_batting['Team'] = self.team_name
        self.team_box_batting['G'] = 1
        self.team_box_batting['Age'] = ''
        self.team_box_batting['Pos'] = ''
        self.box_batting = self.box_batting.append(self.team_box_batting, ignore_index=True)  # combine totals + indiv
        self.box_batting = bbstats.team_batting_stats(self.box_batting)

        self.team_box_pitching = self.box_pitching[['GS', 'CG', 'SHO', 'IP', 'H', 'ER', 'K', 'BB', 'HR', 'W', 'L',
                                                    'SV', 'BS', 'HLD', 'ERA', 'WHIP']].sum()
        self.team_box_pitching['Player'] = 'Team Totals'
        self.team_box_pitching['Team'] = self.team_name
        self.team_box_pitching['G'] = 1
        self.team_box_pitching['Age'] = ''
        self.box_pitching = self.box_pitching.append(self.team_box_pitching, ignore_index=True)
        self.box_pitching = bbstats.team_pitching_stats(self.box_pitching)
        return

    def print(self):
        print(self.box_batting.to_string(index=False, justify='center'))
        print('')
        print(self.box_pitching.to_string(index=False, justify='center'))
        return