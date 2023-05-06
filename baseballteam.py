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
        return

    def batting_result(self, batter_num, outcome):
        outcome[1] = 'K' if outcome[1] == 'SO' else outcome[1]  # handle stat translation from pitcher SO to batter K
        if outcome[1] != 'BB':  # handle walks
            self.box_batting.loc[batter_num, ['AB']] = self.box_batting.loc[batter_num, ['AB']] + 1

        if outcome[1] in ['H', '2B', '3B', 'HR', 'SO', 'HBP']:  # handle plate appearance
            self.box_batting.loc[batter_num, [outcome[1]]] = self.box_batting.loc[batter_num, [outcome[1]]] + 1

        # increment hit count if OB, not a walk, and not a single
        self.box_batting.loc[batter_num, ['H']] = self.box_batting.loc[batter_num, ['H']] + 1 \
            if outcome[1] != 'H' and outcome[0] == 'OB' else self.box_batting.loc[batter_num, ['H']]
        return

    def totals(self):
        self.team_box_batting = self.box_batting[['AB', 'R', 'H', '2B', '3B', 'HR', 'RBI', 'SB', 'CS', 'BB', 'SO', 'SH', 'SF', 'HBP']].sum()
        self.team_box_batting['Player'] = 'Team Totals'
        self.team_box_batting['Team'] = self.team_name
        self.team_box_batting['G'] = 1
        self.team_box_batting['Age'] = ''
        self.team_box_batting['Pos'] = ''
        # self.team_box_batting = self.team_box_batting.to_frame().transpose()  # set up for horizontal printing
        # self.box_batting = pd.concat([self.box_batting, self.team_box_batting], ignore_index=True)
        self.box_batting = self.box_batting.append(self.team_box_batting, ignore_index=True)
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
        return
