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
from typing import List, Dict, Optional


class PlayerProjector:
    def __init__(self, league_averages: Dict[str, float], k_values: Dict[str, int], gate_pa: int = 400):
        self.lg_avgs = league_averages
        self.k_vals = k_values
        self.gate = gate_pa

    def get_projection(self, player_history: pd.DataFrame, stat_col: str, vol_col: str) -> float:
        num_years = len(player_history)
        career_vol = player_history[vol_col].sum()
        age_2026 = int(player_history.iloc[-1]['Age']) + 1
        is_pitching = (vol_col == 'IP')

        # --- STEP 1: SELECT RAW STRATEGY ---
        if num_years == 1 and career_vol >= 300:
            actual_rate = player_history.iloc[-1][stat_col] / max(1, player_history.iloc[-1][vol_col])
            lg_rate = self.lg_avgs.get(f"{stat_col}_per_{vol_col}", 0.10)
            # Use a consistent 75/25 blend for all stats for 1-year starters
            raw_rate = (actual_rate * 0.75) + (lg_rate * 0.25)
        elif (career_vol / num_years) < 100 or num_years < 2:
            raw_rate = self._regress_to_mean(player_history, stat_col, vol_col)
        elif self._is_injury_year(player_history, vol_col):
            raw_rate = self._project_with_injury_smoothing(player_history, stat_col, vol_col)
        elif self._is_consistent_trend(player_history, stat_col, vol_col):
            raw_rate = self._linear_regression(player_history, stat_col,
                                               vol_col) if num_years >= 3 else self._weighted_career_average(
                player_history, stat_col, vol_col)
        else:
            raw_rate = self._weighted_career_average(player_history, stat_col, vol_col)

        # --- STEP 2: GROWTH FLOOR ---
        if not is_pitching and age_2026 <= 25:
            weighted_avg = self._weighted_career_average(player_history, stat_col, vol_col)
            if stat_col in ['H', 'HR', 'BB', '2B', '3B', 'HBP']:
                raw_rate = max(raw_rate, weighted_avg)
            elif stat_col == 'SO':
                raw_rate = min(raw_rate, weighted_avg)

        # --- STEP 3: AGING ---
        trust = min(career_vol / self.gate, 1.0)
        full_m = self._get_aging_multiplier(age_2026, is_pitching)
        dampened_m = 1.0 + (full_m - 1.0) * trust
        final_rate = raw_rate * dampened_m

        # --- STEP 4: GLOBAL UNPROVEN TAX ---
        # We apply this to ALL stats equally to prevent "Stat Floating"
        safe_vol = max(1, career_vol)
        if not is_pitching:
            unproven_factor = max(0, 1.0 - (safe_vol / 500))
            # 20% max penalty for a 0-PA player, scaling to 0% at 500 PAs
            tax_multiplier = 1.0 - (0.20 * unproven_factor)

            # Strikeouts are the only stat we don't tax (as it would lower them)
            if stat_col != 'SO':
                final_rate *= tax_multiplier
        else:
            unproven_factor = max(0, 1.0 - (safe_vol / 150))
            tax_multiplier = 1.15 if unproven_factor > 0 else 1.0  # 15% rookie inflation for bad stats
            if stat_col in ['H', 'BB', 'ER', 'HR']:
                final_rate *= (1.0 + (0.15 * unproven_factor))
            else:
                final_rate *= (1.0 - (0.15 * unproven_factor))

        # --- STEP 5: RETURN & SANITY ---
        final_rate = self._apply_sanity_caps(final_rate, stat_col, is_pitching)
        return float(final_rate) if final_rate is not None and not np.isnan(final_rate) else 0.0
        # num_years = len(player_history)
        # career_vol = player_history[vol_col].sum()
        # age_2026 = int(player_history.iloc[-1]['Age']) + 1
        # is_pitching = (vol_col == 'IP')
        #
        # # STEP 1: SELECT RAW STRATEGY
        # # --- NEW LOGIC FOR DURBIN-STYLE ANOMALIES ---
        # # If they have only 1 year but high volume, don't use heavy Bayesian regression.
        # # This prevents the .182 BA for a guy who just hit .256 in 445 ABs.
        # if num_years == 1 and career_vol >= 300:
        #     actual_rate = player_history.iloc[-1][stat_col] / max(1, player_history.iloc[-1][vol_col])
        #     lg_rate = self.lg_avgs.get(f"{stat_col}_per_{vol_col}", 0.10)
        #     # Blend 75% Actual / 25% League to anchor them without tanking them.
        #     raw_rate = (actual_rate * 0.75) + (lg_rate * 0.25)
        #
        # elif (career_vol / num_years) < 100 or num_years < 2:
        #     # Standard path for true small-sample players
        #     raw_rate = self._regress_to_mean(player_history, stat_col, vol_col)
        #
        # elif self._is_injury_year(player_history, vol_col):
        #     raw_rate = self._project_with_injury_smoothing(player_history, stat_col, vol_col)
        #
        # elif self._is_consistent_trend(player_history, stat_col, vol_col):
        #     # TREND GUARD: If we have < 3 years, trend is too volatile; fallback to weighted avg.
        #     if num_years < 3:
        #         raw_rate = self._weighted_career_average(player_history, stat_col, vol_col)
        #     else:
        #         raw_rate = self._linear_regression(player_history, stat_col, vol_col)
        # else:
        #     raw_rate = self._weighted_career_average(player_history, stat_col, vol_col)
        #
        # # --- STEP 2: GROWTH FLOOR (Philosophy #4) ---
        # # Restored and refined: If a young player (<= 25) shows better talent
        # # in their weighted average than the regression, trust the average.
        # if not is_pitching and age_2026 <= 25:
        #     weighted_avg = self._weighted_career_average(player_history, stat_col, vol_col)
        #     if stat_col in ['H', 'HR', 'BB', '2B', '3B']:
        #         raw_rate = max(raw_rate, weighted_avg)
        #     elif stat_col in ['SO', 'HBP']:  # Force HBP to regress toward the lower of the two
        #         raw_rate = min(raw_rate, weighted_avg)
        #
        #     # STEP 3: TRUST-WEIGHTED AGING (Existing)
        #     trust = min(career_vol / self.gate, 1.0)
        #     full_m = self._get_aging_multiplier(age_2026, is_pitching)
        #     dampened_m = 1.0 + (full_m - 1.0) * trust
        #     final_rate = raw_rate * dampened_m
        #
        # # --- STEP 4: THE GLOBAL UNPROVEN TAX (NEW) ---
        # # This prevents 'Stat Inflation' where a rookie's BA is low but HR/BB are high.
        # if not is_pitching:
        #     # Calculate how 'unproven' they are (0.0 = Veteran, 1.0 = Total Rookie)
        #     # Using 500 PAs as the 'Proven' threshold
        #     unproven_factor = max(0, 1.0 - (career_vol / 500))
        #
        #     # Apply a 20% max penalty for completely unproven players
        #     # This drags ALL stats (H, HR, BB, 2B) down together
        #     tax_multiplier = 1.0 - (0.20 * unproven_factor)
        #
        #     # We don't tax Strikeouts (SO) because that would make them 'better'
        #     if stat_col != 'SO':
        #         final_rate *= tax_multiplier
        #
        # # Apply Pitcher Tax if needed (using 150 IP as 'Proven')
        # elif is_pitching:
        #     unproven_factor = max(0, 1.0 - (career_vol / 150))
        #     tax_multiplier = 1.0 - (0.15 * unproven_factor)
        #     # For pitchers, 'Hits Allowed' and 'Walks Allowed' are bad,
        #     # so we actually INCREASE the rate for unproven guys.
        #     if stat_col in ['H', 'BB', 'ER', 'HR']:
        #         final_rate *= (1.0 + (0.15 * unproven_factor))
        #     else:
        #         final_rate *= tax_multiplier
        #
        # # Ensure we NEVER return None or NaN
        # final_rate = self._apply_sanity_caps(final_rate, stat_col, is_pitching)
        #
        # if final_rate is None or np.isnan(final_rate):
        #     return 0.0
        #
        # return float(final_rate)

    # def get_projection(self, player_history: pd.DataFrame, stat_col: str, vol_col: str) -> float:
    #     num_years = len(player_history)
    #     career_vol = player_history[vol_col].sum()
    #     age_2026 = int(player_history.iloc[-1]['Age']) + 1
    #     is_pitching = (vol_col == 'IP')
    #
    #     # STEP 1: SELECT RAW STRATEGY (Bayesian, Smoothing, or Trend)
    #     if (career_vol / num_years) < 100 or num_years < 2:
    #         raw_rate = self._regress_to_mean(player_history, stat_col, vol_col)
    #     elif self._is_injury_year(player_history, vol_col):
    #         raw_rate = self._project_with_injury_smoothing(player_history, stat_col, vol_col)
    #     elif self._is_consistent_trend(player_history, stat_col, vol_col):
    #         raw_rate = self._linear_regression(player_history, stat_col, vol_col)
    #     else:
    #         raw_rate = self._weighted_career_average(player_history, stat_col, vol_col)
    #
    #     # --- STEP 2: GROWTH FLOOR (Philosophy #4) ---
    #     # If the player is 25 or younger, don't let the 'Rookie Penalty'
    #     # bury them if their weighted career average is higher.
    #     # (Protects the Jackson Chourio types who struggle early)
    #     # if not is_pitching and age_2026 <= 25:
    #     #     # We use weighted average because it represents their 'best' recent talent
    #     #     weighted_avg = self._weighted_career_average(player_history, stat_col, vol_col)
    #     #
    #     #     # For success stats (H, HR, BB), use the HIGHER of the two
    #     #     if stat_col in ['H', 'HR', 'BB', '2B', '3B']:
    #     #         raw_rate = max(raw_rate, weighted_avg)
    #     #     # For failure stats (SO), use the LOWER of the two
    #     #     elif stat_col == 'SO':
    #     #         raw_rate = min(raw_rate, weighted_avg)
    #
    #     # STEP 3: TRUST-WEIGHTED AGING; prevents low experience players from benefit from the age curve too much
    #     trust = min(career_vol / self.gate, 1.0)
    #     full_m = self._get_aging_multiplier(age_2026, is_pitching)
    #     dampened_m = 1.0 + (full_m - 1.0) * trust
    #     final_rate = raw_rate * dampened_m
    #     return self._apply_sanity_caps(final_rate, stat_col, is_pitching)

    def _regress_to_mean(self, history: pd.DataFrame, stat_col: str, vol_col: str) -> float:
        """Selector for the appropriate regression path."""
        if vol_col == 'IP':
            return self._regress_pitcher_to_mean(history, stat_col, vol_col)
        return self._regress_batter_to_mean(history, stat_col, vol_col)

    def _regress_batter_to_mean(self, history: pd.DataFrame, stat_col: str, vol_col: str) -> float:
        career_total = history[stat_col].sum()
        career_vol = history[vol_col].sum()

        # 1. Stabilization Constants (K)
        k_map = {'H': 400, 'BB': 600, 'SO': 400, 'HR': 800, '2B': 1000, '3B': 1500}
        k = k_map.get(stat_col, 500)

        # 2. Pull raw league average
        lg_rate = self.lg_avgs.get(f"{stat_col}_per_{vol_col}", 0.10)

        # --- INJECTION POINT: THE UNPROVEN FACTOR ---
        # If the player hasn't reached the 300 PA gate, we apply the penalty
        if career_vol < 300:
            # sliding scale: 1.0 (at 0 PA) down to 0.0 (at 300 PA)
            unproven_factor = (300 - career_vol) / 300

            # penalty_multiplier: starts at 0.65 and climbs to 1.0
            penalty_multiplier = 1.0 - (0.35 * unproven_factor)

            if stat_col in ['H', 'HR', 'BB', '2B', '3B']:
                # Success stats are penalized (multiplied by < 1.0)
                lg_rate *= penalty_multiplier
            elif stat_col == 'SO':
                # Failure stats are increased (multiplied by > 1.0)
                lg_rate *= (1.0 + (1.0 - penalty_multiplier))
        # --- END INJECTION ---

        # 3. Apply Bayesian Formula with the "Taxed" lg_rate
        regressed_rate = (career_total + k * lg_rate) / (career_vol + k)

        # 4. HIT COMPOSITION GUARD (Stops the .460 SLG / .173 AVG monster)
        if stat_col in ['2B', '3B', 'HR'] and career_vol < self.gate:
            projected_h_rate = self.get_projection(history, 'H', vol_col)
            caps_per_hit = {'2B': 0.22, '3B': 0.03, 'HR': 0.18}
            max_rate = projected_h_rate * caps_per_hit[stat_col]
            regressed_rate = min(regressed_rate, max_rate)

        return regressed_rate
    # def _regress_batter_to_mean(self, history: pd.DataFrame, stat_col: str, vol_col: str) -> float:
    #     career_total = history[stat_col].sum()
    #     career_vol = history[vol_col].sum()
    #
    #     # 1. Improved K-Values (The 'Anchor')
    #     # Total Hits need less shrinkage than rare events like Triples or HRs
    #     k_map = {'H': 400, 'AB': 500, 'BB': 600, 'SO': 400, 'HR': 800, '2B': 1000, '3B': 1500}
    #     k = k_map.get(stat_col, 500)
    #
    #     # 2. Experience Multiplier (The 'Rookie Tax')
    #     # Rookies (low vol) should have their raw stats pulled down more aggressively
    #     vol_factor = min(career_vol / self.gate, 1.0)
    #     dyn_penalty = 0.75 + (0.25 * vol_factor)  # Starts at 75% talent for pure rookies
    #
    #     # 3. Dynamic League Rates (Based on 2024-2025 Trends)
    #     safe_defaults = {
    #         'H': 0.215,  # Hits per PA
    #         '2B': 0.045,  # ~21% of Hits
    #         '3B': 0.003,  # ~1.5% of Hits
    #         'HR': 0.032,  # ~15% of Hits
    #         'BB': 0.082,  # League Avg OBP is usually BA + .070
    #         'SO': 0.225
    #     }
    #     lg_rate = self.lg_avgs.get(f"{stat_col}_per_{vol_col}", safe_defaults.get(stat_col, 0.10))
    #
    #     # Apply the Tax to 'Success' stats
    #     if stat_col in ['H', '2B', '3B', 'HR', 'BB']:
    #         lg_rate *= dyn_penalty
    #     elif stat_col == 'SO':
    #         lg_rate *= (1.0 + (1.0 - dyn_penalty))
    #
    #     # 4. The Bayesian Shrinkage Formula
    #     regressed_rate = (career_total + k * lg_rate) / (career_vol + k)
    #
    #     # --- THE "TYLER BLACK" FIX: HIT COMPOSITION GUARD ---
    #     # If we are calculating an extra-base hit, ensure it doesn't exceed
    #     # a logical % of the total projected hits.
    #     if stat_col in ['2B', '3B', 'HR'] and not (history[vol_col].sum() > self.gate):
    #         projected_h_rate = self.get_projection(history, 'H', vol_col)  # Recursive check
    #
    #         # Max allowable % of hits for a non-elite prospect
    #         caps_per_hit = {'2B': 0.25, '3B': 0.05, 'HR': 0.20}
    #         max_rate = projected_h_rate * caps_per_hit[stat_col]
    #
    #         return min(regressed_rate, max_rate)
    #
    #     return regressed_rate

    def _regress_pitcher_to_mean(self, history: pd.DataFrame, stat_col: str, vol_col: str) -> float:
        career_total = history[stat_col].sum()
        career_vol = history[vol_col].sum()

        # Keep the high K (Source of Truth anchor)
        k = self.k_vals.get(stat_col, 100)

        # 1. Pitcher Experience Penalty (The "Adjustment Curve")
        # We use a 150 IP gate for pitchers to reach 'Trust'
        vol_factor = min(career_vol / 150, 1.0)
        # dyn_penalty scales from 0.85 (Heavy Penalty) to 1.0 (Neutral)
        dyn_penalty = 0.85 + (0.15 * vol_factor)

        # 2. Per-IP League Defaults
        safe_defaults = {'H': 0.92, 'SO': 0.95, 'BB': 0.38, 'HR': 0.12}
        lg_rate = self.lg_avgs.get(f"{stat_col}_per_IP", safe_defaults.get(stat_col, 0.10))

        # 3. Apply the "Rookie Struggle" to the Mean
        if stat_col in ['H', 'BB', 'HR']:
            # Rookie pitchers ALLOW more hits/walks/HRs
            # If dyn_penalty is 0.85, the multiplier is 1.15x
            rookie_inflation = 1.0 + (1.0 - dyn_penalty)
            lg_rate *= rookie_inflation
        elif stat_col == 'SO':
            # Rookie pitchers strike out fewer batters
            lg_rate *= dyn_penalty

        # 4. Bayesian Shrinkage
        return (career_total + k * lg_rate) / (career_vol + k)

    def _is_injury_year(self, history, vol_col):
        if len(history) < 3: return False
        vols = history[vol_col].values
        return vols[-2] < (vols[-3] * 0.4) and vols[-1] > (vols[-2] * 1.5)

    def _project_with_injury_smoothing(self, history: pd.DataFrame, stat_col: str, vol_col: str) -> float:
        """
        Philosophy #3: If 2024 was an injury year (low volume),
        we prioritize the most recent (2025) and the pre-injury (2023) rates.
        """
        rates = (history[stat_col] / history[vol_col].replace(0, 1)).values

        # If we have 3 years: [2023, 2024 (Injury), 2025]
        if len(rates) >= 3:
            # Weight the healthy years (1 and 3) significantly more than the injury year (2)
            # This 'forgives' the statistical dip often seen during injury recovery
            return (rates[-3] * 0.40) + (rates[-2] * 0.10) + (rates[-1] * 0.50)

        # Fallback to weighted average if history is short
        return self._weighted_career_average(history, stat_col, vol_col)

    def _is_consistent_trend(self, history, stat_col, vol_col):
        rates = (history[stat_col] / history[vol_col].replace(0, 1)).values
        if len(rates) < 2: return False
        diffs = np.diff(rates)
        return all(d >= 0 for d in diffs) or all(d <= 0 for d in diffs)

    def _linear_regression(self, history: pd.DataFrame, stat_col: str, vol_col: str) -> float:
        # Calculate rates (e.g., H/AB or BB/PA)
        rates = (history[stat_col] / history[vol_col].replace(0, 1)).values
        num_years = len(rates)
        age = history.iloc[-1]['Age']

        # --- THE TREND GATE ---
        # 1. Linear trends (polyfit) are dangerous under 3 years of data.
        # This prevents 'Rocket Ship' projections from a lucky 2nd season.
        if num_years < 3:
            return self._weighted_career_average(history, stat_col, vol_col)

        x = np.arange(num_years)
        try:
            # Using deg=1 for a simple linear trend
            slope, intercept = np.polyfit(x, rates, 1)
        except:
            return self._weighted_career_average(history, stat_col, vol_col)

        # --- DAMPENING & CLIPPING ---
        # 2. Slope Dampener: Trust the trend more as years increase.
        # 3 years = 45% trust, 5+ years = 80% trust.
        dampener = min(0.15 * num_years, 0.8)

        # 3. Slope Clip (The HBP Magnet Fix):
        # Limits rate growth to +/- 1.5% per year.
        # This stops HBP rates from jumping to 10% just because a guy got hit twice in 2025.
        lg_std_limit = 0.015
        slope = np.clip(slope, -lg_std_limit, lg_std_limit)

        # 4. Project for the 'next' year (index = num_years)
        proj = (slope * dampener * num_years) + intercept

        # --- THE 'DURBIN' SAFETY CEILING ---
        # Don't let the trend exceed a reasonable % of their career best.
        # Young stars (26-30) get 15% buffer; vets (31+) get 5%.
        growth_buffer = 1.15 if 26 <= age <= 30 else 1.05
        max_allowed = rates.max() * growth_buffer

        return max(0.0, min(proj, max_allowed))

    # def _linear_regression(self, history, stat_col, vol_col):
    #     rates = (history[stat_col] / history[vol_col].replace(0, 1)).values
    #     x = np.arange(len(rates))
    #
    #     # Calculate the raw slope
    #     slope, intercept = np.polyfit(x, rates, 1)
    #
    #     # DAMPENING FACTOR:
    #     # 1. If we only have 2-3 years, cut the slope by 50%
    #     # 2. If the slope is extremely steep (like Raleigh's HRs), cap the growth
    #     dampener = 0.5 if len(rates) < 4 else 0.8
    #
    #     # Calculate projection
    #     proj = (slope * dampener * len(rates)) + intercept
    #
    #     # FOR ROOKIES (< 26): Use a blend of trend and career mean
    #     # This stops Tyler Black from exploding after 18 games
    #     if history.iloc[-1]['Age'] < 26:
    #         career_avg = rates.mean()
    #         return (proj * 0.4) + (career_avg * 0.6)
    #
    #     # FOR VETERANS: Ensure they don't exceed their career best by more than 10%
    #     # (The "Cal Raleigh" Guard)
    #     return min(proj, rates.max() * 1.1)

    def _weighted_career_average(self, history, stat_col, vol_col):
        rates = (history[stat_col] / history[vol_col].replace(0, 1)).values
        return np.average(rates, weights=[3, 4, 5][-len(rates):])

    def _apply_global_experience_filter(self, raw, vol, stat, vol_c):
        safe_defaults = {'H': 0.245, 'HR': 0.035, 'BB': 0.085, 'SO': 0.220}
        lg = self.lg_avgs.get(f"{stat}_per_{vol_c}", safe_defaults.get(stat, 0.100))
        trust = min(vol / self.gate, 1.0)
        adj_lg = lg * (0.80 + 0.20 * trust)
        return (raw * trust) + (adj_lg * (1 - trust))

    def _get_aging_multiplier(self, age, is_p):
        if age <= 25:
            m = -0.002 * (age - 26) ** 2 + 1.05
        elif age <= 30:
            m = 1.0
        else:
            m = 1.0 - (0.0035 * (age - 30) ** 2)
        return np.clip(m, 0.80, 1.10)

    def _apply_sanity_caps(self, rate: float, stat_col: str, is_p: bool) -> float:
        if not is_p:
            # HBP HARD CAP: 3.5% is elite. 10% (where you are now) is a bug.
            if stat_col == 'HBP':
                return min(rate, 0.035)

            # BB HARD CAP: 18% is Juan Soto territory.
            if stat_col == 'BB':
                return min(rate, 0.185)

            # BA HARD CAP: Ensure we don't accidentally project .450 hitters.
            if stat_col == 'H':
                return min(rate, 0.380)

        return rate


if __name__ == "__main__":
    # 1. Setup Mock League Averages & K-Values
    mock_lg = {
        'H_per_PA': 0.210, 'BB_per_PA': 0.085, 'SO_per_PA': 0.225, 'HR_per_PA': 0.028, 'AB_per_PA': 0.880,
        'H_per_IP': 0.950, 'SO_per_IP': 1.100, 'BB_per_IP': 0.350
    }
    # K=500 for Batters, K=100 for Pitchers
    mock_k = {'H': 500, 'BB': 500, 'SO': 500, 'HR': 500, 'AB': 500, 'IP': 100}

    # --- CASE 1: The "Tyler Black" (Low Sample Rookie) ---
    df_tb = pd.DataFrame({
        'Player': ['Tyler Black'], 'Season': [2024], 'Age': [23],
        'PA': [56], 'AB': [49], 'H': [10], 'BB': [7], 'SO': [17], 'HR': [0]
    })

    # --- CASE 2: The "Prospect Ace" (Nuclear K/9, Low IP) ---
    df_prospect_p = pd.DataFrame({
        'Player': ['Prospect Ace'], 'Season': [2025], 'Age': [22],
        'IP': [12.0], 'H': [8], 'BB': [9], 'SO': [22], 'HR': [1]
    })

    # --- CASE 3: The "Reliever X" (Struggling Small Sample) ---
    df_struggle_p = pd.DataFrame({
        'Player': ['Reliever X'], 'Season': [2025], 'Age': [26],
        'IP': [8.2], 'H': [12], 'BB': [6], 'SO': [5], 'HR': [3]
    })

    # --- CASE 4: The "Injured Star" (Hitter V-Shape Recovery) ---
    df_hitter_v = pd.DataFrame({
        'Player': ['Injured Star'] * 3,
        'Season': [2023, 2024, 2025],
        'Age': [28, 29, 30],
        'PA': [600, 200, 580], 'AB': [530, 180, 510],
        'H': [150, 35, 145], 'HR': [30, 4, 28]
    })

    # --- CASE 5: The "V-Slope Pitcher" (Pitcher Command Recovery) ---
    df_pitcher_v = pd.DataFrame({
        'Player': ['V-Slope Pitcher'] * 3,
        'Season': [2023, 2024, 2025],
        'Age': [26, 27, 28],
        'IP': [180.0, 45.0, 175.0],
        'H': [150, 65, 155], 'BB': [45, 30, 48], 'SO': [200, 35, 190]
    })

    # --- CASE 6: The "Established Star" (Trend Recognition) ---
    df_star = pd.DataFrame({
        'Player': ['William Contreras'] * 3,
        'Season': [2023, 2024, 2025],
        'Age': [25, 26, 27],
        'PA': [600, 650, 620], 'AB': [540, 590, 560],
        'H': [156, 167, 147], 'HR': [17, 23, 17], 'BB': [60, 75, 80]
    })

    projector = PlayerProjector(mock_lg, mock_k, gate_pa=400)
    test_suite = [df_tb, df_prospect_p, df_struggle_p, df_hitter_v, df_pitcher_v, df_star]

    print("\n" + "=" * 80)
    print(f"{'PLAYER NAME':<20} | {'TYPE':<10} | {'STAT':<4} | {'PROJ RATE':<10} | {'METHOD'}")
    print("=" * 80)

    for df in test_suite:
        name = df.iloc[-1]['Player']
        is_p = 'IP' in df.columns
        vol_col = 'IP' if is_p else 'PA'

        # Determine Method (Mimics your get_projection selection logic)
        num_years = len(df)
        avg_vol = df[vol_col].mean()
        if avg_vol < 100 or num_years < 2:
            method = "Regressed"
        elif projector._is_injury_year(df, vol_col):
            method = "Smoothing"
        else:
            method = "Trend/Wtd"

        # Check H and SO (or HR for batters)
        test_stats = ['H', 'SO'] if is_p else ['H', 'HR']

        for stat in test_stats:
            rate = projector.get_projection(df, stat, vol_col)
            rate_display = f"{rate:.3f}" if rate is not None else "None"
            print(f"{name:<20} | {'Pitcher' if is_p else 'Batter':<10} | {stat:<4} | {rate_display:<10} | {method}")
        print("-" * 80)

    print("=" * 80 + "\n")