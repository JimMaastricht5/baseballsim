import baseball_stats
import at_bat
import numpy as np


class Bases:
    def __init__(self):
        self.clear_bases()  # initialize bases to no runners
        self.runs_scored = 0
        self.num_runners = 0
        return

    def advance_runners(self, bases_to_advance=1):
        # if bases_to_advance > 1:
        #     print('pre roll' + str(self.baserunners))
        self.baserunners = list(np.roll(self.baserunners, bases_to_advance))  # advance runners
        # if bases_to_advance > 1:
        #     print('post roll' + str(self.baserunners))
        #     print('scored?' + str(self.baserunners[-4:]))
        self.runs_scored = np.sum(self.baserunners[-4:])  # 0 ab 1, 2, 3 are bases. 4-7 run crossed home hence length 4
        self.baserunners[-4] = 0  # send the runners that score back to the dug out
        self.baserunners = [baserunner if i <= 3 else 0 for i, baserunner in enumerate(self.baserunners)]
        # print('runners back to dug out?' + str(self.baserunners))
        self.num_runners = np.sum(self.baserunners[1:3])  # add the number of people on base 1st, 2b, and 3rd
        return

    def new_ab(self):
        self.baserunners[0] = 1  # put a player ab
        self.runs_scored = 0
        return

    def clear_bases(self):
        # index 0 is ab, 1st = 1, 2nd =2 , 3rd=3, 4th=home, pos 5-7 scored
        self.baserunners = [0, 0, 0, 0, 0, 0, 0, 0]
        self.num_runners = 0
        return

    def describe_runners(self):
        desc = ''
        base_names = ['AB', '1st', '2nd', '3rd', 'home', 'scored', 'scored', 'scored']  # leave this here to keep sort order between batters
        base_names_zip = set(zip(base_names, self.baserunners))
        base_names_with_runners = list(filter(lambda base_name_zip: base_name_zip[1] > 0 and base_name_zip[0] != 'AB'
                                              and base_name_zip[0] != 'home', base_names_zip))
        base_names_with_runners.sort()
        for base_name in base_names_with_runners:  # ?? not handling triples ??
            desc = base_name[0] if desc == '' else desc + ', ' + base_name[0]
        prefix = 'Runner on ' if self.num_runners == 1 else 'Runners on '
        return prefix + desc


class TeamBoxScore:
    def __init__(self, lineup):
        self.hitting = None  # add lineup and box options for each pos or pitcher
        self.pitching = None  # pitcher plus box options for pitching
        self.box = lineup
        return


class Team:
    def __init__(self, team_name, baseball_data):
        self.team_name = team_name
        self.baseball_data = baseball_data
        self.pitchers = baseball_data.pitching_data[baseball_data.pitching_data["Team"] == team_name]
        self.pos_players = baseball_data.batting_data[baseball_data.batting_data["Team"] == team_name]

        self.lineup = None
        self.pitching = None
        self.team_box_score = None
        return

    def set_lineup(self):
        self.lineup = self.pos_players.head(10)  # assumes DH
        self.pitching = self.pitchers.head(1)
        self.team_box_score = TeamBoxScore(self.lineup)
        return


class Game:
    def __init__(self, home_team_name, away_team_name, seasons=[2022]):
        self.seasons = seasons
        self.team_names = [away_team_name, home_team_name]
        self.baseball_data = baseball_stats.BaseballData(seasons=self.seasons)
        print(f'Getting data...')
        self.baseball_data.get_seasons()

        print(f'Setting away team as {self.team_names[0]}')
        self.teams = []
        self.teams.insert(0, Team(self.team_names[0], self.baseball_data))  # away team
        self.teams[0].set_lineup()

        print(f'Setting home team as {self.team_names[1]}')
        self.teams.insert(1, Team(self.team_names[1], self.baseball_data))  # home team
        self.teams[1].set_lineup()

        self.score = [0, 0]
        self.inning = [1, 1]
        self.batting_num = [1, 1]
        self.outs = 0
        self.top_bottom = 0  # zero is top offset, 1 is bottom offset

        self.rng = np.random.default_rng()  # random number generator between 0 and 1
        self.bases = Bases()
        self.at_bat = at_bat.SimAB(self.baseball_data)
        return

    def sim_ab(self):
        pitching = self.teams[(self.top_bottom + 1) % 2].pitching.iloc[0]
        batting = self.teams[self.top_bottom].lineup.iloc[self.batting_num[self.top_bottom]-1]
        self.bases.new_ab()
        outcome = self.at_bat.outcome(pitching, batting)
        if outcome[0] == 'OUT':
            self.outs += 1
        elif outcome[0] == 'OB':
            self.bases.advance_runners(bases_to_advance=outcome[2])  # outcome 2 is number of bases to advance
            self.score[self.top_bottom] += self.bases.runs_scored
        return pitching, batting, outcome

    def sim_half_inning(self):
        top_or_bottom = 'top' if self.top_bottom == 0 else 'bottom'
        print(f'Starting the {top_or_bottom} of inning {self.inning[self.top_bottom]}.')
        while self.outs < 3:
            pitching, batting, outcome = self.sim_ab()
            print(f'Pitcher: {pitching.Player} against '
                  f'{self.team_names[self.top_bottom]} batter #'
                  f'{self.batting_num[self.top_bottom]}. {batting.Player} \n'
                  f'\t {outcome[1]}, {self.outs} Outs')
            if self.bases.runs_scored > 0:
                print(f'\tScored {self.bases.runs_scored} run(s)!  The score is {self.team_names[0]} {self.score[0]} to '
                      f'{self.team_names[1]} {self.score[1]}')  # ?? need to handle walk offs...
            if self.bases.num_runners >= 1 and self.outs < 3:  # leave out the batter to check for runner
                print(f'\t{self.bases.describe_runners()}')
            self.batting_num[self.top_bottom] = self.batting_num[self.top_bottom] + 1 \
                if self.batting_num[self.top_bottom] <= 9 else 1

        # half inning over
        self.bases.clear_bases()
        print(f'\nCompleted {top_or_bottom} half of inning {self.inning[self.top_bottom]}.')
        print(f'The score is {self.team_names[0]} {self.score[0]} to {self.team_names[1]} {self.score[1]}\n')
        self.inning[self.top_bottom] += 1
        self.top_bottom = 0 if self.top_bottom == 1 else 1
        self.outs = 0
        return

    def sim_game(self):
        game_end = False
        while game_end is False:
            if self.score[0] == self.score[1]:  # tie game play on no matter what
                self.sim_half_inning()
            elif self.top_bottom == 0:  # always play top half an inning
                self.sim_half_inning()
            elif self.inning[1] == 9 and self.score[0] < self.score[1]:  # home team is winning don't play bot 9
                game_end = True  # end game
            elif self.inning[1] <= 9:  # played less than 9 complete if the active inning is 9
                self.sim_half_inning()
            else:
                game_end = True  # end game
                # report final score for standings
        return game_end


if __name__ == '__main__':
    home_team = 'MIL'
    away_team = 'MIN'
    game = Game(home_team_name=home_team, away_team_name=away_team)
    _ = game.sim_game()
