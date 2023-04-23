import baseball_stats
import numpy as np


class Bases:
    def __init__(self):
        self.baserunners = np.zeros(5)  # 0th position is the batter, 4 bases, all empty, home plate (4) is a run scored
        self.runs_scored = 0
        self.num_runners = 0
        return

    def advance_runners(self):
        self.baserunners = np.roll(self.baserunners, 1)  # advance runners
        self.runs_scored = self.baserunners[4]  # run crossed home
        self.num_runners = np.sum(self.baserunners)
        return

    def new_ab(self):
        self.baserunners[0] = 1  # put a player ab
        self.runs_scored = 0
        return

    def clear_bases(self):
        self.baserunners = np.zeros(5)
        self.num_runners = 0
        return

    def describe_runners(self):
        desc = ''
        base_names = ['AB', '1st', '2nd', '3rd', 'home']  # leave this here to keep sort order between batters
        base_names_zip = set(zip(base_names, self.baserunners))
        base_names_with_runners = list(filter(lambda base_name_zip: base_name_zip[1] > 0 and base_name_zip[0]!='AB' and
                                                                    base_name_zip[0]!='home', base_names_zip))
        base_names_with_runners.sort()
        for base_name in base_names_with_runners:
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
        self.league_batting_obp = .4
        self.league_pitching_obp = .375

        self.rng = np.random.default_rng()  # random number generator between 0 and 1
        self.bases = Bases()
        return

    # odds ratio is odds of the hitter * odds of the pitcher over the odds of the league or enviroment
    # the ratio only works for 2 outcomes, e.g., on base or note on base.
    # additional outcomes need to be chained, e.g., on base was it a hit?
    # example odds ratio.  Hitter with an obp of .400 odds ratio would be .400/(1-.400)
    # hitter with an OBP of .400 in a league of .300 facing a pitcher with an OBP of .250 in a league of .350, and
    # they are both playing in a league ( or park) where the OBP is expected to be .380 for the league average player.
    # Odds(matchup)(.400 / .600) * (.250 / .750)
    # ——————- =————————————-
    # (.380 / .620)(.300 / .700) * (.350 / .650)
    # Odds(matchup) = .590
    # Matchup
    # OBP = .590 / 1.590 = .371
    def odds_ratio(self, hitter_stat, pitcher_stat, league_hitter_stat, league_pitcher_stat):
        odds_ratio = (hitter_stat / (1 - hitter_stat) * pitcher_stat / (1 - pitcher_stat)) / \
                     (league_hitter_stat / (1 - league_hitter_stat) * league_pitcher_stat / (1 - league_pitcher_stat))
        return odds_ratio

    def ab_outcome(self, pitching, batting):
        # outcome: on base or out pos 0, how in pos 1, rbis in pos 2
        # ?? hbp is missing, total batters faced is missing
        odds_onbase = self.odds_ratio(batting.OBP, ((pitching.H + pitching.BB) /
                                                    (pitching.WHIP * pitching.IP + pitching.IP * 3)),
                                      self.league_batting_obp, self.league_pitching_obp)
        dice_roll = self.rng.random()
        # print(dice_roll, odds_onbase)
        if dice_roll <= odds_onbase:
            result = ['OB', 'H', 0]  # need to split out bb, hbp, and h and subdivide hit types
        else:
            result = ['OUT', 'K', 0]  # ob, out sub types ob: 1b, 2b, 3b, hr, hbp, e, w; out: k, ...
        return result

    def sim_ab(self):
        pitching = self.teams[(self.top_bottom + 1) % 2].pitching.iloc[0]
        batting = self.teams[self.top_bottom].lineup.iloc[self.batting_num[self.top_bottom]-1]
        self.bases.new_ab()
        outcome = self.ab_outcome(pitching, batting)
        if outcome[0] == 'OUT':
            self.outs += 1
        elif outcome[0] == 'OB':
            self.bases.advance_runners()
            self.score[self.top_bottom] += self.bases.runs_scored  # return rbis and clears runners across home
            if self.bases.runs_scored > 0:
                print(f'scored... {self.score}')
        return pitching, batting, outcome

    def sim_half_inning(self):
        top_or_bottom = 'top' if self.top_bottom == 0 else 'bottom'
        print(f'Starting the {top_or_bottom} of inning {self.inning[self.top_bottom]}.')
        while self.outs < 3:
            pitching, batting, outcome = self.sim_ab()  # assuming an out for now...
            print(f'Pitcher: {pitching.Player} against '
                  f'{self.team_names[self.top_bottom]} batter #'
                  f'{self.batting_num[self.top_bottom]}. {batting.Player} \n'
                  f'\t {outcome[1]}, {self.outs} Outs')
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
            elif self.inning[1] <= 9:  # played less than 9 complete if the active inning is 9
                self.sim_half_inning()
            elif self.inning[1] == 9 and self.score[0] >= self.score[1]:  # home team is tied or losing, play bot 9
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
