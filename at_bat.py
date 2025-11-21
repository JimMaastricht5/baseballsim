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
from bblogger import logger


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
        self.league_batting_obp = self.league_batting_totals_df.at[0, 'OBP']
        self.league_pitching_obp = self.league_pitching_totals_df.at[0, 'OBP']
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
        did the batter reach base? adjusted for age, injury, and streak
        adjustments are neg values if worse and positive for improvements
        requires negation on pitchers,
        :return: true if batter reached base
        """
        return self.rng() < self.odds_ratio(self.batting.OBP + self.pitching.Game_Fatigue_Factor + self.OBP_adjustment +
                                            self.batting.Age_Adjustment + self.batting.Injury_Perf_Adj +
                                            self.batting.Streak_Adjustment,
                                            self.pitching.OBP + self.pitching.Game_Fatigue_Factor + self.OBP_adjustment +
                                            -1 * self.pitching.Age_Adjustment + -1 * self.pitching.Injury_Perf_Adj +
                                            -1 * self.pitching.Streak_Adjustment,
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
        if self.debug_b:
            logger.debug('Computing odds ratio - hitter stat: {}, pitcher stat: {}',
                         hitter_stat, pitcher_stat)

        odds = 0
        with warnings.catch_warnings():
            warnings.filterwarnings("error")
            try:
                odds = ((hitter_stat / (1 - hitter_stat)) * (pitcher_stat / (1 - pitcher_stat))) / \
                             (league_stat / (1 - league_stat))
            except ZeroDivisionError:
                logger.error('Exception in odds ratio calculation - hitter: {}, pitcher: {}, league: {}, stat_type: {}',
                           hitter_stat, pitcher_stat, league_stat, stat_type)
                logger.error('Batter data: {}', self.batting)
                logger.error('Pitcher data: {}', self.pitching)
            except Warning as warning:
                logger.warning('Warning in odds ratio calculation - hitter: {}, pitcher: {}, league: {}, stat_type: {}',
                             hitter_stat, pitcher_stat, league_stat, stat_type)
                logger.warning('Warning caught: {}', warning)
                logger.warning('Batter data: {}', self.batting)
                logger.warning('Pitcher data: {}', self.pitching)
        return float64(odds / (1 + odds))


if __name__ == '__main__':
    # Configure logger level for testing
    from bblogger import configure_logger
    configure_logger("DEBUG")
    
    # Print header
    print("\n===== Testing at_bat.py Classes and Methods =====\n")
    
    # Create test data for a fictional batter and pitcher
    class MockSeries(dict):
        """Mock pandas Series for testing"""
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.__dict__ = self  # Allow attribute access (series.Value)
    
    # Create custom functions for testing instead of relying on bbstats
    def custom_team_batting_totals(batting_df):
        """Simplified version of bbstats.team_batting_totals for testing"""
        import pandas as pd
        # Create a single-row DataFrame with summarized stats
        return pd.DataFrame([{
            'G': 162,
            'AB': batting_df['AB'].sum(),
            'R': 800,  # Fixed value for testing
            'H': batting_df['H'].sum(),
            '2B': 300,  # Fixed values for testing
            '3B': 30,
            'HR': 200,
            'RBI': 750,
            'SB': 100,
            'CS': 30,
            'BB': batting_df['BB'].sum(),
            'SO': batting_df['SO'].sum(),
            'SH': 50,
            'SF': 70,
            'HBP': batting_df['HBP'].sum(),
            'AVG': batting_df['H'].sum() / batting_df['AB'].sum(),
            'OBP': (batting_df['H'].sum() + batting_df['BB'].sum() + batting_df['HBP'].sum()) / 
                  (batting_df['AB'].sum() + batting_df['BB'].sum() + batting_df['HBP'].sum()),
            'SLG': 0.420,  # Fixed for testing
            'OPS': 0.750   # Fixed for testing
        }])

    def custom_team_pitching_totals(pitching_df):
        """Simplified version of bbstats.team_pitching_totals for testing"""
        import pandas as pd
        # Create a single-row DataFrame with summarized stats
        return pd.DataFrame([{
            'G': 162,
            'GS': 162,
            'CG': 5,
            'SHO': 2,
            'IP': 1458.0,
            'AB': pitching_df['AB'].sum(),
            'H': pitching_df['H'].sum(),
            '2B': 300,  # Fixed values for testing
            '3B': 30,
            'ER': 700,
            'SO': pitching_df['SO'].sum(),
            'BB': pitching_df['BB'].sum(),
            'HR': 200,
            'W': 81,
            'L': 81,
            'SV': 40,
            'BS': 15,
            'HLD': 100,
            'ERA': 4.30,  # Fixed for testing
            'WHIP': 1.30,  # Fixed for testing
            'AVG': pitching_df['H'].sum() / pitching_df['AB'].sum(),
            'OBP': (pitching_df['H'].sum() + pitching_df['BB'].sum()) / 
                  (pitching_df['AB'].sum() + pitching_df['BB'].sum()),
            'SLG': 0.420,  # Fixed for testing
            'OPS': 0.750   # Fixed for testing
        }])
            
    # Create mock BaseballStats object
    class MockBaseballStats:
        def __init__(self):
            # Create minimal batting/pitching data needed for tests
            import pandas as pd
            import numpy as np
            
            # Create mock batting data with all required columns
            batting_data = pd.DataFrame({
                'Team': ['TEST'] * 10,
                'H': np.random.randint(100, 200, 10),
                'BB': np.random.randint(20, 80, 10),
                'HBP': np.random.randint(1, 15, 10),
                'AB': np.random.randint(300, 600, 10),
                'SO': np.random.randint(50, 150, 10),
                # Add other required columns with mock data
                'R': np.random.randint(50, 100, 10),
                '2B': np.random.randint(20, 40, 10),
                '3B': np.random.randint(1, 10, 10),
                'HR': np.random.randint(10, 40, 10),
                'RBI': np.random.randint(50, 100, 10),
                'SB': np.random.randint(5, 30, 10),
                'CS': np.random.randint(1, 10, 10),
                'SH': np.random.randint(1, 10, 10),
                'SF': np.random.randint(1, 10, 10)
            })
            
            # Create mock pitching data with all required columns
            pitching_data = pd.DataFrame({
                'Team': ['TEST'] * 10,
                'H': np.random.randint(100, 200, 10),
                'BB': np.random.randint(20, 80, 10),
                'AB': np.random.randint(300, 600, 10),
                'SO': np.random.randint(50, 150, 10),
                'HBP': np.random.randint(1, 15, 10),
                # Add other required columns with mock data
                'HR': np.random.randint(10, 40, 10),
                '2B': np.random.randint(20, 40, 10),
                '3B': np.random.randint(1, 10, 10)
            })

            self.batting_data = batting_data
            self.pitching_data = pitching_data

            # Add cached league totals for performance optimization (like real BaseballStats)
            self.league_batting_totals = custom_team_batting_totals(self.batting_data)
            self.league_pitching_totals = custom_team_pitching_totals(self.pitching_data)

            # Cache additional league statistics
            batting_data_sum = self.batting_data[['H', 'BB', 'HBP']].sum()
            self.league_batting_total_ob = batting_data_sum['H'] + batting_data_sum['BB'] + batting_data_sum['HBP']
            self.league_pitching_total_ob = self.pitching_data[['H', 'BB']].sum().sum()
            self.league_total_outs = self.batting_data['AB'].sum() - batting_data_sum.sum()
            self.league_k_rate_per_ab = self.batting_data['SO'].sum() / self.league_total_outs

    # Create test batter and pitcher data
    test_batter = MockSeries({
        'Player': 'Test Batter',
        'AVG': 0.280,
        'OBP': 0.350,
        'SLG': 0.480,
        'H': 150,
        'BB': 60,
        'HBP': 8,
        'AB': 500,
        'SO': 120,
        '2B': 30,
        '3B': 5,
        'HR': 25,
        'GIDP': 12,
        'Total_OB': 218,  # H + BB + HBP
        'Total_Outs': 350,  # AB - H + SF + SH approx
        'Age_Adjustment': 0.0,  # Age-related performance adjustment
        'Injury_Rate_Adj': 0.0,  # Injury rate adjustment
        'Injury_Perf_Adj': 1.0,  # Injury performance adjustment (multiplier)
        'Streak_Adjustment': 0.0  # Streak adjustment (hot/cold)
    })
    
    test_pitcher = MockSeries({
        'Player': 'Test Pitcher',
        'ERA': 3.50,
        'WHIP': 1.20,
        'AVG': 0.245,
        'OBP': 0.310,
        'SLG': 0.380,
        'H': 180,
        'BB': 70,
        'HBP': 10,
        'AB': 700,
        'SO': 200,
        '2B': 40,
        '3B': 5,
        'HR': 20,
        'Total_OB': 260,  # H + BB
        'Total_Outs': 520,  # AB - H approx
        'Game_Fatigue_Factor': 0.0,  # No fatigue for test
        'Age_Adjustment': 0.0,  # Age-related performance adjustment
        'Injury_Rate_Adj': 0.0,  # Injury rate adjustment
        'Injury_Perf_Adj': 1.0,  # Injury performance adjustment (multiplier)
        'Streak_Adjustment': 0.0  # Streak adjustment (hot/cold)
    })
    
    # Create test instances
    print("Creating test instances...")
    mock_stats = MockBaseballStats()
    outcome = OutCome()
    
    # TestSimAB now just uses the parent class since MockBaseballStats has cached values
    # No need for custom TestSimAB class anymore - SimAB works with cached values from MockBaseballStats
    sim_ab = SimAB(mock_stats)  # Use SimAB directly instead of TestSimAB subclass

    # Test OutCome class methods
    print("\n----- Testing OutCome class -----")
    outcome.reset()
    print(f"After reset - on_base: {outcome.on_base_b}, score_book_cd: '{outcome.score_book_cd}', bases_to_advance: {outcome.bases_to_advance}")
    
    # Test setting different outcomes
    test_codes = ['BB', 'HR', '2B', 'SO', 'DP', 'SF']
    for code in test_codes:
        outcome.set_score_book_cd(code)
        print(f"Outcome '{code}': on_base={outcome.on_base_b}, bases_to_advance={outcome.bases_to_advance}, outs={outcome.outs_on_play}")
    
    # Test runs scored
    outcome.set_runs_score(2)
    print(f"Runs scored: {outcome.runs_scored}")
    
    # Test SimAB class with the test data
    print("\n----- Testing SimAB class -----")
    sim_ab.pitching = test_pitcher
    sim_ab.batting = test_batter
    
    # Test odds_ratio method
    hr_odds = sim_ab.odds_ratio(
        hitter_stat=test_batter.HR / test_batter.Total_OB,
        pitcher_stat=test_pitcher.HR / test_pitcher.Total_OB,
        league_stat=sim_ab.league_batting_Total_HR / sim_ab.league_batting_Total_OB,
        stat_type='HR'
    )
    print(f"HR odds ratio: {hr_odds:.3f}")
    
    # Run several outcome simulations
    print("\n----- Testing ab_outcome method -----")
    results = {'BB': 0, 'H': 0, '2B': 0, '3B': 0, 'HR': 0, 'HBP': 0, 'SO': 0, 'GB': 0, 'DP': 0, 'GB FC': 0, 'FO': 0, 'LD': 0, 'SF': 0}
    
    # Simulate 100 at-bats and count outcomes
    num_sims = 100
    for _ in range(num_sims):
        outcome.reset()
        sim_ab.ab_outcome(test_pitcher, test_batter, outcome, outs=1, runner_on_first=True, runner_on_third=True)
        results[outcome.score_book_cd] += 1
    
    # Print simulation results
    print(f"Results from {num_sims} simulated at-bats:")
    for result, count in sorted(results.items(), key=lambda x: x[1], reverse=True):
        if count > 0:
            percentage = (count / num_sims) * 100
            print(f"  {result}: {count} ({percentage:.1f}%)")
    
    # Test individual probability methods
    print("\n----- Testing individual probability methods -----")
    outcomes = {
        'On Base': sim_ab.onbase,
        'Walk': sim_ab.bb,
        'HBP': sim_ab.hbp,
        'Home Run': sim_ab.hr,
        'Triple': sim_ab.triple,
        'Double': sim_ab.double,
        'Strikeout': sim_ab.k
    }
    
    # Sample each probability 1000 times
    sample_size = 1000
    for name, method in outcomes.items():
        true_count = sum(method() for _ in range(sample_size))
        percentage = (true_count / sample_size) * 100
        print(f"{name}: {true_count}/{sample_size} ({percentage:.1f}%)")
    
    print("\n===== Test Complete =====")
