# MIT License
#
# 2024 Jim Maastricht
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
#
# JimMaastricht5@gmail.com
import numpy as np
import warnings
import bbstats
from numpy import bool_, float64
from pandas.core.series import Series
from typing import Union


class OutCome:
    def __init__(self, debug: bool = False) -> None:
        """
        class handles tracking battering outcomes and translating that into base running results
        dict in object maintains translation to runner movement and outs
        :return: None
        """
        self.debug = debug
        self.outs_on_play = 0
        self.on_base_b = False  # if this a BB or some form of a hit does not cover GB FC
        self.score_book_cd = ''
        self.bases_to_advance = 0
        self.runs_scored = 0
        self.bases_dict = {'BB': 1, 'HBP': 1, 'H': 1, '2B': 2, '3B': 3, 'HR': 4, 'SO': 0, 'GB': 1, 'DP': 1,
                           'GB FC': 1, 'FO': 0, 'LD': 0, 'SF': 0}  # some outs allow runners to move such as dp or gb
        self.on_base_dict = {'BB': True, 'HBP': True, 'H': True, '2B': True, '3B': True, 'HR': True,
                             'SO': False, 'GB': False, 'DP': False, 'GB FC': False, 'FO': False, 'LD': False,
                             'SF': False}
        self.outs_dict = {'BB': 0, 'HBP': 0, 'H': 0, '2B': 0, '3B': 0, 'HR': 0, 'SO': 1, 'GB': 1, 'DP': 2,
                          'GB FC': 1, 'FO': 1, 'LD': 1, 'SF': 1}
        return

    def reset(self) -> None:
        """
        # resets the bases for the start of a half inning
        :return: None
        """
        self.on_base_b = False
        self.score_book_cd = ''
        self.bases_to_advance = 0
        self.runs_scored = 0
        return

    def set_score_book_cd(self, cd: str) -> None:
        """
        grab the scorebook code for the at bat. advance runners, set outs on play, and on base indicator for ab
        :param cd:
        :return: None
        """
        self.score_book_cd = cd
        self.bases_to_advance = self.bases_dict[cd]  # automatically advance x number of bases for all runners
        self.on_base_b = self.on_base_dict[cd]
        self.outs_on_play = self.outs_dict[cd]
        return

    def set_runs_score(self, runs_scored: int) -> None:
        """
        # set runs scored on play in the class
        :param runs_scored: runs scored on the play
        :return: None
        """
        self.runs_scored = runs_scored
        return


class SimAB:
    def __init__(self, baseball_data: bbstats.BaseballStats, debug: bool = False) -> None:
        """
        class handles calculating the outcome of an ab based on pitcher, batter, and league probabilities
        :param baseball_data: class containing the league data and methods
        :return: None
        """
        self.debug = debug
        self.rng = lambda: np.random.default_rng().uniform(low=0.0, high=1.001)  # random generator between 0 and 1
        self.dice_roll = None
        self.pitching = None
        self.batting = None
        self.baseball_data = baseball_data

        self.league_batting_totals_df = bbstats.team_batting_totals(self.baseball_data.batting_data)
        self.league_pitching_totals_df = bbstats.team_pitching_totals(self.baseball_data.pitching_data)

        # set league totals for odds ratio
        self.league_batting_obp = self.league_batting_totals_df.at[0, 'OBP']
        self.league_pitching_obp = self.league_pitching_totals_df.at[0, 'OBP']
        batting_data_sum = self.baseball_data.batting_data[['H', 'BB', 'HBP']].sum()
        self.league_batting_Total_OB = batting_data_sum['H'] + batting_data_sum['BB'] + batting_data_sum['HBP']
        self.league_pitching_Total_OB = self.baseball_data.pitching_data[['H', 'BB']].sum().sum()
        self.league_batting_Total_BB = self.league_batting_totals_df.at[0, 'BB']
        self.league_batting_Total_HBP = self.league_batting_totals_df.at[0, 'HBP']
        self.league_batting_Total_HR = self.league_batting_totals_df.at[0, 'HR']
        self.league_batting_Total_3B = self.league_batting_totals_df.at[0, '3B']
        self.league_batting_Total_2B = self.league_batting_totals_df.at[0, '2B']
        self.league_Total_outs = self.baseball_data.batting_data['AB'].sum() - batting_data_sum.sum()
        self.league_K_rate_per_AB = self.baseball_data.batting_data['SO'].sum() / self.league_Total_outs
        self.league_GB = .429  # ground ball rate for season
        self.league_GB_FC = .10  # GB FC occur 10 out of 100 times ball in play
        self.league_FB = .372  # fly ball rate for season
        self.league_LD = .199  # line drive rate for the season
        self.OBP_adjustment = 0  # final adjustment to line up with prior seasons, 2022 -0.025
        self.BB_adjustment = -0.30  # final adjustment to shift more bb to H
        self.HBP_rate = .0143  # 1.4% of AB in 2022
        self.HBP_adjustment = 0.0143 * 4.0  # adjustment to shift more to or from hbp league avg is 1.4%, results 1/4 of
        self.HR_adjustment = 1.1  # adjust for higher HR rate with new 2023 pitching rules
        self.DBL_adjustment = 1.1  # adjust for higher 2B rate with new 2023 pitching rules
        self.dp_chance = .20  # 20% chance dp with runner on per mlb
        self.tag_up_chance = .20  # 20% chance of tagging up and scoring, per mlb
        return

    def onbase(self) -> bool:
        """
        did the batter reach base?
        :return: true if batter reached base
        """
        return self.rng() < self.odds_ratio(self.batting.OBP + self.pitching.Game_Fatigue_Factor + self.OBP_adjustment,
                                            self.pitching.OBP + self.pitching.Game_Fatigue_Factor + self.OBP_adjustment,
                                            self.league_batting_obp + self.OBP_adjustment, stat_type='obp')

    def bb(self) -> bool:
        """
        if the batter reached base was it a walk?
        :return: true if walk
        """
        return self.rng() < self.odds_ratio(((self.batting.BB + self.BB_adjustment) / self.batting.Total_OB),
                                            ((self.pitching.BB + self.BB_adjustment) / self.pitching.Total_OB),
                                            ((self.league_batting_Total_BB + self.BB_adjustment) /
                                             self.league_batting_Total_OB),
                                            stat_type='BB')

    def hbp(self) -> bool:
        """
        if the batter reached base with it a hit by pitch?
        :return: true if HBP
        """
        # return self.rng() < (self.HBP_rate + self.HBP_adjustment)
        return self.rng() < self.odds_ratio((self.batting['HBP'] / self.batting.Total_Outs),
                                            (self.pitching['HBP'] / self.pitching.Total_Outs),
                                            float64((self.HBP_rate + self.HBP_adjustment)), stat_type='HBP')

    def hr(self) -> bool:
        """
        if the batter reached base was it a home run?
        :return: true if HR
        """
        return self.rng() < self.odds_ratio(((self.batting.HR + self.HR_adjustment) / self.batting.Total_OB),
                                            ((self.pitching.HR + self.HR_adjustment) / self.pitching.Total_OB),
                                            ((self.league_batting_Total_HR + self.HR_adjustment) /
                                            self.league_batting_Total_OB),
                                            stat_type='HR')

    def triple(self) -> bool:
        """
        if the batter reached base was it a triple?
        :return: true if triple
        """
        # do not have league pitching total for 3b so push it to zero and make it a neutral factor
        return self.rng() < self.odds_ratio(hitter_stat=(self.batting['3B'] / self.batting.Total_OB), pitcher_stat=.016,
                                            league_stat=(self.league_batting_Total_3B / self.league_batting_Total_OB),
                                            stat_type='3B')

    def double(self) -> Union[bool, bool_]:
        """
        if the batter reached base was it a double?
        :return: true if double, allows for either numpy bool or builtin python bool
        """
        # do not have league pitching total for 2b so push it to zero and make it a neutral factor
        return self.rng() < self.odds_ratio(hitter_stat=((self.batting['2B'] + self.DBL_adjustment) /
                                                         self.batting.Total_OB), pitcher_stat=.200,
                                            league_stat=((self.league_batting_Total_2B + self.DBL_adjustment) /
                                                         self.league_batting_Total_OB),
                                            stat_type='2B')

    def k(self) -> bool:
        """
        if the batter was out was it a strike out?
        :return: true if K
        """
        return self.rng() < self.odds_ratio((self.batting['SO'] / self.batting.Total_Outs),
                                            (self.pitching['SO'] / self.pitching.Total_Outs),
                                            self.league_K_rate_per_AB, stat_type='SO')

    def gb_fo_lo(self, outs: int = 0, runner_on_first: bool = False, runner_on_third: bool = False) -> str:
        """
        if the batter did not reach base, and it was not a k handle ground balls, fly outs and line outs
        :param outs: number of outs in inning, used to determine double play probability
        :param runner_on_first: is there a runner on first?  used for double play probability
        :param runner_on_third: is there a runner on third?  used for tag up probabaility
        :return: string containing scorebook code for the out.  gb=ground ball, dp=double play, gb fc is a ground
            ball fielders choice, sf= is a sacrifice fly, and fo is a fly out.
        """
        self.dice_roll = self.rng()
        if self.dice_roll <= self.league_GB:  # ground out
            score_book_cd = 'GB'
            if runner_on_first and outs <= 1 and self.rng() <= (self.batting['GIDP'] / self.batting['AB']):
            # if runner_on_first and outs <= 1 and self.rng() <= self.dp_chance:
                score_book_cd = 'DP'
            elif runner_on_first and outs <= 1 and self.rng() <= self.league_GB_FC:
                score_book_cd = 'GB FC'
        elif self.dice_roll <= (self.league_FB + self.league_GB):  # fly out ball
            if self.rng() <= self.tag_up_chance and runner_on_third and outs < 2:
                score_book_cd = 'SF'
            else:
                score_book_cd = 'FO'
        else:
            score_book_cd = 'LD'  # line drive
        return score_book_cd

    def ab_outcome(self, pitching: Series, batting: Series, outcomes: OutCome, outs: int = 0,
                   runner_on_first: bool = False, runner_on_third: bool = False) -> None:
        """
        tree of the various odds of an event, each event is yes/no.  On base? Yes -> BB? no -> Hit yes (stop)
        outcome: on base or out pos 0, how in pos 1, bases to advance in pos 2, rbis in pos 3
        :param pitching: data for current pitcher in a df series
        :param batting: data for current batter in a df series
        :param outcomes: outcomes class for results translation
        :param outs: outs in inning
        :param runner_on_first: is there a runner on first?
        :param runner_on_third: is there a runner on third?
        :return: None
        """
        self.pitching = pitching
        self.batting = batting
        outcomes.reset()
        if self.onbase():
            if self.bb():
                outcomes.set_score_book_cd('BB')
            elif self.hr():
                outcomes.set_score_book_cd('HR')
            elif self.triple():
                outcomes.set_score_book_cd('3B')
            elif self.double():
                outcomes.set_score_book_cd('2B')
            elif self.hbp():
                outcomes.set_score_book_cd('HBP')
            else:
                outcomes.set_score_book_cd('H')
        else:  # handle outs
            if self.k():
                outcomes.set_score_book_cd('SO')
            else:
                outcomes.set_score_book_cd(self.gb_fo_lo(outs, runner_on_first, runner_on_third))
        return

    def odds_ratio(self, hitter_stat: Union[float, float64], pitcher_stat: Union[float, float64],
                   league_stat: float64, stat_type: str = '') -> float64:
        """
        odds ratio is odds of the hitter * odds of the pitcher over the odds of the league or environment
        the ratio only works for 2 outcomes, e.g., on base or not on base.
        additional outcomes need to be chained, e.g., on base was it a hit?
        example odds ratio.  Hitter with an obp of .400 odds ratio would be .400/(1-.400)
        hitter with an OBP of .400 in a league of .300 facing a pitcher with an OBP of .250 in a league of .350, and
        they are both playing in a league ( or park) where the OBP is expected to be .380 for the league average player.
        Odds(matchup)(.400 / .600) * (.250 / .750)
        ——————- =————————————-
        (.380 / .620)(.300 / .700) * (.350 / .650)
        Odds(matchup) = .590 -> Matchup OBP = .590 / 1.590 = .371
        :param hitter_stat:
        :param pitcher_stat:
        :param league_stat:
        :param stat_type:
        :return: a float of type numpy float64
        """
        if self.debug:
            print(f'at_bat.odds ratio, hitter stat:{hitter_stat}, pitcher stat{pitcher_stat}')

        odds = 0
        with warnings.catch_warnings():
            warnings.filterwarnings("error")
            try:
                odds = ((hitter_stat / (1 - hitter_stat)) * (pitcher_stat / (1 - pitcher_stat))) / \
                             (league_stat / (1 - league_stat))
            except ZeroDivisionError:
                print(f'***Exception in odds ratio calculation for hitter:{hitter_stat}, pitcher:{pitcher_stat}, '
                      f'league: {league_stat} {stat_type}')
                print(self.batting)
                print(self.pitching)
            except Warning as warning:
                print(f'***Warning in odds ratio calculation for hitter:{hitter_stat}, pitcher:{pitcher_stat}, '
                      f'league: {league_stat} {stat_type}')
                print("Warning caught:", warning)
                print(self.batting)
                print(self.pitching)
        return float64(odds / (1 + odds))
