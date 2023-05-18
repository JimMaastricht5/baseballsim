import pandas as pd


class BaseballStats:
    def __init__(self, seasons=[2022]):
        self.seasons = seasons
        self.pitching_data = None
        self.batting_data = None
        self.get_seasons()
        return

    def get_seasons(self):
        if self.pitching_data is None or self.batting_data is None:  # need to read data... else skip as cached
            for season in self.seasons:
                pitching_data = pd.read_csv(str(season) + " player-stats-Pitching.csv")
                pitching_data['Season'] = str(season)
                pitching_data['OBP'] = pitching_data['WHIP'] / (3 + pitching_data['WHIP'])  # batters reached / number faced
                pitching_data['Total_OB'] = pitching_data['H'] + pitching_data['BB']  # + pitching_data['HBP']
                pitching_data['Total_Outs'] = pitching_data['IP'] * 3  # 3 outs per inning
                # pitching_data.index.rename('PlayerNum', inplace=True)
                # print(pitching_data)

                batting_data = pd.read_csv(str(season) + " player-stats-Batters.csv")
                batting_data['Season'] = str(season)
                batting_data['Total_OB'] = batting_data['H'] + batting_data['BB'] + batting_data['HBP']
                batting_data['Total_Outs'] = batting_data['AB'] - batting_data['H'] + batting_data['HBP']
                # batting_data.index.rename('PlayerNum', inplace=True)

                if self.pitching_data is None:
                    self.pitching_data = pitching_data
                    self.batting_data = batting_data
                else:
                    self.pitching_data = pd.concat([self.pitching_data, pitching_data])
                    self.batting_data = pd.concat([self.batting_data, batting_data])
        return


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
    baseball_data = BaseballStats(seasons=[2022])
    baseball_data.get_seasons()

    print(*baseball_data.pitching_data.columns)
    print(*baseball_data.batting_data.columns)
    print(baseball_data.batting_data[baseball_data.batting_data.Team == "MIN"].to_string(justify='center'))
    print(baseball_data.pitching_data[baseball_data.pitching_data.Team == "MIN"].to_string(justify='center'))
    print(baseball_data.batting_data.Team.unique())
