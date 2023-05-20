import pandas as pd


class BaseballStats:
    def __init__(self, load_seasons, new_season):
        self.numeric_bcols = ['G', 'AB', 'R', 'H', '2B', '3B', 'HR', 'RBI', 'SB', 'CS', 'BB', 'SO', 'SH', 'SF', 'HBP',
                              'AVG', 'OBP', 'SLG', 'OPS']
        self.numeric_pcols = ['G', 'GS', 'CG', 'SHO', 'IP', 'H', 'ER', 'K', 'BB', 'HR', 'W', 'L',
                              'SV', 'BS', 'HLD', 'ERA', 'WHIP']

        self.load_seasons = load_seasons
        self.new_season = new_season
        self.pitching_data = None
        self.batting_data = None
        self.new_season_pitching_data = None
        self.new_season_batting_data = None
        self.get_seasons()
        self.create_new_season_from_existing()
        return

    def get_seasons(self):
        if self.pitching_data is None or self.batting_data is None:  # need to read data... else skip as cached
            for season in self.load_seasons:
                pitching_data = pd.read_csv(str(season) + " player-stats-Pitching.csv")
                pitching_data['Season'] = str(season)
                pitching_data['OBP'] = pitching_data['WHIP'] / (3 + pitching_data['WHIP'])  # batters reached / number faced
                pitching_data['Total_OB'] = pitching_data['H'] + pitching_data['BB']  # + pitching_data['HBP']
                pitching_data['Total_Outs'] = pitching_data['IP'] * 3  # 3 outs per inning

                batting_data = pd.read_csv(str(season) + " player-stats-Batters.csv")
                batting_data['Season'] = str(season)
                batting_data['Total_OB'] = batting_data['H'] + batting_data['BB'] + batting_data['HBP']
                batting_data['Total_Outs'] = batting_data['AB'] - batting_data['H'] + batting_data['HBP']

                if self.pitching_data is None:
                    self.pitching_data = pitching_data
                    self.batting_data = batting_data
                else:
                    self.pitching_data = pd.concat([self.pitching_data, pitching_data])
                    self.batting_data = pd.concat([self.batting_data, batting_data])
        return

    def create_new_season_from_existing(self):
        if self.pitching_data is None or self.batting_data is None:
            raise Exception('load at least one season of pitching and batting')

        self.new_season_pitching_data = self.pitching_data.copy()
        self.new_season_pitching_data[self.numeric_pcols] = 0
        self.new_season_pitching_data[['OBP', 'Total_OB', 'Total_Outs']] = 0  # zero out calculated fields
        self.new_season_pitching_data['Season'] = str(self.new_season)
        self.new_season_pitching_data.fillna(0)

        self.new_season_batting_data = self.batting_data.copy()
        self.new_season_batting_data[self.numeric_bcols] = 0
        self.new_season_batting_data[['Total_OB', 'Total_Outs']] = 0  # zero out calculated fields
        self.new_season_batting_data['Season'] = str(self.new_season)
        self.new_season_batting_data = self.new_season_batting_data.fillna(0)
        # print(self.new_season_batting_data.to_string())
        return

    def update_current_season(self, batting_box_score, pitching_box_score):
        numeric_cols = self.numeric_bcols
        for index, row in batting_box_score.iterrows():
            new_row = batting_box_score.loc[index][numeric_cols] + self.new_season_batting_data.loc[index][numeric_cols]
            self.new_season_batting_data.loc[index, numeric_cols] = new_row
            # print(self.new_season_batting_data.loc[index].to_string())
        numeric_cols = self.numeric_pcols
        for index, row in pitching_box_score.iterrows():
            new_row = pitching_box_score.loc[index][numeric_cols] + \
                      self.new_season_pitching_data.loc[index][numeric_cols]
            self.new_season_pitching_data.loc[index, numeric_cols] = new_row
        return

    def print_current_season(self, team):
        print(self.new_season_batting_data[self.new_season_batting_data.Team == team].to_string(justify='center'))
        print(self.new_season_pitching_data[self.new_season_pitching_data.Team == team].to_string(justify='center'))
        return


# static function start
def trunc_col(df_n, d):
    return (df_n*10**d).astype(int)/10**d


def team_batting_stats(df):
    df['AVG'] = trunc_col(df['H'] / df['AB'], 3)
    df['OBP'] = trunc_col((df['H'] + df['BB'] + df['HBP']) / (df['AB'] + df['BB'] + df['HBP']), 3)
    df['SLG'] = trunc_col(((df['H'] - df['2B'] - df['3B'] - df['HR']) + df['2B'] * 2 + df['3B'] * 3 + df['HR'] * 4) / df['AB'], 3)
    df['OPS'] = trunc_col(df['OBP'] + df['SLG'] + df['SLG'], 3)
    return df


def team_pitching_stats(df):
    # missing data
    # hbp is 0, 2b are 0, 3b are 0
    df['IP'] = trunc_col(df['IP'] + .0001, 3)
    df_ab = df['IP'] * 3 + df['H']
    df['AVG'] = trunc_col(df['H'] / df_ab, 3)
    df['OBP'] = trunc_col((df['H'] + df['BB'] + 0) / (df_ab + df['BB'] + 0), 3)
    df['SLG'] = trunc_col(((df['H'] - 0 - 0 - df['HR']) + 0 * 2 + 0 * 3 + df['HR'] * 4) / df_ab, 3)
    df['OPS'] = trunc_col(df['OBP'] + df['SLG'] + df['SLG'], 3)
    return df


if __name__ == '__main__':
    baseball_data = BaseballStats(load_seasons=[2022], new_season=2023)
    baseball_data.get_seasons()
    baseball_data.create_new_season_from_existing()

    print(*baseball_data.pitching_data.columns)
    print(*baseball_data.batting_data.columns)
    print(baseball_data.batting_data[baseball_data.batting_data.Team == "MIN"].to_string(justify='center'))
    print(baseball_data.pitching_data[baseball_data.pitching_data.Team == "MIN"].to_string(justify='center'))
    print(baseball_data.batting_data.Team.unique())
