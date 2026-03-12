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
    def __init__(self, league_averages: Dict[str, float], gate_pa: int = 400):
        self.lg_avgs = league_averages
        self.gate = gate_pa

        # Higher K = Stronger pull toward league average (less trust in small samples)
        self.k_vals_batter = {
            'H': 150,  # Lowered: Trust Batting Average more quickly
            '2B': 250,  # Respect doubles
            '3B': 500,  # Triples are high-variance/luck-based
            'HR': 350,  # Power stabilizes around 300-400 AB
            'BB': 400,  # Plate discipline is fairly stable
            'SO': 150,  # Strikeout rate stabilizes very quickly (~60 PA)
            'HBP': 1500,  # Extremely high: Don't project many HBPs for rookies
            'default': 300
        }

        self.k_vals_pitcher = {
            'H': 1000,  # Hits allowed (BABIP) regresses heavily
            'BB': 400,  # Walk rate
            'SO': 100,  # K-rate stabilizes very fast for pitchers
            'HR': 600,  # HR/FB rate takes time to stabilize
            'ER': 500,  # Essential for preventing 0.00 ERA anomalies
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
        unique_players = history['Hashcode'].unique()
        all_projections = []

        for h_code in unique_players:
            # Filter for the specific player's history
            player_history = history[history['Hashcode'] == h_code].sort_values('Season')

            # Call the internal single-player logic
            proj_dict = self._project_single_player(player_history, stats, is_p)
            all_projections.append(proj_dict)

        # Return a full DataFrame ready for bbstats_preprocess
        return pd.DataFrame(all_projections)

    def _project_single_player(self, history: pd.DataFrame,
                               stats: List[str],
                               is_p: bool) -> dict:
        """
        Finalized Entry Point: Synchronizes Volume and Tethers Stats.
        """
        vol_col = 'IP' if is_p else 'PA'

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
            proj_vol = max(30, min(raw_vol, 220))

        # 2. INITIALIZE RESULT
        result = history.iloc[-1].to_dict()
        result[vol_col] = proj_vol
        result['Years_Included'] = history['Season'].tolist()

        # 3. METHOD LABELING
        career_vol = history[vol_col].sum()
        if num_years == 1 and career_vol >= 350:
            result['Projection_Method'] = "1-Year Starter"
        elif num_years >= 3:
            result['Projection_Method'] = "Trend"
        else:
            result['Projection_Method'] = "Regressed"

        # 4. PROJECT ANCHOR STATS (H, BB, SO)
        for stat in ['H', 'BB', 'SO']:
            rate = self.get_projection(history, stat, vol_col, is_p)
            result[stat] = rate * proj_vol

        # 5. PROJECT TETHERED STATS (2B, 3B, HR)
        if not is_p:
            proj_h = result['H']
            for stat in ['2B', '3B', 'HR']:
                # Project ratio relative to Hits
                ratio = self.get_projection(history, stat, 'H', is_p)
                result[stat] = proj_h * ratio

            # 6. DERIVE AB (The Accuracy Lock)
            # AB = PA - (BB + HBP + SF)
            result['AB'] = result['PA'] - (result.get('BB', 0) + result.get('HBP', 0) + result.get('SF', 0))

            if result['AB'] < result['H']:
                result['AB'] = result['H'] / 0.280  # Safety floor
        else:
            result['AB'] = proj_vol * 3.1
            result['IP'] = proj_vol

        return result
        # # 1. ESTABLISH MASTER DENOMINATOR
        # vol_col = 'IP' if is_p else 'PA'
        #
        # # 2. VOLUME & WEIGHTING (Philosophy #2: Trend Recognition)
        # num_years = len(history)
        # weights = np.array([3, 4, 5][-num_years:])
        #
        # # Calculate Weighted average volume
        # raw_vol = np.sum(history[vol_col].values * weights) / weights.sum()
        # recent_vol = history.iloc[-1][vol_col]
        #
        # # 3. VOLUME TARGETING (Philosophy #3: Injury/Sample Smoothing)
        # if not is_p:
        #     # Define the 'Prospect/Utility' Corridor
        #     corridor_vol = max(150, min(raw_vol, 350))
        #
        #     # Calculate 'Trust' factor: How close are they to a full season?
        #     # A player with 450+ PA is 100% trusted; a player with 100 PA is 20% trusted.
        #     trust_factor = np.clip(raw_vol / 450, 0, 1)
        #
        #     # BLEND: High-volume stars keep their raw_vol; low-volume players stay in corridor.
        #     # This eliminates the '399 PA' cliff.
        #     proj_vol = (raw_vol * trust_factor) + (corridor_vol * (1 - trust_factor))
        #
        #     # Global Hitter Cap
        #     proj_vol = min(proj_vol, 700)
        # else:
        #     # Pitching Volume logic (IP)
        #     if recent_vol >= 100:  # Established Starter
        #         proj_vol = raw_vol
        #     else:
        #         proj_vol = max(30, min(raw_vol, 80))
        #
        #     proj_vol = min(proj_vol, 220)  # Modern IP ceiling
        #
        # # 4. INITIALIZE RESULT & LOCK VOLUME
        # result = history.iloc[-1].to_dict()
        # result[vol_col] = proj_vol  # This is the ANCHOR for all following math
        # result['Years_Included'] = history['Season'].tolist()
        #
        # # Method Labeling
        # career_vol = history[vol_col].sum()
        # if num_years == 1 and career_vol >= 350:
        #     result['Projection_Method'] = "1-Year Starter"
        # elif num_years >= 3:
        #     result['Projection_Method'] = "Trend"
        # else:
        #     result['Projection_Method'] = "Regressed"
        #
        # # 5. PROJECT EVERY STAT (Strictly against the locked proj_vol)
        #     # First, project the base rates (H and BB) to act as anchors
        #     for stat in ['H', 'BB', 'SO']:
        #         rate = self.get_projection(history, stat, vol_col, is_p)
        #         result[stat] = rate * proj_vol
        #
        #     # Now, project XBH tethered to the NEW projected Hits (result['H'])
        #     xbh_stats = ['2B', '3B', 'HR']
        #     total_xbh = 0
        #     proj_h = result['H']
        #
        #     for stat in xbh_stats:
        #         # We use 'H' as the vol_col here to get the Ratio (XBH/H)
        #         rate_of_hits = self.get_projection(history, stat, 'H', is_p)
        #         result[stat] = round(proj_h * rate_of_hits)
        #         total_xbh += result[stat]
        #
        #     # Safety check: if XBH > Hits, scale them down
        #     if total_xbh > proj_h and proj_h > 0:
        #         factor = proj_h / total_xbh
        #         for stat in xbh_stats:
        #             result[stat] = np.floor(result[stat] * factor)
        #     elif proj_h == 0:
        #         for stat in xbh_stats:
        #             result[stat] = 0
        #
        # # 6. DERIVE SECONDARY VOLUME (AB)
        # if not is_p:
        #     # Instead of a ratio, use the counts we just projected in Step 5
        #     # AB = PA - (BB + HBP + SF)
        #     # This ensures AVG, OBP, and SLG are mathematically perfect.
        #     bb_count = result.get('BB', 0)
        #     hbp_count = result.get('HBP', 0)
        #     sf_count = result.get('SF', 0)
        #
        #     result['AB'] = result['PA'] - (bb_count + hbp_count + sf_count)
        #
        #     # Emergency Sanity: Prevent H > AB in edge cases
        #     if result['H'] > result['AB']:
        #         result['AB'] = result['H'] + 1
        #
        # return result

    def get_projection(self, player_history: pd.DataFrame, stat_col: str, vol_col: str,
                       is_pitching: bool) -> float:
        num_years = len(player_history)
        career_vol = player_history[vol_col].sum()
        age_2026 = int(player_history.iloc[-1]['Age']) + 1
        is_pitching = (vol_col == 'IP')

        # --- STEP 1: STRATEGY SELECTION ---
        if num_years == 1 and career_vol >= 300:
            raw_rate = self._project_single_year_starter(player_history, stat_col, vol_col)
        elif (career_vol / num_years) < 100 or num_years < 2:
            raw_rate = self._regress_to_mean(player_history, stat_col, vol_col)
        elif self._is_injury_year(player_history, vol_col):
            raw_rate = self._project_with_injury_smoothing(player_history, stat_col, vol_col)
        elif self._is_consistent_trend(player_history, stat_col, vol_col) and num_years >= 3:
            raw_rate = self._linear_regression(player_history, stat_col, vol_col)
        else:
            raw_rate = self._weighted_career_average(player_history, stat_col, vol_col)

        # --- STEP 2: AGING & GROWTH ---
        trust = min(career_vol / self.gate, 1.0)
        full_m = self._get_aging_multiplier(age_2026, is_pitching)
        dampened_m = 1.0 + (full_m - 1.0) * trust
        final_rate = raw_rate * dampened_m

        # --- STEP 3: THE GLOBAL UNPROVEN TAX ---
        safe_vol = max(1, career_vol)
        if not is_pitching:
            unproven_factor = max(0, 1.0 - (safe_vol / 500))
            tax_multiplier = 1.0 - (0.15 * unproven_factor)
            if stat_col != 'SO':
                final_rate *= tax_multiplier
        else:
            unproven_factor = max(0, 1.0 - (safe_vol / 150))
            if stat_col in ['H', 'BB', 'ER', 'HR']:
                final_rate *= (1.0 + (0.15 * unproven_factor))
            else:
                final_rate *= (1.0 - (0.15 * unproven_factor))

        # --- STEP 4: RETURN & SANITY ---
        final_rate = self._apply_sanity_caps(final_rate, stat_col, is_pitching)
        return float(final_rate) if final_rate is not None and not np.isnan(final_rate) else 0.0

    def _project_single_year_starter(self, history: pd.DataFrame, stat_col: str, vol_col: str) -> float:
        actual_rate = history.iloc[-1][stat_col] / max(1, history.iloc[-1][vol_col])
        lg_rate = self.lg_avgs.get(f"{stat_col}_per_{vol_col}", 0.10)
        return (actual_rate * 0.80) + (lg_rate * 0.20)

    def _regress_to_mean(self, history: pd.DataFrame, stat_col: str, vol_col: str) -> float:
        career_total = history[stat_col].sum()
        career_vol = history[vol_col].sum()
        is_p = (vol_col == 'IP')

        # 1. Fetch the correct K and League Rate
        k_map = self.k_vals_pitcher if is_p else self.k_vals_batter
        k = k_map.get(stat_col, k_map['default'])
        lg_rate = self.lg_avgs.get(f"{stat_col}_per_{vol_col}", 0.10)

        # 2. POWER TETHERING (The Logic Anchor)
        if stat_col in ['2B', '3B', 'HR'] and not is_p:
            # We need the regressed Hit Rate to act as the base
            # Calculate it directly here to avoid infinite recursion
            h_k = self.k_vals_batter['H']
            lg_h_rate = self.lg_avgs.get('H_per_PA', 0.22)
            regressed_h_rate = (history['H'].sum() + h_k * lg_h_rate) / (history['PA'].sum() + h_k)

            # Calculate the League Ratio (XBH per Hit)
            lg_ratio = lg_rate / lg_h_rate

            # Regress the player's XBH/H ratio
            career_h = history['H'].sum()
            regressed_ratio = (career_total + k * lg_ratio) / (career_h + k)

            # Return the Stat/PA rate
            return regressed_ratio * regressed_h_rate

        # 3. STANDARD BAYESIAN CALC
        return (career_total + k * lg_rate) / (career_vol + k)

    def _linear_regression(self, history: pd.DataFrame, stat_col: str, vol_col: str) -> float:
        rates = (history[stat_col] / history[vol_col].replace(0, 1)).values
        num_years = len(rates)
        x = np.arange(num_years)
        try:
            slope, intercept = np.polyfit(x, rates, 1)
        except:
            return self._weighted_career_average(history, stat_col, vol_col)
        dampener = min(0.15 * num_years, 0.8)
        slope = np.clip(slope, -0.015, 0.015)
        proj = (slope * dampener * num_years) + intercept
        age = history.iloc[-1]['Age']
        max_allowed = rates.max() * (1.15 if age < 30 else 1.05)
        return max(0.0, min(proj, max_allowed))

    def _weighted_career_average(self, history, stat_col, vol_col):
        rates = (history[stat_col] / history[vol_col].replace(0, 1)).values
        weights = np.array([3, 4, 5][-len(rates):])
        return np.average(rates, weights=weights)

    def _get_aging_multiplier(self, age, is_p):
        if age <= 25:
            m = -0.002 * (age - 26) ** 2 + 1.05
        elif age <= 30:
            m = 1.0
        else:
            m = 1.0 - (0.0035 * (age - 30) ** 2)
        return np.clip(m, 0.80, 1.10)

    def _is_injury_year(self, history, vol_col):
        if len(history) < 3: return False
        vols = history[vol_col].values
        return vols[-2] < (vols[-3] * 0.4) and vols[-1] > (vols[-2] * 1.5)

    def _project_with_injury_smoothing(self, history, stat_col, vol_col):
        rates = (history[stat_col] / history[vol_col].replace(0, 1)).values
        if len(rates) >= 3:
            return (rates[-3] * 0.45) + (rates[-2] * 0.10) + (rates[-1] * 0.45)
        return self._weighted_career_average(history, stat_col, vol_col)

    def _is_consistent_trend(self, history, stat_col, vol_col):
        rates = (history[stat_col] / history[vol_col].replace(0, 1)).values
        if len(rates) < 2: return False
        diffs = np.diff(rates)
        return all(d >= 0 for d in diffs) or all(d <= 0 for d in diffs)

    def _apply_sanity_caps(self, rate, stat_col, is_p):
        if not is_p:
            caps = {'HBP': 0.035, 'BB': 0.185, 'H': 0.380}
            if stat_col in caps:
                return min(rate, caps[stat_col])
        return rate


if __name__ == "__main__":
    # 1. Setup Mock Averages & K-Values (League Mean per PA)
    mock_lg = {
        'H_per_PA': 0.210, '2B_per_PA': 0.045, '3B_per_PA': 0.005,
        'HR_per_PA': 0.028, 'BB_per_PA': 0.085, 'SO_per_PA': 0.225,
        'AB_per_PA': 0.880, 'H_per_IP': 0.950, 'SO_per_IP': 1.100,
        'BB_per_IP': 0.350
    }

    projector = PlayerProjector(mock_lg)

    # 2. Raw Historical Data
    raw_data = pd.DataFrame([
        # Tyler Black: High BB profile
        {'Hashcode': 'TB1', 'Player': 'Tyler Black', 'Season': 2024, 'Age': 23,
         'AB': 49, 'H': 10, '2B': 2, '3B': 0, 'HR': 0, 'BB': 7, 'HBP': 0, 'SF': 0, 'SO': 17},

        # Caleb Durbin: 1-Year Starter
        {'Hashcode': 'CD1', 'Player': 'Caleb Durbin', 'Season': 2025, 'Age': 25,
         'AB': 445, 'H': 114, '2B': 25, '3B': 0, 'HR': 11, 'BB': 30, 'HBP': 2, 'SF': 3, 'SO': 50},

        # William Contreras: Multi-Year Trend
        {'Hashcode': 'WC1', 'Player': 'W. Contreras', 'Season': 2023, 'Age': 25,
         'AB': 540, 'H': 156, '2B': 38, '3B': 1, 'HR': 17, 'BB': 63, 'HBP': 4, 'SF': 5, 'SO': 126},
        {'Hashcode': 'WC1', 'Player': 'W. Contreras', 'Season': 2024, 'Age': 26,
         'AB': 595, 'H': 167, '2B': 37, '3B': 2, 'HR': 23, 'BB': 78, 'HBP': 3, 'SF': 6, 'SO': 139},
        {'Hashcode': 'WC1', 'Player': 'W. Contreras', 'Season': 2025, 'Age': 27,
         'AB': 566, 'H': 147, '2B': 28, '3B': 0, 'HR': 17, 'BB': 84, 'HBP': 5, 'SF': 4, 'SO': 120}
    ])

    # 3. Apply the PA calculation (Simulating bbstats_preprocess)
    # Using .fillna(0) ensures no PA results in a NaN
    for col in ['AB', 'BB', 'HBP', 'SF']:
        if col not in raw_data.columns:
            raw_data[col] = 0
        else:
            raw_data[col] = raw_data[col].fillna(0)

    raw_data['PA'] = raw_data['AB'] + raw_data['BB'] + raw_data['HBP'] + raw_data['SF']

    # 4. RUN BULK PROJECTION
    stats_to_project = ['H', '2B', '3B', 'HR', 'BB', 'SO']
    projections_df = projector.calculate_projected_stats(raw_data, stats_to_project, is_p=False)

    # 5. POST-PROJECTION CALCS
    # Ensure AB exists and is non-zero to avoid division by zero errors
    projections_df['AVG'] = projections_df['H'] / projections_df['AB'].replace(0, np.nan)
    projections_df['OBP'] = (projections_df['H'] + projections_df['BB']) / projections_df['PA'].replace(0, np.nan)

    singles = projections_df['H'] - (projections_df['2B'] + projections_df['3B'] + projections_df['HR'])
    projections_df['SLG'] = (singles + 2 * projections_df['2B'] + 3 * projections_df['3B'] + 4 * projections_df['HR']) / \
                            projections_df['AB'].replace(0, np.nan)

    # 6. OUTPUT RESULTS (With logic to avoid ValueError on NaN)
    print("\n" + "=" * 110)
    print(f"{'PLAYER':<18} | {'METHOD':<15} | {'PA':<5} | {'AB':<5} | {'H':<5} | {'AVG':<6} | {'OBP':<6} | {'SLG':<6}")
    print("=" * 110)

    for _, row in projections_df.iterrows():
        # Clean formatting: Convert to int if possible, otherwise display 0
        pa = int(row['PA']) if pd.notnull(row['PA']) else 0
        ab = int(row['AB']) if pd.notnull(row['AB']) else 0
        h = int(row['H']) if pd.notnull(row['H']) else 0

        print(f"{row['Player']:<18} | {row['Projection_Method']:<15} | "
              f"{pa:<5} | {ab:<5} | {h:<5} | "
              f"{row['AVG']:<6.3f} | {row['OBP']:<6.3f} | {row['SLG']:<6.3f}")
    print("-" * 110)