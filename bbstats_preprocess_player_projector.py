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
        vol_col = 'PA'

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

            result['AB'] = result['PA'] - (result.get('BB', 0) + result.get('HBP', 0) + result.get('SF', 0))
            if result['AB'] < result['H']:
                result['AB'] = result['H'] / 0.280  # Safety floor
        else:
            proj_outs = result['PA'] - (result['H'] + result['BB'])
            result['AB'] = proj_outs + result['H']
            result['IP'] = (proj_outs // 3) + ((proj_outs % 3) / 10)

        return result

    def get_projection(self, player_history: pd.DataFrame, stat_col: str, vol_col: str,
                       is_pitching: bool) -> float:
        num_years = len(player_history)
        career_vol = player_history[vol_col].sum()
        age_2026 = int(player_history.iloc[-1]['Age']) + 1

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
        is_p = 'IP' in history.columns

        # 1. Fetch the correct K and League Rate
        k_map = self.k_vals_pitcher if is_p else self.k_vals_batter
        k = k_map.get(stat_col, k_map.get('default', 400))
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

        # 3. STANDARD BAYESIAN CALC (Pitchers and Non-Tethered Hitter Stats)
        if career_vol + k == 0:
            return lg_rate

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
    import pandas as pd
    import numpy as np

    # 1. Setup Mock Averages (Universal PA-based rates)
    # Note: K/PA and H/PA are roughly 1/4th of their per-inning counterparts
    mock_lg = {
        'H_per_PA': 0.220,
        '2B_per_PA': 0.045,
        '3B_per_PA': 0.005,
        'HR_per_PA': 0.030,
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