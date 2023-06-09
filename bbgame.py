import bbstats
import gameteam
import at_bat
import numpy as np
import bbbaserunners
import pandas as pd


class Game:
    def __init__(self, away_team_name, home_team_name, baseball_data=None, game_num=1, rotation_len=5,
                 print_lineup=True, chatty=True, print_box_score=True):
        self.team_names = [away_team_name, home_team_name]
        self.baseball_data = bbstats.BaseballStats(load_seasons=[2022], new_season=2023, random_data=False) \
            if baseball_data is None else baseball_data
        self.game_num = game_num  # number of games into season
        self.rotation_len = rotation_len  # number of starting pitchers to rotate thru
        self.chatty = chatty
        self.print_box_score = print_box_score

        self.teams = []  # keep track of away in pos 0 and home team in pos 1
        self.teams.insert(0, gameteam.Team(self.team_names[0], self.baseball_data, self.game_num, self.rotation_len))
        self.teams[0].set_lineup(show_lineup=print_lineup, current_season_stats=(True if game_num > 1 else False))

        # print(f'Setting home team as {self.team_names[1]}')
        self.teams.insert(1, gameteam.Team(self.team_names[1], self.baseball_data, self.game_num, self.rotation_len))
        self.teams[1].set_lineup(show_lineup=print_lineup, current_season_stats=(True if game_num > 1 else False))

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

        self.rng = np.random.default_rng()  # random number generator between 0 and 1
        self.bases = bbbaserunners.Bases()
        self.at_bat = at_bat.SimAB(self.baseball_data)
        return

    def update_inning_score(self, number_of_runs=0):
        if len(self.inning_score) <= self.inning[self.top_bottom]:  # header rows + rows in score must = innings
            self.inning_score.append([self.inning[self.top_bottom], '', ''])  # expand scores by new inning

        # add one to top bottom to account for inning header
        self.inning_score[self.inning[self.top_bottom]][self.top_bottom + 1] = number_of_runs \
            if self.inning_score[self.inning[self.top_bottom]][self.top_bottom + 1] == '' \
            else int(self.inning_score[self.inning[self.top_bottom]][self.top_bottom + 1]) + number_of_runs

        # pitcher of record tracking, look for lead change
        if self.total_score[self.top_bottom] <= self.total_score[(self.top_bottom + 1) % 2] and \
           (self.total_score[self.top_bottom] + self.bases.runs_scored) > self.total_score[(self.top_bottom + 1) % 2]:
            self.winning_pitcher = self.teams[self.top_bottom].pitching.index
            self.losing_pitcher = self.teams[(self.top_bottom + 1) % 2].pitching.index

        self.total_score[self.top_bottom] += self.bases.runs_scored  # update total score
        return

    def print_inning_score(self):
        print_inning_score = self.inning_score.copy()
        print_inning_score.append(['R', self.total_score[0], self.total_score[1]])
        print_inning_score.append(['H', self.teams[0].box_score.total_hits, self.teams[1].box_score.total_hits])
        print_inning_score.append(['E', self.teams[0].box_score.total_errors, self.teams[1].box_score.total_errors])
        row_to_col = list(zip(*print_inning_score))
        for ii in range(0, 3):  # print each row
            print_line = ''
            for jj in range(0, len(row_to_col[ii])):
                print_line = print_line + str(row_to_col[ii][jj]) + '\t'
            print(print_line)
        print('')
        return

    def sim_ab(self):
        cur_pitching_index = self.teams[(self.top_bottom + 1) % 2].cur_pitcher_index
        pitching = self.teams[(self.top_bottom + 1) % 2].pitching.iloc[0]  # data for pitcher

        cur_batter_index = self.teams[self.top_bottom].cur_lineup_index[self.batting_num[self.top_bottom]-1]
        batting = self.teams[self.top_bottom].lineup.iloc[self.batting_num[self.top_bottom]-1]  # data for batter
        self.bases.new_ab(batter_num=cur_batter_index, player_name=batting.Player)
        outcome = self.at_bat.outcome(pitching, batting)
        if outcome[0] == 'OUT':
            self.outs += 1
        elif outcome[0] == 'OB':
            self.bases.advance_runners(bases_to_advance=outcome[2])  # outcome 2 is number of bases to advance
            # self.total_score[self.top_bottom] += self.bases.runs_scored  # moved to update innning score
            outcome[3] = self.bases.runs_scored  # rbis for batter
        self.teams[(self.top_bottom + 1) % 2].box_score.pitching_result(cur_pitching_index, outcome)
        self.teams[self.top_bottom].box_score.batting_result(cur_batter_index, outcome, self.bases.player_scored)
        return pitching, batting, outcome

    def sim_half_inning(self, chatty=True):
        top_or_bottom = 'top' if self.top_bottom == 0 else 'bottom'
        if chatty:
            print(f'\nStarting the {top_or_bottom} of inning {self.inning[self.top_bottom]}.')
        while self.outs < 3:
            pitching, batting, outcome = self.sim_ab()
            if chatty:
                print(f'Pitcher: {pitching.Player} against '
                      f'{self.team_names[self.top_bottom]} batter #'
                      f'{self.batting_num[self.top_bottom]}. {batting.Player} \n'
                      f'\t {outcome[1]}, {self.outs} Outs')
            if self.bases.runs_scored > 0:
                self.update_inning_score(number_of_runs=self.bases.runs_scored)
            if self.bases.runs_scored > 0 and chatty:
                players = ''
                for player_id in self.bases.player_scored.keys():
                    players = players + ', ' + self.bases.player_scored[player_id] if players != '' \
                        else self.bases.player_scored[player_id]
                # print(f'{self.bases.player_scored} scored!')
                print(f'\tScored {self.bases.runs_scored} run(s)!  ({players})\n'
                      f'\tThe score is {self.team_names[0]} {self.total_score[0]} to'
                      f' {self.team_names[1]} {self.total_score[1]}')  # ?? need to handle walk offs...
            if self.bases.num_runners >= 1 and self.outs < 3 and chatty:  # leave out the batter to check for runner
                print(f'\t{self.bases.describe_runners()}')
            self.batting_num[self.top_bottom] = self.batting_num[self.top_bottom] + 1 \
                if (self.batting_num[self.top_bottom] + 1) <= 9 else 1

        # half inning over
        self.update_inning_score(number_of_runs=0)  # push a zero on the board if no runs score this half inning
        self.bases.clear_bases()
        if chatty:
            print('')  # add a blank line for verbose output
            print(f'Completed {top_or_bottom} half of inning {self.inning[self.top_bottom]}. '
                  f'The score is {self.team_names[0]} {self.total_score[0]} to {self.team_names[1]} '
                  f'{self.total_score[1]}')
            self.print_inning_score()
        self.inning[self.top_bottom] += 1
        self.top_bottom = 0 if self.top_bottom == 1 else 1
        self.outs = 0
        return

    def is_game_end(self):
        return False if self.inning[0] <= 9 or self.inning[1] <= 8 or \
                        (self.inning[0] != self.inning[1] and self.total_score[0] >= self.total_score[1]) \
                        or self.total_score[0] == self.total_score[1] else True

    def win_loss_record(self):
        home_win = 0 if self.total_score[0] > self.total_score[1] else 1
        self.win_loss.append([abs(home_win - 1), home_win])  # if home win away team is 0, 1
        self.win_loss.append([home_win, abs(home_win - 1)])  # if home win home team is  1, 0

        # assign winning and losing pitchers, if home team lost assing win to away and vice versa
        if home_win == 0:
            self.teams[0].box_score.pitching_win_loss(self.winning_pitcher, True)
            self.teams[1].box_score.pitching_win_loss(self.losing_pitcher, False)
        else:
            self.teams[0].box_score.pitching_win_loss(self.losing_pitcher, False)
            self.teams[1].box_score.pitching_win_loss(self.winning_pitcher, True)
        return

    def sim_game(self):
        while self.is_game_end() is False:
            self.sim_half_inning(chatty=self.chatty)

        self.win_loss_record()
        self.teams[0].box_score.totals()
        self.teams[1].box_score.totals()
        if self.print_box_score:  # to print or not to print...
            self.teams[0].box_score.print()
            self.teams[1].box_score.print()
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
    for game_num in range(1, season_length + 1):
        print(f'Game number {game_num}: from bbgame.py test code')
        game = Game(home_team_name=home_team, away_team_name=away_team, chatty=True, print_lineup=True,
                    print_box_score=True)
        score, inning, win_loss = game.sim_game()
        season_win_loss[0] = list(np.add(np.array(season_win_loss[0]), np.array(win_loss[0])))
        season_win_loss[1] = list(np.add(np.array(season_win_loss[1]), np.array(win_loss[1])))
        if team0_season_df is None:
            team0_season_df = game.teams[0].box_score.team_box_batting
        else:
            col_list = ['G', 'AB', 'R', 'H', '2B', '3B', 'HR', 'RBI', 'SB', 'CS', 'BB', 'SO', 'SH', 'SF', 'HBP']
            team0_season_df = team0_season_df[col_list].add(game.teams[0].box_score.box_batting[col_list])
            team0_season_df['Player'] = game.teams[0].box_score.box_batting['Player']
            team0_season_df['Team'] = game.teams[0].box_score.box_batting['Team']
            team0_season_df['Pos'] = game.teams[0].box_score.box_batting['Pos']
        # print(f'Code to test inning box, Score was: {score[0]} to {score[1]}')
        print('')
        print(f'{away_team} season : {season_win_loss[0][0]} W and {season_win_loss[0][1]} L')
        print(f'{home_team} season : {season_win_loss[1][0]} W and {season_win_loss[1][1]} L')

    # team0_season_df = bbstats.team_batting_stats(team0_season_df)
    # print(team0_season_df.to_string(index=False, justify='center'))
    # end season
