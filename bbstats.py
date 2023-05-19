import pandas as pd


class BaseballStats:
    def __init__(self, load_seasons, new_season):
        self.load_seasons = load_seasons
        self.new_season = new_season
        self.pitching_data = None
        self.batting_data = None
        self.new_season_pitching_data = None
        self.new_season_batting_data = None
        self.get_seasons()
        self.create_new_season_from_existing()

        self.numeric_batting_cols = ['G', 'AB', 'R', 'H', '2B', '3B', 'HR', 'RBI', 'SB', 'CS', 'BB', 'SO', 'SH', 'SF',
                                     'HBP']
        self.numeric_pitching_cols = ['GS', 'CG', 'SHO', 'IP', 'H', 'ER', 'K', 'BB', 'HR', 'W', 'L',
                                      'SV', 'BS', 'HLD', 'ERA', 'WHIP']
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
        self.new_season_pitching_data = self.new_season_pitching_data.applymap(zero_out_numbers)
        self.new_season_pitching_data['Season'] = str(self.new_season)
        self.new_season_pitching_data.fillna(0)

        self.new_season_batting_data = self.batting_data.copy()
        self.new_season_batting_data = self.new_season_batting_data.applymap(zero_out_numbers)
        self.new_season_batting_data['Season'] = str(self.new_season)
        self.new_season_batting_data.fillna(0)
        print(self.new_season_batting_data.to_string())
        return

    def update_current_season(self, batting_box_score, pitching_box_score):
        print(batting_box_score.to_string())
        print(self.new_season_batting_data.to_string())
        df_sum = self.new_season_batting_data[self.numeric_batting_cols] + batting_box_score[self.numeric_batting_cols]
        print(df_sum.to_string())
        self.new_season_batting_data = pd.concat([self.new_season_batting_data.drop(self.numeric_batting_cols, axis=1), df_sum], axis=1)
        print(self.new_season_batting_data.to_string())

        df_sum = self.new_season_pitching_data[self.numeric_pitching_cols] + pitching_box_score[self.numeric_pitching_cols]
        self.new_season_pitching_data = pd.concat(
            [self.new_season_pitching_data.drop(self.numeric_pitching_cols, axis=1), df_sum], axis=1)
        return

    def print_season(self, season, team):
        if season == self.new_season:
            dfb = self.new_season_batting_data
            dfp = self.new_season_pitching_data
        else:
            dfb = self.batting_data
            dfp = self.pitching_data

        print(dfb[dfb.Team == team].to_string(justify='center'))
        return


# static function start
def zero_out_numbers(x):
    if pd.api.types.is_numeric_dtype(x):
        return 0
    return x


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
