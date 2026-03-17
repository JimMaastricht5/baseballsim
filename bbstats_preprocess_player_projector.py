"""
PLAYER PROJECTOR MODULE
-----------------------
This class implements a multi-strategy statistical engine to project MLB player
performance for the 2026 season. Rather than applying a 'one-size-fits-all'
Bayesian formula, this engine acts as a selector, analyzing a players
career trajectory, age, and health history to determine the most realistic
true talentt level.

Core Philosophies:
1. BAYESIAN SHRINKAGE: For low-sample players (rookies), regress heavily
   toward a league mean that is staggered, penalizing inexperience.
2. TREND RECOGNITION: For established stars, prioritize linear trajectory
   over simple averages, allowing for late-career surges or age-related declines.
3. INJURY SMOOTHING: detect 'V-shaped' volume patterns (e.g., 2024 injury)
   to prevent a high-variance, low-volume year from unfairly anchoring a projection.
4. GROWTH FLOOR: For players <26 years old, project the higher of the Trend
   or the Weighted Average, ensuring prospects do not slope downward after
   tough adjustment year.
5. AGING CURVE: A final parabolic multiplier (Growth/Prime/Decline) is applied
based on the player's biological age in 2026.
"""
import numpy as np
import pandas as pd
from typing import Dict, List, Optional


class PlayerProjector:
    """
    Multi-strategy statistical engine for projecting MLB player performance.

    Selects among several projection strategies per player based on career
    length, sample size, injury history, and age. Applies Bayesian shrinkage,
    linear trend detection, injury smoothing, and aging curve adjustments.
    """

    def __init__(self, league_averages: Dict[str, float], gate_pa: int = 400):
        """
        Initialize the projector with league context.

        :param league_averages: Dict of league-average rates keyed as
            '{stat}_per_{vol_col}' (e.g. 'H_per_PA', 'SO_per_PA').
        :param gate_pa: PA threshold at which full trust in player data is
            granted for aging-curve dampening. Default 400.
        """
        self.lg_avgs = league_averages
        self.gate = gate_pa

        # Higher K = Stronger pull toward league average (less trust in small samples)
        self.k_vals_batter = {
            'H': 40,  # Slightly raised: reduces over-regression for mid-sample batters
            '2B': 80,  # Respect doubles
            '3B': 200,  # Triples are high-variance/luck-based
            'HR': 60,  # Power stabilizes around 300-400 AB
            'BB': 50,  # Plate discipline is fairly stable
            'SO': 400,  # Strikeout rate stabilizes very quickly (~60 PA)
            'HBP': 500,  # Extremely high: Don't project many HBPs for rookies
            'default': 150
        }

        self.k_vals_pitcher = {
            'H': 300,  # Hits allowed (BABIP) regresses heavily
            'BB': 800,  # Walk rate
            'SO': 150,  # K-rate stabilizes very fast for pitchers
            'ER': 300,  # Essential for preventing 0.00 ERA anomalies
            'default': 250
        }

    def calculate_projected_stats(self, history: pd.DataFrame,
                                  stats: List[str],
                                  is_p: bool) -> pd.DataFrame:
        """
        New Bulk Entry Point.
        Iterates through the entire historical DataFrame and returns a
        projected DataFrame for the new season.
        """
        history = history[history['Season'] < 2026].copy()
        unique_players = history['Hashcode'].unique()
        all_projections = []

        for h_code in unique_players:
            # .copy() is vital here to prevent cross-contamination
            player_history = history[history['Hashcode'] == h_code].sort_values('Season').copy()

            # Ensure we aren't projecting someone who has 0 volume
            if player_history['PA'].sum() == 0:
                continue

            proj_dict = self._project_single_player(player_history, stats, is_p)
            all_projections.append(proj_dict)

        # Return a full DataFrame ready for bbstats_preprocess
        return pd.DataFrame(all_projections)

    def _get_projection_batter(self, player_history: pd.DataFrame, stat_col: str, vol_col: str) -> float:
        """
        Select the best projection strategy for a single batter stat and apply aging.

        Strategy selection priority:
          1. Single qualifying season (>= 300 vol): lightly regressed blend.
          2. Low volume or < 2 seasons: Bayesian regression to league mean.
          3. Consistent trend with >= 2 seasons: linear regression, with a growth
             floor for players aged <= 25 (max of trend vs weighted average).
          4. Otherwise: recency-weighted career average.

        After selecting a raw rate, an aging multiplier (parabolic, dampened by
        career volume trust) and an unproven-player tax are applied.

        :param player_history: Historical season DataFrame for one player, sorted by Season.
        :param stat_col: Stat column to project (e.g. 'H', 'BB', 'SO').
        :param vol_col: Volume denominator column (e.g. 'PA', 'AB', 'H').
        :return: Projected per-vol rate, clipped to [0, 0.450].
        """
        num_years = len(player_history)
        career_vol = player_history[vol_col].sum()
        age_2026 = int(player_history.iloc[-1]['Age']) + 1

        # 1. STRATEGY SELECTION
        if num_years == 1 and career_vol >= 300:
            raw_rate = self._project_single_year_starter(player_history, stat_col, vol_col)
        elif (career_vol / num_years) < 100 or num_years < 2:
            raw_rate = self._regress_to_mean(player_history, stat_col, vol_col)
        elif self._is_consistent_trend(player_history, stat_col, vol_col) and num_years >= 2:
            trend_rate = self._linear_regression(player_history, stat_col, vol_col)
            w_avg_rate = self._weighted_career_average(player_history, stat_col, vol_col)
            if age_2026 <= 25:
                # GROWTH FLOOR: young players project the higher of trend vs weighted avg
                raw_rate = max(trend_rate, w_avg_rate)
            elif 27 <= age_2026 <= 32:
                # PRIME FLOOR: don't let a declining trend extrapolate below the career
                # weighted average - mild declines shouldn't be over-projected downward
                raw_rate = max(trend_rate, w_avg_rate)
            else:
                raw_rate = trend_rate
        else:
            raw_rate = self._weighted_career_average(player_history, stat_col, vol_col)
            # PRIME ANCHOR: for established prime hitters (27-33) with no consistent trend,
            # the most recent season acts as a soft floor - prevents a bounceback year from
            # being washed out by poor earlier seasons (and vice versa for outlier good years)
            if 27 <= age_2026 <= 33 and career_vol >= 600 and stat_col in ['H', 'BB']:
                recent_rate = player_history.iloc[-1][stat_col] / max(1, player_history.iloc[-1][vol_col])
                raw_rate = max(raw_rate, recent_rate * 0.93)

        # 2. AGING & TAX
        trust = min(career_vol / self.gate, 1.0)
        multiplier = 1.0 + (self._get_aging_multiplier(age_2026, False) - 1.0) * trust
        if vol_col == 'H':
            multiplier = 1.0 + (multiplier - 1.0) * 0.5

        unproven_factor = np.clip(1.0 - (career_vol / 500), 0, 1)
        # REDUCED: from 0.12 to 0.04 (4%). 12% is a Deadball Era death sentence; 8% SO to 6% SO
        tax = 1.0 - (0.04 * unproven_factor) if stat_col != 'SO' else 1.0 + (0.06 * unproven_factor)
        final_rate = float(np.clip(raw_rate * multiplier * tax, 0, 0.480))  # Realistic ceiling
        return self._apply_sanity_caps(final_rate, stat_col, is_p=False, player_history=player_history)

    def _get_projection_pitcher(self, player_history: pd.DataFrame, stat_col: str, vol_col: str) -> float:
        """
        Select the best projection strategy for a single pitcher stat and apply aging.

        Strategy selection:
          - < 2 seasons or < 150 career vol: Bayesian regression to league mean.
          - Otherwise: 50/50 blend of linear trend and weighted career average,
            preventing wild swings from single-season outliers.

        After selecting a raw rate, a full aging multiplier and an unproven-pitcher
        tax are applied. An anti-ghost gravity anchor pulls sub-elite ER rates back
        toward a 2.80 ERA baseline, and a hard outlier brake prevents position
        players from projecting as Cy Young candidates.

        :param player_history: Historical season DataFrame for one player, sorted by Season.
        :param stat_col: Stat column to project (e.g. 'H', 'BB', 'SO', 'ER').
        :param vol_col: Volume denominator column (e.g. 'PA', 'IP_Dec').
        :return: Projected per-vol rate (not yet multiplied by projected volume).
        """
        num_years = len(player_history)
        career_vol = player_history[vol_col].sum()
        age_2026 = int(player_history.iloc[-1]['Age']) + 1

        # 1. STRATEGY SELECTION (Pitchers lean more on Weighted Averages to stabilize ERA)
        if num_years < 2 or career_vol < 150:
            raw_rate = self._regress_to_mean(player_history, stat_col, vol_col)
        else:
            # For Pitchers, blend Trend with Weighted Average 50/50 to prevent death spirals
            trend_rate = self._linear_regression(player_history, stat_col, vol_col)
            w_avg_rate = self._weighted_career_average(player_history, stat_col, vol_col)
            raw_rate = (trend_rate * 0.5) + (w_avg_rate * 0.5)

        # anchor OBP
        if stat_col in ['H', 'BB']:
            lg_target = self.lg_avgs.get(f"{stat_col}_per_{vol_col}", 0.240)

            # Catch pitchers projecting >13% better than league average
            # and pull 40% toward mean to prevent unrealistic OBP suppression
            if raw_rate < (lg_target * 0.87):
                raw_rate = (raw_rate * 0.40) + (lg_target * 0.60)

        # 2. AGING & TAX
        # Get raw skill multiplier
        raw_m = self._get_aging_multiplier(age_2026, True)

        if stat_col in ['H', 'BB', 'ER'] and raw_m < 1.0:
            if stat_col == 'BB':
                # BLEND: Average of linear and inverse to prevent walk explosion
                multiplier = ((1.0 + (1.0 - raw_m)) + (1.0 / raw_m)) / 2
            else:
                multiplier = 1.0 / raw_m
        else:
            multiplier = raw_m

        unproven_factor = np.clip(1.0 - (career_vol / 250), 0, 1)
        tax = 1.0 + (0.07 * unproven_factor) if stat_col in ['H', 'BB', 'ER'] else 1.0 - (0.07 * unproven_factor)
        final_rate = raw_rate * multiplier * tax

        # 3. ANTI-GHOST LOGIC (The Gravity Anchor)
        # Instead of max(rate, 2.10), we pull outliers back toward a 'Great' baseline
        if stat_col == 'ER':
            # 0.085 is roughly a 2.80 ERA. If they project better than that, pull them back.
            elite_anchor = 0.085
            if final_rate < elite_anchor:
                # Gravity pulls them 50% of the way to a 3.50 ERA (0.108 rate)
                gravity_well = 0.108
                final_rate = (final_rate + gravity_well) / 2

        # (Step 4) outlier brake
        if stat_col == 'ER' and vol_col == 'IP_Dec':
            lg_er_per_ip = self.lg_avgs.get('ER_per_IP', 4.25) / 9
            # If a player has < 150 career IP, don't let them be better than 90% of league average
            # This keeps position players like Torrens from looking like Cy Young winners
            if career_vol < 150:
                final_rate = max(final_rate, lg_er_per_ip * 0.9)
            else:
                # For established guys, allow them to be elite (up to 40% of league average)
                final_rate = max(final_rate, lg_er_per_ip * 0.4)

        return self._apply_sanity_caps(float(final_rate), stat_col, is_p=True, player_history=player_history)

    def _project_single_player(self, history: pd.DataFrame, stats: List[str], is_p: bool) -> dict:
        """Dispatcher to route players to the correct projection engine."""
        # 1. Handle Role-specific routing
        role = str(history['Role'].iloc[0])

        if is_p:
            return self._project_pitcher(history)

        # Handle Pitchers-at-the-plate (Batting stats for Pitchers)
        if 'Pitcher' in role:
            result = {s: 0.0 for s in stats}
            result['PA'] = history['PA'].iloc[-1]
            result['AB'], result['SO'], result['AVG'] = result['PA'], result['PA'] * 0.50, 0.0
            result['Projection_Method'] = "Pitcher-Hitting"
            return result

        return self._project_batter(history)

    def _project_batter(self, history: pd.DataFrame) -> dict:
        """
        Build a full projected stat line for a position player.

        Volume is computed as a recency-weighted average of the last 1-3 seasons
        (weights 3/4/5), clamped to [150, 700] PA. Stats are projected in a
        specific order to maintain internal consistency:
          1. BB and SO anchors (per PA).
          2. AB derived via subtraction (PA - BB - HBP - SF).
          3. Hits projected as BA rate × AB (prevents the 7-point AVG leak).
          4. 2B/3B/HR tethered to the projected hit total as ratios.
          5. AVG and OBP recalculated from the final counts.

        :param history: Historical season DataFrame for one player, sorted by Season.
        :return: Dict of projected stat values ready for DataFrame assembly.
        """
        num_years = len(history)

        # Volume Logic
        weights = np.array([3, 4, 5][-num_years:])
        raw_vol = np.sum(history['PA'].fillna(0).values * weights) / weights.sum()
        proj_vol = min(max(150, raw_vol), 700)

        result = history.iloc[-1].to_dict()
        result['PA'] = proj_vol
        result['Years_Included'] = history['Season'].tolist()
        result['Projection_Method'] = "Trend" if num_years >= 2 else "Regressed"

        # A. Project Anchors (BB and SO per PA)
        result['BB'] = self._get_projection_batter(history, 'BB', 'PA') * proj_vol
        result['SO'] = self._get_projection_batter(history, 'SO', 'PA') * proj_vol

        # B. Sync AB/Hits to avoid the 7-point leak
        result['AB'] = proj_vol - (result.get('BB', 0) + result.get('HBP', 0) + result.get('SF', 0))
        proj_ba = self._get_projection_batter(history, 'H', 'AB')
        result['H'] = result['AB'] * proj_ba

        # C. Tether Power to the NEW Hit total
        proj_h_count = max(0.1, result['H'])
        for stat in ['2B', '3B', 'HR']:
            ratio = self._get_projection_batter(history, stat, 'H')
            result[stat] = proj_h_count * ratio

        result['AVG'] = result['H'] / max(1, result['AB'])
        result['OBP'] = (result['H'] + result['BB']) / proj_vol
        return result

    def _project_pitcher(self, history: pd.DataFrame) -> dict:
        """
        Project a pitcher's 2026 performance using standardized unit logic.
        Converts box-score IP (e.g. 200.1) to True Decimal IP (200.33)
        to prevent math leaks.
        """
        num_years = len(history)

        # 1. IP CONVERSION (The Logan Webb Fix)
        # Create a temporary column of true decimal innings for calculation
        history = history.copy()
        history['IP_Dec'] = history['IP'].apply(lambda x: int(x) + (x % 1) * 3.333)

        # 2. VOLUME LOGIC (BF/PA Target)
        is_workhorse = (history['PA'] > 750).sum() >= 2
        raw_vol = history['PA'].iloc[-1]
        # Workhorses get a higher cap/floor to ensure the rotation stays full
        if is_workhorse:
            proj_vol = max(700, min(raw_vol, 850))
        else:
            proj_vol = max(75, min(raw_vol, 650))

        # 3. INITIALIZE RESULT
        result = history.iloc[-1].to_dict()
        result['PA'] = proj_vol
        result['Years_Included'] = history['Season'].tolist()
        result['Projection_Method'] = "Trend" if num_years >= 2 else "Regressed"

        # 4. PROJECT PERIPHERALS (Rates per Batter Faced)
        # These use PA as the denominator and are relatively stable
        result['H'] = self._get_projection_pitcher(history, 'H', 'PA') * proj_vol
        result['BB'] = self._get_projection_pitcher(history, 'BB', 'PA') * proj_vol
        result['SO'] = self._get_projection_pitcher(history, 'SO', 'PA') * proj_vol

        # 5. DERIVE OUTS AND IP
        # In baseball, PA - Hits - Walks - (HBP/SF) = Outs.
        # We'll use a simplified (PA - H - BB) to find the 2026 Outs.
        proj_outs = max(1, proj_vol - (result['H'] + result['BB']))
        proj_ip_true = proj_outs / 3

        # 6. PROJECT EARNED RUNS (The Unit Correction)
        # We project the rate of ER per INNING (not per 9 innings).
        # 'IP_Dec' ensures we aren't dividing by 200.1 when we mean 200.33.
        er_per_inning = self._get_projection_pitcher(history, 'ER', 'IP_Dec')

        # Apply a SOFT floor (1.50 ERA equivalent) rather than the 1.91 hard floor
        # lg_era (4.25) / 9 = 0.472 runs per inning. 0.472 * 0.35 = 0.165 (1.48 ERA)
        lg_er_per_ip = self.lg_avgs.get('ER_per_IP', 4.25) / 9
        er_per_inning = max(er_per_inning, lg_er_per_ip * 0.35)

        result['ER'] = er_per_inning * proj_ip_true

        # 7. FINAL DISPLAY FORMATTING
        # Convert IP back to box score format (e.g., 187.1)
        result['IP'] = (proj_outs // 3) + ((proj_outs % 3) / 10)
        result['IP_True'] = proj_ip_true

        # Recalculate rates for the CSV output
        result['ERA'] = (result['ER'] * 9) / proj_ip_true
        result['WHIP'] = (result['H'] + result['BB']) / proj_ip_true

        # Calculate AB (Hits + Outs)
        result['AB'] = result['H'] + proj_outs

        return result

    def _project_single_year_starter(self, history: pd.DataFrame, stat_col: str, vol_col: str) -> float:
        """
        Project a player with exactly one qualifying season (>= 300 vol).

        Blends the player's actual per-vol rate (80%) with the league average (20%)
        to lightly regress without fully discarding a real starter's performance.

        :param history: Single-row DataFrame for the player.
        :param stat_col: Stat column to project.
        :param vol_col: Volume denominator column.
        :return: Blended per-vol rate.
        """
        actual_rate = history.iloc[-1][stat_col] / max(1, history.iloc[-1][vol_col])
        lg_rate = self.lg_avgs.get(f"{stat_col}_per_{vol_col}", 0.10)
        return (actual_rate * 0.80) + (lg_rate * 0.20)

    def _regress_to_mean(self, history: pd.DataFrame, stat_col: str, vol_col: str) -> float:
        """
        Bayesian regression to the league mean for low-sample or unproven players.

        Uses a dynamic K-value that slides from 800 (rookie, 0 PA) down to 20
        (veteran, 1500+ PA) to control how strongly the league mean is weighted.
        Stat-specific K overrides from k_vals_batter / k_vals_pitcher are applied
        on top of the volume-scaled base.

        For extra-base hits (2B, 3B, HR) when vol_col == 'H', the XBH/H ratio is
        regressed against the league XBH/H ratio rather than the raw rate, keeping
        power stats tethered to hit totals instead of plate appearances.

        Formula (standard): (career_total + K * lg_rate) / (career_vol + K)
        Formula (XBH):      (career_total + K * lg_ratio) / (career_H + K)

        :param history: Player's historical season DataFrame.
        :param stat_col: Stat column to regress (e.g. 'H', 'BB', '2B').
        :param vol_col: Volume denominator column (e.g. 'PA', 'AB', 'H').
        :return: Bayesian-regressed per-vol rate.
        """
        career_total = history[stat_col].sum()
        career_vol = history[vol_col].sum()
        is_p = 'IP' in history.columns

        # 1. DYNAMIC K-SCALING (The "Trust" Meter)
        vol_trust_factor = np.clip(career_vol / 1500, 0, 1)
        # Slides from 800 (Rookie) down to 20 (Veteran)
        base_k = 800 * (1 - vol_trust_factor) + 20
        k_map = self.k_vals_pitcher if is_p else self.k_vals_batter
        k = k_map.get(stat_col, base_k)
        if not is_p and career_vol > 1000:
            k = k * 0.5

        # 2. THE TETHERED POWER LOGIC (Only for 2B, 3B, HR)
        # CRITICAL: We check vol_col == 'H' to ensure Hits (PA) never enters here.
        if stat_col in ['2B', '3B', 'HR'] and not is_p and vol_col == 'H':
            # 1. Get the player's career ratio (e.g., HR per Hit)
            career_h = history['H'].sum()
            player_ratio = career_total / max(1, career_h)

            # 2. Get the League Mean ratio
            lg_h_pa = self.lg_avgs.get('H_per_PA', 0.245)
            lg_stat_pa = self.lg_avgs.get(f"{stat_col}_per_PA", 0.040)  # Target ~25 HRs for avg
            lg_ratio = lg_stat_pa / lg_h_pa

            # 3. Trust the player's unique profile (Lower K for ratios)
            # This keeps Arraez as a slap hitter and Raleigh as a slugger
            k_ratio = 50
            reg_ratio = (career_total + k_ratio * lg_ratio) / (career_h + k_ratio)
            return float(reg_ratio)

        # 3. THE ANCHOR LOGIC (H, BB, SO)
        # This is where Will Smith's Hits will now correctly land.
        lg_rate = self.lg_avgs.get(f"{stat_col}_per_{vol_col}")
        if lg_rate is None:
            # CRITICAL: If calculating BA (H/AB), don't fallback to a PA rate (0.10)
            if stat_col == 'H' and vol_col == 'AB':
                lg_rate = self.lg_avgs.get('H_per_AB', 0.258)
            else:
                lg_rate = self.lg_avgs.get(f"{stat_col}_per_PA", 0.10)

        if career_vol + k == 0:
            return lg_rate

        return (career_total + k * lg_rate) / (career_vol + k)

    def _linear_regression(self, history: pd.DataFrame, stat_col: str, vol_col: str) -> float:
        """
        Project via linear regression of per-vol rates across seasons.

        Fits a line to the year-over-year rate history, then projects one step
        forward. The slope is clipped to +/- 0.020 per year and dampened by the
        number of seasons to prevent extreme extrapolation. The projection is
        also capped at 120% (or 105% for age >= 30) of the historical peak rate.

        Falls back to _weighted_career_average if polyfit raises an exception.

        :param history: Player's historical season DataFrame (>= 3 rows expected).
        :param stat_col: Stat column to project.
        :param vol_col: Volume denominator column.
        :return: Projected per-vol rate from the trend line.
        """
        rates = (history[stat_col] / history[vol_col].replace(0, 1)).values
        num_years = len(rates)
        career_vol = history[vol_col].sum()
        x = np.arange(num_years)
        try:
            slope, intercept = np.polyfit(x, rates, 1)
        except:
            return self._weighted_career_average(history, stat_col, vol_col)

        # 1. TIGHTEN PROVEN STATUS: Require 3 seasons AND 1000 PAs to trust a full trend
        is_proven = num_years >= 3 and career_vol >= 1000

        # 2. VOLUME-BASED DAMPENING:
        # Instead of just counting years, we scale trust based on career volume.
        # A player with 200 PA should only have ~20% of their trend trusted.
        vol_trust = np.clip(career_vol / 1000, 0, 1)
        dampener = 0.95 if is_proven else (0.8 * vol_trust)

        # 3. TIGHTEN SLOPES:
        # Don't let unproven players (like Abraham Toro) jump too many points in a single year.
        max_slope = 0.035 if (stat_col in ['HR', '2B', 'H'] and is_proven) else 0.012
        slope = np.clip(slope, -max_slope, max_slope)
        proj = (slope * dampener * num_years) + intercept

        # 4. CAP CEILING:
        # Unproven players shouldn't be projected to blast 25% past their career peak; younger players 15%
        max_allowed_mult = 1.20 if is_proven else 1.12
        max_allowed = rates.max() * max_allowed_mult

        return max(0.0, min(proj, max_allowed))

    def _weighted_career_average(self, history, stat_col, vol_col):
        """
        Recency-weighted average of per-vol rates across all available seasons.

        Weights are taken from the tail of [3, 4, 5] so the most recent season
        is always weighted 5, the prior 4, and two seasons back 3.

        :param history: Player's historical season DataFrame.
        :param stat_col: Stat column to average.
        :param vol_col: Volume denominator column.
        :return: Weighted per-vol rate.
        """
        # Ensure we are averaging the RATES, not the raw totals
        rates = (history[stat_col] / history[vol_col].replace(0, 1)).values
        weights = np.array([2, 4, 6][-len(rates):])

        # This returns a percentage (e.g., 0.230), NOT a count of hits
        return np.average(rates, weights=weights)

    def _get_aging_multiplier(self, age: int, is_p: bool) -> float:
        """
        Calculates a parabolic multiplier based on age.
        Hitters: Peak 25-28.
        Pitchers: Peak 27-29.
        """
        if not is_p:
            # --- HITTER CURVE ---
            if age <= 24:
                # High growth phase
                m = -0.0025 * (age - 27) ** 2 + 1.06
            elif age <= 30:
                # The Prime
                m = 1.02
            elif age <= 34:
                m = 0.99
            else:
                # Steady decline
                m = 1.0 - (0.004 * (age - 34) ** 2)
        else:
            # --- PITCHER CURVE ---
            if age <= 26:
                # Gradual development
                m = -0.0015 * (age - 28) ** 2 + 1.04
            elif age <= 30:
                # Peak stability
                m = 1.01
            else:
                # Late-career decline (slightly more punishing after 34)
                decay_factor = 0.0035 if age < 34 else 0.005
                m = 1.0 - (decay_factor * (age - 30) ** 2)

        # Sanity clip to prevent wild swings (80% floor, 110% ceiling)
        return np.clip(m, 0.80, 1.10)

    def _is_injury_year(self, history, vol_col):
        """
        Detect a V-shaped volume pattern indicating a missed/shortened injury year.

        Returns True when all three conditions hold for the middle season:
          - Middle season volume < 40% of the prior season volume.
          - Most recent season volume > 150% of the middle season volume.
          - At least 3 seasons of history are available.

        :param history: Player's historical season DataFrame sorted by Season.
        :param vol_col: Volume denominator column to inspect.
        :return: True if a V-shape injury pattern is detected.
        """
        if len(history) < 3: return False
        vols = history[vol_col].values
        return vols[-2] < (vols[-3] * 0.4) and vols[-1] > (vols[-2] * 1.5)

    def _project_with_injury_smoothing(self, history, stat_col, vol_col):
        """
        Project a rate by down-weighting the injury-shortened middle season.

        When a V-shape is detected the three seasons are blended as:
          pre-injury (45%) + injury year (10%) + return year (45%)
        to prevent the low-volume injury season from dragging down the projection.
        Falls back to _weighted_career_average when fewer than 3 seasons exist.

        :param history: Player's historical season DataFrame sorted by Season.
        :param stat_col: Stat column to project.
        :param vol_col: Volume denominator column.
        :return: Smoothed per-vol rate.
        """
        rates = (history[stat_col] / history[vol_col].replace(0, 1)).values
        if len(rates) >= 3:
            return (rates[-3] * 0.45) + (rates[-2] * 0.10) + (rates[-1] * 0.45)
        return self._weighted_career_average(history, stat_col, vol_col)

    def _is_consistent_trend(self, history, stat_col, vol_col):
        """
        Return True if the per-vol rate has moved monotonically across all seasons.

        A consistent trend means every year-over-year change in the per-vol rate
        is either all non-negative (rising) or all non-positive (falling). Requires
        at least 2 seasons; returns False for a single season.

        :param history: Player's historical season DataFrame sorted by Season.
        :param stat_col: Stat column to inspect.
        :param vol_col: Volume denominator column.
        :return: True if a consistent upward or downward trend exists.
        """
        rates = (history[stat_col] / history[vol_col].replace(0, 1)).values
        if len(rates) < 2: return False
        diffs = np.diff(rates)
        return all(d >= 0 for d in diffs) or all(d <= 0 for d in diffs)

    def _apply_sanity_caps(self, rate, stat_col, is_p, player_history=None):
        """
        Clamp a projected per-vol rate to physically realistic maximums.

        Batter caps (per PA): HBP <= 3.5%, BB <= 18.5%, H <= 38.0%.
        No pitcher caps are currently applied; the method returns the rate unchanged.

        :param rate: Projected per-vol rate to clamp.
        :param stat_col: Stat column name, used to look up the cap.
        :param is_p: True if this is a pitcher stat (caps not applied).
        :return: Rate after applying any relevant cap.
        """
        if not is_p:
            # --- BATTER CAPS ---
            caps = {'HBP': 0.035, 'BB': 0.220, 'H': 0.380}
            if stat_col in caps:
                rate = min(rate, caps[stat_col])

            # Identity Gate: ISO-based Slap-hitter check
            if stat_col == 'HR' and player_history is not None:
                h = player_history['H'].sum()
                tb = (player_history['H'] + player_history['2B'] +
                      2 * player_history['3B'] + 3 * player_history['HR']).sum()
                ab = player_history['AB'].sum()
                career_iso = (tb - h) / max(1, ab)

                if career_iso < 0.100:
                    rate = min(rate, 0.040)  # Cap HR/H ratio at 4%
        else:
            # --- PITCHER CAPS ---
            if stat_col == 'SO':
                rate = max(rate, 0.080)  # Floor (~3.0 K/9)
            if stat_col == 'BB':
                # 0.130 BB/PA is a very wild season (~4.8 BB/9).
                # Cap it here to prevent the .169 league-wide disaster.
                rate = min(rate, 0.130)
            if stat_col == 'H':
                rate = min(rate, 0.330)

        return rate


if __name__ == "__main__":
    import pandas as pd
    import numpy as np

    # 1. Warm Mock Averages (Targeting ~ .315 League OBP)
    mock_lg = {
        'H_per_PA': 0.252,
        'BB_per_PA': 0.098,
        'SO_per_PA': 0.215,
        'ER_per_IP': 4.45,
        'H_per_AB': 0.260,
        '2B_per_H': 0.185,
        '3B_per_H': 0.010,
        'HR_per_H': 0.145,
        'HBP_per_PA': 0.010,
        'SF_per_PA': 0.005,
        'ER_per_PA': 0.110
    }

    projector = PlayerProjector(mock_lg)

    # 2. Expanded Roster
    raw_data = pd.DataFrame([
        {'Hashcode': 'CR1', 'Player': 'Cal Raleigh', 'Season': 2025, 'Age': 28, 'Role': 'Batter',
         'AB': 596, 'H': 147, '2B': 24, '3B': 0, 'HR': 60, 'BB': 97, 'HBP': 2, 'SF': 10, 'SO': 188},
        {'Hashcode': 'AJ99', 'Player': 'Aaron Judge', 'Season': 2025, 'Age': 33, 'Role': 'Batter',
         'AB': 520, 'H': 163, '2B': 24, '3B': 1, 'HR': 52, 'BB': 110, 'HBP': 5, 'SF': 3, 'SO': 160},
        {'Hashcode': 'LA2', 'Player': 'Luis Arraez', 'Season': 2025, 'Age': 28, 'Role': 'Batter',
         'AB': 620, 'H': 205, '2B': 30, '3B': 2, 'HR': 5, 'BB': 25, 'HBP': 2, 'SF': 3, 'SO': 35},
        {'Hashcode': 'TB1', 'Player': 'Tyler Black', 'Season': 2025, 'Age': 24, 'Role': 'Batter',
         'AB': 150, 'H': 35, '2B': 5, '3B': 1, 'HR': 2, 'BB': 25, 'HBP': 2, 'SF': 1, 'SO': 40},
        {'Hashcode': 'PS1', 'Player': 'Paul Skenes', 'Season': 2025, 'Age': 23, 'Role': 'Pitcher',
         'IP': 187.2, 'H': 136, 'ER': 41, 'BB': 42, 'SO': 216, 'HR': 15},
        {'Hashcode': 'ZW1', 'Player': 'Zack Wheeler', 'Season': 2025, 'Age': 35, 'Role': 'Pitcher',
         'IP': 190.0, 'H': 140, 'ER': 55, 'BB': 35, 'SO': 190, 'HR': 18}
    ])

    # 3. Process Volume/Role
    processed_rows = []
    for _, row in raw_data.iterrows():
        r = row.to_dict()
        if 'IP' in r and pd.notnull(r['IP']):
            outs = (int(r['IP']) * 3) + np.round((r['IP'] % 1) * 10)
            r['PA'] = outs + r['H'] + r.get('BB', 0)
            r['is_pitcher'] = True
        else:
            r['PA'] = r.get('AB', 0) + r.get('BB', 0) + r.get('HBP', 0) + r.get('SF', 0)
            r['is_pitcher'] = False
        processed_rows.append(r)

    df_ready = pd.DataFrame(processed_rows)

    # 4. RUN PROJECTIONS
    h_proj = projector.calculate_projected_stats(df_ready[~df_ready['is_pitcher']], [], is_p=False)
    p_proj = projector.calculate_projected_stats(df_ready[df_ready['is_pitcher']], [], is_p=True)

    # 5. DIAGNOSTIC OUTPUT: HITTERS (OBP Focus)
    print("\n" + "=" * 115)
    print(f"{'HITTER OBP INTEGRITY DIAGNOSIS':^115}")
    print("=" * 115)
    print(f"{'Player':<18} | {'PA':<5} | {'BA':<6} | {'BB/PA':<6} | {'OBP':<6} | {'HR':<5} | {'25 OBP':<6} | {'Delta'}")
    print("-" * 115)
    for _, row in h_proj.iterrows():
        p_25 = df_ready[df_ready['Player'] == row['Player']].iloc[-1]
        obp_25 = (p_25['H'] + p_25['BB']) / p_25['PA']
        bb_pa = row['BB'] / row['PA']
        delta = row['OBP'] - obp_25
        print(
            f"{row['Player']:<18} | {int(row['PA']):<5} | {row['AVG']:<6.3f} | {bb_pa:<6.3f} | {row['OBP']:<6.3f} | {int(row['HR']):<5} | {obp_25:<6.3f} | {delta:+.3f}")

    # 6. DIAGNOSTIC OUTPUT: PITCHERS (OBP Against Focus)
    # This section now focuses on how many baserunners the pitchers are allowing (H+BB / PA)
    print("\n" + "=" * 115)
    print(f"{'PITCHER OBP-AGAINST DIAGNOSIS (Fixing the .283 League OBP)':^115}")
    print("=" * 115)
    print(
        f"{'Player':<18} | {'IP':<6} | {'H/PA':<6} | {'BB/PA':<6} | {'OBP-AG':<6} | {'WHIP':<6} | {'25 OBP-AG':<8} | {'Delta'}")
    print("-" * 115)
    for _, row in p_proj.iterrows():
        p_25 = df_ready[df_ready['Player'] == row['Player']].iloc[-1]

        # Calculate 2025 OBP-Against (Baserunners / Batters Faced)
        obp_ag_25 = (p_25['H'] + p_25['BB']) / p_25['PA']

        # Projection Rates
        h_pa = row['H'] / row['PA']
        bb_pa = row['BB'] / row['PA']
        obp_ag_proj = (row['H'] + row['BB']) / row['PA']

        delta = obp_ag_proj - obp_ag_25

        print(
            f"{row['Player']:<18} | {row['IP']:<6.1f} | {h_pa:<6.3f} | {bb_pa:<6.3f} | {obp_ag_proj:<6.3f} | {row['WHIP']:<6.2f} | {obp_ag_25:<8.3f} | {delta:+.3f}")
    print("=" * 115)