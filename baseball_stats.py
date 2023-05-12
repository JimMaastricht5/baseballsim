import pandas as pd


class BaseballData:
    def __init__(self, seasons=[2022]):
        self.seasons = seasons
        self.pitching_data = None
        self.batting_data = None
        return

    def get_seasons(self):
        for season in self.seasons:
            pitching_data = pd.read_csv(str(season) + " player-stats-Pitching.csv")
            pitching_data['Season'] = str(season)
            pitching_data['OBP'] = pitching_data['WHIP'] / (3 + pitching_data['WHIP'])  # batters reached / number faced
            pitching_data['Total_OB'] = pitching_data['H'] + pitching_data['BB'] # + pitching_data['HBP']
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


if __name__ == '__main__':
    baseball_data = BaseballData(seasons=[2022])
    baseball_data.get_seasons()

    print(*baseball_data.pitching_data.columns)
    print(*baseball_data.batting_data.columns)
    print(baseball_data.batting_data[baseball_data.batting_data.Team == "MIN"].to_string(index=False, justify='center'))
    print(baseball_data.pitching_data[baseball_data.pitching_data.Team == "MIN"].to_string(index=False, justify='center'))

