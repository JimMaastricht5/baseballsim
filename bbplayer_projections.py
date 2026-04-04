"""
Baseball statistics preprocessing and data standardization.

This module handles the cleaning, transformation, and aggregation of raw MLB player
statistics downloaded from RotoWire/Baseball-Reference. Creates three types of output files:

1. **Player Projected Files** (for simulation):
   - Career totals: `{seasons} player-projected-stats-pp-Batting.csv`
   - Career totals: `{seasons} player-projected-stats-pp-Pitching.csv`
   - One row per player with age-adjusted projections across all loaded seasons
   - Indexed by player Hashcode

2. **Historical Files** (for year-by-year analysis):
   - Year-by-year: `{seasons} historical-Batting.csv`
   - Year-by-year: `{seasons} historical-Pitching.csv`
   - One row per player per season
   - Indexed by Player_Season_Key (Hashcode_Year)

3. **New Season Files** (empty placeholder for simulation):
   - `{new_season} New-Season-stats-pp-Batting.csv`
   - `{new_season} New-Season-stats-pp-Pitching.csv`
   - Empty template that accumulates simulation data during season

Key Features:
- Handles multi-season data aggregation and de-duplication
- Removes unwanted columns from raw data
- Calculates derived statistics (OBP, SLG, OPS, ERA, WHIP, etc.)
- Supports random league/team/player name generation for testing
- Weighted Average: Give 2025 the most weight (5:4:3).
- Bayesian Shrinkage: Use K values to pull low-AB players toward the league mean (stops the 150-HR bench player).
- Aging Curve: Apply your parabolic formula to the rates.
- Merges salary data from historical records
- Filters players by minimum playing time (AB >= 10, IP >= 5)
- Team name remapping (e.g., OAK → ATH)

Random Data Generation:
- Randomizes team cities, mascots, and player names
- Jiggers stats with normal distribution (±10% with scale=2)
- Creates fictional leagues (ACB, NBL)
- Maintains statistical relationships and distributions

Contact: JimMaastricht5@gmail.com
"""

# data clean up and standardization for stats.  handles random generation if requested
# data imported from https://www.rotowire.com/baseball/stats.php
import pandas as pd
import random
import city_names as city
import bbplayer_projections_forecast_player as player_projector
import hashlib
import salary
import numpy as np
from numpy import ndarray
from pandas.core.frame import DataFrame
from typing import List, Optional
from bblogger import logger


class BaseballStatsPreProcess:
    """
    Preprocessing pipeline for raw MLB player statistics.

    Loads one or more seasons of raw RotoWire/Baseball-Reference CSV files,
    cleans and normalises the data, runs trend-based projections via
    PlayerProjector, and writes three sets of output files:

    - Aggregated files  (``{seasons} player-projected-stats-pp-*.csv``) — one row per
      player with career/projected totals, used by the game simulator.
    - Historical files  (``{seasons} historical-*.csv``) — one row per
      player per season, used by projections and analysis.
    - New-season files  (``{new_season} New-Season-stats-pp-*.csv``) —
      rate stats preserved, counting stats zeroed, ready to start a new season.

    Optionally replaces all real player, team, and league names with randomly
    generated ones (``generate_random_data=True``) for anonymised simulation.
    """

    def __init__(
        self,
        load_seasons: List[int],
        new_season: Optional[int] = None,
        generate_random_data: bool = False,
        load_batter_file: str = "player-stats-Batters.csv",
        load_pitcher_file: str = "player-stats-Pitching.csv",
    ) -> None:
        """
        Load and preprocess baseball statistics for the specified seasons.

        Orchestrates the full pipeline: reads CSV files, merges salary data,
        applies team remapping, calculates defensive WAR, optionally randomises
        data, optionally creates new-season projections, and saves all outputs.

        :param load_seasons: One or more season years to load (e.g. [2023, 2024, 2025]).
        :param new_season: If provided, creates a new-season projection file for
            this year (e.g. 2026). If it equals the last load season, the actual
            partial-season file is used; otherwise stats are derived from the
            aggregated data.
        :param generate_random_data: When True, replaces all player, team, city,
            and league names with randomly generated ones before saving.
        :param load_batter_file: Base filename for raw batter CSV files
            (year prefix added automatically, e.g. ``'player-stats-Batters.csv'``).
        :param load_pitcher_file: Base filename for raw pitcher CSV files.
        """
        # self.create_hash = lambda text: int(hashlib.sha256(text.encode('utf-8')).hexdigest()[:5], 16)
        self.jigger_data = lambda x: x + int(
            np.abs(np.random.normal(loc=x * 0.10, scale=2, size=1))
        )

        self.numeric_bcols = [
            "G",
            "AB",
            "R",
            "H",
            "2B",
            "3B",
            "HR",
            "RBI",
            "SB",
            "CS",
            "BB",
            "SO",
            "SH",
            "SF",
            "BA",
            "GIDP",
            "HBP",
            "Condition",
        ]  # these cols will get added to running season total
        self.numeric_pcols = [
            "G",
            "GS",
            "CG",
            "SHO",
            "IP",
            "AB",
            "H",
            "2B",
            "3B",
            "HR",
            "ER",
            "R",
            "SO",
            "BB",
            "W",
            "L",
            "SV",
            "WP",
            "Total_Outs",
            "Condition",
        ]  # cols will add to running season total
        self.nl = [
            "CHC",
            "CIN",
            "MIL",
            "PIT",
            "STL",
            "ATL",
            "MIA",
            "NYM",
            "PHI",
            "WAS",
            "WSN",
            "COL",
            "LAD",
            "ARI",
            "SDP",
            "SFG",
        ]
        self.al = [
            "ATH",
            "BOS",
            "TEX",
            "NYY",
            "KCR",
            "BAL",
            "CLE",
            "TOR",
            "LAA",
            "CWS",
            "CHW",
            "SEA",
            "MIN",
            "DET",
            "TBR",
            "HOU",
        ]
        self.team_division = {
            "BAL": "East",
            "BOS": "East",
            "NYY": "East",
            "TBR": "East",
            "TOR": "East",
            "CHW": "Central",
            "CWS": "Central",
            "CLE": "Central",
            "DET": "Central",
            "KCR": "Central",
            "MIN": "Central",
            "ATH": "West",
            "HOU": "West",
            "LAA": "West",
            "SEA": "West",
            "TEX": "West",
            "ATL": "East",
            "MIA": "East",
            "NYM": "East",
            "PHI": "East",
            "WAS": "East",
            "WSN": "East",
            "CHC": "Central",
            "CIN": "Central",
            "MIL": "Central",
            "PIT": "Central",
            "STL": "Central",
            "ARI": "West",
            "COL": "West",
            "LAD": "West",
            "SDP": "West",
            "SFG": "West",
        }
        self.digit_pos_map = {
            "1": "P",
            "2": "C",
            "3": "1B",
            "4": "2B",
            "5": "3B",
            "6": "SS",
            "7": "LF",
            "8": "CF",
            "9": "RF",
        }
        # Team remapping dictionary - maps old team names to new team names
        self.team_remapping = {"OAK": "ATH"}
        # # constants for age adjusted performance
        # # key assumptions about year over year performance changes
        # # 1. A young player (21-25) will show significant improvement from year to year
        # #    assuming the peak is at age 29 at an avg OBP of .325, OBP = -0.0008 * (Age - 29)^2 + 0.325
        # # 2. a player in their late 20s (27-29) is typically at their stable peak
        # # 3. a player entering their 30s (30+) will begin to show a slight year-over-year decline.
        # #    assuming the peak is at age 29 at an avg OBP of 0.325, OBP = -0.00059 * (Age - 29)^2 + 0.325
        # # 4. The decline often becomes more rapid after Age 34
        # # Updated constants for the Aging Curve
        # self.young_age_limit = 25  # Significant improvement up to this age
        # self.peak_start_age = 26  # Start of the plateau
        # self.peak_end_age = 30  # End of the plateau (stable peak)
        # self.decline_start_age = 31  # When the parabolic decline kicks in
        # self.coeff_age_improvement = 0.0004  # Reduced from 0.0004: Less optimistic improvement for young players
        # self.coeff_age_decline = -0.0059

        # load seasons
        self.load_seasons = (
            [load_seasons] if not isinstance(load_seasons, list) else load_seasons
        )  # convert to list
        self.new_season = new_season
        self.pitching_data = None
        self.batting_data = None
        self.pitching_data_historical = None
        self.batting_data_historical = None
        self.new_season_pitching_data = None
        self.new_season_batting_data = None
        self.generate_random_data = generate_random_data

        self.df_salary = salary.retrieve_salary(
            "mlb-salaries-2000-24.csv", self.create_hash
        )
        self.get_seasons(load_batter_file, load_pitcher_file)  # get existing data file
        collision = set(self.batting_data.index).intersection(
            set(self.pitching_data.index)
        )
        if collision:
            logger.error(f"Hash Collision Detected: {collision}")
        self.apply_team_remapping()  # apply team name remapping before other processing
        self.calculate_def_war()  # calculate defensive WAR from prior season
        self.generate_random_data = generate_random_data
        if self.generate_random_data:  # generate new data from existing
            self.randomize_data()  # generate random data
        if new_season is not None:
            self.create_new_season_from_existing(load_batter_file, load_pitcher_file)
        self.save_data()
        return

    def create_hash(self, name, role):
        # This ensures "Will Smith_Hitter" and "Will Smith_Pitcher"
        # generate two completely unique hex/integer values
        combined_string = f"{name}_{role}"
        hex_hash = hashlib.md5(combined_string.encode()).hexdigest()
        return int(hex_hash, 16)

    def save_data(self) -> None:
        """
        Write all processed DataFrames to CSV files.

        Saves up to four file pairs depending on what was generated:

        - Aggregated pitching/batting files (always saved).
        - Historical pitching/batting files (saved when historical data exists).
        - New-season pitching/batting files (saved when ``new_season`` was set).

        File names are prefixed with the joined load-season years
        (e.g. ``'2023 2024 2025 player-projected-stats-pp-Batting.csv'``).
        Random-data runs use ``'random-'`` variants of each name.
        """
        # Aggregated files now include 'aggr' in name
        f_pname_aggr = (
            "random-player-projected-stats-pp-Pitching.csv"
            if self.generate_random_data
            else "player-projected-stats-pp-Pitching.csv"
        )
        f_bname_aggr = (
            "random-player-projected-stats-pp-Batting.csv"
            if self.generate_random_data
            else "player-projected-stats-pp-Batting.csv"
        )
        # New season files do NOT include 'aggr' since they are not aggregated
        f_pname_new = (
            "random-stats-pp-Pitching.csv"
            if self.generate_random_data
            else "stats-pp-Pitching.csv"
        )
        f_bname_new = (
            "random-stats-pp-Batting.csv"
            if self.generate_random_data
            else "stats-pp-Batting.csv"
        )
        seasons_str = " ".join(str(season) for season in self.load_seasons)

        # Save aggregated data (with 'aggr' in filename - for bbstats.py)
        self.pitching_data.to_csv(
            f"{seasons_str} {f_pname_aggr}", index=True, header=True
        )
        self.batting_data.to_csv(
            f"{seasons_str} {f_bname_aggr}", index=True, header=True
        )
        print(
            f"Saved aggregated files: {seasons_str} {f_pname_aggr} and {f_bname_aggr}"
        )

        # Save historical year-by-year data (new)
        if self.pitching_data_historical is not None:
            f_hist_pname = (
                "random-historical-Pitching.csv"
                if self.generate_random_data
                else "historical-Pitching.csv"
            )
            self.pitching_data_historical.to_csv(
                f"{seasons_str} {f_hist_pname}", index=True, header=True
            )
            print(f"Saved historical pitching data: {seasons_str} {f_hist_pname}")

        if self.batting_data_historical is not None:
            f_hist_bname = (
                "random-historical-Batting.csv"
                if self.generate_random_data
                else "historical-Batting.csv"
            )
            self.batting_data_historical.to_csv(
                f"{seasons_str} {f_hist_bname}", index=True, header=True
            )
            print(f"Saved historical batting data: {seasons_str} {f_hist_bname}")

        # Save new season data (no 'aggr' prefix - this is single season data, not aggregated)
        if self.new_season is not None:
            self.new_season_pitching_data.to_csv(
                f"{self.new_season} New-Season-{f_pname_new}", index=True, header=True
            )
            self.new_season_batting_data.to_csv(
                f"{self.new_season} New-Season-{f_bname_new}", index=True, header=True
            )
        return

    @staticmethod
    def group_col_to_list(
        df: DataFrame, key_col: str, col: str, new_col: str
    ) -> DataFrame:
        """
        Aggregate unique values of a column into a list, grouped by a key column.

        Iterates the DataFrame and builds a set of unique values in ``col`` for
        each unique value of ``key_col``. Comma-separated strings (e.g. position
        strings like ``"P,SS,2B"``) are split into individual tokens before
        collecting. The result is stored as a Python list in ``new_col``.

        Used to combine team and position data for players who appeared on
        multiple teams in a season (mid-season trades).

        :param df: DataFrame to operate on.
        :param key_col: Column whose values act as the grouping key.
        :param col: Column whose unique values are collected into a list.
        :param new_col: Name of the new column to write the aggregated lists into.
        :return: The original DataFrame with ``new_col`` added.
        """
        groups = {}
        for i, row in df.iterrows():
            key = row[key_col]
            val = row[col]
            if key not in groups:
                groups[key] = set()

            # Handle both string and list values
            if isinstance(val, list):
                # If val is already a list, add each non-empty item
                for item in val:
                    if item and str(item).strip():
                        # Split comma-separated values to handle position strings like "P,SS,2B"
                        if "," in str(item):
                            for subitem in str(item).split(","):
                                if subitem.strip():
                                    groups[key].add(subitem.strip())
                        else:
                            groups[key].add(item)
            elif val and isinstance(val, str) and val.strip():
                # If val is a non-empty string, split on comma for positions
                if "," in val:
                    for subitem in val.split(","):
                        if subitem.strip():
                            groups[key].add(subitem.strip())
                else:
                    groups[key].add(val)
            elif val and not isinstance(val, str):
                # Handle other types (int, float, etc.)
                groups[key].add(val)

        df[new_col] = df[key_col].map(
            groups
        )  # Create a new column to store grouped unique values
        df[new_col] = df[new_col].apply(
            list
        )  # Convert sets to lists for easier handling in DataFrame
        return df

    @staticmethod
    def find_duplicate_rows(df: DataFrame, column_names: str) -> DataFrame:
        """
        Return all rows that have duplicate values in the specified column(s).

        Drops NaN values from the target column(s) before checking, and uses
        ``keep=False`` so that every instance of a duplicated value is included
        in the result (not just the second or later occurrence).

        :param df: DataFrame to inspect.
        :param column_names: Column name (or list of column names) to check for
            duplicate values.
        :return: Subset of ``df`` containing only the duplicated rows.
        """
        filtered_df = df[column_names].dropna()
        duplicates = filtered_df.duplicated(keep=False)  # keep both rows
        return df[duplicates]

    @staticmethod
    def remove_non_numeric(text):
        """
        Strip all non-digit characters from a string.

        :param text: Input string (e.g. a raw position code like ``"1/6"``).
        :return: String containing only the digit characters from ``text``.
        """
        return "".join(char for char in text if char.isdigit())

    def translate_pos(self, digit_string):
        """
        Convert a string of numeric position codes to comma-separated abbreviations.

        Maps each digit character through ``self.digit_pos_map``
        (e.g. ``'1'`` → ``'P'``, ``'6'`` → ``'SS'``). Unrecognised characters
        are passed through unchanged. Trailing comma is stripped.

        :param digit_string: String of position digits (e.g. ``"163"``).
        :return: Comma-separated position abbreviation string (e.g. ``"P,SS,1B"``).
        """
        return "".join(
            self.digit_pos_map.get(digit, digit) + "," for digit in digit_string
        ).rstrip(",")

    def calculate_league_averages(
        self, historical_df: pd.DataFrame, is_pitching: bool = False
    ) -> dict:
        """
        Calculates weighted league average rates to use as the 'Mean' for Bayesian regression.

        Args:
            historical_df: Historical data for all players
            is_pitching: True for pitchers, False for batters

        Returns:
            dict: League average rates (per PA for batters, per IP for pitchers)
        """
        if is_pitching:
            # PITCHING GATE: Use pitchers with at least 20 IP for the baseline
            qualified = historical_df[historical_df["IP"] >= 20].copy()

            # If the database is small, fall back to everyone to avoid division by zero
            if qualified.empty:
                qualified = historical_df

            # Use ONLY the most recent season for league averages to reflect current MLB environment
            # This prevents older seasons with different run environments from pulling down projections
            most_recent_season = historical_df["Season"].max()
            qualified_recent = qualified[
                qualified["Season"] == most_recent_season
            ].copy()

            total_ip = max(1, qualified_recent["IP"].sum())
            total_g = max(1, qualified_recent["G"].sum())
            total_pa = (
                max(1, qualified_recent["PA"].sum())
                if "PA" in qualified_recent.columns
                else None
            )

            lg_avgs = {
                "H_per_IP": qualified_recent["H"].sum() / total_ip,
                "BB_per_IP": qualified_recent["BB"].sum() / total_ip,
                "SO_per_IP": qualified_recent["SO"].sum() / total_ip,
                "HR_per_IP": qualified_recent["HR"].sum() / total_ip,
                # Store ERA (9-inning format) so projector's /9 division works correctly
                "ER_per_IP": (qualified_recent["ER"].sum() / total_ip) * 9,
                "W_rate": qualified_recent["W"].sum() / total_g,
                "L_rate": qualified_recent["L"].sum() / total_g,
                "SV_rate": qualified_recent["SV"].sum() / total_g,
                # PA per IP for projecting PA volume
                "PA_per_IP": total_pa / total_ip if total_pa else 4.3,
            }
            # Add PA-based rates used by projector OBP anchor and Bayesian regression.
            # Without these, the projector falls back to 0.240 for BB_per_PA,
            # which inflates all pitcher walk rates by ~2x.
            if total_pa:
                lg_avgs["H_per_BIP"] = (
                    qualified_recent["H"].sum()
                    / (
                        qualified_recent["PA"]
                        - qualified_recent["SO"]
                        - qualified_recent["BB"]
                    )
                    .clip(lower=1)
                    .sum()
                )
                lg_avgs["H_per_PA"] = qualified_recent["H"].sum() / total_pa
                lg_avgs["BB_per_PA"] = qualified_recent["BB"].sum() / total_pa
                lg_avgs["SO_per_PA"] = qualified_recent["SO"].sum() / total_pa
                lg_avgs["ER_per_PA"] = qualified_recent["ER"].sum() / total_pa
            return lg_avgs
        else:
            # BATTING GATE: Use hitters with at least 100 AB for the baseline
            qualified = historical_df[historical_df["AB"] >= 100].copy()

            if qualified.empty:
                qualified = historical_df

            # Use ONLY the most recent season for league averages to reflect current MLB environment
            # This prevents older seasons with different run environments from pulling down projections
            most_recent_season = historical_df["Season"].max()
            qualified_recent = qualified[
                qualified["Season"] == most_recent_season
            ].copy()

            # Denominator: Total Plate Appearances (from most recent season only)
            total_pa = max(
                1,
                qualified_recent["AB"].sum()
                + qualified_recent["BB"].sum()
                + qualified_recent.get("HBP", 0).sum()
                + qualified_recent.get("SF", 0).sum(),
            )
            total_ab = max(1, qualified_recent["AB"].sum())
            total_h = max(
                1, qualified_recent["H"].sum()
            )  # Use Hits as the denominator for 2b, 3b, and HR
            return {
                "H_per_PA": qualified_recent["H"].sum() / total_pa,
                # H_per_AB is the true batting average baseline used by Bayesian regression
                # when projecting H/AB (vol_col='AB'). Without it, regression falls back to
                # H_per_PA (~0.225) instead of the correct H/AB (~0.248), slightly deflating
                # batting average projections for low-sample batters.
                "H_per_AB": qualified_recent["H"].sum() / total_ab,
                # HR_per_AB is the true HR rate baseline used when projecting HR/AB directly
                # (instead of HR/H) to target the correct 2025 HR/AB rate and fix under-projection
                "HR_per_AB": qualified_recent["HR"].sum() / total_ab,
                # 'HR_per_PA': qualified_recent['HR'].sum() / total_pa,
                # '2B_per_PA': qualified_recent['2B'].sum() / total_pa,
                # '3B_per_PA': qualified_recent['3B'].sum() / total_pa,
                "BB_per_PA": qualified_recent["BB"].sum() / total_pa,
                "SO_per_PA": qualified_recent["SO"].sum() / total_pa,
                "R_per_PA": qualified_recent["R"].sum() / total_pa,
                "RBI_per_PA": qualified_recent["RBI"].sum() / total_pa,
                # Calculate these per Hit (H) to match the Projector's logic
                "2B_per_H": qualified_recent["2B"].sum() / total_h,
                "3B_per_H": qualified_recent["3B"].sum() / total_h,
                "HR_per_H": qualified_recent["HR"].sum() / total_h,
            }

    def de_dup_df(
        self,
        df: DataFrame,
        key_name: str,
        dup_column_names: str,
        stats_cols_to_sum: List[str],
        drop_dups: bool = False,
    ) -> DataFrame:
        """
        Collapse duplicate rows by summing stat columns, then optionally drop extras.

        For each set of rows sharing a duplicate value in ``dup_column_names``,
        writes the column-wise sum of ``stats_cols_to_sum`` back into every
        duplicate row. If ``drop_dups`` is True, only the last row for each
        duplicate key is kept (useful for mid-season trade aggregation).

        :param df: DataFrame to de-duplicate (modified in place).
        :param key_name: Column used to identify which rows belong together
            (e.g. ``'Hashcode'`` or ``'Player_Season_Key'``).
        :param dup_column_names: Column name(s) passed to ``find_duplicate_rows``
            to detect which rows are duplicates.
        :param stats_cols_to_sum: List of numeric column names whose values
            should be summed across duplicate rows.
        :param drop_dups: If True, drop all but the last occurrence of each
            duplicate key after summing.
        :return: De-duplicated (and optionally reduced) DataFrame.
        """
        dup_hashcodes = self.find_duplicate_rows(df=df, column_names=dup_column_names)
        for dfrow_key in dup_hashcodes[key_name].unique():
            df_rows = df.loc[df[key_name] == dfrow_key]
            for dfcol_name in stats_cols_to_sum:
                df.loc[df[key_name] == dfrow_key, dfcol_name] = df_rows[
                    dfcol_name
                ].sum()
        if drop_dups:
            # Use key_name for deduplication, not hardcoded 'Hashcode'
            df = df.drop_duplicates(subset=key_name, keep="last")
        return df

    def is_active_candidate(self, years_list, age, career_war, most_recent_season):
        """
        Determine whether a player should be retained in the simulation roster.

        A player is kept when any of these conditions hold:
        - They played in the most recent loaded season (``last_active == most_recent_season``).
        - They missed exactly one season AND are either under 33 years old or
          have career WAR > 8.0 (established star recovering from injury).

        Players missing two or more consecutive seasons are treated as retired
        and excluded.

        :param years_list: List of season years the player appeared in.
        :param age: Player's age as of the most recent season row.
        :param career_war: Player's cumulative WAR across all seasons loaded.
        :param most_recent_season: The latest season year in the loaded dataset.
        :return: True if the player should be included in the simulation, False otherwise.
        """
        last_active = max(years_list) if years_list else 0

        # Played last year? Keep them.
        if last_active == most_recent_season:
            return True

        # Missed exactly one year (the "Injury Gap")
        if last_active == (most_recent_season - 1):
            # Keep if they are young (< 33) OR if they are an established star (WAR > 8)
            if age < 33 or career_war > 8.0:
                return True
        # Missed 2+ years? They are effectively retired for sim purposes.
        return False

    def get_pitching_seasons(self, pitcher_file: str, load_seasons: List[int]) -> tuple:
        """
        Load, clean, and project pitcher data for the specified seasons.

        Reads one CSV file per season, concatenates them, drops irrelevant
        columns (FIP, HR9, etc.), creates a SHA-256 Hashcode from the player
        name, merges salary data, and filters out multi-team summary rows.

        Produces two outputs:
        - **Historical DataFrame** (indexed by ``Player_Season_Key``): one row
          per player per season, de-duplicated across mid-season trades.
        - **Aggregated DataFrame** (indexed by ``Hashcode``): trend-projected
          stats for the upcoming season via ``PlayerProjector``, filtered to
          active candidates only (played recently or star with injury gap).

        Derived columns added to aggregated data: ``AB``, ``2B``, ``3B``,
        ``HBP``, ``OBP``, ``Total_OB``, ``Total_Outs``, ``AVG_faced``,
        ``Game_Fatigue_Factor``, ``Condition``, ``Status``, ``BS``, ``HLD``,
        ``Injury_Rate_Adj``, ``Injury_Perf_Adj``, ``Streak_Adjustment``.

        .. caution::
            WAR and salary columns are summed across seasons during the merge;
            interpret career totals accordingly.

        :param pitcher_file: Base filename for raw pitcher CSVs
            (year prefix added automatically).
        :param load_seasons: List of season years to load and project from.
        :return: Tuple of ``(aggregated_df, historical_df)``.
        """
        # Returns tuple of (aggregated_df, historical_df)
        # caution war and salary cols will get aggregated across multiple seasons
        pitching_data = None
        stats_pcols_sum = [
            "G",
            "PA",
            "GS",
            "CG",
            "SHO",
            "IP",
            "H",
            "ER",
            "SO",
            "BB",
            "HR",
            "W",
            "L",
            "SV",
            "HBP",
            "BK",
            "WP",
        ]
        for season in load_seasons:
            df = pd.read_csv(str(season) + f" {pitcher_file}")
            df["Season"] = season  # Add season before concatenating
            pitching_data = pd.concat([pitching_data, df], axis=0)

        # drop unwanted cols
        pitching_data.drop(
            [
                "Rk",
                "Lg",
                "W-L%",
                "GF",
                "IBB",
                "ERA+",
                "FIP",
                "H9",
                "BB9",
                "SO9",
                "SO/BB",
                "HR9",
                "Awards",
                "Player-additional",
                "BF",
            ],
            inplace=True,
            axis=1,
        )
        pitching_data = pitching_data[
            ~((pitching_data["IP"] < 10) & (pitching_data["G"] < 5))
        ]  # remove pos players pitching
        pitching_data["Player"] = (
            pitching_data["Player"].str.replace("*", "").str.replace("#", "")
        )
        pitching_data["Hashcode"] = pitching_data["Player"].apply(
            lambda x: self.create_hash(x, "Pitcher")
        )

        # Filter salary to only Pitchers before merging
        pitcher_salaries = self.df_salary[self.df_salary["Role"] == "Pitcher"]
        pitching_data = pd.merge(
            pitching_data, pitcher_salaries, on="Hashcode", how="left"
        )
        pitching_data = salary.fill_nan_salary(
            pitching_data, "Salary"
        )  # set league min for missing data
        # pitching_data = salary.fill_nan_salary(pitching_data, 'MLS', 0)  # set min for missing data
        pitching_data["Team"] = pitching_data["Team"].apply(
            lambda x: x if x in self.nl + self.al else ""
        )
        # players with multiple teams have a 2TM or 3TM line that is the total of all stats.  Drop rows since we total
        pitching_data = pitching_data[
            pitching_data["Team"] != ""
        ]  # drop rows without a formal team name
        pitching_data["League"] = pitching_data["Team"].apply(
            lambda x: "NL" if x in self.nl else ("AL" if x in self.al else "")
        )
        pitching_data["Division"] = (
            pitching_data["Team"].map(self.team_division).fillna("")
        )
        # Create Player_Season_Key BEFORE de-duplication
        pitching_data["Player_Season_Key"] = (
            pitching_data["Hashcode"].astype(str)
            + "_"
            + pitching_data["Season"].astype(str)
        )
        outs = (pitching_data["IP"].astype(int) * 3) + np.round(
            (pitching_data["IP"] % 1) * 10
        )
        pitching_data["PA"] = (
            outs
            + pitching_data["H"]
            + pitching_data["BB"]
            + pitching_data.get("HBP", 0)
        )

        # *** Create HISTORICAL data (year-by-year) - one row per player per season ***
        historical_data = pitching_data.copy()
        historical_data = self.group_col_to_list(
            df=historical_data, key_col="Player_Season_Key", col="Team", new_col="Teams"
        )
        historical_data = self.group_col_to_list(
            df=historical_data,
            key_col="Player_Season_Key",
            col="League",
            new_col="Leagues",
        )
        # For historical, only de-dup within same season (mid-season trades)
        historical_data = self.de_dup_df(
            df=historical_data,
            key_name="Player_Season_Key",
            dup_column_names="Player_Season_Key",
            stats_cols_to_sum=stats_pcols_sum,
            drop_dups=True,
        )
        historical_data = historical_data.set_index("Player_Season_Key")

        # *** Create AGGREGATED data (trend-based projections) - one row per player ***
        # Apply trend-based projection to 2026 instead of simple summation
        stats_to_project = [
            "G",
            "GS",
            "CG",
            "SHO",
            "IP",
            "H",
            "ER",
            "SO",
            "BB",
            "HR",
            "W",
            "L",
            "SV",
            "HBP",
            "BK",
            "WP",
        ]
        league_averages = self.calculate_league_averages(
            historical_df=historical_data, is_pitching=True
        )
        projector = player_projector.PlayerProjector(league_averages)
        pitching_data = projector.calculate_projected_stats(
            history=historical_data, stats=stats_to_project, is_p=True
        )
        pitching_data = pitching_data.set_index("Hashcode")
        most_recent_season = max(load_seasons)
        pitching_data["Should_Retain"] = pitching_data.apply(
            lambda row: self.is_active_candidate(
                row["Years_Included"],
                row["Age"],
                row.get("WAR", 0),  # Use actual WAR if available
                most_recent_season,
            ),
            axis=1,
        )
        players_before_filter = len(pitching_data)
        pitching_data = pitching_data[pitching_data["Should_Retain"]]
        pitching_data = pitching_data.drop("Should_Retain", axis=1)
        players_after_filter = len(pitching_data)
        print(
            f"Pitchers: Filtered {players_before_filter - players_after_filter} players not in {most_recent_season} season (kept {players_after_filter})"
        )

        # Apply random data jigger if needed (to both datasets)
        if self.generate_random_data:
            for stats_col in stats_pcols_sum:
                pitching_data[stats_col] = pitching_data[stats_col].apply(
                    self.jigger_data
                )
                historical_data[stats_col] = historical_data[stats_col].apply(
                    self.jigger_data
                )

        # Calculate derived stats for AGGREGATED data
        # 1. Convert .1/.2 format to total outs
        outs = (pitching_data["IP"].astype(int) * 3) + np.round(
            (pitching_data["IP"] % 1) * 10
        )
        pitching_data["AB"] = outs + pitching_data["H"]
        pitching_data["2B"] = 0
        pitching_data["3B"] = 0
        pitching_data["HBP"] = 0
        pitching_data["Season"] = str(
            max(load_seasons) + 1
        )  # Projected year (e.g., 2026)
        pitching_data["OBP"] = pitching_data["WHIP"] / (
            3 + pitching_data["WHIP"]
        )  # bat reached / number faced
        pitching_data["Total_OB"] = (
            pitching_data["H"] + pitching_data["BB"]
        )  # + pitching_data['HBP']
        pitching_data["Total_Outs"] = pitching_data["IP"] * 3  # 3 outs per inning
        pitching_data = pitching_data[
            pitching_data["IP"] >= 1
        ]  # drop pitchers without any meaningful innings (reduced from 5 to 1)
        pitching_data["AVG_faced"] = (
            pitching_data["Total_OB"] + pitching_data["Total_Outs"]
        ) / pitching_data.G
        pitching_data["Game_Fatigue_Factor"] = 0
        pitching_data["Condition"] = 100
        pitching_data["Status"] = "Active"  # DL or active
        pitching_data["Injured Days"] = 0  # days to spend in IL
        pitching_data["BS"] = 0
        pitching_data["HLD"] = 0
        pitching_data["E"] = 0
        pitching_data["Age_Adjustment"] = 0.0  # adjust performance based on age change
        if "Injury_Rate_Adj" not in pitching_data.columns:
            pitching_data["Injury_Rate_Adj"] = 0
            pitching_data["Injury_Perf_Adj"] = 0
        if "Streak_Adjustment" not in pitching_data.columns:
            pitching_data["Streak_Adjustment"] = 0.0  # Always 0 for aggregated data

        if "Injury_Rate_Adj" not in historical_data.columns:
            historical_data["Injury_Rate_Adj"] = 0
            historical_data["Injury_Perf_Adj"] = 0
        if "Streak_Adjustment" not in historical_data.columns:
            historical_data["Streak_Adjustment"] = 0.0  # Always 0 for historical data
        return pitching_data, historical_data

    def get_batting_seasons(self, batter_file: str, load_seasons: List[int]) -> tuple:
        """
        Load, clean, and project batter data for the specified seasons.

        Reads one CSV file per season, concatenates them, drops irrelevant
        columns (OPS+, rOBA, TB, etc.), creates a SHA-256 Hashcode from the
        player name, merges salary data, translates numeric position codes, and
        filters out multi-team summary rows.

        Produces two outputs:
        - **Historical DataFrame** (indexed by ``Player_Season_Key``): one row
          per player per season, de-duplicated across mid-season trades.
        - **Aggregated DataFrame** (indexed by ``Hashcode``): trend-projected
          stats for the upcoming season via ``PlayerProjector``, filtered to
          active candidates only.

        Derived columns added to aggregated data: ``OBP``, ``SLG``, ``OPS``,
        ``Total_OB``, ``Total_Outs``, ``E``, ``Game_Fatigue_Factor``,
        ``Condition``, ``Status``, ``Injury_Rate_Adj``, ``Injury_Perf_Adj``,
        ``Streak_Adjustment``.

        Same columns are also calculated for the historical DataFrame.

        .. caution::
            WAR and salary columns are summed across seasons during the merge.

        :param batter_file: Base filename for raw batter CSVs
            (year prefix added automatically).
        :param load_seasons: List of season years to load and project from.
        :return: Tuple of ``(aggregated_df, historical_df)``.
        """
        # Returns tuple of (aggregated_df, historical_df)
        batting_data = None
        stats_bcols_sum = [
            "G",
            "PA",
            "AB",
            "R",
            "H",
            "2B",
            "3B",
            "HR",
            "RBI",
            "SB",
            "CS",
            "BB",
            "SO",
            "SH",
            "SF",
            "HBP",
            "GIDP",
        ]
        for season in load_seasons:
            df = pd.read_csv(str(season) + f" {batter_file}")
            df["Season"] = season  # Add season before concatenating
            batting_data = pd.concat([batting_data, df], axis=0)

        # drop unwanted cols
        batting_data.drop(
            [
                "Rk",
                "Lg",
                "OPS+",
                "rOBA",
                "Rbat+",
                "TB",
                "IBB",
                "Awards",
                "Player-additional",
            ],
            inplace=True,
            axis=1,
        )
        batting_data["Player"] = (
            batting_data["Player"].str.replace("#", "").str.replace("*", "")
        )
        batting_data["Hashcode"] = batting_data["Player"].apply(
            lambda x: self.create_hash(x, "Hitter")
        )

        # Filter salary to only Hitters before merging
        hitter_salaries = self.df_salary[self.df_salary["Role"] == "Hitter"]
        batting_data = pd.merge(
            batting_data, hitter_salaries, on="Hashcode", how="left"
        )
        batting_data = salary.fill_nan_salary(
            batting_data, "Salary"
        )  # set league min for missing data
        # batting_data = salary.fill_nan_salary(batting_data, 'MLS', 0)  # set min for missing data
        batting_data["Pos"] = (
            batting_data["Pos"].apply(self.remove_non_numeric).apply(self.translate_pos)
        )
        # DON'T group by Hashcode yet - we need year-by-year data for historical file
        batting_data["Team"] = batting_data["Team"].apply(
            lambda x: x if x in self.nl + self.al else ""
        )
        batting_data["League"] = batting_data["Team"].apply(
            lambda x: "NL" if x in self.nl else ("AL" if x in self.al else "")
        )
        batting_data["Division"] = (
            batting_data["Team"].map(self.team_division).fillna("")
        )
        # players with multiple teams have a 2TM or 3TM line that is the total of all stats.  Drop rows since we total
        batting_data = batting_data[
            batting_data["Team"] != ""
        ]  # drop rows without a formal team name
        # Create Player_Season_Key BEFORE de-duplication
        batting_data["Player_Season_Key"] = (
            batting_data["Hashcode"].astype(str)
            + "_"
            + batting_data["Season"].astype(str)
        )
        batting_data["PA"] = (
            batting_data["AB"]
            + batting_data["BB"]
            + batting_data["HBP"]
            + batting_data["SF"]
        )

        # *** Create HISTORICAL data (year-by-year) - one row per player per season ***
        # Must do this BEFORE grouping by Hashcode to preserve year-by-year data
        historical_data = batting_data.copy()
        historical_data = self.group_col_to_list(
            df=historical_data, key_col="Player_Season_Key", col="Pos", new_col="Pos"
        )
        historical_data = self.group_col_to_list(
            df=historical_data, key_col="Player_Season_Key", col="Team", new_col="Teams"
        )
        historical_data = self.group_col_to_list(
            df=historical_data,
            key_col="Player_Season_Key",
            col="League",
            new_col="Leagues",
        )
        # For historical, only de-dup within same season (mid-season trades)
        historical_data = self.de_dup_df(
            df=historical_data,
            key_name="Player_Season_Key",
            dup_column_names="Player_Season_Key",
            stats_cols_to_sum=stats_bcols_sum,
            drop_dups=True,
        )
        historical_data = historical_data.set_index("Player_Season_Key")

        # *** Create AGGREGATED data (trend-based projections) - one row per player ***
        # Apply trend-based projection to 2026 instead of simple summation
        stats_to_project = [
            "G",
            "PA",
            "AB",
            "R",
            "H",
            "2B",
            "3B",
            "HR",
            "RBI",
            "SB",
            "CS",
            "BB",
            "SO",
            "SH",
            "SF",
            "HBP",
            "GIDP",
        ]
        league_averages = self.calculate_league_averages(
            historical_data, is_pitching=False
        )
        projector = player_projector.PlayerProjector(league_averages=league_averages)
        batting_data = projector.calculate_projected_stats(
            history=historical_data, stats=stats_to_project, is_p=False
        )

        most_recent_season = max(load_seasons)
        # Apply the probability logic instead of the hard 'In_Recent_Season' check
        batting_data["Should_Retain"] = batting_data.apply(
            lambda row: self.is_active_candidate(
                row["Years_Included"],
                row["Age"],
                row.get("WAR", 0),  # Use actual WAR if available
                most_recent_season,
            ),
            axis=1,
        )

        players_before = len(batting_data)
        batting_data = batting_data[batting_data["Should_Retain"]]
        batting_data = batting_data.drop("Should_Retain", axis=1)
        print(
            f"Batters: Retained {len(batting_data)} players (Filtered {players_before - len(batting_data)} retired/inactive)"
        )
        batting_data = batting_data.set_index("Hashcode")

        # Apply random data jigger if needed (to both datasets)
        if self.generate_random_data:
            for stats_col in stats_bcols_sum:
                batting_data[stats_col] = batting_data[stats_col].apply(
                    self.jigger_data
                )
                historical_data[stats_col] = historical_data[stats_col].apply(
                    self.jigger_data
                )

        # Calculate derived stats for AGGREGATED data
        batting_data["Season"] = str(
            max(load_seasons) + 1
        )  # Projected year (e.g., 2026)
        batting_data["OBP"] = self.trunc_col(
            np.nan_to_num(
                np.divide(
                    batting_data["H"] + batting_data["BB"] + batting_data["HBP"],
                    batting_data["AB"]
                    + batting_data["BB"]
                    + batting_data["HBP"]
                    + batting_data.get("SF", 0),
                ),
                nan=0.0,
                posinf=0.0,
            ),
            3,
        )

        batting_data["SLG"] = self.trunc_col(
            np.nan_to_num(
                np.divide(
                    (
                        batting_data["H"]
                        - batting_data["2B"]
                        - batting_data["3B"]
                        - batting_data["HR"]
                    )
                    + batting_data["2B"] * 2
                    + batting_data["3B"] * 3
                    + batting_data["HR"] * 4,
                    batting_data["AB"],
                ),
                nan=0.0,
                posinf=0.0,
            ),
            3,
        )
        batting_data["OPS"] = self.trunc_col(
            np.nan_to_num(
                batting_data["OBP"] + batting_data["SLG"], nan=0.0, posinf=0.0
            ),
            3,
        )
        batting_data["Total_OB"] = (
            batting_data["H"] + batting_data["BB"] + batting_data["HBP"]
        )
        batting_data["Total_Outs"] = batting_data["AB"] - batting_data["H"]
        batting_data = batting_data[
            batting_data["AB"] >= 1
        ]  # drop players without enough AB
        batting_data["E"] = 0
        batting_data["Game_Fatigue_Factor"] = 0
        batting_data["Condition"] = 100
        batting_data["Status"] = "Active"  # DL or active
        batting_data["Injured Days"] = 0
        batting_data["Age_Adjustment"] = 0.0  # adjust performance based on age change
        if "Injury_Rate_Adj" not in batting_data.columns:
            batting_data["Injury_Rate_Adj"] = 0
            batting_data["Injury_Perf_Adj"] = 0
        if "Streak_Adjustment" not in batting_data.columns:
            batting_data["Streak_Adjustment"] = 0.0  # Always 0 for aggregated data

        # Calculate derived stats for HISTORICAL data
        # Season is already set per row from the loop
        historical_data["OBP"] = self.trunc_col(
            np.nan_to_num(
                np.divide(
                    historical_data["H"]
                    + historical_data["BB"]
                    + historical_data["HBP"],
                    historical_data["AB"]
                    + historical_data["BB"]
                    + historical_data["HBP"],
                ),
                nan=0.0,
                posinf=0.0,
            ),
            3,
        )
        historical_data["SLG"] = self.trunc_col(
            np.nan_to_num(
                np.divide(
                    (
                        historical_data["H"]
                        - historical_data["2B"]
                        - historical_data["3B"]
                        - historical_data["HR"]
                    )
                    + historical_data["2B"] * 2
                    + historical_data["3B"] * 3
                    + historical_data["HR"] * 4,
                    historical_data["AB"],
                ),
                nan=0.0,
                posinf=0.0,
            ),
            3,
        )
        historical_data["OPS"] = self.trunc_col(
            np.nan_to_num(
                historical_data["OBP"] + historical_data["SLG"], nan=0.0, posinf=0.0
            ),
            3,
        )
        historical_data["Total_OB"] = (
            historical_data["H"] + historical_data["BB"] + historical_data["HBP"]
        )
        historical_data["Total_Outs"] = historical_data["AB"] - historical_data["H"]
        historical_data = historical_data[historical_data["AB"] >= 10]
        historical_data["E"] = 0
        historical_data["Game_Fatigue_Factor"] = 0
        historical_data["Condition"] = 100
        historical_data["Status"] = "Active"
        historical_data["Injured Days"] = 0
        historical_data["Age_Adjustment"] = 0.0
        if "Injury_Rate_Adj" not in historical_data.columns:
            historical_data["Injury_Rate_Adj"] = 0
            historical_data["Injury_Perf_Adj"] = 0
        if "Streak_Adjustment" not in historical_data.columns:
            historical_data["Streak_Adjustment"] = 0.0  # Always 0 for historical data

        return batting_data, historical_data

    def get_seasons(self, batter_file: str, pitcher_file: str) -> None:
        """
        Load and preprocess all pitching and batting data for the configured seasons.

        Delegates to ``get_pitching_seasons`` and ``get_batting_seasons``, storing
        the results in ``self.pitching_data``, ``self.pitching_data_historical``,
        ``self.batting_data``, and ``self.batting_data_historical``.

        :param batter_file: Base filename for raw batter CSV files.
        :param pitcher_file: Base filename for raw pitcher CSV files.
        """
        self.pitching_data, self.pitching_data_historical = self.get_pitching_seasons(
            pitcher_file, self.load_seasons
        )
        self.batting_data, self.batting_data_historical = self.get_batting_seasons(
            batter_file, self.load_seasons
        )
        return

    def apply_team_remapping(self) -> None:
        """
        Apply team name remapping based on self.team_remapping dictionary.
        This remaps old team names to new team names in both pitching and batting data.
        """
        if not self.team_remapping:
            return  # No remapping needed if dictionary is empty

        remapped_teams = []

        # Apply remapping to pitching data (aggregated)
        for old_team, new_team in self.team_remapping.items():
            if old_team in self.pitching_data["Team"].values:
                self.pitching_data["Team"] = self.pitching_data["Team"].replace(
                    old_team, new_team
                )
                remapped_teams.append(f"Pitching: {old_team} → {new_team}")

        # Apply remapping to batting data (aggregated)
        for old_team, new_team in self.team_remapping.items():
            if old_team in self.batting_data["Team"].values:
                self.batting_data["Team"] = self.batting_data["Team"].replace(
                    old_team, new_team
                )
                if f"Pitching: {old_team} → {new_team}" not in remapped_teams:
                    remapped_teams.append(f"Batting: {old_team} → {new_team}")

        # Apply remapping to historical data as well
        if self.pitching_data_historical is not None:
            for old_team, new_team in self.team_remapping.items():
                if old_team in self.pitching_data_historical["Team"].values:
                    self.pitching_data_historical["Team"] = (
                        self.pitching_data_historical["Team"].replace(
                            old_team, new_team
                        )
                    )

        if self.batting_data_historical is not None:
            for old_team, new_team in self.team_remapping.items():
                if old_team in self.batting_data_historical["Team"].values:
                    self.batting_data_historical["Team"] = self.batting_data_historical[
                        "Team"
                    ].replace(old_team, new_team)

        # Log the remappings that were applied
        if remapped_teams:
            print(f"Applied team remappings: {', '.join(remapped_teams)}")

        return

    def calculate_def_war(self) -> None:
        """
        Calculate Def_WAR (defensive/baserunning value) for both Hitters and Pitchers.
        Def_WAR = Real_WAR - Calculated_Sim_WAR.
        Ensures unique joins via Hashcode to prevent 'Will Smith' mashups.
        """
        if not self.load_seasons:
            print("No seasons loaded, skipping Def_WAR calculation")
            return

        prior_season = max(self.load_seasons)
        print(f"Calculating Def_WAR from {prior_season} season data...")

        # === PITCHERS ===
        if self.pitching_data_historical is not None:
            prior_p = self.pitching_data_historical[
                self.pitching_data_historical["Season"] == prior_season
            ].copy()
            prior_p = prior_p[prior_p["IP"] >= 5].copy()

            if not prior_p.empty:
                prior_p["FIP"] = (
                    (13 * prior_p["HR"] + 3 * prior_p["BB"] - 2 * prior_p["SO"])
                    / prior_p["IP"]
                ) + 3.10
                league_fip = prior_p["FIP"].mean()
                replacement_fip = league_fip + 1.0
                prior_p["Calculated_Sim_WAR"] = (
                    ((replacement_fip - prior_p["FIP"]) / 9.0) * prior_p["IP"] / 10.0
                )
                prior_p["Def_WAR"] = prior_p["WAR"] - prior_p["Calculated_Sim_WAR"]

                def_war_p_map = (
                    prior_p[["Hashcode", "Def_WAR", "WAR"]]
                    .drop_duplicates("Hashcode")
                    .set_index("Hashcode")
                )

                if "Def_WAR" in self.pitching_data.columns:
                    self.pitching_data.drop("Def_WAR", axis=1, inplace=True)

                self.pitching_data = self.pitching_data.join(
                    def_war_p_map["Def_WAR"], how="left"
                )
                self.pitching_data["Def_WAR"] = self.pitching_data["Def_WAR"].fillna(
                    0.0
                )
                self.pitching_data["WAR"] = def_war_p_map["WAR"].combine_first(
                    self.pitching_data["WAR"]
                )
                print(
                    f"  Pitchers: Added Def_WAR for {(self.pitching_data['Def_WAR'] != 0).sum()} players"
                )
            else:
                self.pitching_data["Def_WAR"] = 0.0

        # === BATTERS ===
        if self.batting_data_historical is not None:
            prior_b = self.batting_data_historical[
                self.batting_data_historical["Season"] == prior_season
            ].copy()
            prior_b = prior_b[prior_b["AB"] >= 100].copy()

            if not prior_b.empty:
                # 1. Calculate wOBA (Simulated Offensive Value)
                singles = prior_b["H"] - prior_b["2B"] - prior_b["3B"] - prior_b["HR"]
                woba_num = (
                    0.69 * prior_b["BB"]
                    + 0.72 * prior_b["HBP"]
                    + 0.88 * singles
                    + 1.24 * prior_b["2B"]
                    + 1.56 * prior_b["3B"]
                    + 1.95 * prior_b["HR"]
                )

                # Use PA as denominator for wOBA
                prior_b["PA_calc"] = (
                    prior_b["AB"]
                    + prior_b["BB"]
                    + prior_b["HBP"]
                    + prior_b.get("SF", 0)
                )
                prior_b["wOBA"] = woba_num / prior_b["PA_calc"].replace(0, 1)

                # 2. Calculate Sim_WAR
                league_woba = prior_b["wOBA"].mean()
                replacement_woba = league_woba - 0.020
                prior_b["Calculated_Sim_WAR"] = (
                    ((prior_b["wOBA"] - replacement_woba) / 1.15)
                    * prior_b["PA_calc"]
                    / 10.0
                )

                # 3. Calculate Def_WAR (Baserunning + Defense)
                prior_b["Def_WAR"] = prior_b["WAR"] - prior_b["Calculated_Sim_WAR"]

                # 4. Create mapping and Join
                def_war_b_map = (
                    prior_b[["Hashcode", "Def_WAR", "WAR"]]
                    .drop_duplicates("Hashcode")
                    .set_index("Hashcode")
                )

                if "Def_WAR" in self.batting_data.columns:
                    self.batting_data.drop("Def_WAR", axis=1, inplace=True)

                self.batting_data = self.batting_data.join(
                    def_war_b_map["Def_WAR"], how="left"
                )
                self.batting_data["Def_WAR"] = self.batting_data["Def_WAR"].fillna(0.0)
                self.batting_data["WAR"] = def_war_b_map["WAR"].combine_first(
                    self.batting_data["WAR"]
                )

                print(
                    f"  Batters: Added Def_WAR for {(self.batting_data['Def_WAR'] != 0).sum()} players"
                )
            else:
                self.batting_data["Def_WAR"] = 0.0

    def randomize_data(self):
        """
        Replace all real identifiers with randomly generated ones.

        Calls ``create_leagues``, ``randomize_city_names``, and
        ``randomize_player_names`` in sequence. Raises an exception if any
        resulting Hashcode index contains a zero value, which would corrupt
        the base-runner representation.
        """
        self.create_leagues()
        self.randomize_city_names()
        self.randomize_player_names()
        if (
            np.min(self.batting_data.index) == 0
            or np.min(self.pitching_data.index) == 0
        ):  # last ditch check key error
            raise Exception(
                "Index value cannot be zero"
            )  # screws up bases where 0 is no runner
        return

    def create_leagues(self):
        """
        Replace AL/NL league names with fictional league abbreviations.

        Substitutes ``'AL'`` → ``'ACB'`` (Armchair Baseball) and
        ``'NL'`` → ``'NBL'`` (Nerd Baseball) in both aggregated and historical
        DataFrames for pitching and batting. Also updates the ``Leagues`` list
        column to match.
        """
        # replace AL and NL with random league names, set leagues column to match
        league_names = [
            "ACB",
            "NBL",
        ]  # Armchair Baseball and Nerd Baseball, Some Other League SOL, No Name NNL

        # Update aggregated data
        self.pitching_data.loc[self.pitching_data["League"] == "AL", "League"] = (
            league_names[0]
        )
        self.pitching_data.loc[self.pitching_data["League"] == "NL", "League"] = (
            league_names[1]
        )
        self.pitching_data["Leagues"] = self.pitching_data["League"].apply(
            lambda x: [x]
        )
        self.batting_data.loc[self.batting_data["League"] == "AL", "League"] = (
            league_names[0]
        )
        self.batting_data.loc[self.batting_data["League"] == "NL", "League"] = (
            league_names[1]
        )
        self.batting_data["Leagues"] = self.batting_data["League"].apply(lambda x: [x])

        # Update historical data
        if self.pitching_data_historical is not None:
            self.pitching_data_historical.loc[
                self.pitching_data_historical["League"] == "AL", "League"
            ] = league_names[0]
            self.pitching_data_historical.loc[
                self.pitching_data_historical["League"] == "NL", "League"
            ] = league_names[1]
            self.pitching_data_historical["Leagues"] = self.pitching_data_historical[
                "League"
            ].apply(lambda x: [x])

        if self.batting_data_historical is not None:
            self.batting_data_historical.loc[
                self.batting_data_historical["League"] == "AL", "League"
            ] = league_names[0]
            self.batting_data_historical.loc[
                self.batting_data_historical["League"] == "NL", "League"
            ] = league_names[1]
            self.batting_data_historical["Leagues"] = self.batting_data_historical[
                "League"
            ].apply(lambda x: [x])

        return

    def randomize_city_names(self):
        """
        Replace real MLB team abbreviations with random city abbreviations and mascots.

        Reads city names from the imported ``city`` module and animal mascots
        from ``animals.txt``. Builds a mapping of 3-letter city abbreviations to
        ``[city_name, mascot]`` pairs, then randomly samples enough entries to
        cover all unique team names in the dataset. Updates ``Team``, ``City``,
        ``Mascot``, and ``Teams`` columns in all four DataFrames (aggregated and
        historical, pitching and batting).
        """
        # create team name and mascots, set teams column to match
        city_dict = {}
        current_team_names = (
            self.batting_data.Team.unique()
        )  # get list of current team names
        city_abbrev = [
            str(name[:3]).upper() for name in city.names
        ]  # city names are imported
        mascots = self.randomize_mascots(len(city.names))
        for ii, team_abbrev in enumerate(city_abbrev):
            city_dict.update(
                {city_abbrev[ii]: [city.names[ii], mascots[ii]]}
            )  # update will use the last unique abbrev

        new_teams = list(random.sample(city_abbrev, len(current_team_names)))
        for ii, team in enumerate(
            current_team_names
        ):  # do not use a df merge here resets the index, that is bad
            new_team = new_teams[ii]
            mascot = city_dict[new_team][1]
            city_name = city_dict[new_team][0]

            # Update aggregated data
            self.pitching_data.replace([team], [new_team], inplace=True)
            self.pitching_data.loc[self.pitching_data["Team"] == new_team, "City"] = (
                city_name
            )
            self.pitching_data["Teams"] = self.pitching_data["Team"].apply(
                lambda x: [x]
            )
            self.pitching_data.loc[self.pitching_data["Team"] == new_team, "Mascot"] = (
                mascot
            )
            self.batting_data.replace([team], [new_team], inplace=True)
            self.batting_data.loc[self.batting_data["Team"] == new_team, "City"] = (
                city_name
            )
            self.batting_data["Teams"] = self.batting_data["Team"].apply(lambda x: [x])
            self.batting_data.loc[self.batting_data["Team"] == new_team, "Mascot"] = (
                mascot
            )

            # Update historical data
            if self.pitching_data_historical is not None:
                self.pitching_data_historical.replace([team], [new_team], inplace=True)
                self.pitching_data_historical.loc[
                    self.pitching_data_historical["Team"] == new_team, "City"
                ] = city_name
                self.pitching_data_historical["Teams"] = self.pitching_data_historical[
                    "Team"
                ].apply(lambda x: [x])
                self.pitching_data_historical.loc[
                    self.pitching_data_historical["Team"] == new_team, "Mascot"
                ] = mascot

            if self.batting_data_historical is not None:
                self.batting_data_historical.replace([team], [new_team], inplace=True)
                self.batting_data_historical.loc[
                    self.batting_data_historical["Team"] == new_team, "City"
                ] = city_name
                self.batting_data_historical["Teams"] = self.batting_data_historical[
                    "Team"
                ].apply(lambda x: [x])
                self.batting_data_historical.loc[
                    self.batting_data_historical["Team"] == new_team, "Mascot"
                ] = mascot

        return

    @staticmethod
    def randomize_mascots(length):
        """
        Return a random sample of animal mascot names from ``animals.txt``.

        :param length: Number of mascot names to return.
        :return: List of ``length`` unique animal name strings.
        """
        with open("animals.txt", "r") as f:
            animals = f.readlines()
        animals = [animal.strip() for animal in animals]
        mascots = random.sample(animals, length)
        return mascots

    def randomize_player_names(self):
        """
        Replace all player names and Hashcodes with randomly generated ones.

        Builds a pool of random full names by mixing first and last names drawn
        from the combined pitcher and batter roster. Assigns unique names to each
        player in the aggregated DataFrames, recalculates their SHA-256 Hashcodes,
        then propagates the new names and Hashcodes into the historical DataFrames
        by mapping from the old Hashcode (extracted from ``Player_Season_Key``).
        """
        # change pitching_data and batting data names, team name, etc
        df = pd.concat(
            [
                self.batting_data.Player.str.split(pat=" ", n=1, expand=True),
                self.pitching_data.Player.str.split(pat=" ", n=1, expand=True),
            ]
        )
        first_names = df[0].values.tolist()
        last_names = df[1].values.tolist()
        random_names = []
        for ii in range(
            1, (df.shape[0] + 1) * 2
        ):  # generate twice as many random names as needed
            random_names.append(
                random.choice(first_names) + " " + random.choice(last_names)
            )
        random_names = list(set(random_names))  # drop non-unique names
        random_names = random.sample(
            random_names, self.batting_data.shape[0] + self.pitching_data.shape[0]
        )

        # load new names and reset hashcode index for AGGREGATED data
        self.batting_data["Player"] = random_names[
            : len(self.batting_data)
        ]  # grab first x rows of list
        self.batting_data = self.batting_data.reset_index()
        self.batting_data["Hashcode"] = self.batting_data["Player"].apply(
            lambda x: self.create_hash(x, "Hitter")
        )
        self.batting_data = self.batting_data.set_index("Hashcode")

        self.pitching_data["Player"] = random_names[
            -len(self.pitching_data) :
        ]  # next x rows list
        self.pitching_data = self.pitching_data.reset_index()
        self.pitching_data["Hashcode"] = self.pitching_data["Player"].apply(
            lambda x: self.create_hash(x, "Pitcher")
        )
        self.pitching_data = self.pitching_data.set_index("Hashcode")

        # Update HISTORICAL data with same player names (need to map old hashcode to new)
        # Create mapping from old hashcode to new player name
        if self.batting_data_historical is not None:
            # Extract hashcode from Player_Season_Key (format: hashcode_season)
            self.batting_data_historical = self.batting_data_historical.reset_index()
            self.batting_data_historical["Old_Hashcode"] = (
                self.batting_data_historical["Player_Season_Key"]
                .str.split("_")
                .str[0]
                .apply(int)
            )
            # Map old hashcode to new player name from aggregated data
            old_to_new_player = dict(
                zip(
                    self.batting_data.reset_index()["Hashcode"],
                    self.batting_data.reset_index()["Player"],
                )
            )
            self.batting_data_historical["Player"] = self.batting_data_historical[
                "Old_Hashcode"
            ].map(old_to_new_player)
            # Recalculate hashcode and Player_Season_Key
            self.batting_data_historical["Hashcode"] = self.batting_data_historical[
                "Player"
            ].apply(lambda x: self.create_hash(x, "Hitter"))
            self.batting_data_historical["Player_Season_Key"] = (
                self.batting_data_historical["Hashcode"].astype(str)
                + "_"
                + self.batting_data_historical["Season"].astype(str)
            )
            self.batting_data_historical = self.batting_data_historical.drop(
                "Old_Hashcode", axis=1
            )
            self.batting_data_historical = self.batting_data_historical.set_index(
                "Player_Season_Key"
            )

        if self.pitching_data_historical is not None:
            self.pitching_data_historical = self.pitching_data_historical.reset_index()
            self.pitching_data_historical["Old_Hashcode"] = (
                self.pitching_data_historical["Player_Season_Key"]
                .str.split("_")
                .str[0]
                .apply(int)
            )
            old_to_new_player = dict(
                zip(
                    self.pitching_data.reset_index()["Hashcode"],
                    self.pitching_data.reset_index()["Player"],
                )
            )
            self.pitching_data_historical["Player"] = self.pitching_data_historical[
                "Old_Hashcode"
            ].map(old_to_new_player)
            self.pitching_data_historical["Hashcode"] = self.pitching_data_historical[
                "Player"
            ].apply(lambda x: self.create_hash(x, "Pitcher"))
            self.pitching_data_historical["Player_Season_Key"] = (
                self.pitching_data_historical["Hashcode"].astype(str)
                + "_"
                + self.pitching_data_historical["Season"].astype(str)
            )
            self.pitching_data_historical = self.pitching_data_historical.drop(
                "Old_Hashcode", axis=1
            )
            self.pitching_data_historical = self.pitching_data_historical.set_index(
                "Player_Season_Key"
            )

        return

    def create_new_season_from_existing(
        self, load_batter_file: str, load_pitcher_file: str
    ) -> None:
        """
        Generate new-season DataFrames with rate stats preserved and counting stats zeroed.

        Two code paths:
        - **Actual partial season** (``new_season == load_seasons[-1]`` and not random):
          Reads real partial-season files directly via ``get_pitching_seasons``
          and ``get_batting_seasons``.
        - **Projected next season** (any other case, including random data):
          Copies the aggregated DataFrames, calculates ERA/WHIP/OBP (pitchers)
          or AVG/OBP/SLG/OPS (batters) from the projected counting stats, then
          zeros all counting stats so the simulator starts fresh. Player ages are
          incremented by 1 when ``new_season`` is not in ``load_seasons``.

        Results are stored in ``self.new_season_pitching_data`` and
        ``self.new_season_batting_data``.

        :param load_batter_file: Base batter file name (used for the partial-season path).
        :param load_pitcher_file: Base pitcher file name (used for the partial-season path).
        :raises Exception: If pitching or batting data has not been loaded yet.
        """
        if self.pitching_data is None or self.batting_data is None:
            raise Exception("load at least one season of pitching and batting")
        # blend of actual partial season, load org new season from file
        if (
            self.load_seasons[-1] == self.new_season
            and self.generate_random_data is False
        ):
            self.new_season_pitching_data = self.get_pitching_seasons(
                load_pitcher_file, [self.new_season]
            )
            self.new_season_batting_data = self.get_batting_seasons(
                load_batter_file, [self.new_season]
            )
        else:  # handle random league data and or consecutive seasons
            # --- Pitching ---
            self.new_season_pitching_data = self.pitching_data.copy()
            self.new_season_pitching_data[self.numeric_pcols] = (
                self.new_season_pitching_data[self.numeric_pcols].astype("int")
            )
            self.new_season_pitching_data["Season"] = str(self.new_season)

            # Calculate projected rate stats from counting stats before zeroing
            pp = self.new_season_pitching_data
            pp["ERA"] = self.trunc_col(
                np.nan_to_num(np.divide(pp["ER"] * 9, pp["IP"]), nan=0.0, posinf=0.0), 2
            )
            pp["WHIP"] = self.trunc_col(
                np.nan_to_num(
                    np.divide(pp["BB"] + pp["H"], pp["IP"]), nan=0.0, posinf=0.0
                ),
                3,
            )
            pp["OBP"] = self.trunc_col(
                np.nan_to_num(
                    np.divide(pp["WHIP"], 3 + pp["WHIP"]), nan=0.0, posinf=0.0
                ),
                3,
            )

            # Zero counting stats for simulation tracking (preserve ERA/WHIP/OBP)
            self.new_season_pitching_data[self.numeric_pcols] = 0
            self.new_season_pitching_data[
                [
                    "AVG_faced",
                    "Total_OB",
                    "Total_Outs",
                    "AB",
                    "HLD",
                    "BS",
                    "Injured Days",
                ]
            ] = 0
            self.new_season_pitching_data["Condition"] = 100
            self.new_season_pitching_data["Streak_Adjustment"] = 0.0
            self.new_season_pitching_data.drop(["Total_OB", "Total_Outs"], axis=1)
            if (
                self.new_season not in self.load_seasons
            ):  # add a year to age if it is the next year
                self.new_season_pitching_data["Age"] = (
                    self.new_season_pitching_data["Age"] + 1
                )

            # --- Batting ---
            self.new_season_batting_data = self.batting_data.copy()
            self.new_season_batting_data["Season"] = str(self.new_season)

            # Calculate projected rate stats from counting stats before zeroing
            bp = self.new_season_batting_data
            bp["AVG"] = self.trunc_col(
                np.nan_to_num(np.divide(bp["H"], bp["AB"]), nan=0.0, posinf=0.0), 3
            )
            bp["OBP"] = self.trunc_col(
                np.nan_to_num(
                    np.divide(
                        bp["H"] + bp["BB"] + bp["HBP"],
                        bp["AB"] + bp["BB"] + bp["HBP"] + bp.get("SF", 0),
                    ),
                    nan=0.0,
                    posinf=0.0,
                ),
                3,
            )
            bp["SLG"] = self.trunc_col(
                np.nan_to_num(
                    np.divide(
                        (bp["H"] - bp["2B"] - bp["3B"] - bp["HR"])
                        + bp["2B"] * 2
                        + bp["3B"] * 3
                        + bp["HR"] * 4,
                        bp["AB"],
                    ),
                    nan=0.0,
                    posinf=0.0,
                ),
                3,
            )
            bp["OPS"] = self.trunc_col(
                np.nan_to_num(bp["OBP"] + bp["SLG"], nan=0.0, posinf=0.0), 3
            )
            if (
                self.new_season not in self.load_seasons
            ):  # add a year to age if it is the next year
                self.new_season_batting_data["Age"] = (
                    self.new_season_batting_data["Age"] + 1
                )

            # Zero counting stats for simulation tracking (preserve AVG/OBP/SLG/OPS)
            self.new_season_batting_data[self.numeric_bcols] = 0
            self.new_season_batting_data[["Total_OB", "Total_Outs", "Injured Days"]] = 0
            self.new_season_batting_data["Condition"] = 100
            self.new_season_batting_data["Streak_Adjustment"] = 0.0
            self.new_season_batting_data.drop(["Total_OB", "Total_Outs"], axis=1)

        return

    @staticmethod
    def trunc_col(df_n: ndarray, d: int = 3) -> ndarray:
        """
        Truncate a numeric array to ``d`` decimal places without rounding.

        Avoids floating-point rounding artefacts by shifting the decimal,
        casting to int (which floors toward zero), then shifting back.

        :param df_n: NumPy array or scalar to truncate.
        :param d: Number of decimal places to keep. Default 3.
        :return: Array of the same shape with values truncated to ``d`` decimals.
        """
        return (df_n * 10**d).astype(int) / 10**d


# =============================================================================
# FORECAST INTEGRITY CHECKS
# =============================================================================


def check_batting_integrity():
    """Compare projected batting stats against historical baselines."""
    B_PROJ_FILE = "2023 2024 2025 player-projected-stats-pp-Batting.csv"
    B_HIST_FILE = "2023 2024 2025 historical-Batting.csv"

    df_proj = pd.read_csv(B_PROJ_FILE)
    df_hist = pd.read_csv(B_HIST_FILE)
    df_25 = df_hist[df_hist["Season"] == 2025].copy()
    df_23_25 = df_hist[df_hist["Season"].isin([2023, 2024, 2025])].copy()

    df_proj["BA"] = df_proj["H"] / df_proj["AB"].replace(0, 1)
    df_proj["BB_Rate"] = df_proj["BB"] / df_proj["PA"].replace(0, 1)
    df_proj["SO_Rate"] = df_proj["SO"] / df_proj["PA"].replace(0, 1)
    df_proj["OBP"] = (df_proj["H"] + df_proj["BB"] + df_proj.get("HBP", 0)) / df_proj[
        "PA"
    ].replace(0, 1)

    lg_ba_23_25 = df_23_25["H"].sum() / df_23_25["AB"].sum()
    lg_obp_23_25 = (df_23_25["H"] + df_23_25["BB"]).sum() / df_23_25["PA"].sum()
    lg_bb_23_25 = df_23_25["BB"].sum() / df_23_25["PA"].sum()
    lg_so_23_25 = df_23_25["SO"].sum() / df_23_25["PA"].sum()

    lg_ba_25 = df_25["H"].sum() / df_25["AB"].sum()
    lg_obp_25 = (df_25["H"] + df_25["BB"]).sum() / df_25["PA"].sum()
    lg_bb_25 = df_25["BB"].sum() / df_25["PA"].sum()
    lg_so_25 = df_25["SO"].sum() / df_25["PA"].sum()

    lg_ba = df_proj["H"].sum() / df_proj["AB"].sum()
    lg_obp = (df_proj["H"] + df_proj["BB"]).sum() / df_proj["PA"].sum()
    lg_bb = df_proj["BB"].sum() / df_proj["PA"].sum()
    lg_so = df_proj["SO"].sum() / df_proj["PA"].sum()

    print("=" * 90)
    print(f"{'HITTER INTEGRITY CHECK: PROJECTION vs HISTORICAL BASELINES':^90}")
    print("=" * 90)
    print(f"                            2023-2025 Hist    2025 Hist    2026 Proj")
    print(
        f"League AVG:                 {lg_ba_23_25:.3f}         {lg_ba_25:.3f}       {lg_ba:.3f}"
    )
    print(
        f"League OBP:                 {lg_obp_23_25:.3f}         {lg_obp_25:.3f}       {lg_obp:.3f}"
    )
    print(
        f"BB Rate (BB/PA):            {lg_bb_23_25:.3f}         {lg_bb_25:.3f}       {lg_bb:.3f}"
    )
    print(
        f"SO Rate (SO/PA):           {lg_so_23_25:.3f}         {lg_so_25:.3f}       {lg_so:.3f}"
    )
    print(
        f"OBP Spread (OBP - AVG):  {lg_obp_23_25 - lg_ba_23_25:.3f}         {lg_obp_25 - lg_ba_25:.3f}       {lg_obp - lg_ba:.3f}"
    )
    print("-" * 90)

    proj_vs_blend_obp = lg_obp - lg_obp_23_25
    proj_vs_25_obp = lg_obp - lg_obp_25
    proj_vs_blend_bb = lg_bb - lg_bb_23_25
    proj_vs_25_bb = lg_bb - lg_bb_25
    proj_vs_blend_so = lg_so - lg_so_23_25
    proj_vs_25_so = lg_so - lg_so_25

    print(
        f"2026 Proj vs 2023-2025 Blend: OBP {proj_vs_blend_obp:+.3f} | BB {proj_vs_blend_bb:+.3f} | SO {proj_vs_blend_so:+.3f}"
    )
    print(
        f"2026 Proj vs 2025 Only:       OBP {proj_vs_25_obp:+.3f} | BB {proj_vs_25_bb:+.3f} | SO {proj_vs_25_so:+.3f}"
    )
    print("-" * 90)


def check_pitching_integrity():
    """Compare projected pitching stats against historical baselines."""
    P_PROJ_FILE = "2023 2024 2025 player-projected-stats-pp-Pitching.csv"
    P_HIST_FILE = "2023 2024 2025 historical-Pitching.csv"

    df_proj = pd.read_csv(P_PROJ_FILE)
    df_hist = pd.read_csv(P_HIST_FILE)
    df_25 = df_hist[df_hist["Season"] == 2025].copy()
    df_23_25 = df_hist[df_hist["Season"].isin([2023, 2024, 2025])].copy()

    df_proj["H_PA"] = df_proj["H"] / df_proj["PA"].replace(0, 1)
    df_proj["BB_PA"] = df_proj["BB"] / df_proj["PA"].replace(0, 1)
    df_proj["SO_PA"] = df_proj["SO"] / df_proj["PA"].replace(0, 1)
    df_proj["OBP_Against"] = (df_proj["H"] + df_proj["BB"]) / df_proj["PA"].replace(
        0, 1
    )

    lg_h_pa_23_25 = df_23_25["H"].sum() / df_23_25["PA"].sum()
    lg_bb_pa_23_25 = df_23_25["BB"].sum() / df_23_25["PA"].sum()
    lg_so_pa_23_25 = df_23_25["SO"].sum() / df_23_25["PA"].sum()
    lg_obpa_23_25 = lg_h_pa_23_25 + lg_bb_pa_23_25

    lg_h_pa_25 = df_25["H"].sum() / df_25["PA"].sum()
    lg_bb_pa_25 = df_25["BB"].sum() / df_25["PA"].sum()
    lg_so_pa_25 = df_25["SO"].sum() / df_25["PA"].sum()
    lg_obpa_25 = lg_h_pa_25 + lg_bb_pa_25

    lg_h_pa = df_proj["H"].sum() / df_proj["PA"].sum()
    lg_bb_pa = df_proj["BB"].sum() / df_proj["PA"].sum()
    lg_so_pa = df_proj["SO"].sum() / df_proj["PA"].sum()
    lg_obpa = lg_h_pa + lg_bb_pa

    print("\n" + "=" * 90)
    print(f"{'PITCHER INTEGRITY CHECK: PROJECTION vs HISTORICAL BASELINES':^90}")
    print("=" * 90)
    print(f"                            2023-2025 Hist    2025 Hist    2026 Proj")
    print(
        f"League Hits/PA:            {lg_h_pa_23_25:.3f}         {lg_h_pa_25:.3f}       {lg_h_pa:.3f}"
    )
    print(
        f"League Walks/PA:            {lg_bb_pa_23_25:.3f}         {lg_bb_pa_25:.3f}       {lg_bb_pa:.3f}"
    )
    print(
        f"League K/PA:               {lg_so_pa_23_25:.3f}         {lg_so_pa_25:.3f}       {lg_so_pa:.3f}"
    )
    print(
        f"OBP Against:               {lg_obpa_23_25:.3f}         {lg_obpa_25:.3f}       {lg_obpa:.3f}"
    )
    print("-" * 90)

    stiflers = df_proj[
        (df_proj["PA"] > 200) & (df_proj["OBP_Against"] < 0.250)
    ].sort_values("OBP_Against")
    if not stiflers.empty:
        print("PITCHERS SUPPRESSING OBP UNREALISTICALLY (< .250 OBP Against):")
        print(
            stiflers[["Player", "PA", "H_PA", "BB_PA", "OBP_Against"]]
            .head(10)
            .to_string(index=False)
        )
    print("-" * 90)


def diagnose_power_inflation():
    """Compare 2026 projections vs 2025 actual for power metrics (2B, 3B, HR -> SLG)."""
    B_PROJ_FILE = "2023 2024 2025 player-projected-stats-pp-Batting.csv"
    B_HIST_FILE = "2023 2024 2025 historical-Batting.csv"

    df_proj = pd.read_csv(B_PROJ_FILE)
    df_hist = pd.read_csv(B_HIST_FILE)
    df_25 = df_hist[df_hist["Season"] == 2025].copy()

    df_proj["1B"] = (
        df_proj["H"]
        - df_proj["2B"].fillna(0)
        - df_proj["3B"].fillna(0)
        - df_proj["HR"].fillna(0)
    )
    df_25["1B"] = (
        df_25["H"]
        - df_25["2B"].fillna(0)
        - df_25["3B"].fillna(0)
        - df_25["HR"].fillna(0)
    )

    df_proj["SLG"] = (
        df_proj["1B"]
        + 2 * df_proj["2B"].fillna(0)
        + 3 * df_proj["3B"].fillna(0)
        + 4 * df_proj["HR"].fillna(0)
    ) / df_proj["AB"].replace(0, 1)
    df_25["SLG"] = (
        df_25["1B"]
        + 2 * df_25["2B"].fillna(0)
        + 3 * df_25["3B"].fillna(0)
        + 4 * df_25["HR"].fillna(0)
    ) / df_25["AB"].replace(0, 1)

    lg_1b_25 = df_25["1B"].sum() / df_25["AB"].sum()
    lg_2b_25 = df_25["2B"].sum() / df_25["AB"].sum()
    lg_3b_25 = df_25["3B"].sum() / df_25["AB"].sum()
    lg_hr_25 = df_25["HR"].sum() / df_25["AB"].sum()
    lg_slg_25 = df_25["SLG"].mean()

    lg_1b_26 = df_proj["1B"].sum() / df_proj["AB"].sum()
    lg_2b_26 = df_proj["2B"].sum() / df_proj["AB"].sum()
    lg_3b_26 = df_proj["3B"].sum() / df_proj["AB"].sum()
    lg_hr_26 = df_proj["HR"].sum() / df_proj["AB"].sum()
    lg_slg_26 = df_proj["SLG"].mean()

    print("\n" + "=" * 90)
    print(f"{'POWER INFLATION DIAGNOSTIC: 2B, 3B, HR -> SLG':^90}")
    print("=" * 90)
    print(f"                            2025 Actual    2026 Proj    Delta")
    print(
        f"Singles/AB:                {lg_1b_25:.4f}       {lg_1b_26:.4f}    {lg_1b_26 - lg_1b_25:+.4f}"
    )
    print(
        f"Doubles/AB (2B):           {lg_2b_25:.4f}       {lg_2b_26:.4f}    {lg_2b_26 - lg_2b_25:+.4f}"
    )
    print(
        f"Triples/AB (3B):           {lg_3b_25:.4f}       {lg_3b_26:.4f}    {lg_3b_26 - lg_3b_25:+.4f}"
    )
    print(
        f"Home Runs/AB (HR):         {lg_hr_25:.4f}       {lg_hr_26:.4f}    {lg_hr_26 - lg_hr_25:+.4f}"
    )
    print(
        f"League SLG (avg):          {lg_slg_25:.4f}       {lg_slg_26:.4f}    {lg_slg_26 - lg_slg_25:+.4f}"
    )
    print("-" * 90)

    slg_delta = (lg_slg_26 - lg_slg_25) * 1000
    print(f"SLG Delta: {slg_delta:+.0f} points (target: ~0)")
    if abs(slg_delta) > 30:
        print("WARNING: Significant SLG inflation detected!")
    print("-" * 90)


def diagnose_bip_leakage():
    """Compare BABIP between projection and historical baselines."""
    P_PROJ_FILE = "2023 2024 2025 player-projected-stats-pp-Pitching.csv"
    P_HIST_FILE = "2023 2024 2025 historical-Pitching.csv"

    df_p_hist = pd.read_csv(P_HIST_FILE)
    df_p_proj = pd.read_csv(P_PROJ_FILE)

    p_25 = df_p_hist[df_p_hist["Season"] == 2025].copy()
    p_23_25 = df_p_hist[df_p_hist["Season"].isin([2023, 2024, 2025])].copy()

    p_25["BIP"] = p_25["PA"] - p_25["SO"] - p_25["BB"]
    p_25_h_bip = p_25["H"].sum() / p_25["BIP"].sum()

    p_23_25["BIP"] = p_23_25["PA"] - p_23_25["SO"] - p_23_25["BB"]
    p_23_25_h_bip = p_23_25["H"].sum() / p_23_25["BIP"].sum()

    df_p_proj["BIP"] = df_p_proj["PA"] - df_p_proj["SO"] - df_p_proj["BB"]
    proj_h_bip = df_p_proj["H"].sum() / df_p_proj["BIP"].sum()

    print("\n" + "=" * 90)
    print(f"{'BIP LEAKAGE DIAGNOSTIC (BABIP Comparison)':^90}")
    print("=" * 90)
    print(f"                            2023-2025 Hist    2025 Hist    2026 Proj")
    print(
        f"Historical H/BIP:          {p_23_25_h_bip:.4f}         {p_25_h_bip:.4f}       {proj_h_bip:.4f}"
    )
    print("-" * 90)
    print(
        f"2026 Proj vs 2023-2025 Blend: {(proj_h_bip - p_23_25_h_bip) * 1000:+.1f} points"
    )
    print(
        f"2026 Proj vs 2025 Only:       {(proj_h_bip - p_25_h_bip) * 1000:+.1f} points"
    )
    print("-" * 90)


def diagnose_h_surplus():
    """Compare hit rates between projection and baselines."""
    B_PROJ_FILE = "2023 2024 2025 player-projected-stats-pp-Batting.csv"
    B_HIST_FILE = "2023 2024 2025 historical-Batting.csv"
    P_PROJ_FILE = "2023 2024 2025 player-projected-stats-pp-Pitching.csv"
    P_HIST_FILE = "2023 2024 2025 historical-Pitching.csv"

    df_b_proj = pd.read_csv(B_PROJ_FILE)
    df_b_hist = pd.read_csv(B_HIST_FILE)
    df_p_proj = pd.read_csv(P_PROJ_FILE)
    df_p_hist = pd.read_csv(P_HIST_FILE)

    b_25 = df_b_hist[df_b_hist["Season"] == 2025]
    b_23_25 = df_b_hist[df_b_hist["Season"].isin([2023, 2024, 2025])]
    p_25 = df_p_hist[df_p_hist["Season"] == 2025]
    p_23_25 = df_p_hist[df_p_hist["Season"].isin([2023, 2024, 2025])]

    b_25_h_rate = b_25["H"].sum() / b_25["PA"].sum()
    b_23_25_h_rate = b_23_25["H"].sum() / b_23_25["PA"].sum()
    b_26_h_rate = df_b_proj["H"].sum() / df_b_proj["PA"].sum()

    p_25_h_rate = p_25["H"].sum() / p_25["PA"].sum()
    p_23_25_h_rate = p_23_25["H"].sum() / p_23_25["PA"].sum()
    p_26_h_rate = df_p_proj["H"].sum() / df_p_proj["PA"].sum()

    print("\n" + "=" * 90)
    print(f"{'HIT INFLATION DIAGNOSTIC: PROJECTION vs BASELINES':^90}")
    print("=" * 90)
    print(f"                            2023-2025 Hist    2025 Hist    2026 Proj")
    print(
        f"Hitters (H/PA):            {b_23_25_h_rate:.4f}       {b_25_h_rate:.4f}     {b_26_h_rate:.4f}"
    )
    print(
        f"Pitchers (H_Allowed/PA):   {p_23_25_h_rate:.4f}       {p_25_h_rate:.4f}     {p_26_h_rate:.4f}"
    )
    print("-" * 90)

    h_vs_blend = (b_26_h_rate - b_23_25_h_rate) * 1000
    h_vs_25 = (b_26_h_rate - b_25_h_rate) * 1000
    p_vs_blend = (p_26_h_rate - p_23_25_h_rate) * 1000
    p_vs_25 = (p_26_h_rate - p_25_h_rate) * 1000

    print(
        f"2026 Proj vs 2023-2025 Blend: Hitters {h_vs_blend:+.1f} pts | Pitchers {p_vs_blend:+.1f} pts"
    )
    print(
        f"2026 Proj vs 2025 Only:       Hitters {h_vs_25:+.1f} pts | Pitchers {p_vs_25:+.1f} pts"
    )
    print("-" * 90)


# =============================================================================
# PLAYER-SPECIFIC CHECKS
# =============================================================================


def run_player_checks():
    """Run checks for specific players of interest."""
    baseball_data = BaseballStatsPreProcess(
        load_seasons=[2023, 2024, 2025],
        new_season=2026,
        generate_random_data=False,
        load_batter_file="player-stats-Batters.csv",
        load_pitcher_file="player-stats-Pitching.csv",
    )

    BATTERS_TO_CHECK = [
        "Tyler Black",
        "William Contreras",
        "Jackson Chourio",
        "Cal Raleigh",
        "Will Smith",
    ]
    PITCHERS_TO_CHECK = [
        "Freddy Peralta",
        "Logan Webb",
        "Jared Jones",
        "Tobias Myers",
        "Will Smith",
    ]

    B_HDR = f"{'Season':<10}{'Team':<6}{'Age':>4}{'G':>5}{'AB':>6}{'H':>5}{'2B':>4}{'3B':>4}{'HR':>4}{'BB':>5}{'SO':>5}{'AVG':>7}{'OBP':>7}{'SLG':>7}{'OPS':>7}  Method"
    P_HDR = f"{'Season':<10}{'Team':<6}{'Age':>4}{'G':>5}{'GS':>5}{'IP':>7}{'H':>5}{'ER':>5}{'BB':>5}{'SO':>5}{'K/9':>7}{'WHIP':>7}{'ERA':>7}  Method"
    SEP = "=" * 105

    def _fmt_batting_row(r, season_label=None):
        season = season_label if season_label else str(int(float(r.get("Season", 0))))
        ab = float(r.get("AB", 0))
        h = float(r.get("H", 0))
        avg_val = (h / ab) if ab > 0 else float(r.get("AVG", r.get("BA", 0.0)))
        method = r.get("Projection_Method", "Actual")
        return (
            f"{season:<10}{str(r.get('Team', '')):6}{int(float(r.get('Age', 0))):>4}"
            f"{int(float(r.get('G', 0))):>5}{int(ab):>6}{int(h):>5}"
            f"{int(float(r.get('2B', 0))):>4}{int(float(r.get('3B', 0))):>4}"
            f"{int(float(r.get('HR', 0))):>4}{int(float(r.get('BB', 0))):>5}{int(float(r.get('SO', 0))):>5}"
            f"{avg_val:>7.3f}{float(r.get('OBP', 0)):>7.3f}"
            f"{float(r.get('SLG', 0)):>7.3f}{float(r.get('OPS', 0)):>7.3f}  {method:<10}"
        )

    def _fmt_pitching_row(r, season_label=None):
        season = season_label if season_label else str(int(float(r.get("Season", 0))))
        ip = float(r.get("IP", 0))
        h = float(r.get("H", 0))
        bb = float(r.get("BB", 0))
        so = float(r.get("SO", 0))
        er = float(r.get("ER", 0))
        ip_true = int(ip) + (ip % 1) * 3.333
        era = float(r.get("ERA", (er * 9 / ip_true) if ip_true > 0 else 0))
        whip = float(r.get("WHIP", ((h + bb) / ip_true) if ip_true > 0 else 0))
        k9 = float(r.get("K/9", (so / ip_true * 9) if ip_true > 0 else 0))
        method = r.get("Projection_Method", "Actual")
        return (
            f"{season:<10}{str(r.get('Team', '')):6}{int(float(r.get('Age', 0))):>4}"
            f"{int(float(r.get('G', 0))):>5}{int(float(r.get('GS', 0))):>5}{int(ip):>3}.{int((ip % 1) * 3.333):>3}"
            f"{int(h):>5}{int(er):>5}{int(bb):>5}{int(so):>5}"
            f"{k9:>7.2f}{whip:>7.2f}{era:>7.2f}  {method:<10}"
        )

    def _find_player(df, name):
        if df is None or df.empty:
            return pd.DataFrame()
        if "Player" not in df.columns:
            return df[df.index.astype(str).str.contains(name, case=False)]
        reset = df.reset_index()
        return (
            reset[reset["Player"] == name]
            if "Player" in reset.columns
            else pd.DataFrame()
        )

    seasons_str = " ".join(str(s) for s in baseball_data.load_seasons)
    try:
        hist_bat_df = pd.read_csv(
            f"{seasons_str} historical-Batting.csv", index_col="Player_Season_Key"
        )
        hist_pit_df = pd.read_csv(
            f"{seasons_str} historical-Pitching.csv", index_col="Player_Season_Key"
        )
    except FileNotFoundError:
        hist_bat_df = hist_pit_df = pd.DataFrame()

    for player_name in BATTERS_TO_CHECK:
        print(f"\n{SEP}\n  BATTER CHECK: {player_name.upper()}\n{SEP}")
        print(f"--- Historical Actuals ---\n{B_HDR}")
        if not hist_bat_df.empty:
            p_hist = hist_bat_df[hist_bat_df["Player"] == player_name].sort_values(
                "Season"
            )
            for _, r in p_hist.iterrows():
                print(_fmt_batting_row(r))
        player_proj = _find_player(baseball_data.batting_data, player_name)
        if not player_proj.empty:
            print(f"\n--- 2026 Projection ---\n{B_HDR}")
            for _, r in player_proj.iterrows():
                print(_fmt_batting_row(r, "2026 PROJ"))

    for player_name in PITCHERS_TO_CHECK:
        print(f"\n{SEP}\n  PITCHER CHECK: {player_name.upper()}\n{SEP}")
        print(f"--- Historical Actuals ---\n{P_HDR}")
        if not hist_pit_df.empty:
            p_hist = hist_pit_df[hist_pit_df["Player"] == player_name].sort_values(
                "Season"
            )
            for _, r in p_hist.iterrows():
                print(_fmt_pitching_row(r))
        player_proj = _find_player(baseball_data.pitching_data, player_name)
        if not player_proj.empty:
            print(f"\n--- 2026 Projection ---\n{P_HDR}")
            for _, r in player_proj.iterrows():
                print(_fmt_pitching_row(r, "2026 PROJ"))

    print(f"\n{SEP}\n")


if __name__ == "__main__":
    print("=" * 90)
    print("BASEBALL STATISTICS PREPROCESSING")
    print("=" * 90)

    print("\n[1/3] Running preprocessing to generate projection files...")
    baseball_data = BaseballStatsPreProcess(
        load_seasons=[2023, 2024, 2025],
        new_season=2026,
        generate_random_data=False,
        load_batter_file="player-stats-Batters.csv",
        load_pitcher_file="player-stats-Pitching.csv",
    )

    print("\n[2/3] Running forecast integrity checks...")
    check_batting_integrity()
    check_pitching_integrity()
    diagnose_h_surplus()
    diagnose_power_inflation()
    diagnose_bip_leakage()

    print("\n[3/3] Running player-specific checks...")
    run_player_checks()

    print("=" * 90)
    print("PREPROCESSING COMPLETE")
    print("=" * 90)
