import pandas as pd


class BaseballData:
    def __init__(self, seasons=[2022]):
        # pybaseball_cache.enable()
        self.seasons = seasons
        self.pitching_data = None
        self.batting_data = None
        return

    def get_seasons(self):
        for season in self.seasons:
            pitching_data = pd.read_csv(str(season) + " player-stats-Pitching.csv")
            pitching_data['Season'] = str(season)
            pitching_data['OBP'] = pitching_data['WHIP'] / (3 + pitching_data['WHIP'])  # batters reached / number faced
            batting_data = pd.read_csv(str(season) + " player-stats-Batters.csv")
            batting_data['Season'] = str(season)
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
    print(baseball_data.batting_data[baseball_data.batting_data.Team == "MIN"])
    print(baseball_data.batting_data)
