from pybaseball import pitching_stats
from pybaseball import batting_stats
from pybaseball import cache as pybaseball_cache


# class Pitchers:
#     def __init__(self, pitching_data, baseline_season=2022):
#         self.pitching_data = pitching_data
#         self.baseline_season = baseline_season
#         self.pitchers = None
#         return
#
#     def set_team(self, team_name):
#         self.pitchers = self.pitching_data[self.pitching_data["Team"] == team_name]
#         return


class BaseballData:
    def __init__(self, seasons=[2022]):
        pybaseball_cache.enable()
        self.seasons = seasons
        self.pitching_data = None
        self.batting_data = None
        return

    def get_seasons(self):
        if len(self.seasons) == 1:
            self.pitching_data = pitching_stats(self.seasons[0])
            self.batting_data = batting_stats(self.seasons[0])
        else:
            self.pitching_data = pitching_stats(self.seasons[0], self.seasons[1])
            self.batting_data = batting_stats(self.seasons[0], self.seasons[1])
        return


if __name__ == '__main__':
    pybaseball_cache.enable()
    baseball_data = BaseballData(seasons=[2021, 2022])
    baseball_data.get_seasons()

    # home_pitcher = Pitchers(baseball_data.pitching_data)

    # print(type(baseball_data.pitching_data))
    # print(baseball_data.pitching_data.shape)
    print(*baseball_data.pitching_data.columns)
    # print(baseball_data.pitching_data.head)
    # home_pitcher.set_team("MIL")

    # print(baseball_data.batting_data.shape)
    print(*baseball_data.batting_data.columns)
    # print(baseball_data.batting_data.head)
