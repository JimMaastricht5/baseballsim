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
                 season_length: int = 6, series_length: int = 3,
                 rotation_len: int = 5, include_leagues: list = None, season_interactive: bool = False,
                 season_print_lineup_b: bool = False, season_print_box_score_b: bool = False,
                 season_chatty: bool = False, season_team_to_follow: str = None,
                 load_batter_file: str = 'stats-pp-Batting.csv',
                 load_pitcher_file: str = 'stats-pp-Pitching.csv',
                 debug: bool = False) -> None:
        """
        :param load_seasons: list of seasons to load for stats, can blend multiple seasons
        :param new_season: int value representing the year of the new season can be the same as one of the loads
        :param team_list: list of teams to use in the simulations, optional param
        :param season_length: number of games to be played for the season
        :param series_length: series is usually 3, the default is one for testing
        :param rotation_len: number of starters to rotate, default is 5
        :param include_leagues: list of leagues to include in the season
        :param season_interactive: if true the sim pauses after each day
        :param season_print_lineup_b: if true print lineups
        :param season_print_box_score_b: if true print box scores
        :param season_chatty: if true provide more detail
        :param season_team_to_follow: if none skip otherwise follow this team in gory detail
        :param load_batter_file: name of the file with batter data, year will be added to the front of the text
        :param load_pitcher_file: name of the file for the pitcher data, year will be added to the front of the text
        :param debug: like the name says.... True prints more stuff
        :return: None
        """
        self.season_day_num = 0  # set to first day of the season
        self.season_length = season_length
        self.series_length = series_length
        self.rotation_len = rotation_len
        self.team_season_df = None
        self.team_season_pitching_df = None
        self.load_seasons = load_seasons  # pull base data across for what seasons
        self.new_season = new_season
        self.schedule = []
        self.interactive = season_interactive
        self.print_lineup_b = season_print_lineup_b
        self.print_box_score_b = season_print_box_score_b
        self.season_chatty = season_chatty
        self.team_to_follow = season_team_to_follow
        self.debug = debug
        self.baseball_data = bbstats.BaseballStats(load_seasons=self.load_seasons, new_season=new_season,
                                                   include_leagues=include_leagues, load_batter_file=load_batter_file,
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
        if len(self.schedule) < self.season_length:
            self.create_schedule()  # recursive call to add more games to get over minimum
        elif len(self.schedule) > self.season_length:
            self.schedule = self.schedule[0:self.season_length]
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

    def sim_start(self) -> None:
        """
        Print start of season info
        :return: None
        """
        print(f'{self.new_season} will have {len(self.schedule)} games per team. \n')
        if self.season_chatty:
            print(f'Full schedule of games: {self.schedule}')
        return

    def sim_end(self) -> None:
        """
        print end of season info and update end of season stats
        :return: None
        """
        self.baseball_data.update_season_stats()
        print(f'\n\n****** End of {self.new_season} season ******')
        print(f'{self.new_season} Season Standings:')
        self.print_standings()
        print(f'\n{self.new_season} Season Stats')
        if self.team_to_follow != '':
            self.baseball_data.print_current_season(teams=[self.team_to_follow], summary_only_b=False)
        self.baseball_data.print_current_season(teams=self.teams, summary_only_b=not self.season_chatty)
        return

    def sim_day(self, season_day_num: int) -> None:
        """
        sim one day of games across the league
        :return: None
        """
        self.print_day_schedule(season_day_num)
        todays_games = self.schedule[season_day_num]
        self.baseball_data.new_game_day()  # update rest and injury data for a new day, print DL injury list
        for match_up in todays_games:  # run all games for a day, day starts at zero
            if 'OFF DAY' not in match_up:  # not an off day
                print(f'Playing day #{season_day_num + 1}: {match_up[0]} away against {match_up[1]}')
                game = bbgame.Game(away_team_name=match_up[0], home_team_name=match_up[1],
                                   baseball_data=self.baseball_data, game_num=season_day_num,
                                   rotation_len=self.rotation_len, print_lineup=self.print_lineup_b,
                                   chatty=self.season_chatty, print_box_score_b=self.print_box_score_b,
                                   interactive=self.interactive)
                score, inning, win_loss_list = game.sim_game(team_to_follow=self.team_to_follow)
                self.update_win_loss(away_team_name=match_up[0], home_team_name=match_up[1], win_loss=win_loss_list)
                print(f'Final: {match_up[0]} {score[0]} {match_up[1]} {score[1]}')
                self.baseball_data.game_results_to_season(box_score_class=game.teams[AWAY].box_score)
                self.baseball_data.game_results_to_season(box_score_class=game.teams[HOME].box_score)
                print('')
                # end of game
            # end of all games for one day
        return

    def sim_next_day(self) -> None:
        """
        sims the next day for a season
        :return: None
        """
        self.sim_day(season_day_num=self.season_day_num)
        print(f'Standings for Day {self.season_day_num + 1}:')
        self.print_standings()
        self.season_day_num = self.season_day_num + 1
        return

    def sim_full_season(self) -> None:
        """
        function drives overall sim for entire season
        :return: None
        """
        self.sim_start()
        while self.season_day_num <= len(self.schedule) - 1:  # loop over every day and every game scheduled that day
            self.sim_next_day()

        self.sim_end()
        return


class MultiBaseballSeason:
    def __init__(self, load_seasons: List[int], new_season: int, team_list: Optional[list] = None,
                 season_length: int = 6, series_length: int = 3,
                 rotation_len: int = 5, include_leagues: list = None, season_interactive: bool = False,
                 season_print_lineup_b: bool = False, season_print_box_score_b: bool = False,
                 season_chatty: bool = False, season_team_to_follow: str = None,
                 load_batter_file: str = 'stats-pp-Batting.csv',
                 load_pitcher_file: str = 'stats-pp-Pitching.csv',
                 debug: bool = False) -> None:
        """
                :param load_seasons: list of seasons to load for stats, can blend multiple seasons
                :param new_season: int value representing the year of the new season can be the same as one of the loads
                :param team_list: list of teams to use in the simulations, optional param
                :param season_length: number of games to be played for the season
                :param series_length: series is usually 3, the default is one for testing
                :param rotation_len: number of starters to rotate, default is 5
                :param include_leagues: leagues to include in season, each league will get its own season
                :param season_interactive: if true the sim pauses after each day
                :param season_print_lineup_b: if true print lineups
                :param season_print_box_score_b: if true print box scores
                :param season_chatty: if true provide more detail
                :param season_team_to_follow: if none skip otherwise follow this team in gory detail
                :param load_batter_file: name of the file with batter data, year will be added to the front of the text
                :param load_pitcher_file: name of the file for the pitcher data, year will be added to the front of name
                :param debug: like the name says.... True prints more stuff
                :return: None
                """
        self.season_day_num = 0  # set to first day of the season
        self.load_seasons = load_seasons  # pull base data across for what seasons
        self.new_season = new_season
        self.team_list = team_list
        self.season_length = season_length
        self.series_length = series_length
        self.rotation_len = rotation_len
        self.include_leagues = include_leagues
        self.interactive = season_interactive
        self.print_lineup_b = season_print_lineup_b
        self.print_box_score_b = season_print_box_score_b
        self.season_chatty = season_chatty
        self.team_to_follow = season_team_to_follow
        self.load_batter_file = load_batter_file
        self.load_pitcher_file = load_pitcher_file
        self.debug = debug

        self.bbseason_a = BaseballSeason(load_seasons=self.load_seasons, new_season=self.new_season,
                                         season_length=self.season_length, series_length=self.season_length,
                                         rotation_len=self.rotation_len,
                                         include_leagues=['NL'],
                                         season_interactive=self.interactive,
                                         season_chatty=self.season_chatty, season_print_lineup_b=self.print_lineup_b,
                                         season_print_box_score_b=self.print_box_score_b,
                                         season_team_to_follow=self.team_to_follow,
                                         load_batter_file=self.load_batter_file,
                                         load_pitcher_file=self.load_pitcher_file,
                                         debug=self.debug)

        self.bbseason_b = BaseballSeason(load_seasons=self.load_seasons, new_season=self.new_season,
                                         season_length=self.season_length, series_length=self.season_length,
                                         rotation_len=self.rotation_len,
                                         include_leagues=['AL'],
                                         season_interactive=self.interactive,
                                         season_chatty=self.season_chatty, season_print_lineup_b=self.print_lineup_b,
                                         season_print_box_score_b=self.print_box_score_b,
                                         season_team_to_follow=self.team_to_follow,
                                         load_batter_file=self.load_batter_file,
                                         load_pitcher_file=self.load_pitcher_file,
                                         debug=self.debug)
        return

    def sim_day_for_both_seasons(self):
        self.bbseason_a.sim_start()
        self.bbseason_b.sim_start()

        self.bbseason_a.sim_next_day()
        self.bbseason_b.sim_next_day()

        self.bbseason_a.sim_next_day()
        self.bbseason_b.sim_next_day()

        self.bbseason_a.sim_next_day()
        self.bbseason_b.sim_next_day()

        self.bbseason_a.sim_end()
        self.bbseason_b.sim_end()
        return


# test a number of games
if __name__ == '__main__':
    startdt = datetime.datetime.now()

    # full season
    # num_games = 162 - 42  # 42 games already played
    num_games = 3
    interactive = False
    # team_to_follow = bbseason23.teams[0]  # follow the first team in the random set
    # my_teams_to_follow = 'MIL'  # or follow no team
    my_teams_to_follow = 'MIL'
    bbseason23 = MultiBaseballSeason(load_seasons=[2024], new_season=2024,
                                     season_length=num_games, series_length=3, rotation_len=5,
                                     include_leagues=['AL', 'NL'],
                                     season_interactive=interactive,
                                     season_chatty=False, season_print_lineup_b=False,
                                     season_print_box_score_b=False, season_team_to_follow=my_teams_to_follow,
                                     load_batter_file='stats-pp-Batting.csv',  # 'random-stats-pp-Batting.csv',
                                     load_pitcher_file='stats-pp-Pitching.csv',  # 'random-stats-pp-Pitching.csv'
                                     debug=False)

    bbseason23.sim_day_for_both_seasons()
    # handle full season
    # bbseason23.sim_full_season()

    # or do it yourself for 3 days
    # bbseason23.sim_start()
    # bbseason23.sim_next_day()
    # bbseason23.sim_next_day()
    # bbseason23.sim_next_day()
    # bbseason23.sim_end()

    print(startdt)
    print(datetime.datetime.now())
