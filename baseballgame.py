import baseball_stats
import numpy as np


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
        self.baserunners = np.zeros(4)  # 4 bases, all empty, homeplate is a run scored
        self.top_bottom = 0  # zero is top offset, 1 is bottom offset
        self.league_batting_obp = .4
        self.league_pitching_obp = .375

        self.rng = np.random.default_rng()  # random number generator between 0 and 1
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
        # ?? hbp is missing, total batters faced is missing
        odds_onbase = self.odds_ratio(batting.OBP, ((pitching.H + pitching.BB) / (pitching.WHIP * pitching.IP + pitching.IP * 3)), self.league_batting_obp, self.league_pitching_obp)
        dice_roll = self.rng.random()
        if dice_roll <= odds_onbase:
            result = ['OB', 'H']  # everything is a hit for now, need to split out bb, hbp, and h and sub divide hit types
        else:
            result = ['OUT', 'K']  # ob, out sub types ob: 1b, 2b, 3b, hr, hbp, e, w; out: k, ...
        return result

    def sim_ab(self):
        pitching = self.teams[self.top_bottom].pitching.iloc[0]
        batting = self.teams[self.top_bottom].lineup.iloc[self.batting_num[self.top_bottom]-1]
        outcome = self.ab_outcome(pitching, batting)
        if outcome[0] == 'OUT':
            self.outs += 1
        elif outcome[0] == 'OB':
            print('handle base runner.....')
            np.roll(self.baserunners, 1)  # advance runners and make room at first
            self.baserunners[1-1] = 1
            if self.baserunners[4-1]:
                print('run scored')
                self.baserunners[4-1] = 0

        return pitching, batting, outcome

    def sim_half_inning(self):
        while self.outs < 3:
            pitching, batting, outcome = self.sim_ab()  # assuming an out for now...
            print(f'Pitching: {pitching.Player} against '
                  f'{self.team_names[self.top_bottom]} batter #'
                  f'{self.batting_num[self.top_bottom]}. {batting.Player} '
                  f' {outcome[1]}, {self.outs} Outs')
            self.batting_num[self.top_bottom] = self.batting_num[self.top_bottom] + 1 \
                if self.batting_num[self.top_bottom] <= 9 else 1

        # half inning over
        top_or_bottom = 'top' if self.top_bottom == 0 else 'bottom'
        print(f'Completed {top_or_bottom} half inning: {self.inning[self.top_bottom]}')
        print(f'The score is {self.team_names[0]} {self.score[0]} to {self.team_names[1]} {self.score[1]}')
        self.inning[self.top_bottom] += 1
        self.top_bottom = 0 if self.top_bottom == 1 else 1
        self.outs = 0
        return

    def sim_game(self):
        game_end = False
        while game_end is False:
            if self.inning[1] < 9:  # home team has played less than nine innings
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
