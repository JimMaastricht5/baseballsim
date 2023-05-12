import numpy as np


class SimAB:
    def __init__(self, baseball_data):
        self.rng = lambda: np.random.default_rng().uniform(low=0.0, high=1.001)  # random generator between 0 and 1
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
        self.league_batting_Total_HR = int(self.baseball_data.batting_data['HR'].sum())
        self.league_batting_Total_3B = int(self.baseball_data.batting_data['3B'].sum())
        self.league_batting_Total_2B = int(self.baseball_data.batting_data['2B'].sum())
        self.league_Total_outs = int(self.baseball_data.batting_data['AB'].sum() -
                                     self.baseball_data.batting_data['H'].sum() - \
                                 self.baseball_data.batting_data['HBP'].sum() )
        self.league_K_rate_per_AB = float(self.baseball_data.batting_data['SO'].sum() /
                                          self.league_Total_outs)  # strike out or in play
        self.league_GB = .429  # ground ball rate for season
        self.league_FB = .372  # fly ball rate for season
        self.league_LD = .199  # line drive rate for the season

        return

    # odds ratio is odds of the hitter * odds of the pitcher over the odds of the league or enviroment
    # the ratio only works for 2 outcomes, e.g., on base or not on base.
    # additional outcomes need to be chained, e.g., on base was it a hit?
    # example odds ratio.  Hitter with an obp of .400 odds ratio would be .400/(1-.400)
    # hitter with an OBP of .400 in a league of .300 facing a pitcher with an OBP of .250 in a league of .350, and
    # they are both playing in a league ( or park) where the OBP is expected to be .380 for the league average player.
    # Odds(matchup)(.400 / .600) * (.250 / .750)
    # ——————- =————————————-
    # (.380 / .620)(.300 / .700) * (.350 / .650)
    # Odds(matchup) = .590 -> Matchup OBP = .590 / 1.590 = .371
    #
    def odds_ratio(self, hitter_stat, pitcher_stat, league_stat):
        odds_ratio = ((hitter_stat / (1 - hitter_stat)) * (pitcher_stat / (1 - pitcher_stat))) / \
                     (league_stat / (1 - league_stat))
        print(str(odds_ratio / (1 + odds_ratio)))
        return odds_ratio / (1 + odds_ratio)

    def onbase(self):
        # print('on base: ' + str(self.odds_ratio(self.batting.OBP, self.pitching.OBP, self.league_batting_obp)))
        return self.rng() < self.odds_ratio(self.batting.OBP, self.pitching.OBP, self.league_batting_obp)

    def bb(self):
        return self.rng() < self.odds_ratio((self.batting.BB / self.batting.Total_OB),
                                                   (self.pitching.BB / self.pitching.Total_OB),
                                                   (self.league_batting_Total_BB / self.league_batting_Total_OB))

    def hr(self):
        return self.rng() < self.odds_ratio((self.batting.HR / self.batting.Total_OB),
                                            (self.pitching.HR / self.pitching.Total_OB),
                                            (self.league_batting_Total_HR / self.league_batting_Total_OB))

    def triple(self):
        # do not have league pitching total for 3b so push it to zero and make it a neutral factor
        return self.rng() < self.odds_ratio((self.batting['3B'] / self.batting.Total_OB), (.1),
                                                   (self.league_batting_Total_3B / self.league_batting_Total_OB))

    def double(self):
        # do not have league pitching total for 2b so push it to zero and make it a neutral factor
        return self.rng() < self.odds_ratio((self.batting['2B'] / self.batting.Total_OB), (.200),
                                                   (self.league_batting_Total_2B / self.league_batting_Total_OB))

    def k(self):
        return self.rng() < self.odds_ratio((self.batting['SO'] / self.batting.Total_Outs),
                                                   (self.pitching['K'] / self.pitching.Total_Outs),
                                                   self.league_K_rate_per_AB)

    def gb_fb_lo(self, result):
        dice_roll = self.rng()
        if dice_roll <= self.league_GB:  # ground out
            result[1] = 'GB'
        elif dice_roll <= (self.league_FB + self.league_GB):  # fly ball
            result[1] = 'FB'
        else:
            result[1] = 'LD'  # line drive
        return result

    def outcome(self, pitching, batting):
        # tree of the various odds of an event, each event is yes/no.  Onbase? Yes -> BB? no -> Hit yes (stop)
        # outcome: on base or out pos 0, how in pos 1, bases to advance in pos 2
        # ?? hbp is missing, total batters faced is missing, should calc or get pitcher obp
        self.pitching = pitching
        self.batting = batting
        result = ['OB', '', 1]
        if self.onbase():
            print('on base')
            if self.bb():
                result[1] = 'BB'
            elif self.double():
                result[1] = '2B'
                result[2] = 2
            elif self.triple():
                result[1] = '3B'
                result[2] = 3
            elif self.hr():
                result[1] = 'HR'
                result[2] = 4
            else:
                result[1] = 'H'  # one base is default
        else:  # handle outs
            if self.k():
                result = ['OUT', 'K', 0]  # ob, out sub types ob: 1b, 2b, 3b, hr, hbp, e, w; out: k, ...
            else:
                result = self.gb_fb_lo(['OUT', '', 0])  # not a strike out, fb, go, or lo
        return result
