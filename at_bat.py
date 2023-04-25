import pandas as pd
import numpy as np


class SimAB:
    def __init__(self):
        self.rng = np.random.default_rng()  # random number generator between 0 and 1
        self.pitching = None
        self.batting = None
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
    # Odds(matchup) = .590 -> Matchup OBP = .590 / 1.590 = .371
    def odds_ratio(self, hitter_stat, pitcher_stat, league_hitter_stat, league_pitcher_stat):
        odds_ratio = ((hitter_stat / (1 - hitter_stat)) * (pitcher_stat / (1 - pitcher_stat))) / \
                     ((league_hitter_stat / (1 - league_hitter_stat)) *
                      (league_pitcher_stat / (1 - league_pitcher_stat)))
        return odds_ratio / (1 + odds_ratio)

    def onbase(self, pitching, batting):
        return self.rng.random() < self.odds_ratio(batting.OBP, pitching.OBP, self.league_batting_obp,
                                                   self.league_pitching_obp)

    def bb(self, pitching, batting):
        return self.rng.random() < self.odds_ratio((batting.BB / batting.Total_OB), (pitching.BB / pitching.Total_OB),
                                                   (self.league_pitching_Total_BB / self.league_batting_Total_OB),
                                                   (self.league_pitching_Total_BB / self.league_pitching_Total_OB))

    def ab_outcome(self, pitching, batting):
        # outcome: on base or out pos 0, how in pos 1, rbis in pos 2
        # ?? hbp is missing, total batters faced is missing, should calc or get pitcher obp
        self.pitching = pitching
        self.batting = batting
        if self.onbase(pitching, batting):
            if self.bb(pitching, batting):
                result = ['OB', 'BB', 0]  # need to split out bb, hbp, and h and subdivide hit types
            else:  # hit, but what kind?
                result = ['OB', 'H', 0]  # need to split out bb, hbp, and h and subdivide hit types
        else:
            result = ['OUT', 'K', 0]  # ob, out sub types ob: 1b, 2b, 3b, hr, hbp, e, w; out: k, ...
        return result

    def sim_ab(self):
        pitching = self.teams[(self.top_bottom + 1) % 2].pitching.iloc[0]
        batting = self.teams[self.top_bottom].lineup.iloc[self.batting_num[self.top_bottom] - 1]
        self.bases.new_ab()
        outcome = self.ab_outcome(pitching, batting)
        if outcome[0] == 'OUT':
            self.outs += 1
        elif outcome[0] == 'OB':
            self.bases.advance_runners()
            self.score[self.top_bottom] += self.bases.runs_scored  # return rbis and clears runners across home
        return pitching, batting, outcome
