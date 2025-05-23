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
import bbstats
import bbteam
import at_bat
import numpy as np
import random
import bbbaserunners
import datetime
from pandas.core.series import Series
from typing import List, Tuple
import queue
from bblogger import logger

AWAY = 0
HOME = 1


class Game:
    def __init__(self, away_team_name: str = '', home_team_name: str = '', baseball_data=None,
                 game_num: int = 1, rotation_len: int = 5,
                 print_lineup: bool = False, chatty: bool = False, print_box_score_b: bool = False,
                 load_seasons: List[int] = 2023, new_season: int = 2024,
                 starting_pitchers: None = None, starting_lineups: None = None,
                 load_batter_file: str = 'player-stats-Batters.csv',
                 load_pitcher_file: str = 'player-stats-Pitching.csv',
                 interactive: bool = False, show_bench: bool = False, debug: bool = False) -> None:
        """
        class manages the details of an individual game
        :param away_team_name: away team name is a 3 character all caps abbreviation
        :param home_team_name: home team
        :param baseball_data: class with all the baseball data for the league. prior and current season
        :param game_num: game number in season
        :param rotation_len: len of rotation for team or series.  typically 5
        :param print_lineup: true will print the lineup prior to the game
        :param chatty: prints more output to console
        :param print_box_score_b: true prints the final box score
        :param load_seasons: list of integers with years of prior season being used to calc probabilities
        :param new_season: int of new season year
        :param starting_pitchers: optional hashcode for the starting pitchers in a list form [away, home]
        :param starting_lineups: list of dicts with starting lineups in format
            [{647549: 'LF', 239398: 'C', 224423: '1B', 138309: 'DH', 868055: 'CF', 520723: 'SS',
                  299454: '3B', 46074: '2B', 752787: 'RF'}. None] in example none is the home team lineup
        :param load_batter_file: name of files with batter data, will prefix years
        :param load_pitcher_file: name of files with pitcher data, will prefix years
        :param interactive: allows for gaming of the sim, pauses sim at appropriate times for input
        :param show_bench: show the players not in game along with the lineup
        :param debug: prints extra info
        """
        self.game_recap = ''
        if baseball_data is None:
            self.baseball_data = bbstats.BaseballStats(load_seasons=load_seasons, new_season=new_season,
                                                       load_batter_file=load_batter_file,
                                                       load_pitcher_file=load_pitcher_file)
        else:
            self.baseball_data = baseball_data
        if away_team_name != '' and home_team_name != '':
            self.team_names = [away_team_name, home_team_name]
        else:
            self.team_names = random.sample(list(self.baseball_data.batting_data.Team.unique()), 2)
        self.game_num = game_num  # number of games into season
        self.rotation_len = rotation_len  # number of starting pitchers to rotate over
        self.chatty = chatty
        self.print_box_score_b = print_box_score_b
        logger.debug(f"Initializing Game: {away_team_name} vs {home_team_name}, game #{game_num}")
        if starting_pitchers is None:
            starting_pitchers = [None, None]
        self.starting_pitchers = starting_pitchers  # can use if you want to sim the same two starters repeatedly
        if starting_lineups is None:
            starting_lineups = [None, None]
        self.starting_lineups = starting_lineups  # is a list of two dict, each dict is in batting order with field pos

        self.teams = []  # keep track of away in pos 0 and home team in pos 1
        self.teams.insert(AWAY, bbteam.Team(team_name=self.team_names[AWAY], baseball_data=self.baseball_data,
                                              game_num=self.game_num, rotation_len=self.rotation_len))  # init away team class
        alineup_card = self.teams[AWAY].set_initial_lineup(show_lineup=print_lineup, show_bench=show_bench,
                                                          current_season_stats=(True if game_num > 1 else False),
                                                          force_starting_pitcher=starting_pitchers[AWAY],
                                                          force_lineup_dict=starting_lineups[AWAY])
        self.teams.insert(HOME, bbteam.Team(team_name=self.team_names[HOME], baseball_data=self.baseball_data,
                                              game_num=self.game_num, rotation_len=self.rotation_len))  # init away team class
        hlineup_card = self.teams[HOME].set_initial_lineup(show_lineup=print_lineup, show_bench=show_bench,
                                                           current_season_stats=(True if game_num > 1 else False),
                                                           force_starting_pitcher=starting_pitchers[HOME],
                                                           force_lineup_dict=starting_lineups[HOME])
        self.game_recap += alineup_card + hlineup_card
        self.win_loss = []
        self.is_save_sit = [False, False]
        self.total_score = [0, 0]  # total score
        self.inning_score = [['   ', away_team_name, home_team_name], [1, 0, ''], [2, '', ''],
                             [3, '', ''], [4, '', ''], [5, '', ''], [6, '', ''], [7, '', ''], [8, '', ''],
                             [9, '', '']]  # inning 1, away, home score
        self.inning = [1, 1]
        self.batting_num = [1, 1]
        self.prior_batter_out_num = [1, 1]  # used for extra inning runners
        self.prior_batter_out_name = ['', '']  # used for extra innings
        self.pitching_num = [0, 0]
        self.outs = 0
        self.top_bottom = 0  # zero is top offset, 1 is bottom offset
        self.winning_pitcher = None
        self.losing_pitcher = None

        self.rng = lambda: np.random.default_rng().uniform(low=0.0, high=1.001)  # random generator between 0 and 1
        self.bases = bbbaserunners.Bases()
        self.outcomes = at_bat.OutCome()
        self.at_bat = at_bat.SimAB(self.baseball_data)  # setup class
        self.steal_multiplier = 1.7  # rate of steals per on base is not generating the desired result so increase it
        self.interactive = interactive  # is this game being controlled by a human or straight sim
        self.manager = None
        return

    def team_pitching(self) -> int:
        """
        which team is pitching
        :return: 0 away, 1, home team
        """
        return (self.top_bottom + 1) % 2

    def team_hitting(self) -> int:
        """
        which team is hitting
        :return: 0 away and 1 home
        """
        return self.top_bottom

    def score_diff(self) -> int:
        """
        looks at the score from the perspective of the team that is currently pitching.  used for save situation
        team pitching with lead will be positive difference, team pitching behind will be neg
        :return: score difference
        """
        return self.total_score[self.team_pitching()] - self.total_score[self.team_hitting()]

    def save_sit(self) -> bool:
        """
        is this a save situation?
        can go two innings for a save so start measure in the 8th inning
        if pitching team is leading and runners + ab + on deck is equal to score diff
        :return: true save situation
        """
        return (self.score_diff() > 0 and (self.score_diff() <= self.bases.count_runners() + 2) and
                self.inning[self.team_hitting()] >= 8)

    def close_game(self) -> bool:
        """
        is the game close in the late innings?  True if team leading by 0 to 3 runs in 7inning or later
        :return: true for close game
        """
        return 0 <= self.score_diff() <= 3 and self.inning[self.team_hitting()] >= 7

    def update_inning_score(self, number_of_runs: int = 0) -> None:
        """
        update half inning score
        :param number_of_runs: number of run scored so far in this half inning
        :return: None
        """
        if len(self.inning_score) <= self.inning[self.team_hitting()]:  # header rows + rows in score must = innings
            self.inning_score.append([self.inning[self.team_hitting()], '', ''])  # expand scores by new inning

        # inning score is a list of lists with inning number and away and home scores
        # add one to top bottom to account for inning header
        self.inning_score[self.inning[self.team_hitting()]][self.team_hitting() + 1] = str(number_of_runs) \
            if self.inning_score[self.inning[self.team_hitting()]][self.team_hitting() + 1] == '' \
            else str(int(self.inning_score[self.inning[self.team_hitting()]][self.team_hitting() + 1]) + number_of_runs)

        # pitcher of record tracking, look for lead change
        if self.total_score[self.team_hitting()] <= self.total_score[self.team_pitching()] \
                < (self.total_score[self.team_hitting()] + self.bases.runs_scored):
            self.winning_pitcher = self.teams[self.team_hitting()].is_pitching_index()
            self.losing_pitcher = self.teams[self.team_pitching()].is_pitching_index()
            if self.is_save_sit[self.team_pitching()]:  # blown save
                cur_pitcher = self.teams[self.team_pitching()].is_pitching_index()
                self.teams[self.team_pitching()].box_score.pitching_blown_save(cur_pitcher)

        self.total_score[self.team_hitting()] += number_of_runs  # update total score
        return

    def print_inning_score(self) -> None:
        """
        print inning by inning score
        :return: None
        """
        print_inning_score = self.inning_score.copy()
        print_inning_score.append(['R', self.total_score[AWAY], self.total_score[HOME]])
        print_inning_score.append(['H', self.teams[AWAY].box_score.total_hits, self.teams[HOME].box_score.total_hits])
        print_inning_score.append(['E', self.teams[AWAY].box_score.total_errors,
                                   self.teams[HOME].box_score.total_errors])
        row_to_col = list(zip(*print_inning_score))
        for ii in range(0, 3):  # print each row
            print_line = ''
            for jj in range(0, len(row_to_col[ii])):
                print_line = print_line + str(row_to_col[ii][jj]) + '\t'
            self.game_recap += print_line + '\n'
            # print(print_line)
        self.game_recap += '\n'
        # print('')
        return

    def pitching_sit(self, pitching: Series, pitch_switch: bool) -> bool:
        """
        switches pitchers based on fatigue or
        close game which is hitting inning >= 7 and, pitching team winning or tied and runners on = save sit
        if switch due to save or close game, don't switch again in same inning
        :param pitching: current pitchers data in a df series
        :param pitch_switch: did we already switch pitchers this inning?  Do not sub too fast
        :return: should we switch pitchers?
        """
        if (self.teams[self.team_pitching()].is_pitcher_fatigued(pitching.Condition) and self.outs < 3) or \
                (pitch_switch is False and (self.close_game() or self.save_sit())):
            prior_pitcher = self.teams[self.team_pitching()].is_pitching_index()
            self.teams[self.team_pitching()].pitching_change(inning=self.inning[self.team_hitting()],
                                                             score_diff=self.score_diff())
            if prior_pitcher != self.teams[self.team_pitching()].is_pitching_index():  # we are switching pitchers
                pitching = self.teams[self.team_pitching()].cur_pitcher_stats()  # data for new pitcher
                pitch_switch = True  # we switched pitcher this inning
                self.is_save_sit[self.team_pitching()] = self.save_sit()
                if self.chatty and pitch_switch:
                    self.game_recap += f'Manager has made the call to the bull pen.  Pitching change....\n'
                    self.game_recap += f'\t{pitching.Player} has entered the game for {self.team_names[self.team_pitching()]}\n'
                    # print(f'\tManager has made the call to the bull pen.  Pitching change....')
                    # print(f'\t{pitching.Player} has entered the game for {self.team_names[self.team_pitching()]}')
        return pitch_switch

    def balk_wild_pitch(self) -> None:
        """
        if this a situation where a balk or a wild pitch matters?  did it occur? what was the result?
        :return: None
        """
        # if self.bases.count_runners() > 0:
        #     die_roll = self.rng()
        #     balk_wild_pitch_rate = ((self.teams[self.team_pitching()].cur_pitcher_stats()['BK'] +
        #                             self.teams[self.team_pitching()].cur_pitcher_stats()['WP']) /
        #                             (self.teams[self.team_pitching()].cur_pitcher_stats()['AB'] +
        #                              self.teams[self.team_pitching()].cur_pitcher_stats()['BB']))
        #     balk_rate = (self.teams[self.team_pitching()].cur_pitcher_stats()['BK'] /
        #                             (self.teams[self.team_pitching()].cur_pitcher_stats()['AB'] +
        #                              self.teams[self.team_pitching()].cur_pitcher_stats()['BB']))
        #     if die_roll <= balk_wild_pitch_rate:
        #         if die_roll <= balk_rate:
        #             self.game_recap += f'******* balk '
        #         else:
        #             self.game_recap += f'**** wild pitch'
        return

    def stolen_base_sit(self) -> None:
        """
        is this a stolen base situation?  should we steal? what was the result?
        :return: None
        """
        if self.bases.is_eligible_for_stolen_base():
            runner_key = self.bases.get_runner_key(1)
            runner_stats = self.teams[self.team_hitting()].pos_player_prior_year_stats(runner_key)
            # scale steal attempts with frequency of stealing when on base
            # runner_stats.SB + runner_stats.CS >= self.min_steal_attempts and \
            if self.rng() <= (runner_stats.SB + runner_stats.CS) / (runner_stats.H + runner_stats.BB) \
                    * self.steal_multiplier:
                if self.rng() <= (runner_stats.SB / (runner_stats.SB + runner_stats.CS)):  # successful steal
                    self.bases.push_a_runner(1, 2)  # move runner from 1st to second
                    self.teams[self.team_hitting()].box_score.steal_result(runner_key, True)  # stole the base
                    if self.chatty:
                        self.game_recap += f'\t{runner_stats.Player} stole 2nd base!\n'
                        self.game_recap += f'\t{self.bases.describe_runners()}\n'
                else:
                    self.teams[self.team_hitting()].box_score.steal_result(runner_key, False)  # caught stealing
                    self.bases.remove_runner(1)  # runner was on first and never made it to second on the out
                    if self.chatty:
                        self.outs += 1  # this could result in the third out
                        self.game_recap += f'\t{runner_stats.Player} was caught stealing for out number {self.outs}\n'
        return

    def is_extra_innings(self) -> bool:
        """
        :return: are we in extra inning?
        """
        return self.inning[self.team_hitting()] > 9

    def extra_innings(self) -> None:
        """
        adds a running to second base for extra innings
        :return: None
        """
        # ignores player name, is already in lookup table if he was the last batter / out
        if self.is_extra_innings():
            self.bases.add_runner_to_base(base_num=2, batter_num=self.prior_batter_out_num[self.team_hitting()],
                                          player_name=self.prior_batter_out_name[self.team_hitting()])
            if self.chatty:
                self.game_recap += (f'Extra innings: {self.prior_batter_out_name[self.team_hitting()]} '
                                    f'will start at 2nd base.\n')
        return

    def sim_ab(self) -> Tuple[Series, Series]:
        """
        simulates an ab in a game
        :return: a tuple containing the updates series data for the pitcher and hitter as a result of the ab
        """
        cur_pitcher_index = self.teams[self.team_pitching()].cur_pitcher_index
        pitching = self.teams[self.team_pitching()].cur_pitcher_stats()  # data for pitcher
        pitching.Game_Fatigue_Factor, cur_percentage = \
            self.teams[self.team_pitching()].update_fatigue(cur_pitcher_index)

        cur_batter_index = self.teams[self.team_hitting()].batter_index_in_lineup(self.batting_num[self.team_hitting()])
        batting = self.teams[self.team_hitting()].batter_stats_in_lineup(cur_batter_index)
        self.bases.new_ab(batter_num=cur_batter_index, player_name=batting.Player)
        self.at_bat.ab_outcome(pitching, batting, self.outcomes, self.outs, self.bases.is_runner_on_base_num(1),
                               self.bases.is_runner_on_base_num(3))
        self.outs = self.outs + self.outcomes.outs_on_play
        self.bases.handle_runners(score_book_cd=self.outcomes.score_book_cd,
                                  bases_to_advance=self.outcomes.bases_to_advance,
                                  on_base_b=self.outcomes.on_base_b, outs=self.outs)
        self.outcomes.set_runs_score(self.bases.runs_scored)  # runs and rbis for batter and pitcher

        self.teams[self.team_pitching()].box_score.pitching_result(cur_pitcher_index, self.outcomes, pitching.Condition)
        self.teams[self.team_hitting()].box_score.batting_result(cur_batter_index, self.outcomes,
                                                                 self.bases.player_scored)
        if self.chatty:
            out_text = 'Out' if self.outs <= 1 else 'Outs'
            self.game_recap += (f'Pitcher: {pitching.Player} against {self.team_names[self.team_hitting()]} '
                  f'batter #{self.batting_num[self.team_hitting()]} {batting.Player} - '
                  f'{self.outcomes.score_book_cd}, {self.outs} {out_text}\n')

        self.prior_batter_out_name[self.team_hitting()] = batting.Player
        self.prior_batter_out_num[self.team_hitting()] = cur_batter_index
        return pitching, batting

    def sim_half_inning(self) -> None:
        """
        simulates a half inning of a game
        :return: None
        """
        pitch_switch = False  # did we switch pitchers this inning, don't sub if closer came in
        top_or_bottom = 'top' if self.top_bottom == 0 else 'bottom'
        if self.chatty:
            self.game_recap += f'\nStarting the {top_or_bottom} of inning {self.inning[self.team_hitting()]}.\n'
        self.extra_innings()  # set runner on second if it is extra innings
        while self.outs < 3:
            # check for pitching change due to fatigue or game sit
            pitch_switch = self.pitching_sit(self.teams[self.team_pitching()].cur_pitcher_stats(),
                                             pitch_switch=pitch_switch)
            self.stolen_base_sit()  # check for base stealing and then resolve ab
            if self.outs >= 3:
                break  # handle caught stealing

            self.balk_wild_pitch()  # handle wild pitch and balks
            __pitching, __batting = self.sim_ab()  # resolve ab
            if self.bases.runs_scored > 0:  # did a run score?
                self.update_inning_score(number_of_runs=self.bases.runs_scored)
            if self.bases.runs_scored > 0 and self.chatty:
                players = ''
                for player_id in self.bases.player_scored.keys():
                    players = players + ', ' + self.bases.player_scored[player_id] if players != '' \
                        else self.bases.player_scored[player_id]
                self.game_recap += (f'\tScored {self.bases.runs_scored} run(s)!  ({players})\n'
                      f'\tThe score is {self.team_names[0]} {self.total_score[0]} to'
                      f' {self.team_names[1]} {self.total_score[1]}\n')
            if self.bases.count_runners() >= 1 and self.outs < 3 and self.chatty:  # leave out batter check for runner
                self.game_recap += f'\t{self.bases.describe_runners()}\n'
            self.batting_num[self.team_hitting()] = self.batting_num[self.team_hitting()] + 1 \
                if (self.batting_num[self.team_hitting()] + 1) <= 9 else 1  # wrap around lineup
            # check for walk off
            if self.is_extra_innings() and self.total_score[AWAY] < self.total_score[HOME]:
                break  # end the half inning

        # half inning over
        self.update_inning_score(number_of_runs=0)  # push a zero on the board if no runs score this half inning
        self.bases.clear_bases()
        if self.chatty:
            self.game_recap += (f'\nCompleted {top_or_bottom} half of inning {self.inning[self.team_hitting()]}\n'
                  f'The score is {self.team_names[0]} {self.total_score[0]} to {self.team_names[1]} '
                  f'{self.total_score[1]}\n')
            self.print_inning_score()
        self.inning[self.team_hitting()] += 1
        self.top_bottom = 0 if self.top_bottom == 1 else 1  # switch teams hitting and pitching
        self.outs = 0  # rest outs to zero
        return

    def is_game_end(self) -> bool:
        """
        checks to see if the game should be over.  handles situations like home team leading after top of 9 or
        extra innings
        :return:
        """
        return False if self.inning[AWAY] <= 9 or self.inning[HOME] <= 8 or \
                        (self.inning[AWAY] != self.inning[HOME] and self.total_score[AWAY] >= self.total_score[HOME]) \
                        or self.total_score[AWAY] == self.total_score[HOME] else True

    def win_loss_record(self) -> None:
        """
        update the teams win and loss records and record for winning and losing pitchers.  also updates saves
        :return: None
        """
        home_win = 0 if self.total_score[0] > self.total_score[1] else 1
        self.win_loss.append([abs(home_win - 1), home_win])  # if home win away team is 0, 1
        self.win_loss.append([home_win, abs(home_win - 1)])  # if home win home team is  1, 0

        # assign winning and losing pitchers, if home team lost assign win to away and vice versa
        if home_win == 0:
            self.teams[AWAY].box_score.pitching_win_loss_save(self.winning_pitcher, win_b=True,
                                                              save_b=self.is_save_sit[AWAY])  #
            self.teams[HOME].box_score.pitching_win_loss_save(self.losing_pitcher, win_b=False, save_b=False)
        else:
            self.teams[AWAY].box_score.pitching_win_loss_save(self.losing_pitcher, win_b=False, save_b=False)
            self.teams[HOME].box_score.pitching_win_loss_save(self.winning_pitcher, win_b=True,
                                                              save_b=self.is_save_sit[HOME])
        return

    def end_game(self) -> None:
        """
        handle end of the game including updating condition of players, win loss records, box scores, and printing
        :return: None
        """
        self.teams[AWAY].set_batting_condition()
        self.teams[HOME].set_batting_condition()
        self.win_loss_record()
        self.teams[AWAY].box_score.totals()
        self.teams[HOME].box_score.totals()
        if self.print_box_score_b:  # print or not to print...
            self.game_recap += self.teams[AWAY].box_score.print_boxes()
            self.game_recap += self.teams[HOME].box_score.print_boxes()
        self.game_recap += 'Final:\n'
        self.print_inning_score()
        return

    def sim_game(self, team_to_follow: str = '') -> Tuple[List[int], List[int], List[List[int]], str]:
        """
        simulate an entire game
        :param team_to_follow: three character abbrev of a team that the user is following, prints more detail
        :return: tuple contains a list of total score for each team, inning by inning score and win loss records,
            and the output string
        """
        self.game_recap += f'{self.team_names[0]} vs. {self.team_names[1]}\n'
        if team_to_follow in self.team_names:
            self.game_recap += f'Following team: {team_to_follow}\n'
            self.chatty = True
            self.print_box_score_b = True
            # if self.interactive:
            #     pass  # ??? need to handle interactive
        while self.is_game_end() is False:
            self.sim_half_inning()
        self.end_game()
        return self.total_score, self.inning, self.win_loss, self.game_recap

    def sim_game_threaded(self, q: queue) -> None:
        """
        handles input and output using the queue for multi-threading
        :param q: queue for data exchange
        :return: None
        """
        g_score, g_innings, g_win_loss, final_game_recap = self.sim_game(team_to_follow=q.get())
        q.put((g_score, g_innings, g_win_loss, self.teams[AWAY].box_score, self.teams[HOME].box_score, final_game_recap))  # results on q
        return


# test a number of games
if __name__ == '__main__':
    # Configure logger level - change to "DEBUG" for more detailed logs
    from bblogger import configure_logger
    configure_logger("INFO")
    
    startdt = datetime.datetime.now()

    away_team = 'NYM'
    home_team = 'MIL'

    # MIL_lineup = {647549: 'LF', 239398: 'C', 224423: '1B', 138309: 'DH', 868055: 'CF', 520723: 'SS',
    #               299454: '3B', 46074: '2B', 752787: 'RF'}
    # NYM_starter = 626858
    # MIL_starter = 288650
    sims = 1
    season_win_loss = [[0, 0], [0, 0]]  # away record pos 0, home pos 1
    score_total = [0, 0]
    # team0_season_df = None
    for sim_game_num in range(1, sims + 1):
        print(f'Game number {sim_game_num}: from bbgame.py sims {sims}')
        game = Game(home_team_name=home_team, away_team_name=away_team,
                    chatty=False, print_lineup=True,
                    print_box_score_b=False,
                    load_seasons=[2024], new_season=2025,
                    # load_batter_file='random-stats-pp-Batting.csv',
                    # load_pitcher_file='random-stats-pp-Pitching.csv',
                    load_batter_file='stats-pp-Batting.csv',
                    load_pitcher_file='stats-pp-Pitching.csv',
                    interactive=False,
                    show_bench=False
                    # , starting_pitchers=[MIL_starter, BOS_starter]
                    # , starting_lineups=[MIL_lineup, None]
                    )
        score, inning, win_loss, game_recap_str = game.sim_game(team_to_follow=home_team)
        print(game_recap_str)
        season_win_loss[0] = list(np.add(np.array(season_win_loss[0]), np.array(win_loss[0])))
        season_win_loss[1] = list(np.add(np.array(season_win_loss[1]), np.array(win_loss[1])))
        score_total[0] = score_total[0] + score[0]
        score_total[1] = score_total[1] + score[1]
        # if team0_season_df is None:
        # team0_season_df = game.teams[AWAY].box_score.team_box_batting
        # else:
        #     col_list = ['G', 'AB', 'R', 'H', '2B', '3B', 'HR', 'RBI', 'SB', 'CS', 'BB', 'SO', 'SH', 'SF', 'HBP']
        #     team0_season_df = team0_season_df[col_list].add(game.teams[AWAY].box_score.box_batting[col_list])
        #     team0_season_df['Player'] = game.teams[AWAY].box_score.box_batting['Player']
        #     team0_season_df['Team'] = game.teams[AWAY].box_score.box_batting['Team']
        #     team0_season_df['Pos'] = game.teams[AWAY].box_score.box_batting['Pos']
    #     print('')
    #     print(f'{away_team} season : {season_win_loss[0][0]} W and {season_win_loss[0][1]} L')
    #     print(f'{home_team} season : {season_win_loss[1][0]} W and {season_win_loss[1][1]} L')
    # print(f'away team scored {score_total[0]} for an average of {score_total[0]/sims}')
    # print(f'home team scored {score_total[1]} for an average of {score_total[1] / sims}')
    print(startdt)
    print(datetime.datetime.now())
