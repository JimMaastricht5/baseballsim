import numpy as np


class SimAB:
    def __init__(self, baseball_data):
        self.rng = np.random.default_rng()  # random number generator between 0 and 1
        self.pitching = None
        self.batting = None
        self.baseball_data = baseball_data

        self.league_batting_obp = self.baseball_data.batting_data['OBP'].mean()  # ?? incorrect, lazy, fine for now
        self.league_pitching_obp = self.baseball_data.pitching_data['OBP'].mean()  # ?? incorrect, lazy, fine for now
        self.league_batting_Total_OB = int(
            self.baseball_data.batting_data['H'].sum() + self.baseball_data.batting_data['BB'].sum() +
            self.baseball_data.batting_data['HBP'].sum())
        self.league_pitching_Total_OB = int(
            self.baseball_data.pitching_data['H'].sum() + self.baseball_data.pitching_data[
                'BB'].sum())  # + self.baseball_data.pitching_data['HBP']
        self.league_batting_Total_BB = int(self.baseball_data.batting_data['BB'].sum())
        self.league_pitching_Total_BB = int(self.baseball_data.pitching_data['BB'].sum())
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

    def onbase(self):
        return self.rng.random() < self.odds_ratio(self.batting.OBP, self.pitching.OBP, self.league_batting_obp,
                                                   self.league_pitching_obp)

    def h(self):
        return self.rng.random() < self.odds_ratio((self.batting.BB / self.batting.Total_OB),
                                                   (self.pitching.BB / self.pitching.Total_OB),
                                                   (self.league_pitching_Total_BB / self.league_batting_Total_OB),
                                                   (self.league_pitching_Total_BB / self.league_pitching_Total_OB))

    def hr(self):
        return self.rng.random() < self.odds_ratio((self.batting.BB / self.batting.Total_OB), (self.pitching.BB / self.pitching.Total_OB),
                                                   (self.league_pitching_Total_BB / self.league_batting_Total_OB),
                                                   (self.league_pitching_Total_BB / self.league_pitching_Total_OB))

    def triple(self):
        return self.rng.random() < self.odds_ratio((self.batting.BB / self.batting.Total_OB), (self.pitching.BB / self.pitching.Total_OB),
                                                   (self.league_pitching_Total_BB / self.league_batting_Total_OB),
                                                   (self.league_pitching_Total_BB / self.league_pitching_Total_OB))

    def double(self):
        return self.rng.random() < self.odds_ratio((self.batting.BB / self.batting.Total_OB), (self.pitching.BB / self.pitching.Total_OB),
                                                   (self.league_pitching_Total_BB / self.league_batting_Total_OB),
                                                   (self.league_pitching_Total_BB / self.league_pitching_Total_OB))

    def outcome(self, pitching, batting):
        # tree of the various odds of an event, each event is yes/no.  Onbase? Yes -> BB? no -> Hit yes (stop)
        # outcome: on base or out pos 0, how in pos 1, rbis in pos 2
        # ?? hbp is missing, total batters faced is missing, should calc or get pitcher obp
        self.pitching = pitching
        self.batting = batting
        result = ['OB', '', 0]
        if self.onbase():
            if self.h():
                result[1] = 'H'
            elif self.hr():
                result[1] = 'HR'
            elif self.triple():
                result[1] = '3B'
            elif self.double():
                result[1] = '2B'
            else:
                result[1] = 'BB'
        else:  # handle outs
            result = ['OUT', 'K', 0]  # ob, out sub types ob: 1b, 2b, 3b, hr, hbp, e, w; out: k, ...
        return result

