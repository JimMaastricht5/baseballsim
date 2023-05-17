import random

import bbgame
import bbstats
import numpy as np


class BaseballSeason:
    def __init__(self, season_list, team_list, season_length_limit=0):
        self.season_length_limit = season_length_limit
        self.team_season_df = None
        self.team_season_pitching_df = None
        self.seasons = season_list  # pull base data across for what seasons
        self.teams = team_list
        self.schedule = []
        self.create_schedule()  # set schedule
        self.baseball_data = bbstats.BaseballStats(seasons=self.seasons)
        self.team_win_loss = {}
        for team in self.teams:
            self.team_win_loss.update({team: [0, 0]})  # set team win loss to 0, 0
        return

    def create_schedule(self):
        for game_day in range(0, len(self.teams)-1):  # each team must play all other teams one time
            random.shuffle(self.teams)  # randomize team match ups. may repeat, deal with it
            day_schedule = []
            for ii in range(0, len(teams), 2):  # select home and away without repeating a team
                day_schedule.append([teams[ii], teams[ii+1]])
            self.schedule.append(day_schedule)  # add day schedule to full schedule
        # self.schedule.append([['MIL', 'COL'], ['PIT', 'CIN'], ['CHC', 'STL']])  # test schedule
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
                # end of game

            # end of all games for one day
            print(f'Win Loss records after day {season_day_num + 1}: {self.team_win_loss}')
            # if self.team_season_df is None:
            #     self.team_season_df = game.teams[0].team_box_score.box_batting
            #     self.team_season_pitching_df = game.teams[0].team_box_score.box_pitching
            # else:
            #     col_list = ['G', 'AB', 'R', 'H', '2B', '3B', 'HR', 'RBI', 'SB', 'CS', 'BB', 'SO', 'SH', 'SF', 'HBP']
            #     self.team_season_df = self.team_season_df[col_list].add(game.teams[0].
            #                                                               team_box_score.box_batting[col_list])
            #     self.team_season_df['Player'] = game.teams[0].team_box_score.box_batting['Player']
            #     self.team_season_df['Team'] = game.teams[0].team_box_score.box_batting['Team']
            #     self.team_season_df['Pos'] = game.teams[0].team_box_score.box_batting['Pos']
            #
            #     col_list = ['G', 'GS', 'CG', 'SHO', 'IP', 'H', 'ER', 'K', 'BB', 'HR', 'W', 'L', 'SV', 'BS', 'HLD']
            #     self.team_season_pitching_df = self.team0_season_pitching_df[col_list].add(
            #         game.teams[0].team_box_score.box_pitching[col_list])
            #     self.team_season_pitching_df['Player'] = game.teams[0].team_box_score.box_pitching['Player']
            #     self.team_season_pitching_df['Team'] = game.teams[0].team_box_score.box_pitching['Team']

            # print(f'{self.away_team} season : {self.season_win_loss[0][0]} W and {self.season_win_loss[0][1]} L')
            # print(f'{self.home_team} season : {self.season_win_loss[1][0]} W and {self.season_win_loss[1][1]} L')

        # end of season
        # team0_season_df = bbstats.team_batting_stats(self.team0_season_df)
        # print(team0_season_df.to_string(index=False, justify='center'))
        # print('')
        # team0_season_pitching_df = bbstats.team_pitching_stats(self.team0_season_pitching_df)
        # print(team0_season_pitching_df.to_string(index=False, justify='center'))
        # end season
        return


# test a number of games
if __name__ == '__main__':
    seasons = [2022]
    teams = ['CHC', 'CIN', 'COL', 'MIL', 'PIT', 'STL']  # included COL for balance in scheduling
    bbseason23 = BaseballSeason(season_list=seasons, team_list=teams, season_length_limit=1)  # mult of teams
    bbseason23.sim_season(chatty=False)
