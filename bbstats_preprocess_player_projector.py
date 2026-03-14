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
            'H': 60,  # Lowered: Trust Batting Average more quickly
            '2B': 80,  # Respect doubles
            '3B': 200,  # Triples are high-variance/luck-based
            'HR': 80,  # Power stabilizes around 300-400 AB
            'BB': 150,  # Plate discipline is fairly stable
            'SO': 800,  # Strikeout rate stabilizes very quickly (~60 PA)
            'HBP': 500,  # Extremely high: Don't project many HBPs for rookies
            'default': 200
        }

        self.k_vals_pitcher = {
            'H': 250,  # Hits allowed (BABIP) regresses heavily
            'BB': 350,  # Walk rate
            'SO': 200,  # K-rate stabilizes very fast for pitchers
            'HR': 300,  # HR/FB rate takes time to stabilize
            'ER': 400,  # Essential for preventing 0.00 ERA anomalies
            'default': 400
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

    def _get_projection(self, player_history: pd.DataFrame, stat_col: str, vol_col: str,
                       is_pitching: bool) -> float:
        """
        Select a projection strategy for a single stat and return a per-vol-unit rate.

        Strategy selection order:
          1. Single-year starter (1 season, >= 300 vol) — lightly regressed actual rate.
          2. Low sample / single season < 300 vol — Bayesian regression to mean.
          3. Injury-year V-shape detected — injury smoothing across three seasons.
          4. Consistent monotone trend (2+ seasons) — linear regression of rates.
          5. Default — recency-weighted career average.

        After selecting a raw rate the method applies:
          - Aging curve multiplier (dampened by career volume trust factor).
          - Unproven tax: penalty on positive stats for batters with < 500 career PA,
            or bonus on negative stats (H, BB, ER, HR against) for pitchers.
          - Sanity caps via _apply_sanity_caps.

        :param player_history: DataFrame of a single player's season rows sorted by Season.
        :param stat_col: Stat column to project (e.g. 'H', 'HR', 'SO').
        :param vol_col: Volume denominator column ('PA' for batters, 'PA' for pitchers).
        :param is_pitching: True if projecting a pitcher stat.
        :return: Projected per-vol-unit rate as a float.
        """
        num_years = len(player_history)
        career_vol = player_history[vol_col].sum()
        age_2026 = int(player_history.iloc[-1]['Age']) + 1
        player_name = player_history.iloc[-1].get('Player', 'Unknown')

        # --- DEBUG TRACE FOR WILL SMITH ---
        # Retrieve Hashcode (check index if not a column)
        player_hash = player_history.index[0] if player_history.index.name == 'Hashcode' else player_history.iloc[
            -1].get('Hashcode', 'N/A')
        is_debug = "Will Smith" in player_name
        if is_debug:
            print(f"\n{'=' * 60}")
            print(f"DEBUG [{player_name}] | Hashcode: {player_hash}")
            print(f"DEBUG | Projecting: {stat_col} per {vol_col}")
            # This will help identify if the data is being duplicated/stacked
            print(f"DEBUG | History Rows: {num_years} | Career Vol: {career_vol}")

        # --- STEP 1: STRATEGY SELECTION ---
        if num_years == 1 and career_vol >= 300:
            method = "1-Year Starter"
            raw_rate = self._project_single_year_starter(player_history, stat_col, vol_col)
        elif (career_vol / num_years) < 100 or num_years < 2:
            method = "Regress to Mean"
            raw_rate = self._regress_to_mean(player_history, stat_col, vol_col)
        elif self._is_injury_year(player_history, vol_col):
            method = "Injury Smooth"
            raw_rate = self._project_with_injury_smoothing(player_history, stat_col, vol_col)
        elif self._is_consistent_trend(player_history, stat_col, vol_col) and num_years >= 2:
            method = "Trend"
            raw_rate = self._linear_regression(player_history, stat_col, vol_col)
        else:
            method = "Weighted Avg"
            raw_rate = self._weighted_career_average(player_history, stat_col, vol_col)
        if is_debug:
            print(f"   -> Method: {method} | Raw Rate: {raw_rate:.6f}")

        # --- STEP 2: AGING & GROWTH ---
        trust = min(career_vol / self.gate, 1.0)
        full_m = self._get_aging_multiplier(age_2026, is_pitching)
        dampened_m = 1.0 + (full_m - 1.0) * trust
        final_rate = raw_rate * dampened_m
        # --- STEP 3: THE GLOBAL UNPROVEN TAX ---
        safe_vol = max(1, career_vol)
        if not is_pitching:
            unproven_factor = max(0, 1.0 - (safe_vol / 500))
            tax_multiplier = 1.0 - (0.250 * unproven_factor)  # TB projects at .223 up from 2025 .204
            if stat_col == 'SO':
                # Flip the tax for SO: Unproven guys strike out MORE
                final_rate *= (1.0 + (0.08 * unproven_factor))
            else:
                final_rate *= tax_multiplier
        else:
            unproven_factor = max(0, 1.0 - (safe_vol / 150))
            if stat_col in ['H', 'BB', 'ER', 'HR']:
                final_rate *= (1.0 + (0.15 * unproven_factor))
            else:
                final_rate *= (1.0 - (0.15 * unproven_factor))

        # --- STEP 4: RETURN & SANITY ---
        if is_debug:
            print(f"   -> Final Rate (Post-Aging/Tax): {final_rate:.6f}")

        final_rate = self._apply_sanity_caps(final_rate, stat_col, is_pitching)
        return float(final_rate) if final_rate is not None and not np.isnan(final_rate) else 0.0

    def _project_single_player(self, history: pd.DataFrame,
                               stats: List[str],
                               is_p: bool) -> dict:
        """
        Finalized Entry Point: Synchronizes Volume and Tethers Stats.
        """
        vol_col = 'PA'
        # If we are projecting BATTING stats for a player whose role is PITCHER
        # Give them 'Pitcher-at-the-Plate' rates (essentially zero).
        if not is_p and 'Pitcher' in str(history['Hashcode'].iloc[0]):
            result = {s: 0.0 for s in stats}
            result['PA'] = history['PA'].iloc[-1]  # Keep their expected PA volume
            result['AB'] = result['PA']
            result['SO'] = result['PA'] * 0.50  # Pitchers strike out a lot
            result['AVG'] = 0.000
            return result

        # 1. VOLUME TARGETING
        num_years = len(history)
        weights = np.array([3, 4, 5][-num_years:])
        raw_vol = np.sum(history[vol_col].fillna(0).values * weights) / weights.sum()

        if not is_p:
            corridor_vol = max(150, min(raw_vol, 350))
            trust_factor = np.clip(raw_vol / 450, 0, 1)
            proj_vol = (raw_vol * trust_factor) + (corridor_vol * (1 - trust_factor))
            proj_vol = min(proj_vol, 700)
        else:
            # Define Workhorse: 2+ seasons of 750+ PA (roughly 185-190 IP)
            is_workhorse = (history[vol_col] > 750).sum() >= 2
            if is_workhorse:
                proj_vol = max(150, min(raw_vol, 850))  # Workhorses get a much higher ceiling (up to ~220 IP)
            else:
                # Standard starters are capped more strictly to prevent
                # small-sample or injury-prone guys from getting 200 IP
                proj_vol = max(75, min(raw_vol, 650))

        # 2. INITIALIZE RESULT
        result = history.iloc[-1].to_dict()
        result[vol_col] = proj_vol
        result['Years_Included'] = history['Season'].tolist()

        # 3. METHOD LABELING
        career_vol = history[vol_col].sum()
        if num_years == 1 and career_vol >= 350:
            result['Projection_Method'] = "1-Year Starter"
        elif num_years >= 2:
            result['Projection_Method'] = "Trend"
        else:
            result['Projection_Method'] = "Regressed"

        # 4. PROJECT ANCHOR STATS (H, BB, SO)
        for stat in ['H', 'BB', 'SO']:
            num_years = len(history)
            career_vol = history[vol_col].sum()
            is_proven = (num_years >= 2 and career_vol >= 1000)

            if stat == 'H' and not is_proven and not is_p:
                # ONLY protect the Batting Average for young players
                rate_avg = self._weighted_career_average(history, stat, vol_col)
                rate_trend = self._get_projection(history, stat, vol_col, is_p)
                rate = max(rate_avg, rate_trend)
            else:
                # BB and SO should ALWAYS be regressed skeptically
                rate = self._get_projection(history, stat, vol_col, is_p)

            result[stat] = rate * proj_vol

        # 5. PROJECT TETHERED STATS (2B, 3B, HR)
        if not is_p:
            proj_h = max(0.001, result['H']) # The safety floor in case hits is 0
            for stat in ['2B', '3B', 'HR']:
                # Project ratio relative to Hits
                ratio = self._get_projection(history, stat, 'H', is_p)
                result[stat] = proj_h * ratio

            proj_h_rate = result['H'] / max(1, result['PA'])
            result['AB'] = result['PA'] - (result.get('BB', 0) + result.get('HBP', 0) + result.get('SF', 0))
            # Dynamic Safety Floor
            # If ABs drop below Hits, we calculate a floor based on their projected talent.
            # We add a small buffer (0.02) to ensure the AVG doesn't literally hit 1.000.
            if result['AB'] <= result['H']:
                # Use the higher of their projected rate or a league-average floor
                # This lets stars be .320 hitters and bench guys be .240 hitters
                talent_floor = max(0.240, proj_h_rate + 0.02)
                result['AB'] = result['H'] / talent_floor
        else:
            proj_outs = result['PA'] - (result['H'] + result['BB'])
            result['AB'] = proj_outs + result['H']
            result['IP'] = (proj_outs // 3) + ((proj_outs % 3) / 10)

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
        career_total = history[stat_col].sum()
        career_vol = history[vol_col].sum()
        is_p = 'IP' in history.columns

        # 1. DYNAMIC K-SCALING (The "Trust" Meter)
        vol_trust_factor = np.clip(career_vol / 1500, 0, 1)
        # Slides from 800 (Rookie) down to 20 (Veteran)
        base_k = 800 * (1 - vol_trust_factor) + 20
        k_map = self.k_vals_pitcher if is_p else self.k_vals_batter
        k = k_map.get(stat_col, base_k)

        # 2. THE TETHERED POWER LOGIC (Only for 2B, 3B, HR)
        # CRITICAL: We check vol_col == 'H' to ensure Hits (PA) never enters here.
        if stat_col in ['2B', '3B', 'HR'] and not is_p and vol_col == 'H':
            lg_h_pa = self.lg_avgs.get('H_per_PA', 0.235)
            lg_stat_pa = self.lg_avgs.get(f"{stat_col}_per_PA", 0.035)
            lg_ratio = lg_stat_pa / lg_h_pa  # The "League Mean" ratio (e.g. 0.15 HR/H)

            career_h = history['H'].sum()
            # Regress the player's personal XBH/H ratio toward the league ratio
            reg_ratio = (career_total + k * lg_ratio) / (career_h + k)

            # Return the Ratio (per Hit), NOT a Rate (per PA)
            return float(reg_ratio)

        # 3. THE ANCHOR LOGIC (H, BB, SO)
        # This is where Will Smith's Hits will now correctly land.
        lg_rate = self.lg_avgs.get(f"{stat_col}_per_{vol_col}")
        if lg_rate is None:
            # Final fallback to PA-based rate
            lg_rate = self.lg_avgs.get(f"{stat_col}_per_PA", 0.10)

        if career_vol + k == 0:
            return lg_rate

        return (career_total + k * lg_rate) / (career_vol + k)
    # def _regress_to_mean(self, history: pd.DataFrame, stat_col: str, vol_col: str) -> float:
    #     """
    #     Bayesian regression to the league mean for low-sample players.
    #
    #     Uses a K-value (prior strength) from k_vals_batter / k_vals_pitcher to
    #     weight the player's observed rate against the league average rate.
    #     Formula: (career_total + K * lg_rate) / (career_vol + K).
    #
    #     For extra-base hits (2B, 3B, HR) the regression is tethered to hits:
    #     the XBH/H ratio is regressed separately, then converted back to a PA rate
    #     via the regressed H/PA rate.
    #
    #     :param history: Player's historical season DataFrame.
    #     :param stat_col: Stat column to regress.
    #     :param vol_col: Volume denominator column.
    #     :return: Bayesian-regressed per-vol rate.
    #     """
    #     career_total = history[stat_col].sum()
    #     career_vol = history[vol_col].sum()
    #     is_p = 'IP' in history.columns
    #
    #     # DYNAMIC K-SCALING:
    #     # Proven veterans (1500+ PA) get K=20 (nearly pure trust)
    #     # Rookies (0 PA) get K=800 (massive pull to mean)
    #     vol_trust_factor = np.clip(career_vol / 1500, 0, 1)
    #     base_k = 800 * (1 - vol_trust_factor) + 20
    #     k_map = self.k_vals_pitcher if is_p else self.k_vals_batter
    #     k = k_map.get(stat_col, base_k)
    #
    #     # FIXED: Look for the specific per_vol rate, or calculate it from the PA rate
    #     lg_rate_key = f"{stat_col}_per_{vol_col}"
    #     if lg_rate_key in self.lg_avgs:
    #         lg_rate = self.lg_avgs[lg_rate_key]
    #     else:
    #         # Fallback: Calculate ratio from PA-based averages
    #         lg_pa_rate = self.lg_avgs.get(f"{stat_col}_per_PA", 0.03)
    #         lg_h_rate = self.lg_avgs.get("H_per_PA", 0.235)
    #         lg_rate = lg_pa_rate / lg_h_rate if vol_col == 'H' else lg_pa_rate
    #
    #     # 2. POWER TETHERING (The Logic Anchor)
    #     if stat_col in ['2B', '3B', 'HR'] and not is_p:
    #         # We need the regressed Hit Rate to act as the base
    #         # Calculate it directly here to avoid infinite recursion
    #         h_k = self.k_vals_batter['H']
    #         lg_h_rate = self.lg_avgs.get('H_per_PA', 0.235)  # higher hits per PA
    #         regressed_h_rate = (history['H'].sum() + h_k * lg_h_rate) / (history['PA'].sum() + h_k)
    #
    #         # Calculate the League Ratio (XBH per Hit)
    #         lg_ratio = lg_rate / lg_h_rate
    #
    #         # Regress the player's XBH/H ratio
    #         career_h = history['H'].sum()
    #         regressed_ratio = (career_total + k * lg_ratio) / (career_h + k)
    #
    #         # Return the Stat/PA rate
    #         return regressed_ratio
    #
    #     # 3. STANDARD BAYESIAN CALC (Pitchers and Non-Tethered Hitter Stats)
    #     if career_vol + k == 0:
    #         return lg_rate
    #
    #     return (career_total + k * lg_rate) / (career_vol + k)

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

        # EXPERIENCE-BASED DAMPENING:
        # If they have 3+ years of data OR 1000+ PAs, we trust the trend almost 100%
        is_proven = num_years >= 2 or career_vol >= 750
        dampener = 0.95 if is_proven else min(0.25 * num_years, 0.8)

        # Allow steeper slopes for proven power/hitters to capture surges
        max_slope = 0.035 if (stat_col in ['HR', '2B', 'H'] and is_proven) else 0.020
        slope = np.clip(slope, -max_slope, max_slope)

        proj = (slope * dampener * num_years) + intercept
        # Proven players get a higher ceiling relative to their career peak
        max_allowed_mult = 1.25 if is_proven else 1.10
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
        weights = np.array([3, 4, 5][-len(rates):])

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
            elif age <= 28:
                # The Prime
                m = 1.02
            else:
                # Steady decline
                m = 1.0 - (0.004 * (age - 28) ** 2)
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

    def _apply_sanity_caps(self, rate, stat_col, is_p):
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
            caps = {'HBP': 0.035, 'BB': 0.190, 'H': 0.380}
            if stat_col in caps:
                return min(rate, caps[stat_col])
        return rate


if __name__ == "__main__":
    import pandas as pd
    import numpy as np

    # 1. Setup Mock Averages (Universal PA-based rates)
    # Note: K/PA and H/PA are roughly 1/4th of their per-inning counterparts
    mock_lg = {
        'H_per_PA': 0.230,
        '2B_per_PA': 0.050,
        '3B_per_PA': 0.002,
        'HR_per_PA': 0.035,
        'BB_per_PA': 0.085,
        'SO_per_PA': 0.225,
        'ER_per_PA': 0.110,
        'HBP_per_PA': 0.010,
        'SF_per_PA': 0.005
    }

    projector = PlayerProjector(mock_lg)

    # 2. Raw Historical Data
    raw_data = pd.DataFrame([
        # --- BATTERS ---
        {'Hashcode': 'TB1', 'Player': 'Tyler Black', 'Season': 2024, 'Age': 23,
         'AB': 49, 'H': 10, '2B': 2, '3B': 0, 'HR': 0, 'BB': 7, 'HBP': 0, 'SF': 0, 'SO': 17},
        {'Hashcode': 'CD1', 'Player': 'Caleb Durbin', 'Season': 2025, 'Age': 25,
         'AB': 445, 'H': 114, '2B': 25, '3B': 0, 'HR': 11, 'BB': 30, 'HBP': 2, 'SF': 3, 'SO': 50},

        # --- PITCHERS ---
        # Jared Jones (Rookie): 70.1 IP
        {'Hashcode': 'JJ1', 'Player': 'Jared Jones', 'Season': 2024, 'Age': 22,
         'IP': 70.1, 'H': 60, 'ER': 30, 'BB': 25, 'SO': 85, 'HR': 10},

        # Logan Webb (Veteran): 213.2 IP
        {'Hashcode': 'LW1', 'Player': 'Logan Webb', 'Season': 2024, 'Age': 27,
         'IP': 213.2, 'H': 200, 'ER': 80, 'BB': 50, 'SO': 180, 'HR': 20}
    ])

    # 3. Pre-process PA (Standardizing the Denominator)
    processed_rows = []
    for _, row in raw_data.iterrows():
        r = row.to_dict()
        if 'IP' in r and pd.notnull(r['IP']):
            # Pitching PA = (IP_Whole * 3 + IP_Dec * 10) + H + BB
            outs = (int(r['IP']) * 3) + np.round((r['IP'] % 1) * 10)
            r['PA'] = outs + r['H'] + r.get('BB', 0)
            r['is_pitcher'] = True
        else:
            # Hitting PA = AB + BB + HBP + SF
            r['PA'] = r.get('AB', 0) + r.get('BB', 0) + r.get('HBP', 0) + r.get('SF', 0)
            r['is_pitcher'] = False
            r['IP'] = np.nan
        processed_rows.append(r)

    df_ready = pd.DataFrame(processed_rows)

    # 4. RUN PROJECTIONS
    hitter_stats = ['H', '2B', '3B', 'HR', 'BB', 'SO']
    pitcher_stats = ['H', 'BB', 'SO', 'HR', 'ER']

    h_proj = projector.calculate_projected_stats(df_ready[~df_ready['is_pitcher']], hitter_stats, is_p=False)
    p_proj = projector.calculate_projected_stats(df_ready[df_ready['is_pitcher']], pitcher_stats, is_p=True)

    # 5. OUTPUT BATTERS
    print("\n" + "=" * 100)
    print(f"{'BATTER':<18} | {'METHOD':<15} | {'PA':<5} | {'AB':<5} | {'H':<5} | {'AVG':<6} | {'OBP':<6}")
    print("-" * 100)
    for _, row in h_proj.iterrows():
        avg = row['H'] / row['AB'] if row['AB'] > 0 else 0
        obp = (row['H'] + row['BB']) / row['PA'] if row['PA'] > 0 else 0
        print(
            f"{row['Player']:<18} | {row['Projection_Method']:<15} | {int(row['PA']):<5} | {int(row['AB']):<5} | {int(row['H']):<5} | {avg:<6.3f} | {obp:<6.3f}")

    # 6. OUTPUT PITCHERS
    print("\n" + "=" * 100)
    print(f"{'PITCHER':<18} | {'METHOD':<15} | {'IP':<6} | {'PA(BF)':<7} | {'AB':<5} | {'K/9':<6} | {'WHIP':<6}")
    print("-" * 100)
    for _, row in p_proj.iterrows():
        # WHIP and K/9 calculations
        outs = (int(row['IP']) * 3) + np.round((row['IP'] % 1) * 10)
        ip_true = outs / 3
        whip = (row['H'] + row['BB']) / ip_true if ip_true > 0 else 0
        k9 = (row['SO'] * 9) / ip_true if ip_true > 0 else 0

        print(
            f"{row['Player']:<18} | {row['Projection_Method']:<15} | {row['IP']:<6.1f} | {int(row['PA']):<7} | {int(row['AB']):<5} | {k9:<6.2f} | {whip:<6.2f}")
    print("=" * 100)