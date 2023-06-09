import random

import pandas as pd

import bbgame
import bbstats
import numpy as np


class BaseballSeason:
    def __init__(self, load_seasons, new_season, team_list, season_length_limit=0, min_games=0, series_length=1,
                 rotation_len=5):
        self.season_length_limit = season_length_limit  # zero mean there is no limit, based on schedule parameters
        self.min_games = min_games
        self.series_length = series_length
        self.rotation_len = rotation_len
        self.team_season_df = None
        self.team_season_pitching_df = None
        self.load_seasons = load_seasons  # pull base data across for what seasons
        self.new_season = new_season
        self.teams = team_list
        self.schedule = []
        self.create_schedule()  # set schedule
        self.baseball_data = bbstats.BaseballStats(load_seasons=self.load_seasons, new_season=new_season)
        self.team_win_loss = {}
        for team in self.teams:
            self.team_win_loss.update({team: [0, 0]})  # set team win loss to 0, 0
        return

    def create_schedule(self):
        # day schedule in format  ([['MIL', 'COL'], ['PIT', 'CIN'], ['CHC', 'STL']])  # test schedule
        for game_day in range(0, len(self.teams)-1):  # setup each team play all other teams one time
            random.shuffle(self.teams)  # randomize team match ups. may repeat, deal with it
            day_schedule = []
            for ii in range(0, len(teams), 2):  # select home and away without repeating a team, inc by 2 for away/home
                day_schedule.append([teams[ii], teams[ii+1]])  # build schedule for one day

            for series_game in range(0, self.series_length):  # repeat day schedule to build series
                self.schedule.append(day_schedule)  # add day schedule to full schedule

        # schedule is built, check against minimums and repeat if needed, recursive call to build out further
        if len(self.schedule) < self.min_games:
            self.create_schedule()  # recursive call to add more games to get over minimum
        return

    def print_day_schedule(self, day):
        day_schedule = self.schedule[day]
        print(f'Games for day {day + 1}:')
        for game in day_schedule:
            print(f'{game[0]} vs. {game[1]}')
        print('')
        return

    def print_standings(self):
        teaml, winl, lossl = [], [], []
        for team in self.team_win_loss:
            win_loss = self.team_win_loss[team]
            teaml.append(team)
            winl.append(win_loss[0])
            lossl.append(win_loss[1])
        df = pd.DataFrame({'Team': teaml, 'Win': winl, 'Loss': lossl})
        print(df.sort_values('Win', ascending=False).to_string(index=False, justify='center'))
        print('')
        return

    def update_win_loss(self, away_team_name, home_team_name, win_loss):
        self.team_win_loss[away_team_name] = list(
            np.add(np.array(self.team_win_loss[away_team_name]), np.array(win_loss[0])))
        self.team_win_loss[home_team_name] = list(
            np.add(np.array(self.team_win_loss[home_team_name]), np.array(win_loss[1])))
        return

    def sim_season(self, chatty=True, print_box_score=True):
        print(f'{self.new_season} will be {len(self.schedule)} games in length.')
        print(f'Full schedule of games: {self.schedule}')
        for season_day_num in range(0, len(self.schedule)):  # loop from 0 to len of schedule - 1 end pt not included
            if self.season_length_limit != 0 and season_day_num + 1 > self.season_length_limit:  # stop if exceeds limit
                break
            self.print_day_schedule(season_day_num)
            todays_games = self.schedule[season_day_num]
            for match_up in todays_games:
                print(f'Playing: {match_up[0]} away against {match_up[1]}')
                game = bbgame.Game(away_team_name=match_up[0], home_team_name=match_up[1],
                                   baseball_data=self.baseball_data, game_num=season_day_num, rotation_len=5,
                                   print_lineup=False, chatty=False, print_box_score=False)
                score, inning, win_loss_list = game.sim_game()
                self.update_win_loss(away_team_name=match_up[0], home_team_name=match_up[1], win_loss=win_loss_list)
                print(f'Final: {match_up[0]} {score[0]} {match_up[1]} {score[1]}')
                self.baseball_data.game_results_to_season(batting_box_score=game.teams[0].box_score.game_batting_stats,
                                                         pitching_box_score=game.teams[0].box_score.game_pitching_stats)
                self.baseball_data.game_results_to_season(batting_box_score=game.teams[1].box_score.game_batting_stats,
                                                         pitching_box_score=game.teams[1].box_score.game_pitching_stats)
                print('')
                # end of game
            # end of all games for one day
            print(f'Standings for Day {season_day_num + 1}:')
            self.print_standings()
        # end season
        self.baseball_data.update_season_stats()
        print(f'\n\n****** End of {self.new_season} season ******')
        print(f'{self.new_season} Season Standings:')
        self.print_standings()

        print(f'\n{self.new_season} Season Stats')
        self.baseball_data.print_current_season(teams=self.teams)  # season totals
        return


# test a number of games
if __name__ == '__main__':
    seasons = [2022]
    teams = ['CHC', 'CIN', 'COL', 'MIL', 'PIT', 'STL']  # included COL for balance in scheduling
    bbseason23 = BaseballSeason(load_seasons=seasons, new_season=2023, team_list=teams, season_length_limit=5,
                                min_games=30, series_length=3, rotation_len=5)
    bbseason23.sim_season(chatty=False, print_box_score=False)
