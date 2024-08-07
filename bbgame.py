import bbstats
import gameteam
import at_bat
import numpy as np
import random
import bbbaserunners
import datetime
from pandas.core.series import Series
from typing import List, Tuple

AWAY = 0
HOME = 1


class Game:
    def __init__(self, away_team_name: str = '', home_team_name: str = '', baseball_data: None = None,
                 game_num: int = 1, rotation_len: int = 5,
                 print_lineup: bool = False, chatty: bool = False, print_box_score_b: bool = False,
                 load_seasons: List[int] = 2023, new_season: int = 2024,
                 starting_pitchers: None = None, starting_lineups: None = None,
                 load_batter_file: str = 'player-stats-Batters.csv',
                 load_pitcher_file: str = 'player-stats-Pitching.csv',
                 interactive: bool = False, show_bench: bool = False) -> None:
        if baseball_data is None:
            self.baseball_data = bbstats.BaseballStats(load_seasons=load_seasons, new_season=new_season,
                                                       load_batter_file=load_batter_file,
                                                       load_pitcher_file=load_pitcher_file)
        else:
            self.baseball_data = baseball_data
        if away_team_name != '' or home_team_name != '':
            self.team_names = [away_team_name, home_team_name]
        else:
            self.team_names = random.sample(list(self.baseball_data.batting_data.Team.unique()), 2)
        self.game_num = game_num  # number of games into season
        self.rotation_len = rotation_len  # number of starting pitchers to rotate thru
        self.chatty = chatty
        self.print_box_score_b = print_box_score_b
        if starting_pitchers is None:
            starting_pitchers = [None, None]
        self.starting_pitchers = starting_pitchers  # can use if you want to sim the same two starters repeatedly
        if starting_lineups is None:
            starting_lineups = [None, None]
        self.starting_lineups = starting_lineups  # is a list of two dict, each dict is in batting order with field pos

        self.teams = []  # keep track of away in pos 0 and home team in pos 1
        self.teams.insert(AWAY, gameteam.Team(self.team_names[AWAY], self.baseball_data, self.game_num,
                                              self.rotation_len))  # init away team class
        self.teams[AWAY].set_initial_lineup(show_lineup=print_lineup, show_bench=show_bench,
                                            current_season_stats=(True if game_num > 1 else False),
                                            force_starting_pitcher=starting_pitchers[AWAY],
                                            force_lineup_dict=starting_lineups[AWAY])

        # print(f'Setting home team as {self.team_names[1]}')
        self.teams.insert(HOME, gameteam.Team(self.team_names[HOME], self.baseball_data, self.game_num,
                                              self.rotation_len))  # init away team class
        self.teams[HOME].set_initial_lineup(show_lineup=print_lineup, show_bench=show_bench,
                                            current_season_stats=(True if game_num > 1 else False),
                                            force_starting_pitcher=starting_pitchers[HOME],
                                            force_lineup_dict=starting_lineups[HOME])

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
        return (self.top_bottom + 1) % 2

    def team_hitting(self) -> int:
        return self.top_bottom

    def score_diff(self) -> int:
        # team pitching with lead will be positive, team pitching behind will be neg
        return self.total_score[self.team_pitching()] - self.total_score[self.team_hitting()]

    def save_sit(self) -> bool:
        # can go two innings for a save so start measure in the 8th inning
        # if pitching team is leading and runners + ab + on deck is equal to score diff
        return (self.score_diff() > 0 and (self.score_diff() <= self.bases.count_runners() + 2) and
                self.inning[self.team_hitting()] >= 8)

    def close_game(self) -> bool:
        return self.score_diff() >= 0 and self.inning[self.team_hitting()] >= 7

    # noinspection PyTypeChecker
    def update_inning_score(self, number_of_runs: int = 0) -> None:
        if len(self.inning_score) <= self.inning[self.team_hitting()]:  # header rows + rows in score must = innings
            self.inning_score.append([self.inning[self.team_hitting()], '', ''])  # expand scores by new inning

        # add one to top bottom to account for inning header
        self.inning_score[self.inning[self.team_hitting()]][self.team_hitting() + 1] = number_of_runs \
            if self.inning_score[self.inning[self.team_hitting()]][self.team_hitting() + 1] == '' \
            else int(self.inning_score[self.inning[self.team_hitting()]][self.team_hitting() + 1]) + number_of_runs

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
            print(print_line)
        print('')
        return

    def score_difference(self) -> int:
        return self.total_score[self.team_pitching()] - self.total_score[self.team_hitting()]

    def pitching_sit(self, pitching: Series, pitch_switch: bool) -> bool:
        # switch pitchers based on fatigue or close game
        # close game is hitting inning >= 7 and, pitching team winning or tied and runners on = save sit
        # if switch due to save or close game, don't switch again in same inning
        if (self.teams[self.team_pitching()].is_pitcher_fatigued(pitching.Condition) and self.outs < 3) or \
                (pitch_switch is False and (self.close_game() or self.save_sit())):
            prior_pitcher = self.teams[self.team_pitching()].is_pitching_index()
            self.teams[self.team_pitching()].pitching_change(inning=self.inning[self.team_hitting()],
                                                             score_diff=self.score_difference())
            if prior_pitcher != self.teams[self.team_pitching()].is_pitching_index():  # we are switching pitchers
                pitching = self.teams[self.team_pitching()].cur_pitcher_stats()  # data for new pitcher
                pitch_switch = True  # we switched pitcher this inning
                self.is_save_sit[self.team_pitching()] = self.save_sit()
                if self.chatty and pitch_switch:
                    print(f'\tManager has made the call to the bull pen.  Pitching change....')
                    print(f'\t{pitching.Player} has entered the game for {self.team_names[self.team_pitching()]}')
        return pitch_switch

    def stolen_base_sit(self) -> None:
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
                        print(f'\t{runner_stats.Player} stole 2nd base!')
                        print(f'\t{self.bases.describe_runners()}')
                else:
                    self.teams[self.team_hitting()].box_score.steal_result(runner_key, False)  # caught stealing
                    if self.chatty:
                        self.outs += 1  # this could result in the third out
                        print(f'\t{runner_stats.Player} was caught stealing for out number {self.outs}')
        return

    def is_extra_innings(self) -> bool:
        return self.inning[self.team_hitting()] > 9

    def extra_innings(self) -> None:
        # ignores player name, is already in lookup table if he was the last batter / out
        if self.is_extra_innings():
            self.bases.add_runner_to_base(base_num=2, batter_num=self.prior_batter_out_num[self.team_hitting()],
                                          player_name=self.prior_batter_out_name[self.team_hitting()])
            if self.chatty:
                print(f'Extra innings: {self.prior_batter_out_name[self.team_hitting()]} will start at 2nd base.')
        return

    def sim_ab(self) -> Tuple[Series, Series]:
        cur_pitcher_index = self.teams[self.team_pitching()].cur_pitcher_index
        pitching = self.teams[self.team_pitching()].cur_pitcher_stats()  # data for pitcher
        pitching.Game_Fatigue_Factor, cur_percentage = \
            self.teams[self.team_pitching()].update_fatigue(cur_pitcher_index)

        # cur_batter_index = self.teams[self.team_hitting()].
        # cur_lineup_index_list[self.batting_num[self.team_hitting()]-1]
        cur_batter_index = self.teams[self.team_hitting()].batter_index_in_lineup(self.batting_num[self.team_hitting()])
        # batting = self.teams[self.team_hitting()].cur_batter_stats(self.batting_num[self.team_hitting()]-1)  # lineup
        batting = self.teams[self.team_hitting()].batter_stats_in_lineup(cur_batter_index)
        self.bases.new_ab(batter_num=cur_batter_index, player_name=batting.Player)
        self.at_bat.outcome(pitching, batting, self.outcomes, self.outs, self.bases.is_runner_on_base_num(1),
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
            print(f'Pitcher: {pitching.Player} against '
                  f'{self.team_names[self.team_hitting()]} batter #'
                  f'{self.batting_num[self.team_hitting()]}. {batting.Player} \n'
                  f'\t {self.outcomes.score_book_cd}, {self.outs} {out_text}')

        self.prior_batter_out_name[self.team_hitting()] = batting.Player
        self.prior_batter_out_num[self.team_hitting()] = cur_batter_index
        return pitching, batting

    def sim_half_inning(self) -> None:
        pitch_switch = False  # did we switch pitchers this inning, don't sub if closer came in
        top_or_bottom = 'top' if self.top_bottom == 0 else 'bottom'
        if self.chatty:
            print(f'\nStarting the {top_or_bottom} of inning {self.inning[self.team_hitting()]}.')
        self.extra_innings()  # set runner on second if it is extra innings
        while self.outs < 3:
            # check for pitching change due to fatigue or game sit
            pitch_switch = self.pitching_sit(self.teams[self.team_pitching()].cur_pitcher_stats(),
                                             pitch_switch=pitch_switch)
            # check for base stealing and then resolve ab
            self.stolen_base_sit()
            if self.outs >= 3:
                break  # handle caught stealing
            __pitching, __batting = self.sim_ab()  # resolve ab
            if self.bases.runs_scored > 0:  # did a run score?
                self.update_inning_score(number_of_runs=self.bases.runs_scored)
            if self.bases.runs_scored > 0 and self.chatty:
                players = ''
                for player_id in self.bases.player_scored.keys():
                    players = players + ', ' + self.bases.player_scored[player_id] if players != '' \
                        else self.bases.player_scored[player_id]
                print(f'\tScored {self.bases.runs_scored} run(s)!  ({players})\n'
                      f'\tThe score is {self.team_names[0]} {self.total_score[0]} to'
                      f' {self.team_names[1]} {self.total_score[1]}')
            if self.bases.count_runners() >= 1 and self.outs < 3 and self.chatty:  # leave out batter check for runner
                print(f'\t{self.bases.describe_runners()}')
            self.batting_num[self.team_hitting()] = self.batting_num[self.team_hitting()] + 1 \
                if (self.batting_num[self.team_hitting()] + 1) <= 9 else 1  # wrap around lineup
            # check for walk off
            if self.is_extra_innings() and self.total_score[AWAY] < self.total_score[HOME]:
                break  # end the half inning

        # half inning over
        self.update_inning_score(number_of_runs=0)  # push a zero on the board if no runs score this half inning
        self.bases.clear_bases()
        if self.chatty:
            print('')  # add a blank line for verbose output
            print(f'Completed {top_or_bottom} half of inning {self.inning[self.team_hitting()]}. '
                  f'The score is {self.team_names[0]} {self.total_score[0]} to {self.team_names[1]} '
                  f'{self.total_score[1]}')
            self.print_inning_score()
        self.inning[self.team_hitting()] += 1
        self.top_bottom = 0 if self.top_bottom == 1 else 1  # switch teams hitting and pitching
        self.outs = 0  # rest outs to zero
        return

    def is_game_end(self) -> bool:
        return False if self.inning[AWAY] <= 9 or self.inning[HOME] <= 8 or \
                        (self.inning[AWAY] != self.inning[HOME] and self.total_score[AWAY] >= self.total_score[HOME]) \
                        or self.total_score[AWAY] == self.total_score[HOME] else True

    def win_loss_record(self) -> None:
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
        self.teams[AWAY].set_batting_condition()
        self.teams[HOME].set_batting_condition()
        self.win_loss_record()
        self.teams[AWAY].box_score.totals()
        self.teams[HOME].box_score.totals()
        if self.print_box_score_b:  # print or not to print...
            self.teams[AWAY].box_score.print_boxes()
            self.teams[HOME].box_score.print_boxes()
        print('Final:')
        self.print_inning_score()
        return

    def sim_game(self, team_to_follow: str = '') -> Tuple[List[int], List[int], List[List[int]]]:
        if team_to_follow in self.team_names:
            print(f'Following team: {team_to_follow}')
            self.chatty = True
            self.print_box_score_b = True
            if self.interactive:
                pass

        while self.is_game_end() is False:
            self.sim_half_inning()
        self.end_game()

        return self.total_score, self.inning, self.win_loss


# test a number of games
if __name__ == '__main__':
    startdt = datetime.datetime.now()

    away_team = 'MIL'
    home_team = 'CHC'
    # away_team = 'SAN'
    # home_team = 'TEM'
    MIL_lineup = {647549: 'LF', 239398: 'C', 224423: '1B', 138309: 'DH', 868055: 'CF', 520723: 'SS',
                  299454: '3B', 46074: '2B', 752787: 'RF'}
    BOS_starter = 516876
    MIL_starter = 993801
    sims = 1
    season_win_loss = [[0, 0], [0, 0]]  # away record pos 0, home pos 1
    # team0_season_df = None
    for sim_game_num in range(1, sims + 1):
        print(f'Game number {sim_game_num}: from bbgame.py test code')
        game = Game(home_team_name=home_team, away_team_name=away_team,
                    chatty=True, print_lineup=True,
                    print_box_score_b=True,
                    load_seasons=[2023], new_season=2024,
                    # load_batter_file='random-stats-pp-Batting.csv',
                    # load_pitcher_file='random-stats-pp-Pitching.csv',
                    load_batter_file='stats-pp-Batting.csv',
                    load_pitcher_file='stats-pp-Pitching.csv',
                    interactive=True,
                    show_bench=True
                    # , starting_pitchers=[MIL_starter, BOS_starter]
                    # , starting_lineups=[MIL_lineup, None]
                    )
        score, inning, win_loss = game.sim_game(team_to_follow='MIL')
        season_win_loss[0] = list(np.add(np.array(season_win_loss[0]), np.array(win_loss[0])))
        season_win_loss[1] = list(np.add(np.array(season_win_loss[1]), np.array(win_loss[1])))
        # if team0_season_df is None:
        team0_season_df = game.teams[AWAY].box_score.team_box_batting
        # else:
        #     col_list = ['G', 'AB', 'R', 'H', '2B', '3B', 'HR', 'RBI', 'SB', 'CS', 'BB', 'SO', 'SH', 'SF', 'HBP']
        #     team0_season_df = team0_season_df[col_list].add(game.teams[AWAY].box_score.box_batting[col_list])
        #     team0_season_df['Player'] = game.teams[AWAY].box_score.box_batting['Player']
        #     team0_season_df['Team'] = game.teams[AWAY].box_score.box_batting['Team']
        #     team0_season_df['Pos'] = game.teams[AWAY].box_score.box_batting['Pos']
        print('')
        print(f'{away_team} season : {season_win_loss[0][0]} W and {season_win_loss[0][1]} L')
        print(f'{home_team} season : {season_win_loss[1][0]} W and {season_win_loss[1][1]} L')

        print(startdt)
        print(datetime.datetime.now())
