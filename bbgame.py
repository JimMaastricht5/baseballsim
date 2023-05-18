import bbstats
import bbteam
import at_bat
import numpy as np
import bbbaserunners
import pandas as pd


class Game:
    def __init__(self, away_team_name, home_team_name, baseball_data=None):
        self.team_names = [away_team_name, home_team_name]
        self.baseball_data = bbstats.BaseballStats() if baseball_data is None else baseball_data
        # if baseball_data is None:  # else passed in from season sim
        #     self.baseball_data = bbstats.BaseballStats()
        # else:
        #     self.baseball_data = baseball_data
        # print(f'Setting away team as {self.team_names[0]}')
        self.teams = []  # keep track of away in pos 0 and home team in pos 1
        self.teams.insert(0, bbteam.Team(self.team_names[0], self.baseball_data))  # away team
        self.teams[0].set_lineup()

        # print(f'Setting home team as {self.team_names[1]}')
        self.teams.insert(1, bbteam.Team(self.team_names[1], self.baseball_data))  # home team
        self.teams[1].set_lineup()

        self.win_loss = []
        self.score = [0, 0]
        self.inning = [1, 1]
        self.batting_num = [1, 1]
        self.pitching_num = [0, 0]
        self.outs = 0
        self.top_bottom = 0  # zero is top offset, 1 is bottom offset

        self.rng = np.random.default_rng()  # random number generator between 0 and 1
        self.bases = bbbaserunners.Bases()
        self.at_bat = at_bat.SimAB(self.baseball_data)
        return

    def sim_ab(self):
        cur_pitching_index = self.teams[(self.top_bottom + 1) % 2].cur_pitcher_index
        pitching = self.teams[(self.top_bottom + 1) % 2].pitching.iloc[cur_pitching_index]  # data for pitcher

        cur_batter_index = self.teams[self.top_bottom].??
        batting = self.teams[self.top_bottom].lineup.iloc[self.batting_num[self.top_bottom]-1]  # data for batter
        self.bases.new_ab()
        outcome = self.at_bat.outcome(pitching, batting)
        if outcome[0] == 'OUT':
            self.outs += 1
        elif outcome[0] == 'OB':
            self.bases.advance_runners(bases_to_advance=outcome[2])  # outcome 2 is number of bases to advance
            self.score[self.top_bottom] += self.bases.runs_scored
            outcome[3] = self.bases.runs_scored  # rbis for batter
        self.teams[(self.top_bottom + 1) % 2].team_box_score.pitching_result(cur_pitching_index, outcome)
        self.teams[self.top_bottom].team_box_score.batting_result(self.batting_num[self.top_bottom]-1, outcome)
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
            if self.bases.runs_scored > 0 and chatty:
                print(f'\tScored {self.bases.runs_scored} run(s)!  The score is {self.team_names[0]} {self.score[0]} to'
                      f' {self.team_names[1]} {self.score[1]}')  # ?? need to handle walk offs...
            if self.bases.num_runners >= 1 and self.outs < 3 and chatty:  # leave out the batter to check for runner
                print(f'\t{self.bases.describe_runners()}')
            self.batting_num[self.top_bottom] = self.batting_num[self.top_bottom] + 1 \
                if self.batting_num[self.top_bottom] <= 9 else 1

        # half inning over
        self.bases.clear_bases()
        if chatty:
            print('')  # add a blank line for verbose output
            print(f'Completed {top_or_bottom} half of inning {self.inning[self.top_bottom]}. '
                  f'The score is {self.team_names[0]} {self.score[0]} to {self.team_names[1]} {self.score[1]}')
        self.inning[self.top_bottom] += 1
        self.top_bottom = 0 if self.top_bottom == 1 else 1
        self.outs = 0
        return

    def game_end(self):
        return False if self.inning[0] <= 9 or self.inning[1] <= 8 or\
                        (self.inning[0] != self.inning[1] and self.score[0] >= self.score[1])\
                        or self.score[0] == self.score[1] else True

    def win_loss_record(self):
        home_win = 0 if self.score[0] > self.score[1] else 1
        self.win_loss.append([abs(home_win - 1), home_win])  # if home win away team is 0, 1
        self.win_loss.append([home_win, abs(home_win - 1)])  # if home win home team is  1, 0
        return

    def sim_game(self, chatty=True):
        while self.game_end() is False:
            self.sim_half_inning(chatty=chatty)

        self.win_loss_record()
        self.teams[0].team_box_score.totals()
        self.teams[0].team_box_score.print()

        self.teams[1].team_box_score.totals()
        self.teams[1].team_box_score.print()
        return self.score, self.inning, self.win_loss


# test a number of games
if __name__ == '__main__':
    home_team = 'MIL'
    away_team = 'MIN'
    season_length = 1
    season_win_loss = [[0, 0], [0, 0]]  # away record pos 0, home pos 1
    team0_season_df = None
    for game_num in range(1, season_length + 1):
        print(game_num)
        game = Game(home_team_name=home_team, away_team_name=away_team)
        score, inning, win_loss = game.sim_game(chatty=True)
        season_win_loss[0] = list(np.add(np.array(season_win_loss[0]), np.array(win_loss[0])))
        season_win_loss[1] = list(np.add(np.array(season_win_loss[1]), np.array(win_loss[1])))
        if team0_season_df is None:
            team0_season_df = game.teams[0].team_box_score.box_batting
        else:
            col_list = ['G', 'AB', 'R', 'H', '2B', '3B', 'HR', 'RBI', 'SB', 'CS', 'BB', 'SO', 'SH', 'SF', 'HBP']
            team0_season_df = team0_season_df[col_list].add(game.teams[0].team_box_score.box_batting[col_list])
            team0_season_df['Player'] = game.teams[0].team_box_score.box_batting['Player']
            team0_season_df['Team'] = game.teams[0].team_box_score.box_batting['Team']
            team0_season_df['Pos'] = game.teams[0].team_box_score.box_batting['Pos']
        print(f'Score was: {score[0]} to {score[1]}')
        print(f'{away_team} season : {season_win_loss[0][0]} W and {season_win_loss[0][1]} L')
        print(f'{home_team} season : {season_win_loss[1][0]} W and {season_win_loss[1][1]} L')

    # team0_season_df = bbstats.team_batting_stats(team0_season_df)
    # print(team0_season_df.to_string(index=False, justify='center'))
    # end season
