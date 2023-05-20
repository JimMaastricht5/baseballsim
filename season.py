import random

import bbgame
import bbstats
import numpy as np


class BaseballSeason:
    def __init__(self, load_seasons, new_season, team_list, season_length_limit=0):
        self.season_length_limit = season_length_limit
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
        for game_day in range(0, len(self.teams)-1):  # each team must play all other teams one time
            random.shuffle(self.teams)  # randomize team match ups. may repeat, deal with it
            day_schedule = []
            for ii in range(0, len(teams), 2):  # select home and away without repeating a team
                day_schedule.append([teams[ii], teams[ii+1]])
            self.schedule.append(day_schedule)  # add day schedule to full schedule
        return

    def update_win_loss(self, away_team_name, home_team_name, win_loss):
        self.team_win_loss[away_team_name] = list(
            np.add(np.array(self.team_win_loss[away_team_name]), np.array(win_loss[0])))
        self.team_win_loss[home_team_name] = list(
            np.add(np.array(self.team_win_loss[home_team_name]), np.array(win_loss[1])))
        return

    def sim_season(self, chatty=True):
        print(f'Full schedule of games: {self.schedule}')
        for season_day_num in range(0, len(self.schedule)-1):
            if self.season_length_limit != 0 and season_day_num + 1 > self.season_length_limit:  # stop if exceeds limit
                break
            todays_games = self.schedule[season_day_num]
            print(f"Today's games: {todays_games}")
            for match_up in todays_games:
                print(f'Playing: {match_up}')
                game = bbgame.Game(away_team_name=match_up[0], home_team_name=match_up[1],
                                   baseball_data=self.baseball_data)
                score, inning, win_loss_list = game.sim_game(chatty=chatty)
                self.update_win_loss(away_team_name=match_up[0], home_team_name=match_up[1], win_loss=win_loss_list)
                print(f'Score was: {match_up[0]} {score[0]} {match_up[1]} {score[1]}')
                self.baseball_data.update_current_season(batting_box_score=game.teams[0].box_score.game_batting_stats,
                                                         pitching_box_score=game.teams[0].box_score.game_pitching_stats)
                # end of game

            # end of all games for one day
            print(f'Win Loss records after day {season_day_num + 1}: {self.team_win_loss}')
            self.baseball_data.print_current_season(team='MIL')  # running totals
        # end season
        return


# test a number of games
if __name__ == '__main__':
    seasons = [2022]
    teams = ['CHC', 'CIN', 'COL', 'MIL', 'PIT', 'STL']  # included COL for balance in scheduling
    bbseason23 = BaseballSeason(load_seasons=seasons, new_season=2023, team_list=teams, season_length_limit=1)
    bbseason23.sim_season(chatty=False)
