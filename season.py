# MIT License
#
# 2024 Jim Maastricht
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
#
# JimMaastricht5@gmail.com
import datetime
import random
import pandas as pd
import bbgame
import bbstats
import numpy as np
from typing import List, Optional

AWAY = 0
HOME = 1


class BaseballSeason:
    def __init__(self, load_seasons: List[int], new_season: int, team_list: Optional[list] = None,
                 season_length_limit: int = 0,
                 min_games: int = 0, series_length: int = 1,
                 rotation_len: int = 5, only_nl_b: bool = False, interactive: bool = False,
                 load_batter_file: str = 'stats-pp-Batting.csv',
                 load_pitcher_file: str = 'stats-pp-Pitching.csv') -> None:
        """
        :param load_seasons: list of seasons to load for stats, can blend multiple seasons
        :param new_season: int value representing the year of the new season can be the same as one of the loads
        :param team_list: list of teams to use in the simulations, optional param
        :param season_length_limit: max number of games to sim for the season, hard stop after this day of games
        :param min_games: number of games to be played for the season, can exceed season length, season len overrides
        :param series_length: series is usually 3, the default is one for testing
        :param rotation_len: number of starters to rotate, default is 5
        :param only_nl_b: use only the nl teams
        :param interactive: if true the sim pauses after each day
        :param load_batter_file: name of the file with batter data, year will be added to the front of the text
        :param load_pitcher_file: name of the file for the pitcher data, year will be added to the front of the text
        :return: None
        """
        self.season_length_limit = season_length_limit  # zero mean there is no limit, based on schedule parameters
        self.min_games = min_games
        self.series_length = series_length
        self.rotation_len = rotation_len
        self.team_season_df = None
        self.team_season_pitching_df = None
        self.load_seasons = load_seasons  # pull base data across for what seasons
        self.new_season = new_season
        self.schedule = []
        self.interactive = interactive
        self.baseball_data = bbstats.BaseballStats(load_seasons=self.load_seasons, new_season=new_season,
                                                   only_nl_b=only_nl_b, load_batter_file=load_batter_file,
                                                   load_pitcher_file=load_pitcher_file)
        self.teams = list(self.baseball_data.batting_data.Team.unique()) if team_list == [] or team_list is None \
            else team_list
        if len(self.teams) % 2 == 1:  # odd number of teams
            self.teams.append('OFF DAY')

        self.create_schedule()  # set schedule
        self.team_win_loss = {}
        for team in self.teams:
            self.team_win_loss.update({team: [0, 0]})  # set team win loss to 0, 0
        return

    def create_schedule(self) -> None:
        """
        set the schedule for the seasons using the teams, series length, min games in season, and limit of games
        conflicts sometimes occur between the params, so it is possible for a team to play an extra game
        day schedule in format  ([['MIL', 'COL'], ['PIT', 'CIN'], ['CHC', 'STL']])  # test schedule
        if there are an odd number of teams there may be an "OFF" day in the schedule
        :return: None
        """
        for game_day in range(0, len(self.teams)-1):  # setup each team play all other teams one time
            random.shuffle(self.teams)  # randomize team match ups. may repeat, deal with it
            day_schedule = []
            for ii in range(0, len(self.teams), 2):  # select home and away without repeating a team, inc by 2 away/home
                day_schedule.append([self.teams[ii], self.teams[ii+1]])  # build schedule for one day

            for series_game in range(0, self.series_length):  # repeat day schedule to build series
                self.schedule.append(day_schedule)  # add day schedule to full schedule
        # schedule is built, check against minimums and repeat if needed, recursive call to build out further
        if len(self.schedule) < self.min_games:
            self.create_schedule()  # recursive call to add more games to get over minimum
        return

    def print_day_schedule(self, day: int) -> None:
        """
        prints the schedule for the day passed in
        :param day: integer of the day in season, e.g., 161
        :return: None
        """
        game_str = ''
        day_schedule = self.schedule[day]
        print(f'Games for day {day + 1}:')
        for game in day_schedule:
            if 'OFF DAY' not in game:
                print(f'{game[0]} vs. {game[1]}')
            else:
                game_str = game[0] if game[0] != 'OFF DAY' else game[1]
        if game_str != '':
            print(f'{game_str} has the day off')
        print('')
        return

    def print_standings(self) -> None:
        """
        print the current standings
        :return: None
        """
        teaml, winl, lossl = [], [], []
        for team in self.team_win_loss:
            if team != 'OFF DAY':
                win_loss = self.team_win_loss[team]
                teaml.append(team)
                winl.append(win_loss[0])
                lossl.append(win_loss[1])
        df = pd.DataFrame({'Team': teaml, 'Win': winl, 'Loss': lossl})
        print(df.sort_values('Win', ascending=False).to_string(index=False, justify='center'))
        print('')
        return

    def update_win_loss(self, away_team_name: str, home_team_name: str, win_loss: List[List[int]]) -> None:
        """
        :param away_team_name: name of away team for the game
        :param home_team_name: name of home team for the game
        :param win_loss: list of lists with team name and integer win and loss ['MAD', [1, 0]] is a w for Mad
        :return: None
        """
        self.team_win_loss[away_team_name] = list(
            np.add(np.array(self.team_win_loss[away_team_name]), np.array(win_loss[0])))
        self.team_win_loss[home_team_name] = list(
            np.add(np.array(self.team_win_loss[home_team_name]), np.array(win_loss[1])))
        return

    def sim_day(self, season_day_num: int, print_lineup_b: bool = False, print_box_score_b: bool = False,
                game_chatty: bool = False, team_to_follow: str = '') -> None:
        """
        sim one day of games across the league
        :return: None
        """
        self.print_day_schedule(season_day_num)
        todays_games = self.schedule[season_day_num]
        self.baseball_data.new_game_day()  # update rest and injury data for a new day, print DL injury list
        for match_up in todays_games:  # run all games for a day, day starts at zero
            if 'OFF DAY' not in match_up:  # not an off day
                if team_to_follow in match_up and self.interactive:
                    print(f'Teams stats for day {season_day_num + 1}')
                    if season_day_num > 0:
                        self.baseball_data.print_current_season(teams=[team_to_follow])
                    else:
                        self.baseball_data.print_prior_season(teams=[team_to_follow])
                    pass
                print(f'Playing day #{season_day_num + 1}: {match_up[0]} away against {match_up[1]}')
                game = bbgame.Game(away_team_name=match_up[0], home_team_name=match_up[1],
                                   baseball_data=self.baseball_data, game_num=season_day_num,
                                   rotation_len=self.rotation_len, print_lineup=print_lineup_b,
                                   chatty=game_chatty, print_box_score_b=print_box_score_b,
                                   interactive=self.interactive)
                score, inning, win_loss_list = game.sim_game(team_to_follow=team_to_follow)
                self.update_win_loss(away_team_name=match_up[0], home_team_name=match_up[1], win_loss=win_loss_list)
                print(f'Final: {match_up[0]} {score[0]} {match_up[1]} {score[1]}')
                self.baseball_data.game_results_to_season(box_score_class=game.teams[AWAY].box_score)
                self.baseball_data.game_results_to_season(box_score_class=game.teams[HOME].box_score)
                print('')
                # end of game
            # end of all games for one day
        return

    def sim_full_season(self, season_chatty: bool = False, season_print_lineup_b: bool = False,
                        season_print_box_score_b: bool = False,
                        team_to_follow: str = '', team_to_follow_detail: bool = False) -> None:
        """
        function drives overall sim for the season
        :param season_chatty: prints more or less text to console
        :param season_print_lineup_b: prints the lineup at the start of the game for every game
        :param season_print_box_score_b: prints the box score at the end of every game
        :param team_to_follow: allows the user to follow a team in more detail, overrides the lineup and box bool
        :param team_to_follow_detail: prints entire teams stats for followed teams vs summary level at end of season
        :return:
        """
        print(f'{self.new_season} will have '
              f'{self.season_length_limit if self.season_length_limit != 0 else len(self.schedule)} games per team.')
        # print(f'Full schedule of games: {self.schedule}')

        # loop over every day and every game scheduled that day
        for season_day_num in range(0, len(self.schedule)):  # loop from 0 to len of schedule - 1 end pt not included
            if self.season_length_limit != 0 and season_day_num + 1 > self.season_length_limit:  # stop if exceeds limit
                break

            self.sim_day(season_day_num=season_day_num, print_lineup_b=season_print_lineup_b,
                         print_box_score_b=season_print_box_score_b, game_chatty=season_chatty,
                         team_to_follow=team_to_follow)
            print(f'Standings for Day {season_day_num + 1}:')
            self.print_standings()
            if self.interactive:
                pass  # pause for adjustments here....

        # end season
        self.baseball_data.update_season_stats()
        print(f'\n\n****** End of {self.new_season} season ******')
        print(f'{self.new_season} Season Standings:')
        self.print_standings()
        print(f'\n{self.new_season} Season Stats')
        if team_to_follow != '':
            self.baseball_data.print_current_season(teams=[team_to_follow], summary_only_b=False)  # season for a team
        self.baseball_data.print_current_season(teams=self.teams, summary_only_b=team_to_follow_detail)  # season totals
        return


# test a number of games
if __name__ == '__main__':
    startdt = datetime.datetime.now()

    # full season
    # num_games = 162 - 42  # 42 games already played
    num_games = 5
    only_national_league_teams = False
    interactive_keyboard_pauses = False
    bbseason23 = BaseballSeason(load_seasons=[2024], new_season=2024,
                                season_length_limit=num_games,
                                min_games=num_games, series_length=3, rotation_len=5,
                                only_nl_b=only_national_league_teams,
                                interactive=interactive_keyboard_pauses,
                                load_batter_file='stats-pp-Batting.csv',  # 'random-stats-pp-Batting.csv',
                                load_pitcher_file='stats-pp-Pitching.csv')  # 'random-stats-pp-Pitching.csv'
    # team_to_follow = bbseason23.teams[0]  # follow the first team in the random set
    # my_teams_to_follow = 'MIL'  # or follow no team
    my_teams_to_follow = 'MIL' if 'MIL' in bbseason23.teams else bbseason23.teams[0]
    bbseason23.sim_full_season(season_chatty=False,
                               season_print_lineup_b=False,
                               season_print_box_score_b=False,
                               team_to_follow_detail=False,
                               team_to_follow=my_teams_to_follow)

    print(startdt)
    print(datetime.datetime.now())
