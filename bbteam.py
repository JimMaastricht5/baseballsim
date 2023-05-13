import pandas as pd
class TeamBoxScore:
    def __init__(self, lineup, pitching, team_name):
        self.box_pitching = pitching.copy()
        self.box_pitching[['G', 'GS']] = 1
        self.box_pitching[['CG', 'SHO', 'IP', 'H', 'ER', 'K', 'BB', 'HR', 'W', 'L', 'SV', 'BS', 'HLD', 'ERA', 'WHIP',
                           'OBP', 'SLG', 'OPS']] = 0
        self.box_pitching.drop(['Season', 'Total_OB', 'Total_Outs'], axis=1, inplace=True)
        self.box_pitching = self.box_pitching.reset_index()
        self.team_box_pitching = None

        self.box_batting = lineup.copy()
        self.box_batting[['G']] = 1
        self.box_batting[['AB', 'R', 'H', '2B', '3B', 'HR', 'RBI', 'SB', 'CS', 'BB', 'SO', 'SH', 'SF', 'HBP', 'AVG',
                          'OBP', 'SLG', 'OPS']] = 0
        self.box_batting.drop(['Season', 'Total_OB', 'Total_Outs'], axis=1, inplace=True)
        self.box_batting = self.box_batting.reset_index()
        self.team_box_batting = None

        self.team_name = team_name
        return

    def pitching_result(self, pitcher_num, outcome):
        outcome[1] = 'K' if outcome[1] == 'SO' else outcome[1]  # handle stat translation from pitcher SO to batter K
        if outcome[0] == 'OUT':  # handle walks
            self.box_pitching.loc[pitcher_num, ['IP']] = self.box_pitching.loc[pitcher_num, ['IP']] + .333333

        if outcome[1] in ['H', 'HR', 'K', 'BB', 'HBP']:  # handle plate appearance
            self.box_pitching.loc[pitcher_num, [outcome[1]]] = self.box_pitching.loc[pitcher_num, [outcome[1]]] + 1

            # increment hit count if OB, not a walk, and not a single
        self.box_pitching.loc[pitcher_num, ['H']] = self.box_pitching.loc[pitcher_num, ['H']] + 1 \
            if outcome[1] != 'H' and outcome[0] == 'OB' else self.box_pitching.loc[pitcher_num, ['H']]
        return

    def batting_result(self, batter_num, outcome):
        outcome[1] = 'SO' if outcome[1] == 'K' else outcome[1]  # handle stat translation from pitcher SO to batter K
        if outcome[1] != 'BB':  # handle walks
            self.box_batting.loc[batter_num, ['AB']] = self.box_batting.loc[batter_num, ['AB']] + 1

        if outcome[1] in ['H', '2B', '3B', 'HR', 'BB', 'SO', 'HBP']:  # record result of plate appearance
            self.box_batting.loc[batter_num, [outcome[1]]] = self.box_batting.loc[batter_num, [outcome[1]]] + 1

        # increment hit count if OB, not a walk, and not a single
        self.box_batting.loc[batter_num, ['H']] = self.box_batting.loc[batter_num, ['H']] + 1 \
            if outcome[1] != 'BB' and outcome[1] != 'H' and outcome[0] == 'OB' \
            else self.box_batting.loc[batter_num, ['H']]
        return

    def team_batting_stats(self, df):
        df['AVG'] = df['H'] / df['AB']
        df['OBP'] = (df['H'] + df['BB'] + df['HBP']) / (df['AB'] + df['BB'] + df['HBP'])
        df['SLG'] = ((df['H'] - df['2B'] - df['3B'] - df['HR']) + df['2B'] * 2 + df['3B'] * 3 + df['HR'] * 4) / df['AB']
        df['OPS'] = df['OBP'] + df['SLG'] + df['SLG']
        return df


    def totals(self):
        self.team_box_batting = self.box_batting[['AB', 'R', 'H', '2B', '3B', 'HR', 'RBI', 'SB', 'CS', 'BB',
                                                  'SO', 'SH', 'SF', 'HBP']].sum()
        self.team_box_batting['Player'] = 'Team Totals'
        self.team_box_batting['Team'] = self.team_name
        self.team_box_batting['G'] = 1
        self.team_box_batting['Age'] = ''
        self.team_box_batting['Pos'] = ''
        self.box_batting = self.box_batting.append(self.team_box_batting, ignore_index=True)  # combine totals + indiv
        self.box_batting = self.team_batting_stats(self.box_batting)

        self.team_box_pitching = self.box_pitching[['GS', 'CG', 'SHO', 'IP', 'H', 'ER', 'K', 'BB', 'HR', 'W', 'L',
                                                    'SV', 'BS', 'HLD', 'ERA', 'WHIP']].sum()
        self.team_box_pitching['Player'] = 'Team Totals'
        self.team_box_pitching['Team'] = self.team_name
        self.team_box_pitching['G'] = 1
        self.team_box_pitching['Age'] = ''
        self.box_pitching = self.box_pitching.append(self.team_box_pitching, ignore_index=True)
        return

    def print(self):
        print(self.box_batting.to_string(index=False, justify='center'))
        print('')
        print(self.box_pitching.to_string(index=False, justify='center'))
        return

class Team:
    def __init__(self, team_name, baseball_data):
        self.team_name = team_name
        self.baseball_data = baseball_data
        self.pitchers = baseball_data.pitching_data[baseball_data.pitching_data["Team"] == team_name]
        self.pos_players = baseball_data.batting_data[baseball_data.batting_data["Team"] == team_name]

        self.lineup = None
        self.pitching = None
        self.team_box_score = None
        return

    def set_lineup(self):
        self.lineup = self.pos_players.head(10)  # assumes DH
        self.pitching = self.pitchers.head(1)
        self.team_box_score = TeamBoxScore(self.lineup, self.pitching, self.team_name)
        # print(self.team_box_score.team_batting_stats(pd.DataFrame(self.lineup)).to_string(index=False, justify='center'))
        return
