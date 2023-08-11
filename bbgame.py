import bbstats
import gameteam
import at_bat
import numpy as np
import bbbaserunners

AWAY = 0
HOME = 1


class Game:
    def __init__(self, away_team_name, home_team_name, baseball_data=None, game_num=1, rotation_len=5,
                 print_lineup=True, chatty=True, print_box_score_b=True):
        self.team_names = [away_team_name, home_team_name]
        self.baseball_data = bbstats.BaseballStats(load_seasons=[2022], new_season=2023, random_data=False) \
            if baseball_data is None else baseball_data
        self.game_num = game_num  # number of games into season
        self.rotation_len = rotation_len  # number of starting pitchers to rotate thru
        self.chatty = chatty
        self.print_box_score_b = print_box_score_b

        self.teams = []  # keep track of away in pos 0 and home team in pos 1
        self.teams.insert(0, gameteam.Team(self.team_names[0], self.baseball_data, self.game_num, self.rotation_len))
        self.teams[AWAY].set_lineup(show_lineup=print_lineup, current_season_stats=(True if game_num > 1 else False))

        # print(f'Setting home team as {self.team_names[1]}')
        self.teams.insert(1, gameteam.Team(self.team_names[1], self.baseball_data, self.game_num, self.rotation_len))
        self.teams[HOME].set_lineup(show_lineup=print_lineup, current_season_stats=(True if game_num > 1 else False))

        self.win_loss = []
        self.total_score = [0, 0]  # total score
        self.inning_score = [['   ', away_team_name, home_team_name], [1, 0, ''], [2, '', ''],
                             [3, '', ''], [4, '', ''], [5, '', ''], [6, '', ''], [7, '', ''], [8, '', ''],
                             [9, '', '']]  # inning 1, away, home score
        self.inning = [1, 1]
        self.batting_num = [1, 1]
        self.pitching_num = [0, 0]
        self.outs = 0
        self.top_bottom = 0  # zero is top offset, 1 is bottom offset
        self.winning_pitcher = None
        self.losing_pitcher = None

        # self.fatigue_start_perc = 15  # % of avg max is where fatigue starts
        # self.fatigue_rate = .001  # at 85% of avg max pitchers have a .014 increase in OBP.  using .001 as proxy

        self.rng = np.random.default_rng()  # random number generator between 0 and 1
        self.bases = bbbaserunners.Bases()
        self.at_bat = at_bat.SimAB(self.baseball_data)  # setup at class
        return

    def team_pitching(self):
        return (self.top_bottom + 1) % 2

    def team_hitting(self):
        return self.top_bottom

    def update_inning_score(self, number_of_runs=0):
        if len(self.inning_score) <= self.inning[self.team_hitting()]:  # header rows + rows in score must = innings
            self.inning_score.append([self.inning[self.team_hitting()], '', ''])  # expand scores by new inning

        # add one to top bottom to account for inning header
        self.inning_score[self.inning[self.team_hitting()]][self.team_hitting() + 1] = number_of_runs \
            if self.inning_score[self.inning[self.team_hitting()]][self.team_hitting() + 1] == '' \
            else int(self.inning_score[self.inning[self.team_hitting()]][self.team_hitting() + 1]) + number_of_runs

        # pitcher of record tracking, look for lead change
        if self.total_score[self.team_hitting()] <= self.total_score[self.team_pitching()] and \
           (self.total_score[self.team_hitting()] + self.bases.runs_scored) > self.total_score[self.team_pitching()]:
            self.winning_pitcher = self.teams[self.team_hitting()].pitching.index
            self.losing_pitcher = self.teams[self.team_pitching()].pitching.index

        self.total_score[self.team_hitting()] += self.bases.runs_scored  # update total score
        return

    def print_inning_score(self):
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

    def sim_ab(self):
        cur_pitcher_index = self.teams[self.team_pitching()].cur_pitcher_index
        pitching = self.teams[self.team_pitching()].cur_pitcher_stats()  # data for pitcher
        pitching.Game_Fatigue_Factor, cur_percentage = \
            self.teams[self.team_pitching()].update_fatigue(cur_pitcher_index)
        pitching.Condition = 100 - cur_percentage if 100 - cur_percentage >= 0 else 0

        cur_batter_index = self.teams[self.team_hitting()].cur_lineup_index[self.batting_num[self.team_hitting()]-1]
        batting = self.teams[self.team_hitting()].cur_batter_stats(self.batting_num[self.team_hitting()]-1)  # lineup #
        self.bases.new_ab(batter_num=cur_batter_index, player_name=batting.Player)
        outcome = self.at_bat.outcome(pitching, batting, self.outs, self.bases.is_runner_on_first())

        outs_on_play = 0
        if outcome[0] == 'OUT':
            self.outs += 1
            outs_on_play = 1
            if outcome[1] == 'DP' and self.outs <= 2:
                self.outs += 1
                outs_on_play += 1
                self.bases.remove_runner(1)  # remove runner on first for DP, only considering 1st
            # need to advance runners on fly (tag), fc for lead runner, or gb advance
        elif outcome[0] == 'OB':
            self.bases.advance_runners(bases_to_advance=outcome[2])  # outcome 2 is number of bases to advance
            # self.total_score[self.top_bottom] += self.bases.runs_scored  # moved to update innning score
            outcome[3] = self.bases.runs_scored  # rbis for batter
        self.teams[self.team_pitching()].box_score.pitching_result(cur_pitcher_index, outcome, outs_on_play)
        self.teams[self.team_hitting()].box_score.batting_result(cur_batter_index, outcome, self.bases.player_scored)
        return pitching, batting, outcome

    def sim_half_inning(self, chatty=True):
        top_or_bottom = 'top' if self.top_bottom == 0 else 'bottom'
        if chatty:
            print(f'\nStarting the {top_or_bottom} of inning {self.inning[self.team_hitting()]}.')
        while self.outs < 3:
            pitching, batting, outcome = self.sim_ab()
            if chatty:
                print(f'Pitcher: {pitching.Player} against '
                      f'{self.team_names[self.team_hitting()]} batter #'
                      f'{self.batting_num[self.team_hitting()]}. {batting.Player} \n'
                      f'\t {outcome[1]}, {self.outs} Outs')
            if self.bases.runs_scored > 0:
                self.update_inning_score(number_of_runs=self.bases.runs_scored)
            if self.bases.runs_scored > 0 and chatty:
                players = ''
                for player_id in self.bases.player_scored.keys():
                    players = players + ', ' + self.bases.player_scored[player_id] if players != '' \
                        else self.bases.player_scored[player_id]
                print(f'\tScored {self.bases.runs_scored} run(s)!  ({players})\n'
                      f'\tThe score is {self.team_names[0]} {self.total_score[0]} to'
                      f' {self.team_names[1]} {self.total_score[1]}')  # ?? need to handle walk offs...
            if self.bases.num_runners >= 1 and self.outs < 3 and chatty:  # leave out the batter to check for runner
                print(f'\t{self.bases.describe_runners()}')
            self.batting_num[self.team_hitting()] = self.batting_num[self.team_hitting()] + 1 \
                if (self.batting_num[self.team_hitting()] + 1) <= 9 else 1  # wrap around lineup
            if self.teams[self.team_pitching()].is_pitcher_fatigued() and self.outs < 3:  # pitching change
                self.teams[self.team_pitching()].pitching_change()
                pitching = self.teams[self.team_pitching()].cur_pitcher_stats()  # data for new pitcher
                if chatty:
                    print(f'\tManager has made the call to the bull pen.  Pitching change....')
                    print(f'\t{pitching.Player} has entered the game for {self.team_names[self.team_pitching()]}')

        # half inning over
        self.update_inning_score(number_of_runs=0)  # push a zero on the board if no runs score this half inning
        self.bases.clear_bases()
        if chatty:
            print('')  # add a blank line for verbose output
            print(f'Completed {top_or_bottom} half of inning {self.inning[self.team_hitting()]}. '
                  f'The score is {self.team_names[0]} {self.total_score[0]} to {self.team_names[1]} '
                  f'{self.total_score[1]}')
            self.print_inning_score()
        self.inning[self.team_hitting()] += 1
        self.top_bottom = 0 if self.top_bottom == 1 else 1  # switch teams hitting and pitching
        self.outs = 0  # rest outs to zero
        return

    def is_game_end(self):
        return False if self.inning[0] <= 9 or self.inning[1] <= 8 or \
                        (self.inning[0] != self.inning[1] and self.total_score[0] >= self.total_score[1]) \
                        or self.total_score[0] == self.total_score[1] else True

    def win_loss_record(self):
        home_win = 0 if self.total_score[0] > self.total_score[1] else 1
        self.win_loss.append([abs(home_win - 1), home_win])  # if home win away team is 0, 1
        self.win_loss.append([home_win, abs(home_win - 1)])  # if home win home team is  1, 0

        # assign winning and losing pitchers, if home team lost assign win to away and vice versa
        if home_win == 0:
            self.teams[AWAY].box_score.pitching_win_loss(self.winning_pitcher, True)
            self.teams[HOME].box_score.pitching_win_loss(self.losing_pitcher, False)
        else:
            self.teams[AWAY].box_score.pitching_win_loss(self.losing_pitcher, False)
            self.teams[HOME].box_score.pitching_win_loss(self.winning_pitcher, True)
        return

    def sim_game(self):
        while self.is_game_end() is False:
            self.sim_half_inning(chatty=self.chatty)

        self.win_loss_record()
        self.teams[AWAY].box_score.totals()
        self.teams[HOME].box_score.totals()
        if self.print_box_score_b:  # to print or not to print...
            self.teams[AWAY].box_score.print_boxes()
            self.teams[HOME].box_score.print_boxes()
        print('Final:')
        self.print_inning_score()
        return self.total_score, self.inning, self.win_loss


# test a number of games
if __name__ == '__main__':
    home_team = 'MIL'
    away_team = 'MIN'
    season_length = 1
    season_win_loss = [[0, 0], [0, 0]]  # away record pos 0, home pos 1
    team0_season_df = None
    for sim_game_num in range(1, season_length + 1):
        print(f'Game number {sim_game_num}: from bbgame.py test code')
        game = Game(home_team_name=home_team, away_team_name=away_team, chatty=True, print_lineup=True,
                    print_box_score_b=True)
        score, inning, win_loss = game.sim_game()
        season_win_loss[0] = list(np.add(np.array(season_win_loss[0]), np.array(win_loss[0])))
        season_win_loss[1] = list(np.add(np.array(season_win_loss[1]), np.array(win_loss[1])))
        if team0_season_df is None:
            team0_season_df = game.teams[AWAY].box_score.team_box_batting
        else:
            col_list = ['G', 'AB', 'R', 'H', '2B', '3B', 'HR', 'RBI', 'SB', 'CS', 'BB', 'SO', 'SH', 'SF', 'HBP']
            team0_season_df = team0_season_df[col_list].add(game.teams[AWAY].box_score.box_batting[col_list])
            team0_season_df['Player'] = game.teams[AWAY].box_score.box_batting['Player']
            team0_season_df['Team'] = game.teams[AWAY].box_score.box_batting['Team']
            team0_season_df['Pos'] = game.teams[AWAY].box_score.box_batting['Pos']
        # print(f'Code to test inning box, Score was: {score[0]} to {score[1]}')
        print('')
        print(f'{away_team} season : {season_win_loss[0][0]} W and {season_win_loss[0][1]} L')
        print(f'{home_team} season : {season_win_loss[1][0]} W and {season_win_loss[1][1]} L')

    # team0_season_df = bbstats.team_batting_stats(team0_season_df)
    # print(team0_season_df.to_string(index=False, justify='center'))
    # end season
