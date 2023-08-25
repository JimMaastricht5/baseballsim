import numpy as np
import warnings
import bbstats


class OutCome:
    def __init__(self):
        self.outs_on_play = 0
        self.on_base_b = False
        self.score_book_cd = ''
        self.bases_to_advance = 0
        self.runs_scored = 0
        self.bases_dict = {'BB': 1, 'H': 1, '2B': 2, '3B': 3, 'HR': 4, 'K': 0, 'SO': 0, 'GB': 0, 'DP': 0,
                           'FO': 0, 'LD': 0, 'SF': 0}
        self.on_base_dict = {'BB': True, 'H': True, '2B': True, '3B': True, 'HR': True, 'K': False, 'SO': False,
                             'GB': False, 'DP': False, 'FO': False, 'LD': False, 'SF': False}
        self.outs_dict = {'BB': 0, 'H': 0, '2B': 0, '3B': 0, 'HR': 0, 'K': 1, 'SO': 1, 'GB': 1, 'DP': 2, 'FO': 1,
                          'LD': 1, 'SF': 0}
        return

    def reset(self):
        self.on_base_b = False
        self.score_book_cd = ''
        self.bases_to_advance = 0
        self.runs_scored = 0
        return

    def set_score_book_cd(self, cd):
        self.score_book_cd = cd
        self.bases_to_advance = self.bases_dict[cd]  # automatically advance x number of bases for all runners
        self.on_base_b = self.on_base_dict[cd]
        self.outs_on_play = self.outs_dict[cd]
        return

    def set_runs_score(self, runs_scored):
        self.runs_scored = runs_scored
        return

    def convert_k(self):
        if self.score_book_cd == 'SO':
            self.score_book_cd = 'K'
        return


class SimAB:
    def __init__(self, baseball_data):
        self.rng = lambda: np.random.default_rng().uniform(low=0.0, high=1.001)  # random generator between 0 and 1
        self.dice_roll = None
        self.pitching = None
        self.batting = None
        self.baseball_data = baseball_data

        self.league_batting_totals_df = bbstats.team_batting_totals(self.baseball_data.batting_data, concat=False)
        self.league_pitching_totals_df = bbstats.team_pitching_totals(self.baseball_data.pitching_data, concat=False)

        # set league totals for odds ratio
        self.league_batting_obp = float(self.league_batting_totals_df['OBP'])
        self.league_pitching_obp = float(self.league_pitching_totals_df['OBP'])
        self.league_batting_Total_OB = int(
            self.baseball_data.batting_data['H'].sum() + self.baseball_data.batting_data['BB'].sum() +
            self.baseball_data.batting_data['HBP'].sum())
        self.league_pitching_Total_OB = int(
            self.baseball_data.pitching_data['H'].sum() + self.baseball_data.pitching_data[
                'BB'].sum())  # + self.baseball_data.pitching_data['HBP']
        self.league_batting_Total_BB = int(self.league_batting_totals_df['BB'])
        self.league_batting_Total_HR = int(self.league_batting_totals_df['HR'])
        self.league_batting_Total_3B = int(self.league_batting_totals_df['3B'])
        self.league_batting_Total_2B = int(self.league_batting_totals_df['2B'])
        self.league_Total_outs = int(self.baseball_data.batting_data['AB'].sum() -
                                     self.baseball_data.batting_data['H'].sum() -
                                     self.baseball_data.batting_data['HBP'].sum())
        self.league_K_rate_per_AB = float(self.baseball_data.batting_data['SO'].sum() /
                                          self.league_Total_outs)  # strike out or in play
        self.league_GB = .429  # ground ball rate for season
        self.league_FB = .372  # fly ball rate for season
        self.league_LD = .199  # line drive rate for the season
        self.OBP_adjustment = -0.025  # final adjustment to line up with prior seasons
        self.bb_adjustment = -0.30  # final adjustment to shift more bb to H
        self.dp_chance = .20  # 20% chance dp with runner on per mlb
        self.tag_up_chance = .20  # 20% chance of tagging up and scoring, per mlb
        return

    # odds ratio is odds of the hitter * odds of the pitcher over the odds of the league or environment
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
    def odds_ratio(self, hitter_stat, pitcher_stat, league_stat, stat_type=''):
        # print(f'at_bat.odds ratio, hitter stat:{hitter_stat}, pitcher stat{pitcher_stat}')
        odds_ratio = 0
        with warnings.catch_warnings():
            warnings.filterwarnings("error")
            try:
                odds_ratio = ((hitter_stat / (1 - hitter_stat)) * (pitcher_stat / (1 - pitcher_stat))) / \
                             (league_stat / (1 - league_stat))
            except ZeroDivisionError:
                print(f'Exception in odds ratio calculation for hitter:{hitter_stat}, pitcher:{pitcher_stat}, '
                      f'league: {league_stat} {stat_type}')
            except Warning as warning:
                print(f'Warning in odds ratio calculation for hitter:{hitter_stat}, pitcher:{pitcher_stat}, '
                      f'league: {league_stat} {stat_type}')
                print("Warning caught:", warning)
        return odds_ratio / (1 + odds_ratio)

    def onbase(self):
        # print('on base: ' + str(self.odds_ratio(self.batting.OBP, self.pitching.OBP, self.league_batting_obp)))
        return self.rng() < self.odds_ratio(self.batting.OBP + self.pitching.Game_Fatigue_Factor + self.OBP_adjustment,
                                            self.pitching.OBP + self.pitching.Game_Fatigue_Factor + self.OBP_adjustment,
                                            self.league_batting_obp + self.OBP_adjustment, stat_type='obp')

    def bb(self):
        return self.rng() < self.odds_ratio(((self.batting.BB + self.bb_adjustment) / self.batting.Total_OB),
                                            ((self.pitching.BB + self.bb_adjustment) / self.pitching.Total_OB),
                                            ((self.league_batting_Total_BB + self.bb_adjustment) /
                                              self.league_batting_Total_OB),
                                            stat_type='BB')

    def hr(self):
        return self.rng() < self.odds_ratio((self.batting.HR / self.batting.Total_OB),
                                            (self.pitching.HR / self.pitching.Total_OB),
                                            (self.league_batting_Total_HR / self.league_batting_Total_OB),
                                            stat_type='HR')

    def triple(self):
        # do not have league pitching total for 3b so push it to zero and make it a neutral factor
        return self.rng() < self.odds_ratio(hitter_stat=(self.batting['3B'] / self.batting.Total_OB), pitcher_stat=.016,
                                            league_stat=(self.league_batting_Total_3B / self.league_batting_Total_OB),
                                            stat_type='3B')

    def double(self):
        # do not have league pitching total for 2b so push it to zero and make it a neutral factor
        return self.rng() < self.odds_ratio(hitter_stat=(self.batting['2B'] / self.batting.Total_OB), pitcher_stat=.200,
                                            league_stat=(self.league_batting_Total_2B / self.league_batting_Total_OB),
                                            stat_type='2B')

    def k(self):
        return self.rng() < self.odds_ratio((self.batting['SO'] / self.batting.Total_Outs),
                                            (self.pitching['K'] / self.pitching.Total_Outs),
                                            self.league_K_rate_per_AB, stat_type='K')

    def gb_fo_lo(self, outs=0, runner_on_first=False, runner_on_third=False):
        self.dice_roll = self.rng()
        if self.dice_roll <= self.league_GB:  # ground out
            score_book_cd = 'GB'
            if runner_on_first and outs <= 1 and self.rng() <= self.dp_chance:
                score_book_cd = 'DP'
        elif self.dice_roll <= (self.league_FB + self.league_GB):  # fly out ball
            if self.rng() <= self.tag_up_chance and runner_on_third:
                score_book_cd = 'SF'
            else:
                score_book_cd = 'FO'
        else:
            score_book_cd = 'LD'  # line drive
        return score_book_cd

    def outcome(self, pitching, batting, outcomes, outs=0, runner_on_first=False, runner_on_third=False):
        # tree of the various odds of an event, each event is yes/no.  Onbase? Yes -> BB? no -> Hit yes (stop)
        # outcome: on base or out pos 0, how in pos 1, bases to advance in pos 2, rbis in pos 3
        # ?? hbp is missing, total batters faced is missing, should calc or get pitcher obp
        self.pitching = pitching
        self.batting = batting
        outcomes.reset()
        if self.onbase():
            if self.bb():
                outcomes.set_score_book_cd('BB')
            elif self.double():
                outcomes.set_score_book_cd('2B')
            elif self.triple():
                outcomes.set_score_book_cd('3B')
            elif self.hr():
                outcomes.set_score_book_cd('HR')
            else:
                outcomes.set_score_book_cd('H')
        else:  # handle outs
            if self.k():
                outcomes.set_score_book_cd('K')
            else:
                outcomes.set_score_book_cd(self.gb_fo_lo(outs, runner_on_first, runner_on_third))
        return
