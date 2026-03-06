"""
--- Copyright Notice ---
Copyright (c) 2024 Jim Maastricht

--- File Context and Purpose ---
FILE: at_bat.py (Implied)
DESCRIPTION: Contains the core logic for simulating the outcome of a single
baseball at-bat based on the statistical probabilities of the batter, the pitcher,
and the league environment. It utilizes the Odds Ratio formula for probability
adjustment.

PRIMARY CLASSES:
- OutCome: Acts as a translator for scorebook codes ('H', 'BB', 'SO', etc.) into
  game mechanics: runners advanced, outs recorded, and whether the batter reached base.
- SimAB: Calculates the probability of various events (On Base, HR, K, etc.) using
  the Odds Ratio and determines the final outcome of the at-bat.
DEPENDENCIES: bbstats, bblogger.

Contact: JimMaastricht5@gmail.com
"""

import numpy as np
import warnings
import bbstats
from numpy import bool_, float64
from pandas.core.series import Series
from typing import Union
from bblogger import logger
from bblogger import configure_logger
import pandas as pd


class OutCome:
    def __init__(self, debug_b=False) -> None:
        """
        class handles tracking battering outcomes and translating that into base running results
        dict in object maintains translation to runner movement and outs
        :return: None
        """
        self.debug_b = debug_b
        if self.debug_b:
            logger.debug("Initializing OutCome class")
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
    def __init__(self, baseball_data: bbstats.BaseballStats, debug_b=False) -> None:
        """
        class handles calculating the outcome of an ab based on pitcher, batter, and league probabilities
        :param baseball_data: class containing the league data and methods
        :return: None
        """
        self.debug_b = debug_b
        if self.debug_b:
            logger.debug("Initializing SimAB class")
        # PERFORMANCE: Create RNG instance once, reuse for ~29x speedup (called ~1000x per game)
        self._rng_instance = np.random.default_rng()
        self.rng = lambda: self._rng_instance.uniform(low=0.0, high=1.001)
        self.dice_roll = None
        self.pitching = None
        self.batting = None
        self.baseball_data = baseball_data

        # PERFORMANCE: Use cached league totals instead of recalculating (~2-3x speedup)
        self.league_batting_totals_df = self.baseball_data.league_batting_totals
        self.league_pitching_totals_df = self.baseball_data.league_pitching_totals

        # Set league totals for odds ratio - all from cached values
        self.league_batting_obp = self.baseball_data.league_batting_obp
        self.league_pa_batting = self.baseball_data.league_pa_batting
        self.league_batting_Total_OB = self.baseball_data.league_batting_total_ob
        self.league_pitching_Total_OB = self.baseball_data.league_pitching_total_ob
        self.league_batting_Total_BB = self.league_batting_totals_df.at[0, 'BB']
        self.league_batting_Total_HBP = self.league_batting_totals_df.at[0, 'HBP']
        self.league_batting_Total_HR = self.league_batting_totals_df.at[0, 'HR']
        self.league_batting_Total_3B = self.league_batting_totals_df.at[0, '3B']
        self.league_batting_Total_2B = self.league_batting_totals_df.at[0, '2B']
        self.league_Total_outs = self.baseball_data.league_total_outs
        self.league_K_rate_per_AB = self.baseball_data.league_k_rate_per_ab
        self.league_GB = .429  # ground ball rate for season
        self.league_GB_FC = .10  # GB FC occur 10 out of 100 times ball in play
        self.league_FB = .372  # fly ball rate for season
        self.league_LD = .199  # line drive rate for the season
        self.OBP_adjustment = -0.015  # final adjustment to line up with prior seasons, 2022 -0.025
        self.BB_adjustment = 0.0  # final adjustment to shift more bb to H
        self.HBP_rate = .0143  # 1.4% of AB in 2022
        self.HBP_adjustment = self.HBP_rate * 0  # adjustment to shift more to or from hbp league avg is 1.4%, results 1/4 of
        self.HR_adjustment = 0.0 # adjust for higher HR rate with new 2023 pitching rules
        self.DBL_adjustment = 0.0  # adjust for higher 2B rate with new 2023 pitching rules
        self.dp_chance = .20  # 20% chance dp with runner on per mlb
        self.tag_up_chance = .20  # 20% chance of tagging up and scoring, per mlb

        # PERFORMANCE: Set up warning filter once instead of in every odds_ratio call (~3% speedup)
        # Convert division warnings to errors so we can catch them
        warnings.filterwarnings("error", category=RuntimeWarning)
        return

    def onbase(self, current_team_def_war: float) -> bool:
        """
        Calculates if the batter reached base.
        Now incorporates Def_WAR to simulate hits being 'taken away' by elite defense.
        Clips values to prevent Odds Ratio infinity errors.
        """
        # 1. Player Adjustments
        h_obp = self.batting.OBP + self.batting.Age_Adjustment + \
                self.batting.Injury_Perf_Adj + self.batting.Streak_Adjustment

        # 2. Pitcher & Defense Adjustments
        defense_mod = current_team_def_war * 0.0015
        p_obp = self.pitching.OBP + self.pitching.Game_Fatigue_Factor - \
                self.pitching.Age_Adjustment - self.pitching.Injury_Perf_Adj - \
                self.pitching.Streak_Adjustment - defense_mod

        # 3. Environment (Apply OBP_adjustment ONLY to the baseline)
        # If the league is +10% hot, OBP_adjustment should be negative (-0.015)
        league_baseline = self.league_batting_obp + self.OBP_adjustment

        # 4. Odds Ratio with Safety Clipping
        # Clipping prevents infinity errors when stats approach 1.0 or 0.0
        prob = self.odds_ratio(
            hitter_stat=np.clip(h_obp, 0.001, 0.999),
            pitcher_stat=np.clip(p_obp, 0.001, 0.999),
            league_stat=np.clip(league_baseline, 0.001, 0.999),
            stat_type='obp')

        return self.rng() < prob

        # # 1. Isolate Hitter Adjustments
        # hitter_adj_obp = (self.batting.OBP +
        #                   self.batting.Age_Adjustment +
        #                   self.batting.Injury_Perf_Adj +
        #                   self.batting.Streak_Adjustment)
        #
        # # 2. Isolate Pitcher & Defense Adjustments
        # # Convert cumulative lineup Def_WAR to a per-PA OBP modifier
        # # Positive Def_WAR (good defense) lowers the allowed OBP.
        # defense_mod = current_team_def_war * 0.0015
        #
        # pitcher_adj_obp = (self.pitching.OBP +
        #                    self.pitching.Game_Fatigue_Factor -
        #                    self.pitching.Age_Adjustment -
        #                    self.pitching.Injury_Perf_Adj -
        #                    self.pitching.Streak_Adjustment -
        #                    defense_mod)
        #
        # # 3. Environmental Baseline
        # league_baseline = self.league_batting_obp + self.OBP_adjustment
        #
        # # 4. Final Odds Ratio
        # return self.rng() < self.odds_ratio(
        #     hitter_adj_obp + self.OBP_adjustment,
        #     pitcher_adj_obp + self.OBP_adjustment,
        #     league_baseline,
        #     stat_type='obp')

    def bb(self) -> bool:
        """
        if the batter reached base was it a walk?
        :return: true if walk
        """
        # Safeguard against division by zero - use league average if no data
        batter_bb_rate = ((self.batting.BB + self.BB_adjustment) / self.batting.Total_OB) if self.batting.Total_OB > 0 else \
                         ((self.league_batting_Total_BB + self.BB_adjustment) / self.league_batting_Total_OB)
        pitcher_bb_rate = ((self.pitching.BB + self.BB_adjustment) / self.pitching.Total_OB) if self.pitching.Total_OB > 0 else \
                          ((self.league_batting_Total_BB + self.BB_adjustment) / self.league_batting_Total_OB)

        return self.rng() < self.odds_ratio(batter_bb_rate, pitcher_bb_rate,
                                            ((self.league_batting_Total_BB + self.BB_adjustment) /
                                             self.league_batting_Total_OB),
                                            stat_type='BB')

    def hbp(self) -> bool:
        """
        if the batter reached base with it a hit by pitch?
        :return: true if HBP
        """
        # Safeguard against division by zero - use league average if no data
        batter_hbp_rate = (self.batting['HBP'] / self.batting.Total_Outs) if self.batting.Total_Outs > 0 else \
                          float64(self.HBP_rate + self.HBP_adjustment)
        pitcher_hbp_rate = (self.pitching['HBP'] / self.pitching.Total_Outs) if self.pitching.Total_Outs > 0 else \
                           float64(self.HBP_rate + self.HBP_adjustment)

        return self.rng() < self.odds_ratio(batter_hbp_rate, pitcher_hbp_rate,
                                            float64((self.HBP_rate + self.HBP_adjustment)), stat_type='HBP')

    def hr(self) -> bool:
        """
        Refined HR logic: If a pitcher is fatigued, the probability of a
        Home Run should also increase, not just the probability of reaching base.
        """
        league_hr_rate = (self.league_batting_Total_HR + self.HR_adjustment) / self.league_batting_Total_OB

        # We apply a portion of the fatigue factor to the HR rate as well
        # This makes 'tired' pitchers give up 'hanging sliders' (Home Runs)
        fatigue_hr_boost = self.pitching.Game_Fatigue_Factor * 0.0  # adjust up from zero to incorporate feature

        batter_hr_rate = ((self.batting.HR + self.HR_adjustment) / self.batting.Total_OB) if self.batting.Total_OB > 0 \
            else league_hr_rate
        pitcher_hr_rate = ((self.pitching.HR + self.HR_adjustment + fatigue_hr_boost) / self.pitching.Total_OB) \
            if self.pitching.Total_OB > 0 else league_hr_rate

        return self.rng() < self.odds_ratio(batter_hr_rate, pitcher_hr_rate, league_hr_rate, stat_type='HR')

    def triple(self) -> bool:
        """
        if the batter reached base was it a triple?
        :return: true if triple
        """
        # Safeguard against division by zero - use league average if no data
        league_3b_rate = self.league_batting_Total_3B / self.league_batting_Total_OB
        batter_3b_rate = (self.batting['3B'] / self.batting.Total_OB) if self.batting.Total_OB > 0 else league_3b_rate

        # do not have league pitching total for 3b so push it to zero and make it a neutral factor
        return self.rng() < self.odds_ratio(hitter_stat=batter_3b_rate, pitcher_stat=.016,
                                            league_stat=league_3b_rate, stat_type='3B')

    def double(self) -> Union[bool, bool_]:
        """
        if the batter reached base was it a double?
        :return: true if double, allows for either numpy bool or builtin python bool
        """
        # Safeguard against division by zero - use league average if no data
        league_2b_rate = (self.league_batting_Total_2B + self.DBL_adjustment) / self.league_batting_Total_OB
        batter_2b_rate = ((self.batting['2B'] + self.DBL_adjustment) / self.batting.Total_OB) if self.batting.Total_OB > 0 else league_2b_rate

        # do not have league pitching total for 2b so push it to zero and make it a neutral factor
        return self.rng() < self.odds_ratio(hitter_stat=batter_2b_rate, pitcher_stat=.200,
                                            league_stat=league_2b_rate, stat_type='2B')

    def k(self) -> bool:
        """
        if the batter was out was it a strike out?
        :return: true if K
        """
        # Safeguard against division by zero - use league average if no data
        batter_k_rate = (self.batting['SO'] / self.batting.Total_Outs) if self.batting.Total_Outs > 0 else self.league_K_rate_per_AB
        pitcher_k_rate = (self.pitching['SO'] / self.pitching.Total_Outs) if self.pitching.Total_Outs > 0 else self.league_K_rate_per_AB

        return self.rng() < self.odds_ratio(batter_k_rate, pitcher_k_rate, self.league_K_rate_per_AB, stat_type='SO')

    def gb_fo_lo(self, outs: int = 0, runner_on_first: bool = False, runner_on_third: bool = False) -> str:
        """
        Handles ground balls and fly outs.
        Incorporates Def_WAR into Double Play probability.
        """
        self.dice_roll = self.rng()
        if self.dice_roll <= self.league_GB:
            score_book_cd = 'GB'

            # Base DP rate from batter's GIDP history
            gidp_rate = (self.batting['GIDP'] / self.batting['AB']) if self.batting['AB'] > 0 else self.dp_chance

            # Modifier: Elite defense (Def_WAR) increases the chance of turning the two.
            # 1.0 Def_WAR = +1% chance to turn the DP
            defense_dp_boost = self.pitching.get('Def_WAR', 0) * 0.01

            if runner_on_first and outs <= 1 and self.rng() <= (gidp_rate + defense_dp_boost):
                score_book_cd = 'DP'
            elif runner_on_first and outs <= 1 and self.rng() <= self.league_GB_FC:
                score_book_cd = 'GB FC'

        elif self.dice_roll <= (self.league_FB + self.league_GB):
            # Potential for Sacrifice Fly logic
            if self.rng() <= self.tag_up_chance and runner_on_third and outs < 2:
                score_book_cd = 'SF'
            else:
                score_book_cd = 'FO'
        else:
            score_book_cd = 'LD'

        return score_book_cd

    def ab_outcome(self, pitching: Series, batting: Series, outcomes: OutCome, outs: int = 0,
                   runner_on_first: bool = False, runner_on_third: bool = False,
                   lineup_def_war: float = 0) -> None:
        """
        tree of the various odds of an event, each event is yes/no.  On base? Yes -> BB? no -> Hit yes (stop)
        outcome: on base or out pos 0, how in pos 1, bases to advance in pos 2, rbis in pos 3
        :param pitching: data for current pitcher in a df series
        :param batting: data for current batter in a df series
        :param outcomes: outcomes class for results translation
        :param outs: outs in inning
        :param runner_on_first: is there a runner on first?
        :param runner_on_third: is there a runner on third?
        :param lineup_def_war: float representing the current lineups def war to incorporate fielding
        :return: None
        """
        self.pitching = pitching
        self.batting = batting
        outcomes.reset()

        # --- 1. SAFE DENOMINATOR CALCULATION ---
        # We use max(x, 1) to prevent ZeroDivisionErrors/RuntimeWarnings
        # These must include SF (Sacrifice Flies) to keep OBP from running "Hot"
        pa_batter = max(batting.Total_OB + (batting.AB - batting.H) + batting.get('SF', 0), 1)
        pa_pitcher = max(pitching.Total_OB + pitching.Total_Outs, 1)
        pa_league = max(self.baseball_data.league_pa_batting, 1)

        # 1. THE PRIMARY GATE (OBP Resolution)
        if self.onbase(lineup_def_war):

            # 2. SUB-TYPE RESOLUTION (Relative Multipliers)
            def get_mult(stat, b_val, p_val, lg_val):
                if lg_val <= 0: return 1.0

                # Hitter contribution
                b_mult = (b_val / pa_batter) / (lg_val / pa_league)

                # Pitchers are neutralized for 3B/2B in this model
                if stat in ['3B', '2B']:
                    return b_mult

                # Pitcher contribution
                p_mult = (p_val / pa_pitcher) / (lg_val / pa_league)
                return (b_mult + p_mult) / 2

            # Get League baseline frequencies
            lg_h = self.league_batting_totals_df.at[0, 'H']
            lg_singles = (lg_h - self.league_batting_Total_HR -
                          self.league_batting_Total_2B - self.league_batting_Total_3B)

            # Calculate Weighted Probabilities for each event
            weights = {
                'BB': (self.league_batting_Total_BB / pa_league) * get_mult('BB', batting.BB, pitching.BB,
                                                                            self.league_batting_Total_BB),

                'HR': (self.league_batting_Total_HR / pa_league) * get_mult('HR', batting.HR, pitching.HR,
                                                                            self.league_batting_Total_HR),

                '3B': (self.league_batting_Total_3B / pa_league) * get_mult('3B', batting['3B'], 0,
                                                                            self.league_batting_Total_3B),

                '2B': (self.league_batting_Total_2B / pa_league) * get_mult('2B', batting['2B'], 0,
                                                                            self.league_batting_Total_2B),

                'HBP': self.HBP_rate,

                'H': (lg_singles / pa_league) * get_mult('H', (batting.H - batting.HR - batting['2B'] - batting['3B']),
                                                         (pitching.H - pitching.HR), lg_singles)
            }

            # NORMALIZE: Roll against the sum of calculated weights
            total_w = sum(weights.values())
            roll = self.rng() * total_w

            running_total = 0
            for event, weight in weights.items():
                running_total += weight
                if roll <= running_total:
                    outcomes.set_score_book_cd(event)
                    return

            outcomes.set_score_book_cd('FO')  # fall back if no option is selected
        else:
            # 3. OUT RESOLUTION (Strikeouts vs. BIP)
            lg_k_rate = self.baseball_data.league_k_rate_per_ab

            # Protection against division by zero for K logic
            if lg_k_rate > 0:
                k_mult = ((batting.SO / pa_batter) / lg_k_rate +
                          (pitching.SO / pa_pitcher) / lg_k_rate) / 2
            else:
                k_mult = 1.0

            # Probability of K given that an OUT has already occurred
            # We clip prob_out to 0.001 to prevent division errors
            prob_out = max(1 - (batting.Total_OB / pa_batter), 0.001)

            if self.rng() < (lg_k_rate * k_mult / prob_out):
                outcomes.set_score_book_cd('SO')
            else:
                outcomes.set_score_book_cd(self.gb_fo_lo(outs, runner_on_first, runner_on_third))
        return

        # self.pitching = pitching
        # self.batting = batting
        # outcomes.reset()
        # if self.onbase(lineup_def_war):
        #     if self.bb():
        #         outcomes.set_score_book_cd('BB')
        #     elif self.hr():
        #         outcomes.set_score_book_cd('HR')
        #     elif self.triple():
        #         outcomes.set_score_book_cd('3B')
        #     elif self.double():
        #         outcomes.set_score_book_cd('2B')
        #     elif self.hbp():
        #         outcomes.set_score_book_cd('HBP')
        #     else:
        #         outcomes.set_score_book_cd('H')
        # else:  # handle outs
        #     if self.k():
        #         outcomes.set_score_book_cd('SO')
        #     else:
        #         outcomes.set_score_book_cd(self.gb_fo_lo(outs, runner_on_first, runner_on_third))
        # return

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
        if self.debug_b:
            logger.debug('Computing odds ratio - hitter stat: {}, pitcher stat: {}',
                         hitter_stat, pitcher_stat)

        odds = 0
        # PERFORMANCE: Warning filter set once in __init__ instead of context manager here (~3% speedup)
        try:
            odds = ((hitter_stat / (1 - hitter_stat)) * (pitcher_stat / (1 - pitcher_stat))) / \
                         (league_stat / (1 - league_stat))
        except (ZeroDivisionError, RuntimeWarning) as e:
            if isinstance(e, ZeroDivisionError):
                logger.error('Exception in odds ratio calculation - hitter: {}, pitcher: {}, league: {}, stat_type: {}',
                           hitter_stat, pitcher_stat, league_stat, stat_type)
                logger.error('Batter data: {}', self.batting)
                logger.error('Pitcher data: {}', self.pitching)
            else:  # RuntimeWarning
                logger.warning('Warning in odds ratio calculation - hitter: {}, pitcher: {}, league: {}, stat_type: {}',
                             hitter_stat, pitcher_stat, league_stat, stat_type)
                logger.warning('Warning caught: {}', e)
                logger.warning('Batter data: {}', self.batting)
                logger.warning('Pitcher data: {}', self.pitching)
        return float64(odds / (1 + odds))

# =================================================================
# TEST SUITE HELPERS & MOCKS
# =================================================================

def custom_team_batting_totals(batting_df):
    """Calculates league-wide totals for the test baseline using correct PA logic."""
    import pandas as pd
    t = batting_df.sum()
    # Denominator must include SF/SH to avoid "Hot OBP"
    pa = t['AB'] + t['BB'] + t['HBP'] + t.get('SF', 0) + t.get('SH', 0)
    obp = (t['H'] + t['BB'] + t['HBP']) / pa if pa > 0 else 0

    return pd.DataFrame([{
        'G': 162, 'AB': t['AB'], 'H': t['H'], '2B': t['2B'], '3B': t['3B'],
        'HR': t['HR'], 'BB': t['BB'], 'SO': t['SO'], 'SF': t.get('SF', 0),
        'SH': t.get('SH', 0), 'HBP': t['HBP'], 'OBP': obp
    }])

class MockSeries(dict):
    """Enables dot notation for dictionary data (e.g., hitter.OBP)"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.__dict__ = self


class MockBaseballStats:
    """
    Mocks the BaseballStats object.
    Matches all attributes expected by SimAB.__init__.
    """
    def __init__(self):
        import pandas as pd
        # Define a standard league baseline
        self.batting_data = pd.DataFrame({
            'H': [150] * 10, 'BB': [60] * 10, 'HBP': [8] * 10, 'AB': [550] * 10,
            'SO': [120] * 10, '2B': [30] * 10, '3B': [3] * 10, 'HR': [20] * 10,
            'SF': [7] * 10, 'SH': [2] * 10
        })

        self.pitching_data = self.batting_data.copy()  # Neutral pitcher baseline

        # Denominator Logic (The Anchor)
        b_sum = self.batting_data.sum()
        self.league_pa_batting = b_sum['AB'] + b_sum['BB'] + b_sum['HBP'] + b_sum['SF'] + b_sum['SH']

        # REQUIRED BY SimAB.__init__
        self.league_batting_total_ob = b_sum['H'] + b_sum['BB'] + b_sum['HBP']
        self.league_pitching_total_ob = self.league_batting_total_ob  # Mapped for test

        self.league_batting_obp = self.league_batting_total_ob / self.league_pa_batting
        self.league_total_outs = (b_sum['AB'] - b_sum['H']) + b_sum['SF'] + b_sum['SH']
        self.league_k_rate_per_ab = b_sum['SO'] / self.league_total_outs

        # Dataframes expected by SimAB initialization
        self.league_batting_totals = custom_team_batting_totals(self.batting_data)
        self.league_pitching_totals = self.league_batting_totals

# =================================================================
# TEST EXECUTION
# =================================================================

if __name__ == '__main__':
    configure_logger("INFO")

    print('***** MOCK SIM *****')
    print("\n" + "=" * 55)
    print(" SimAB CALIBRATION & STRESS TEST ".center(55, "="))
    print("=" * 55 + "\n")

    # Setup test participants
    test_batter = MockSeries({
        'Player': 'Elite Hitter', 'OBP': 0.390, 'H': 180, 'BB': 80, 'HBP': 5,
        'AB': 550, 'SO': 90, '2B': 40, '3B': 2, 'HR': 35, 'SF': 8, 'SH': 0, 'GIDP': 10,
        'Total_OB': 265, 'Total_Outs': 378,
        'Age_Adjustment': 0.0, 'Injury_Perf_Adj': 0.0, 'Streak_Adjustment': 0.0
    })

    test_pitcher = MockSeries({
        'Player': 'Ace Pitcher', 'OBP': 0.290, 'H': 150, 'BB': 50, 'HBP': 5,
        'AB': 650, 'SO': 210, 'HR': 15, 'Total_OB': 205, 'Total_Outs': 505,
        'Game_Fatigue_Factor': 0.0, 'Age_Adjustment': 0.0,
        'Injury_Perf_Adj': 0.0, 'Streak_Adjustment': 0.0
    })

    # Run the mock initialization
    mock_stats = MockBaseballStats()
    sim_ab = SimAB(mock_stats, debug_b=False)
    sim_ab.pitching = test_pitcher
    sim_ab.batting = test_batter

    # Display Baseline stats for debugging
    print(f"League OBP Baseline (Anchor) : {sim_ab.league_batting_obp:.3f}")
    print(f"Current OBP Adjustment      : {sim_ab.OBP_adjustment:+.3f}")
    print(f"Expected Probability Range  : {test_pitcher.OBP:.3f} - {test_batter.OBP:.3f}")
    print("-" * 55)

    # Simulation loop
    num_sims = 10000
    results = {'Reach Base': 0, 'Out': 0}
    detail_results = {}
    outcome = OutCome()

    for _ in range(num_sims):
        sim_ab.ab_outcome(test_pitcher, test_batter, outcome)
        cd = outcome.score_book_cd
        detail_results[cd] = detail_results.get(cd, 0) + 1
        if outcome.on_base_b:
            results['Reach Base'] += 1
        else:
            results['Out'] += 1

    actual_obp = results['Reach Base'] / num_sims
    print(f"SIMULATION RESULTS ({num_sims} At-Bats):")
    print(f"  Resulting Matchup OBP   : {actual_obp:.3f}")
    print("-" * 55)

    for res, count in sorted(detail_results.items(), key=lambda x: x[1], reverse=True):
        print(f"  {res.ljust(6)} : {count} ({count / num_sims:.1%})")

    print("\n" + "=" * 55)
    print(" CALIBRATION COMPLETE ".center(55, "="))
    print("=" * 55)


    ####### SIM WITH REAL DATA ######
    print("\n" + "=" * 75)
    print(" 2026 SIM CALIBRATION: PRIOR SEASON TALENT STRESS TEST ".center(75))
    print("=" * 75 + "\n")

    # 1. Initialize BaseballStats
    stats = bbstats.BaseballStats(
        load_seasons=[2023, 2024, 2025],
        new_season=2026,
        load_batter_file='aggr-stats-pp-Batting.csv',
        load_pitcher_file='aggr-stats-pp-Pitching.csv',
        suppress_console_output=True
    )

    # 2. Select Median Players from "True Talent" Projections
    # We use stats.batting_data as the source of truth for the 2026 Sim logic
    qualified_batters = stats.batting_data[stats.batting_data['AB'] > 100]
    if qualified_batters.empty:
        qualified_batters = stats.batting_data

    qualified_pitchers = stats.pitching_data[stats.pitching_data['IP'] > 30]
    if qualified_pitchers.empty:
        qualified_pitchers = stats.pitching_data

    # Find the median to represent "Average"
    median_h_idx = len(qualified_batters) // 2
    median_p_idx = len(qualified_pitchers) // 2

    test_batter = qualified_batters.sort_values('OBP').iloc[median_h_idx]
    test_pitcher = qualified_pitchers.sort_values('OBP', ascending=False).iloc[median_p_idx]

    # 3. Pull Historical Comparison
    stats._ensure_2025_historical_loaded()
    h25 = stats.historical_2025_batting
    h25_pa = h25['AB'].sum() + h25['BB'].sum() + h25['HBP'].sum() + h25.get('SF', pd.Series([0])).sum()
    h25_obp = (h25['H'].sum() + h25['BB'].sum() + h25['HBP'].sum()) / h25_pa if h25_pa > 0 else 0

    # 4. Setup Simulation Environment
    sim_ab = SimAB(stats, debug_b=False)
    outcome = OutCome()

    print(f"CALIBRATION TARGETS:")
    print(f"  2025 Historical OBP (Actual): {h25_obp:.3f}")
    print(f"  2026 Projected OBP (Anchor): {stats.league_batting_obp:.3f}")
    print(f"  Environmental Adjustment:    {sim_ab.OBP_adjustment:+.3f}")
    print("-" * 75)
    print(f"TEST MATCHUP (Median Stats):")
    print(f"  Hitter: {str(test_batter.Player)[:20].ljust(20)} | Projected OBP: {test_batter.OBP:.3f}")
    print(f"  Pitcher: {str(test_pitcher.Player)[:19].ljust(19)} | Projected OBP: {test_pitcher.OBP:.3f}")
    print("-" * 75)

    # 5. Run 10,000 Simuation Cycles
    num_sims = 10000
    on_base_count = 0
    sim_results = {}

    for _ in range(num_sims):
        # We pass the Series directly as ab_outcome expects
        sim_ab.ab_outcome(test_pitcher, test_batter, outcome)
        res = outcome.score_book_cd
        sim_results[res] = sim_results.get(res, 0) + 1
        if outcome.on_base_b:
            on_base_count += 1

    sim_obp = on_base_count / num_sims

    # 6. Final Report
    print(f"SIMULATION PERFORMANCE ({num_sims} At-Bats):")
    print(f"  Simulated OBP: {sim_obp:.3f}")

    variance_vs_hist = sim_obp - h25_obp
    print(f"  Variance vs. 2025 History: {variance_vs_hist:+.3f}")
    print("-" * 75)

    # Sort and display event breakdown
    for res, count in sorted(sim_results.items(), key=lambda x: x[1], reverse=True):
        print(f"  {res.ljust(6)} : {count} ({count / num_sims:.1%})")

    # Success logic: Targeting +/- .010 variance
    if abs(variance_vs_hist) <= 0.010:
        print("\n[OK] BALANCED: Simulation reflects 2025 environment accurately.")
    elif variance_vs_hist > 0:
        print(f"\n[!] HOT: The sim is yielding too many hits. Lower OBP_adjustment.")
    else:
        print(f"\n[!] COLD: The sim is yielding too few hits. Increase OBP_adjustment.")

    print("\n" + "=" * 75)

    # 7. DEFENSIVE IMPACT TEST
    print("\n" + "=" * 75)
    print(" DEFENSIVE IMPACT STRESS TEST (Elite vs. Terrible Defense) ".center(75))
    print("=" * 75)


    def run_def_test(def_war_value):
        ob_count = 0
        for _ in range(5000):
            sim_ab.ab_outcome(test_pitcher, test_batter, outcome, lineup_def_war=def_war_value)
            if outcome.on_base_b: ob_count += 1
        return ob_count / 5000


    elite_obp = run_def_test(15.0)  # Elite defense (+15 Def_WAR)
    bad_obp = run_def_test(-15.0)  # Terrible defense (-15 Def_WAR)

    print(f"Matchup: {test_batter.Player} vs {test_pitcher.Player}")
    print(f"OBP with Elite Defense (+15):  {elite_obp:.3f}")
    print(f"OBP with Bad Defense (-15):    {bad_obp:.3f}")
    print(f"Net Defense Impact (Points):   {abs(elite_obp - bad_obp) * 1000:.1f} OBP points")

    # Based on your logic (defense_mod = current_team_def_war * 0.0015)
    # 30 points of Def_WAR difference should roughly equal a ~45 point OBP swing
    if abs(elite_obp - bad_obp) > 0.020:
        print("\n[OK] DEFENSE IS WORKING: Elite gloves are significantly reducing OBP.")
    else:
        print("\n[!] WARNING: Defense impact is negligible. Check defense_mod scaling.")