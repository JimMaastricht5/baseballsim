"""
Copyright (c) 2024 Jim Maastricht

Stats preprocessing: cleans raw RotoWire/Baseball-Reference CSVs, calculates derived
stats, applies age-adjusted projections, and writes three output file types:

1. Player-projected files ({seasons} player-projected-stats-pp-*.csv) — career
   totals indexed by Hashcode, used by the simulator.
2. Historical files ({seasons} historical-*.csv) — one row per player per season.
3. New-season files ({new_season} New-Season-stats-pp-*.csv) — empty template
   for accumulating sim data.

Supports random data generation for testing.
"""

import hashlib

# data clean up and standardization for stats.  handles random generation if requested
# data imported from https://www.rotowire.com/baseball/stats.php
import os
import random
from typing import List, Optional

import numpy as np
import pandas as pd
from numpy import ndarray
from pandas.core.frame import DataFrame

import bbplayer_projections_forecast_player as player_projector
import city_names as city
import salary
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
        min_games_for_trusted: int = 80,
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
        :param min_games_for_trusted: Minimum games in the max season for projections
            to be considered trusted. If max season has fewer games, it's excluded
            from projection calculations. Defaults to 80.
        :param load_batter_file: Base filename for raw batter CSV files
            (year prefix added automatically, e.g. ``'player-stats-Batters.csv'``).
        :param load_pitcher_file: Base filename for raw pitcher CSV files.
        """
        # self.create_hash = lambda text: int(hashlib.sha256(text.encode('utf-8')).hexdigest()[:5], 16)
        self.jigger_data = lambda x: x + int(np.abs(np.random.normal(loc=x * 0.10, scale=2, size=1)))

        self.numeric_bcols = [
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
            "GIDP",
            "HBP",
            "Condition",
        ]  # these cols will get added to running season total (BA is rate stat, not counting)
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
        self.load_seasons = [load_seasons] if not isinstance(load_seasons, list) else load_seasons  # convert to list
        self.new_season = new_season
        self.min_games_for_trusted = min_games_for_trusted
        self.projection_trusted = True
        self.pitching_data = None
        self.batting_data = None
        self.pitching_data_historical = None
        self.batting_data_historical = None
        self.new_season_pitching_data = None
        self.new_season_batting_data = None
        self.generate_random_data = generate_random_data

        self.df_salary = salary.retrieve_salary("mlb-salaries-2000-24.csv", self.create_hash)

        # Step 1: Load ALL seasons raw data first
        self._load_raw_data(load_batter_file, load_pitcher_file)

        # Step 2: Auto-detect which seasons to use for projections
        self._detect_projection_seasons()

        # Step 3: Process with the appropriate seasons
        self.get_seasons(load_batter_file, load_pitcher_file)

        collision = set(self.batting_data.index).intersection(set(self.pitching_data.index))
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

    def _load_raw_data(self, batter_file: str, pitcher_file: str) -> None:
        """
        Load raw CSV data for all seasons without projection.

        Loads batting and pitching data for all seasons in load_seasons,
        stores them for threshold detection before projection.
        """
        self.raw_batting_data = None
        self.raw_pitching_data = None

        for season in self.load_seasons:
            # Load batting data
            bdf = pd.read_csv(str(season) + f" {batter_file}")
            bdf["Season"] = season
            self.raw_batting_data = pd.concat([self.raw_batting_data, bdf], axis=0)

            # Load pitching data
            pdf = pd.read_csv(str(season) + f" {pitcher_file}")
            pdf["Season"] = season
            self.raw_pitching_data = pd.concat([self.raw_pitching_data, pdf], axis=0)

    def _detect_projection_seasons(self) -> None:
        """
        Auto-detect which seasons to use for projections based on games played.

        Checks the maximum games in the most recent season across both batters and pitchers.
        If any player has >= min_games_for_trusted, the season is considered trusted
        and included in projections. Otherwise, it's excluded.

        Sets self.projection_seasons and self.projection_trusted accordingly.
        """
        max_season = max(self.load_seasons)

        # Get max games for batters in max season
        max_season_batters = self.raw_batting_data[self.raw_batting_data["Season"] == max_season]
        max_batter_games = max_season_batters["G"].max() if not max_season_batters.empty else 0

        # Get max games for pitchers in max season
        max_season_pitchers = self.raw_pitching_data[self.raw_pitching_data["Season"] == max_season]
        max_pitcher_games = max_season_pitchers["G"].max() if not max_season_pitchers.empty else 0

        max_games_in_season = max(max_batter_games, max_pitcher_games)

        if max_games_in_season >= self.min_games_for_trusted:
            self.projection_seasons = self.load_seasons
            self.projection_trusted = True
        else:
            self.projection_seasons = self.load_seasons[:-1]
            self.projection_trusted = False
            print(
                f"WARNING: {max_season} has max {max_games_in_season} games "
                f"(threshold: {self.min_games_for_trusted}). "
                f"Not used in projections."
            )

    def save_data(self) -> None:
        """
        Write all processed DataFrames to CSV files.

        Saves up to four file pairs depending on what was generated:

        - Aggregated pitching/batting files (always saved).
        - Historical pitching/batting files (saved when historical data exists).
        - New-season pitching/batting files (saved when ``new_season`` was set).

        File names are prefixed with the joined load-season years
        (e.g. ``'player-projected-stats-pp-Batting.csv'``).
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
        f_pname_new = "random-stats-pp-Pitching.csv" if self.generate_random_data else "stats-pp-Pitching.csv"
        f_bname_new = "random-stats-pp-Batting.csv" if self.generate_random_data else "stats-pp-Batting.csv"
        seasons_str = " ".join(str(season) for season in self.load_seasons)

        # Save aggregated data (with 'aggr' in filename - for bbstats.py)
        self.pitching_data.to_csv(f"{seasons_str} {f_pname_aggr}", index=True, header=True)
        self.batting_data.to_csv(f"{seasons_str} {f_bname_aggr}", index=True, header=True)
        print(f"Saved aggregated files: {seasons_str} {f_pname_aggr} and {f_bname_aggr}")

        # Save historical year-by-year data (new)
        if self.pitching_data_historical is not None:
            f_hist_pname = "random-historical-Pitching.csv" if self.generate_random_data else "historical-Pitching.csv"
            self.pitching_data_historical.index.name = "Player_Season_Key"
            self.pitching_data_historical.to_csv(f"{seasons_str} {f_hist_pname}", index=True, header=True)
            print(f"Saved historical pitching data: {seasons_str} {f_hist_pname}")

        if self.batting_data_historical is not None:
            f_hist_bname = "random-historical-Batting.csv" if self.generate_random_data else "historical-Batting.csv"
            self.batting_data_historical.index.name = "Player_Season_Key"
            self.batting_data_historical.to_csv(f"{seasons_str} {f_hist_bname}", index=True, header=True)
            print(f"Saved historical batting data: {seasons_str} {f_hist_bname}")

        # Save new season data (no 'aggr' prefix - this is single season data, not aggregated)
        # Preserve existing stats if games have already been played
        if self.new_season is not None:
            new_season_batting_file = f"{self.new_season} New-Season-{f_bname_new}"
            new_season_pitching_file = f"{self.new_season} New-Season-{f_pname_new}"

            # Check if existing file has games played - if so, preserve it
            # Only preserve if current data has no valid games (all zeros from failed merge)
            current_games = (
                self.new_season_batting_data["G"].sum() if "G" in self.new_season_batting_data.columns else 0
            )
            if os.path.exists(new_season_batting_file) and current_games == 0:
                existing_batting = pd.read_csv(new_season_batting_file, index_col="Hashcode")
                existing_games = existing_batting["G"].sum() if "G" in existing_batting.columns else 0
                if existing_games > 0:
                    # Preserve: copy existing stats to new_season_data
                    for col in self.numeric_bcols:
                        if col in self.new_season_batting_data.columns and col in existing_batting.columns:
                            self.new_season_batting_data[col] = existing_batting[col].fillna(0)
                    # Preserve non-numeric columns from existing
                    for col in existing_batting.columns:
                        if col not in self.numeric_bcols:
                            self.new_season_batting_data[col] = existing_batting[col]
                    print(f"Preserved existing batting stats ({existing_games} games)")

            if os.path.exists(new_season_pitching_file) and (
                self.new_season_pitching_data["G"].sum() == 0 if "G" in self.new_season_pitching_data.columns else True
            ):
                existing_pitching = pd.read_csv(new_season_pitching_file, index_col="Hashcode")
                existing_games = existing_pitching["G"].sum() if "G" in existing_pitching.columns else 0
                if existing_games > 0:
                    for col in self.numeric_pcols:
                        if col in self.new_season_pitching_data.columns and col in existing_pitching.columns:
                            self.new_season_pitching_data[col] = existing_pitching[col].fillna(0)
                    for col in existing_pitching.columns:
                        if col not in self.numeric_pcols:
                            self.new_season_pitching_data[col] = existing_pitching[col]
                    print(f"Preserved existing pitching stats ({existing_games} games)")

            self.new_season_pitching_data.index.name = "Hashcode"
            self.new_season_batting_data.index.name = "Hashcode"
            self.new_season_pitching_data.to_csv(new_season_pitching_file, index=True, header=True)
            self.new_season_batting_data.to_csv(new_season_batting_file, index=True, header=True)
        return

    @staticmethod
    def group_col_to_list(df: DataFrame, key_col: str, col: str, new_col: str) -> DataFrame:
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

        df[new_col] = df[key_col].map(groups)  # Create a new column to store grouped unique values
        df[new_col] = df[new_col].apply(list)  # Convert sets to lists for easier handling in DataFrame
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
        return "".join(self.digit_pos_map.get(digit, digit) + "," for digit in digit_string).rstrip(",")

    def calculate_league_averages(self, historical_df: pd.DataFrame, is_pitching: bool = False) -> dict:
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
            qualified_recent = qualified[qualified["Season"] == most_recent_season].copy()

            total_ip = max(1, qualified_recent["IP"].sum())
            total_g = max(1, qualified_recent["G"].sum())
            total_pa = max(1, qualified_recent["PA"].sum()) if "PA" in qualified_recent.columns else None

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
                    / (qualified_recent["PA"] - qualified_recent["SO"] - qualified_recent["BB"]).clip(lower=1).sum()
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
            qualified_recent = qualified[qualified["Season"] == most_recent_season].copy()

            # Denominator: Total Plate Appearances (from most recent season only)
            total_pa = max(
                1,
                qualified_recent["AB"].sum()
                + qualified_recent["BB"].sum()
                + qualified_recent.get("HBP", 0).sum()
                + qualified_recent.get("SF", 0).sum(),
            )
            total_ab = max(1, qualified_recent["AB"].sum())
            total_h = max(1, qualified_recent["H"].sum())  # Use Hits as the denominator for 2b, 3b, and HR
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
        self, df: DataFrame, key_name: str, dup_column_names: str, stats_cols_to_sum: List[str], drop_dups: bool = False
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
                df.loc[df[key_name] == dfrow_key, dfcol_name] = df_rows[dfcol_name].sum()
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

    def get_pitching_seasons(self, pitcher_file: str, load_seasons: List[int], projection_seasons: List[int]) -> tuple:
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
        ``Injury_Rate_Adj``, ``Injury_Perf_Adj``, ``Streak_Adjustment``,
        ``Projection_Trusted``.

        .. caution::
            WAR and salary columns are summed across seasons during the merge;
            interpret career totals accordingly.

        :param pitcher_file: Base filename for raw pitcher CSVs
            (year prefix added automatically).
        :param load_seasons: List of ALL season years to load (for historical data).
        :param projection_seasons: List of season years to use for projections.
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

        # remove pos players pitching
        pitching_data = pitching_data[~((pitching_data["IP"] < 10) & (pitching_data["G"] < 5))]
        pitching_data["Player"] = pitching_data["Player"].str.replace("*", "").str.replace("#", "")
        pitching_data["Hashcode"] = pitching_data["Player"].apply(lambda x: self.create_hash(x, "Pitcher"))

        # Filter salary to only Pitchers before merging
        pitcher_salaries = self.df_salary[self.df_salary["Role"] == "Pitcher"]
        pitching_data = pd.merge(pitching_data, pitcher_salaries, on="Hashcode", how="left")
        pitching_data = salary.fill_nan_salary(pitching_data, "Salary")  # set league min for missing data
        pitching_data["Team"] = pitching_data["Team"].apply(lambda x: x if x in self.nl + self.al else "")

        # players with multiple teams have a 2TM or 3TM line that is the total of all stats.  Drop rows since we total
        pitching_data = pitching_data[pitching_data["Team"] != ""]  # drop rows without a formal team name
        pitching_data["League"] = pitching_data["Team"].apply(
            lambda x: "NL" if x in self.nl else ("AL" if x in self.al else "")
        )
        pitching_data["Division"] = pitching_data["Team"].map(self.team_division).fillna("")

        # Create Player_Season_Key BEFORE de-duplication
        pitching_data["Player_Season_Key"] = (
            pitching_data["Hashcode"].astype(str) + "_" + pitching_data["Season"].astype(str)
        )
        outs = (pitching_data["IP"].astype(int) * 3) + np.round((pitching_data["IP"] % 1) * 10)
        pitching_data["PA"] = outs + pitching_data["H"] + pitching_data["BB"] + pitching_data.get("HBP", 0)

        # *** Create HISTORICAL data (year-by-year) - one row per player per season ***
        historical_data = pitching_data.copy()
        historical_data = self.group_col_to_list(
            df=historical_data, key_col="Player_Season_Key", col="Team", new_col="Teams"
        )
        historical_data = self.group_col_to_list(
            df=historical_data, key_col="Player_Season_Key", col="League", new_col="Leagues"
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
        # Filter to projection_seasons for league averages, note this may not include a partial season (2026)
        league_avg_data = pitching_data[pitching_data["Season"].isin(projection_seasons)].copy()
        max_season = max(load_seasons)

        # Identify rookies: players who only appear in max season
        all_seasons_data = pitching_data.copy()
        player_seasons = all_seasons_data.groupby("Hashcode")["Season"].apply(set)
        rookies = player_seasons[player_seasons.apply(lambda x: len(x) == 1 and max_season in x)].index.tolist()

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
        league_averages = self.calculate_league_averages(historical_df=league_avg_data, is_pitching=True)

        # ensure data is clean (no NaN, no inf)
        players_before_filter = len(pitching_data["Hashcode"].unique())
        projection_data_clean = pitching_data.copy()
        projection_data_clean = projection_data_clean.replace([np.inf, -np.inf], np.nan)
        projection_data_clean = projection_data_clean.dropna(subset=["IP", "H", "BB", "SO"])

        valid_players = projection_data_clean["Hashcode"].unique()
        projection_data_filtered = projection_data_clean[projection_data_clean["Hashcode"].isin(valid_players)]

        projector = player_projector.PlayerProjector(league_averages)
        pitching_data = projector.calculate_projected_stats(
            history=projection_data_filtered, stats=stats_to_project, is_p=True
        )
        pitching_data = pitching_data.set_index("Hashcode")
        # most_recent_season = max(projection_seasons) if projection_seasons else max(load_seasons)
        # pitching_data["Should_Retain"] = pitching_data.apply(
        #     lambda row: self.is_active_candidate(
        #         row["Years_Included"],
        #         row["Age"],
        #         row.get("WAR", 0),  # Use actual WAR if available
        #         most_recent_season,
        #     ),
        #     axis=1,
        # )

        # Also retain rookies (only in max season) - they will be flagged as untrusted
        # pitching_data.loc[pitching_data.index.isin(rookies), "Should_Retain"] = True

        # pitching_data = pitching_data[pitching_data["Should_Retain"]]
        # pitching_data = pitching_data.drop("Should_Retain", axis=1)
        players_after_filter = len(pitching_data)

        # Add Projection_Trusted flag

        print(
            f"Pitchers: Filtered {players_before_filter - players_after_filter} players with insuffucient data. (kept {players_after_filter})"
        )
        if not self.projection_trusted:
            print(f"         rookie count {len(rookies)}")
            rookie_count = len([p for p in rookies if p in pitching_data.index])
            print(f"         {rookie_count} x-ref players (only in {max_season})")

        # Apply random data jigger if needed (to both datasets)
        if self.generate_random_data:
            for stats_col in stats_pcols_sum:
                pitching_data[stats_col] = pitching_data[stats_col].apply(self.jigger_data)
                historical_data[stats_col] = historical_data[stats_col].apply(self.jigger_data)

        # Calculate derived stats for AGGREGATED data
        # 1. Convert .1/.2 format to total outs
        outs = (pitching_data["IP"].astype(int) * 3) + np.round((pitching_data["IP"] % 1) * 10)
        pitching_data["AB"] = outs + pitching_data["H"]
        pitching_data["2B"] = 0
        pitching_data["3B"] = 0
        pitching_data["HBP"] = 0
        pitching_data["Season"] = str(
            max(projection_seasons) + 1 if projection_seasons else max(load_seasons) + 1
        )  # Projected year (e.g., 2026)
        pitching_data["OBP"] = pitching_data["WHIP"] / (3 + pitching_data["WHIP"])  # bat reached / number faced
        pitching_data["Total_OB"] = pitching_data["H"] + pitching_data["BB"]  # + pitching_data['HBP']
        pitching_data["Total_Outs"] = pitching_data["IP"] * 3  # 3 outs per inning
        pitching_data = pitching_data[
            pitching_data["IP"] >= 1
        ]  # drop pitchers without any meaningful innings (reduced from 5 to 1)
        pitching_data["AVG_faced"] = (pitching_data["Total_OB"] + pitching_data["Total_Outs"]) / pitching_data.G
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
        if "Projection_Trusted" not in historical_data.columns:
            historical_data["Projection_Trusted"] = True  # Historical data is always trusted
        return pitching_data, historical_data

    def get_batting_seasons(self, batter_file: str, load_seasons: List[int], projection_seasons: List[int]) -> tuple:
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
        ``Streak_Adjustment``, ``Projection_Trusted``.

        Same columns are also calculated for the historical DataFrame.

        .. caution::
            WAR and salary columns are summed across seasons during the merge.

        :param batter_file: Base filename for raw batter CSVs
            (year prefix added automatically).
        :param load_seasons: List of ALL season years to load (for historical data).
        :param projection_seasons: List of season years to use for projections.
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
            ["Rk", "Lg", "OPS+", "rOBA", "Rbat+", "TB", "IBB", "Awards", "Player-additional"], inplace=True, axis=1
        )
        batting_data["Player"] = batting_data["Player"].str.replace("#", "").str.replace("*", "")
        batting_data["Hashcode"] = batting_data["Player"].apply(lambda x: self.create_hash(x, "Hitter"))

        # Filter salary to only Hitters before merging
        hitter_salaries = self.df_salary[self.df_salary["Role"] == "Hitter"]
        batting_data = pd.merge(batting_data, hitter_salaries, on="Hashcode", how="left")
        batting_data = salary.fill_nan_salary(batting_data, "Salary")  # set league min for missing data
        batting_data["Pos"] = batting_data["Pos"].apply(self.remove_non_numeric).apply(self.translate_pos)
        # DON'T group by Hashcode yet - we need year-by-year data for historical file
        batting_data["Team"] = batting_data["Team"].apply(lambda x: x if x in self.nl + self.al else "")
        batting_data["League"] = batting_data["Team"].apply(
            lambda x: "NL" if x in self.nl else ("AL" if x in self.al else "")
        )
        batting_data["Division"] = batting_data["Team"].map(self.team_division).fillna("")
        # players with multiple teams have a 2TM or 3TM line that is the total of all stats.  Drop rows since we total
        batting_data = batting_data[batting_data["Team"] != ""]  # drop rows without a formal team name
        # Create Player_Season_Key BEFORE de-duplication
        batting_data["Player_Season_Key"] = (
            batting_data["Hashcode"].astype(str) + "_" + batting_data["Season"].astype(str)
        )
        batting_data["PA"] = batting_data["AB"] + batting_data["BB"] + batting_data["HBP"] + batting_data["SF"]

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
            df=historical_data, key_col="Player_Season_Key", col="League", new_col="Leagues"
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
        # Filter to projection_seasons for league averages and projections, note may not include partial years (2026)
        league_average_data = batting_data[batting_data["Season"].isin(projection_seasons)].copy()
        max_season = max(load_seasons)

        # Identify rookies: players who only appear in max season
        all_seasons_data = batting_data.copy()
        player_seasons = all_seasons_data.groupby("Hashcode")["Season"].apply(set)
        rookies = player_seasons[player_seasons.apply(lambda x: len(x) == 1 and max_season in x)].index.tolist()
        rookie_count = len(rookies)

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
        league_averages = self.calculate_league_averages(league_average_data, is_pitching=False)

        # Filter projection_data to only include players with valid history for projection
        players_before = len(batting_data["Hashcode"].unique())
        projection_data_filtered = batting_data.copy()
        projector = player_projector.PlayerProjector(league_averages=league_averages)
        batting_data = projector.calculate_projected_stats(
            history=projection_data_filtered, stats=stats_to_project, is_p=False
        )

        # most_recent_season = max(projection_seasons) if projection_seasons else max(load_seasons)
        # Apply the probability logic instead of the hard 'In_Recent_Season' check
        # batting_data["Should_Retain"] = batting_data.apply(
        #     lambda row: self.is_active_candidate(
        #         row["Years_Included"],
        #         row["Age"],
        #         row.get("WAR", 0),  # Use actual WAR if available
        #         most_recent_season,
        #     ),
        #     axis=1,
        # )

        # Also retain rookies (only in max season) - they will be flagged as untrusted
        # batting_data.loc[batting_data.index.isin(rookies), "Should_Retain"] = True
        # batting_data = batting_data[batting_data["Should_Retain"]]
        # batting_data = batting_data.drop("Should_Retain", axis=1)

        # Add Projection_Trusted flag
        # batting_data["Projection_Trusted"] = ~batting_data.index.isin(rookies)

        batting_data = batting_data.set_index("Hashcode")
        print(
            f"Batters: Retained {len(batting_data)} players (Filtered {players_before - len(batting_data)} retired/inactive)"
        )
        if not self.projection_trusted:
            print(f"         rookie count {rookie_count}")
            rookie_count = len([p for p in rookies if p in batting_data.index])
            print(f"         {rookie_count} x-ref players (only in {max_season})")

        # Apply random data jigger if needed (to both datasets)
        if self.generate_random_data:
            for stats_col in stats_bcols_sum:
                batting_data[stats_col] = batting_data[stats_col].apply(self.jigger_data)
                historical_data[stats_col] = historical_data[stats_col].apply(self.jigger_data)

        # Calculate derived stats for AGGREGATED data
        batting_data["Season"] = str(
            max(projection_seasons) + 1 if projection_seasons else max(load_seasons) + 1
        )  # Projected year (e.g., 2026)
        batting_data["OBP"] = self.trunc_col(
            np.nan_to_num(
                np.divide(
                    batting_data["H"] + batting_data["BB"] + batting_data["HBP"],
                    batting_data["AB"] + batting_data["BB"] + batting_data["HBP"] + batting_data.get("SF", 0),
                ),
                nan=0.0,
                posinf=0.0,
            ),
            3,
        )

        batting_data["SLG"] = self.trunc_col(
            np.nan_to_num(
                np.divide(
                    (batting_data["H"] - batting_data["2B"] - batting_data["3B"] - batting_data["HR"])
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
            np.nan_to_num(batting_data["OBP"] + batting_data["SLG"], nan=0.0, posinf=0.0), 3
        )
        batting_data["Total_OB"] = batting_data["H"] + batting_data["BB"] + batting_data["HBP"]
        batting_data["Total_Outs"] = batting_data["AB"] - batting_data["H"]
        batting_data = batting_data[batting_data["AB"] >= 1]  # drop players without enough AB
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
                    historical_data["H"] + historical_data["BB"] + historical_data["HBP"],
                    historical_data["AB"] + historical_data["BB"] + historical_data["HBP"],
                ),
                nan=0.0,
                posinf=0.0,
            ),
            3,
        )
        historical_data["SLG"] = self.trunc_col(
            np.nan_to_num(
                np.divide(
                    (historical_data["H"] - historical_data["2B"] - historical_data["3B"] - historical_data["HR"])
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
            np.nan_to_num(historical_data["OBP"] + historical_data["SLG"], nan=0.0, posinf=0.0), 3
        )
        historical_data["Total_OB"] = historical_data["H"] + historical_data["BB"] + historical_data["HBP"]
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
        if "Projection_Trusted" not in historical_data.columns:
            historical_data["Projection_Trusted"] = True  # Historical data is always trusted

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
            pitcher_file, self.load_seasons, self.projection_seasons
        )
        self.batting_data, self.batting_data_historical = self.get_batting_seasons(
            batter_file, self.load_seasons, self.projection_seasons
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
                self.pitching_data["Team"] = self.pitching_data["Team"].replace(old_team, new_team)
                remapped_teams.append(f"Pitching: {old_team} → {new_team}")

        # Apply remapping to batting data (aggregated)
        for old_team, new_team in self.team_remapping.items():
            if old_team in self.batting_data["Team"].values:
                self.batting_data["Team"] = self.batting_data["Team"].replace(old_team, new_team)
                if f"Pitching: {old_team} → {new_team}" not in remapped_teams:
                    remapped_teams.append(f"Batting: {old_team} → {new_team}")

        # Apply remapping to historical data as well
        if self.pitching_data_historical is not None:
            for old_team, new_team in self.team_remapping.items():
                if old_team in self.pitching_data_historical["Team"].values:
                    self.pitching_data_historical["Team"] = self.pitching_data_historical["Team"].replace(
                        old_team, new_team
                    )

        if self.batting_data_historical is not None:
            for old_team, new_team in self.team_remapping.items():
                if old_team in self.batting_data_historical["Team"].values:
                    self.batting_data_historical["Team"] = self.batting_data_historical["Team"].replace(
                        old_team, new_team
                    )

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

        prior_season = max(self.projection_seasons) if self.projection_seasons else max(self.load_seasons)
        print(f"Calculating Def_WAR from {prior_season} season data...")

        # === PITCHERS ===
        if self.pitching_data_historical is not None:
            prior_p = self.pitching_data_historical[self.pitching_data_historical["Season"] == prior_season].copy()
            prior_p = prior_p[prior_p["IP"] >= 5].copy()

            if not prior_p.empty:
                prior_p["FIP"] = ((13 * prior_p["HR"] + 3 * prior_p["BB"] - 2 * prior_p["SO"]) / prior_p["IP"]) + 3.10
                league_fip = prior_p["FIP"].mean()
                replacement_fip = league_fip + 1.0
                prior_p["Calculated_Sim_WAR"] = ((replacement_fip - prior_p["FIP"]) / 9.0) * prior_p["IP"] / 10.0
                prior_p["Def_WAR"] = prior_p["WAR"] - prior_p["Calculated_Sim_WAR"]

                def_war_p_map = (
                    prior_p[["Hashcode", "Def_WAR", "WAR"]].drop_duplicates("Hashcode").set_index("Hashcode")
                )

                if "Def_WAR" in self.pitching_data.columns:
                    self.pitching_data.drop("Def_WAR", axis=1, inplace=True)

                self.pitching_data = self.pitching_data.join(def_war_p_map["Def_WAR"], how="left")
                self.pitching_data["Def_WAR"] = self.pitching_data["Def_WAR"].fillna(0.0)
                self.pitching_data["WAR"] = def_war_p_map["WAR"].combine_first(self.pitching_data["WAR"])
                print(f"  Pitchers: Added Def_WAR for {(self.pitching_data['Def_WAR'] != 0).sum()} players")
            else:
                self.pitching_data["Def_WAR"] = 0.0

        # === BATTERS ===
        if self.batting_data_historical is not None:
            prior_b = self.batting_data_historical[self.batting_data_historical["Season"] == prior_season].copy()
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
                prior_b["PA_calc"] = prior_b["AB"] + prior_b["BB"] + prior_b["HBP"] + prior_b.get("SF", 0)
                prior_b["wOBA"] = woba_num / prior_b["PA_calc"].replace(0, 1)

                # 2. Calculate Sim_WAR
                league_woba = prior_b["wOBA"].mean()
                replacement_woba = league_woba - 0.020
                prior_b["Calculated_Sim_WAR"] = (
                    ((prior_b["wOBA"] - replacement_woba) / 1.15) * prior_b["PA_calc"] / 10.0
                )

                # 3. Calculate Def_WAR (Baserunning + Defense)
                prior_b["Def_WAR"] = prior_b["WAR"] - prior_b["Calculated_Sim_WAR"]

                # 4. Create mapping and Join
                def_war_b_map = (
                    prior_b[["Hashcode", "Def_WAR", "WAR"]].drop_duplicates("Hashcode").set_index("Hashcode")
                )

                if "Def_WAR" in self.batting_data.columns:
                    self.batting_data.drop("Def_WAR", axis=1, inplace=True)

                self.batting_data = self.batting_data.join(def_war_b_map["Def_WAR"], how="left")
                self.batting_data["Def_WAR"] = self.batting_data["Def_WAR"].fillna(0.0)
                self.batting_data["WAR"] = def_war_b_map["WAR"].combine_first(self.batting_data["WAR"])

                print(f"  Batters: Added Def_WAR for {(self.batting_data['Def_WAR'] != 0).sum()} players")
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
        if np.min(self.batting_data.index) == 0 or np.min(self.pitching_data.index) == 0:  # last ditch check key error
            raise Exception("Index value cannot be zero")  # screws up bases where 0 is no runner
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
        league_names = ["ACB", "NBL"]  # Armchair Baseball and Nerd Baseball, Some Other League SOL, No Name NNL

        # Update aggregated data
        self.pitching_data.loc[self.pitching_data["League"] == "AL", "League"] = league_names[0]
        self.pitching_data.loc[self.pitching_data["League"] == "NL", "League"] = league_names[1]
        self.pitching_data["Leagues"] = self.pitching_data["League"].apply(lambda x: [x])
        self.batting_data.loc[self.batting_data["League"] == "AL", "League"] = league_names[0]
        self.batting_data.loc[self.batting_data["League"] == "NL", "League"] = league_names[1]
        self.batting_data["Leagues"] = self.batting_data["League"].apply(lambda x: [x])

        # Update historical data
        if self.pitching_data_historical is not None:
            self.pitching_data_historical.loc[self.pitching_data_historical["League"] == "AL", "League"] = league_names[
                0
            ]
            self.pitching_data_historical.loc[self.pitching_data_historical["League"] == "NL", "League"] = league_names[
                1
            ]
            self.pitching_data_historical["Leagues"] = self.pitching_data_historical["League"].apply(lambda x: [x])

        if self.batting_data_historical is not None:
            self.batting_data_historical.loc[self.batting_data_historical["League"] == "AL", "League"] = league_names[0]
            self.batting_data_historical.loc[self.batting_data_historical["League"] == "NL", "League"] = league_names[1]
            self.batting_data_historical["Leagues"] = self.batting_data_historical["League"].apply(lambda x: [x])

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
        current_team_names = self.batting_data.Team.unique()  # get list of current team names
        city_abbrev = [str(name[:3]).upper() for name in city.names]  # city names are imported
        mascots = self.randomize_mascots(len(city.names))
        for ii, team_abbrev in enumerate(city_abbrev):
            city_dict.update({city_abbrev[ii]: [city.names[ii], mascots[ii]]})  # update will use the last unique abbrev

        new_teams = list(random.sample(city_abbrev, len(current_team_names)))
        for ii, team in enumerate(current_team_names):  # do not use a df merge here resets the index, that is bad
            new_team = new_teams[ii]
            mascot = city_dict[new_team][1]
            city_name = city_dict[new_team][0]

            # Update aggregated data
            self.pitching_data.replace([team], [new_team], inplace=True)
            self.pitching_data.loc[self.pitching_data["Team"] == new_team, "City"] = city_name
            self.pitching_data["Teams"] = self.pitching_data["Team"].apply(lambda x: [x])
            self.pitching_data.loc[self.pitching_data["Team"] == new_team, "Mascot"] = mascot
            self.batting_data.replace([team], [new_team], inplace=True)
            self.batting_data.loc[self.batting_data["Team"] == new_team, "City"] = city_name
            self.batting_data["Teams"] = self.batting_data["Team"].apply(lambda x: [x])
            self.batting_data.loc[self.batting_data["Team"] == new_team, "Mascot"] = mascot

            # Update historical data
            if self.pitching_data_historical is not None:
                self.pitching_data_historical.replace([team], [new_team], inplace=True)
                self.pitching_data_historical.loc[self.pitching_data_historical["Team"] == new_team, "City"] = city_name
                self.pitching_data_historical["Teams"] = self.pitching_data_historical["Team"].apply(lambda x: [x])
                self.pitching_data_historical.loc[self.pitching_data_historical["Team"] == new_team, "Mascot"] = mascot

            if self.batting_data_historical is not None:
                self.batting_data_historical.replace([team], [new_team], inplace=True)
                self.batting_data_historical.loc[self.batting_data_historical["Team"] == new_team, "City"] = city_name
                self.batting_data_historical["Teams"] = self.batting_data_historical["Team"].apply(lambda x: [x])
                self.batting_data_historical.loc[self.batting_data_historical["Team"] == new_team, "Mascot"] = mascot

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
        for ii in range(1, (df.shape[0] + 1) * 2):  # generate twice as many random names as needed
            random_names.append(random.choice(first_names) + " " + random.choice(last_names))
        random_names = list(set(random_names))  # drop non-unique names
        random_names = random.sample(random_names, self.batting_data.shape[0] + self.pitching_data.shape[0])

        # load new names and reset hashcode index for AGGREGATED data
        self.batting_data["Player"] = random_names[: len(self.batting_data)]  # grab first x rows of list
        self.batting_data = self.batting_data.reset_index()
        self.batting_data["Hashcode"] = self.batting_data["Player"].apply(lambda x: self.create_hash(x, "Hitter"))
        self.batting_data = self.batting_data.set_index("Hashcode")

        self.pitching_data["Player"] = random_names[-len(self.pitching_data) :]  # next x rows list
        self.pitching_data = self.pitching_data.reset_index()
        self.pitching_data["Hashcode"] = self.pitching_data["Player"].apply(lambda x: self.create_hash(x, "Pitcher"))
        self.pitching_data = self.pitching_data.set_index("Hashcode")

        # Update HISTORICAL data with same player names (need to map old hashcode to new)
        # Create mapping from old hashcode to new player name
        if self.batting_data_historical is not None:
            # Extract hashcode from Player_Season_Key (format: hashcode_season)
            self.batting_data_historical = self.batting_data_historical.reset_index()
            self.batting_data_historical["Old_Hashcode"] = (
                self.batting_data_historical["Player_Season_Key"].str.split("_").str[0].apply(int)
            )
            # Map old hashcode to new player name from aggregated data
            old_to_new_player = dict(
                zip(self.batting_data.reset_index()["Hashcode"], self.batting_data.reset_index()["Player"])
            )
            self.batting_data_historical["Player"] = self.batting_data_historical["Old_Hashcode"].map(old_to_new_player)
            # Recalculate hashcode and Player_Season_Key
            self.batting_data_historical["Hashcode"] = self.batting_data_historical["Player"].apply(
                lambda x: self.create_hash(x, "Hitter")
            )
            self.batting_data_historical["Player_Season_Key"] = (
                self.batting_data_historical["Hashcode"].astype(str)
                + "_"
                + self.batting_data_historical["Season"].astype(str)
            )
            self.batting_data_historical = self.batting_data_historical.drop("Old_Hashcode", axis=1)
            self.batting_data_historical = self.batting_data_historical.set_index("Player_Season_Key")

        if self.pitching_data_historical is not None:
            self.pitching_data_historical = self.pitching_data_historical.reset_index()
            self.pitching_data_historical["Old_Hashcode"] = (
                self.pitching_data_historical["Player_Season_Key"].str.split("_").str[0].apply(int)
            )
            old_to_new_player = dict(
                zip(self.pitching_data.reset_index()["Hashcode"], self.pitching_data.reset_index()["Player"])
            )
            self.pitching_data_historical["Player"] = self.pitching_data_historical["Old_Hashcode"].map(
                old_to_new_player
            )
            self.pitching_data_historical["Hashcode"] = self.pitching_data_historical["Player"].apply(
                lambda x: self.create_hash(x, "Pitcher")
            )
            self.pitching_data_historical["Player_Season_Key"] = (
                self.pitching_data_historical["Hashcode"].astype(str)
                + "_"
                + self.pitching_data_historical["Season"].astype(str)
            )
            self.pitching_data_historical = self.pitching_data_historical.drop("Old_Hashcode", axis=1)
            self.pitching_data_historical = self.pitching_data_historical.set_index("Player_Season_Key")

        return

    def create_new_season_from_existing(self, load_batter_file: str, load_pitcher_file: str) -> None:
        """
        Generate new-season DataFrames with rate stats preserved and counting stats zeroed.

        Uses projected stats from previous seasons as the base for new season.
        If max season is partial, merges partial season stats into new season file
        for accumulation. Always includes max season in historical file.

        The projected stats come from projection_seasons (which excludes max season
        if it's below the min_games_for_trusted threshold).

        Results are stored in ``self.new_season_pitching_data`` and
        ``self.new_season_batting_data``.

        :param load_batter_file: Base batter file name.
        :param load_pitcher_file: Base pitcher file name.
        :raises Exception: If pitching or batting data has not been loaded yet.
        """
        if self.pitching_data is None or self.batting_data is None:
            raise Exception("load at least one season of pitching and batting")

        # Load partial season data for merging (if max season exists and is partial)
        max_season = max(self.load_seasons)
        partial_season_data = None
        if max_season not in self.projection_seasons:
            # Max season was excluded from projections, load it for partial stats
            partial_season_data = self._load_partial_season_data(load_batter_file, load_pitcher_file, max_season)

        # --- Pitching ---
        self.new_season_pitching_data = self.pitching_data.copy()
        self.new_season_pitching_data[self.numeric_pcols] = self.new_season_pitching_data[self.numeric_pcols].astype(
            "int"
        )
        self.new_season_pitching_data["Season"] = str(self.new_season)

        # IP can be decimal (e.g., 12.1 = 12 1/3 innings), change column to float
        self.new_season_pitching_data["IP"] = self.new_season_pitching_data["IP"].astype(float)

        # Calculate projected rate stats from counting stats before zeroing
        pp = self.new_season_pitching_data
        pp["ERA"] = self.trunc_col(np.nan_to_num(np.divide(pp["ER"] * 9, pp["IP"]), nan=0.0, posinf=0.0), 2)
        pp["WHIP"] = self.trunc_col(np.nan_to_num(np.divide(pp["BB"] + pp["H"], pp["IP"]), nan=0.0, posinf=0.0), 3)
        pp["OBP"] = self.trunc_col(np.nan_to_num(np.divide(pp["WHIP"], 3 + pp["WHIP"]), nan=0.0, posinf=0.0), 3)

        # Merge partial season stats if available
        if partial_season_data is not None and "pitching" in partial_season_data:
            partial_pitch = partial_season_data["pitching"]
            for idx in self.new_season_pitching_data.index:
                if idx in partial_pitch.index:
                    partial_row = partial_pitch.loc[idx]
                    g_val = partial_row["G"] if "G" in partial_row.index else None
                    if (
                        g_val is not None and pd.notna(g_val).any()
                        if hasattr(pd.notna(g_val), "any")
                        else pd.notna(g_val)
                    ):
                        # Update team info from partial data (in case of mid-season trades)
                        if "Team" in partial_row.index and pd.notna(partial_row.get("Team")):
                            self.new_season_pitching_data.loc[idx, "Team"] = partial_row["Team"]
                        if "League" in partial_row.index and pd.notna(partial_row.get("League")):
                            self.new_season_pitching_data.loc[idx, "League"] = partial_row["League"]
                        if "Division" in partial_row.index and pd.notna(partial_row.get("Division")):
                            self.new_season_pitching_data.loc[idx, "Division"] = partial_row["Division"]
                        self.new_season_pitching_data.loc[idx, "G"] = int(partial_row.get("G", 0))
                        self.new_season_pitching_data.loc[idx, "GS"] = int(partial_row.get("GS", 0))
                        ip_val = partial_row.get("IP", 0)
                        if pd.notna(ip_val):
                            self.new_season_pitching_data.at[idx, "IP"] = float(ip_val)
                        self.new_season_pitching_data.loc[idx, "H"] = int(partial_row.get("H", 0))
                        self.new_season_pitching_data.loc[idx, "ER"] = int(partial_row.get("ER", 0))
                        self.new_season_pitching_data.loc[idx, "BB"] = int(partial_row.get("BB", 0))
                        self.new_season_pitching_data.loc[idx, "SO"] = int(partial_row.get("SO", 0))
                        self.new_season_pitching_data.loc[idx, "HR"] = int(partial_row.get("HR", 0))
                        self.new_season_pitching_data.loc[idx, "W"] = int(partial_row.get("W", 0))
                        self.new_season_pitching_data.loc[idx, "L"] = int(partial_row.get("L", 0))
                        self.new_season_pitching_data.loc[idx, "SV"] = int(partial_row.get("SV", 0))
                    else:
                        # Player in partial data but no valid games - zero out
                        self.new_season_pitching_data.loc[idx, self.numeric_pcols] = 0
                        self.new_season_pitching_data.loc[
                            idx,
                            [
                                "ERA",
                                "WHIP",
                                "OBP",
                                "AVG_faced",
                                "Total_OB",
                                "Total_Outs",
                                "AB",
                                "HLD",
                                "BS",
                                "Injured Days",
                            ],
                        ] = 0
                else:
                    # Player not in partial data - zero out (hasn't pitched yet)
                    self.new_season_pitching_data.loc[idx, self.numeric_pcols] = 0
                    self.new_season_pitching_data.loc[
                        idx,
                        [
                            "ERA",
                            "WHIP",
                            "OBP",
                            "AVG_faced",
                            "Total_OB",
                            "Total_Outs",
                            "AB",
                            "HLD",
                            "BS",
                            "Injured Days",
                        ],
                    ] = 0

            # Recalculate derived stats from partial data
            pp = self.new_season_pitching_data
            pp["ERA"] = self.trunc_col(
                np.nan_to_num(np.divide(pp["ER"] * 9, pp["IP"].replace(0, np.nan)), nan=0.0, posinf=0.0), 2
            )
            pp["WHIP"] = self.trunc_col(
                np.nan_to_num(np.divide(pp["BB"] + pp["H"], pp["IP"].replace(0, np.nan)), nan=0.0, posinf=0.0), 3
            )
            pp["OBP"] = self.trunc_col(np.nan_to_num(np.divide(pp["WHIP"], 3 + pp["WHIP"]), nan=0.0, posinf=0.0), 3)
            pp["Total_OB"] = pp["H"] + pp["BB"]
            pp["Total_Outs"] = pp["IP"] * 3
            pp["AVG_faced"] = self.trunc_col(
                np.nan_to_num(
                    np.divide(pp["Total_OB"] + pp["Total_Outs"], pp["G"].replace(0, np.nan)), nan=0.0, posinf=0.0
                ),
                3,
            )

        else:
            # Zero counting stats for simulation tracking (no partial data)
            self.new_season_pitching_data[self.numeric_pcols] = 0
            self.new_season_pitching_data[
                ["ERA", "WHIP", "OBP", "AVG_faced", "Total_OB", "Total_Outs", "AB", "HLD", "BS", "Injured Days"]
            ] = 0

        self.new_season_pitching_data["Condition"] = 100
        self.new_season_pitching_data["Streak_Adjustment"] = 0.0
        if self.new_season not in self.load_seasons:  # add a year to age if it is the next year
            self.new_season_pitching_data["Age"] = self.new_season_pitching_data["Age"] + 1

        # --- Batting ---
        self.new_season_batting_data = self.batting_data.copy()
        self.new_season_batting_data["Season"] = str(self.new_season)

        # Calculate projected rate stats from counting stats before zeroing
        bp = self.new_season_batting_data
        bp["AVG"] = self.trunc_col(np.nan_to_num(np.divide(bp["H"], bp["AB"]), nan=0.0, posinf=0.0), 3)
        bp["OBP"] = self.trunc_col(
            np.nan_to_num(
                np.divide(bp["H"] + bp["BB"] + bp["HBP"], bp["AB"] + bp["BB"] + bp["HBP"] + bp.get("SF", 0)),
                nan=0.0,
                posinf=0.0,
            ),
            3,
        )
        bp["SLG"] = self.trunc_col(
            np.nan_to_num(
                np.divide(
                    (bp["H"] - bp["2B"] - bp["3B"] - bp["HR"]) + bp["2B"] * 2 + bp["3B"] * 3 + bp["HR"] * 4, bp["AB"]
                ),
                nan=0.0,
                posinf=0.0,
            ),
            3,
        )
        bp["OPS"] = self.trunc_col(np.nan_to_num(bp["OBP"] + bp["SLG"], nan=0.0, posinf=0.0), 3)
        if self.new_season not in self.load_seasons:  # add a year to age if it is the next year
            self.new_season_batting_data["Age"] = self.new_season_batting_data["Age"] + 1

        # Merge partial season stats if available
        if partial_season_data is not None and "batting" in partial_season_data:
            partial_bat = partial_season_data["batting"]
            for idx in self.new_season_batting_data.index:
                if idx in partial_bat.index:
                    partial_row = partial_bat.loc[idx]
                    g_val = partial_row["G"] if "G" in partial_row.index else None
                    if (
                        g_val is not None and pd.notna(g_val).any()
                        if hasattr(pd.notna(g_val), "any")
                        else pd.notna(g_val)
                    ):
                        self.new_season_batting_data.loc[idx, "G"] = int(partial_row.get("G", 0))
                        self.new_season_batting_data.loc[idx, "PA"] = int(partial_row.get("PA", 0))
                        self.new_season_batting_data.loc[idx, "AB"] = int(partial_row.get("AB", 0))
                        self.new_season_batting_data.loc[idx, "H"] = int(partial_row.get("H", 0))
                        self.new_season_batting_data.loc[idx, "R"] = int(partial_row.get("R", 0))
                        self.new_season_batting_data.loc[idx, "HR"] = int(partial_row.get("HR", 0))
                        self.new_season_batting_data.loc[idx, "RBI"] = int(partial_row.get("RBI", 0))
                        self.new_season_batting_data.loc[idx, "BB"] = int(partial_row.get("BB", 0))
                        self.new_season_batting_data.loc[idx, "SO"] = int(partial_row.get("SO", 0))
                        self.new_season_batting_data.loc[idx, "SB"] = int(partial_row.get("SB", 0))
                        self.new_season_batting_data.loc[idx, "CS"] = int(partial_row.get("CS", 0))
                        self.new_season_batting_data.loc[idx, "2B"] = int(partial_row.get("2B", 0))
                        self.new_season_batting_data.loc[idx, "3B"] = int(partial_row.get("3B", 0))
                        self.new_season_batting_data.loc[idx, "SH"] = int(partial_row.get("SH", 0))
                        self.new_season_batting_data.loc[idx, "SF"] = int(partial_row.get("SF", 0))
                        self.new_season_batting_data.loc[idx, "HBP"] = int(partial_row.get("HBP", 0))
                        self.new_season_batting_data.loc[idx, "GIDP"] = int(partial_row.get("GIDP", 0))
                        # Preserve team info from partial data (handles mid-season trades)
                        team_val = partial_row.get("Team")
                        if pd.notna(team_val):
                            self.new_season_batting_data.loc[idx, "Team"] = team_val
                        league_val = partial_row.get("League")
                        if pd.notna(league_val):
                            self.new_season_batting_data.loc[idx, "League"] = league_val
                        division_val = partial_row.get("Division")
                        if pd.notna(division_val):
                            self.new_season_batting_data.loc[idx, "Division"] = division_val
                    else:
                        # Player in partial data but no valid games - zero out
                        self.new_season_batting_data.loc[idx, self.numeric_bcols] = 0
                        self.new_season_batting_data.loc[
                            idx, ["AVG", "OBP", "SLG", "OPS", "Total_OB", "Total_Outs"]
                        ] = 0
                else:
                    # Player not in partial data - zero out (hasn't played yet)
                    self.new_season_batting_data.loc[idx, self.numeric_bcols] = 0
                    self.new_season_batting_data.loc[idx, ["AVG", "OBP", "SLG", "OPS", "Total_OB", "Total_Outs"]] = 0

            # Recalculate derived stats from partial data
            bp = self.new_season_batting_data
            bp["AVG"] = self.trunc_col(
                np.nan_to_num(np.divide(bp["H"], bp["AB"].replace(0, np.nan)), nan=0.0, posinf=0.0), 3
            )
            bp["OBP"] = self.trunc_col(
                np.nan_to_num(
                    np.divide(bp["H"] + bp["BB"] + bp["HBP"], bp["AB"] + bp["BB"] + bp["HBP"] + bp["SF"].fillna(0)),
                    nan=0.0,
                    posinf=0.0,
                ),
                3,
            )
            singles = bp["H"] - bp["2B"] - bp["3B"] - bp["HR"]
            bp["SLG"] = self.trunc_col(
                np.nan_to_num(
                    np.divide(singles + bp["2B"] * 2 + bp["3B"] * 3 + bp["HR"] * 4, bp["AB"].replace(0, np.nan)),
                    nan=0.0,
                    posinf=0.0,
                ),
                3,
            )
            bp["OPS"] = self.trunc_col(np.nan_to_num(bp["OBP"] + bp["SLG"], nan=0.0, posinf=0.0), 3)
            bp["Total_OB"] = bp["H"] + bp["BB"] + bp["HBP"]
            bp["Total_Outs"] = bp["AB"] - bp["H"]

        else:
            # Zero counting stats for simulation tracking (no partial data)
            self.new_season_batting_data[self.numeric_bcols] = 0
            self.new_season_batting_data[["AVG", "OBP", "SLG", "OPS", "Total_OB", "Total_Outs"]] = 0

        self.new_season_batting_data["Condition"] = 100
        self.new_season_batting_data["Streak_Adjustment"] = 0.0
        self.new_season_batting_data["Injured Days"] = 0

        # Ensure historical data includes partial season
        if partial_season_data is not None:
            self._merge_partial_season_to_historical(partial_season_data)

        return

    def _load_partial_season_data(self, batter_file: str, pitcher_file: str, season: int) -> dict:
        """
        Load partial season data for merging into new season file.

        Returns dict with 'pitching' and 'batting' DataFrames.
        """
        partial_data = {}

        try:
            pdf = pd.read_csv(f"{season} {pitcher_file}")
            pdf["Season"] = season
            pdf["Player"] = pdf["Player"].str.replace("*", "").str.replace("#", "")
            pdf["Hashcode"] = pdf["Player"].apply(lambda x: self.create_hash(x, "Pitcher"))
            pdf = pdf.set_index("Hashcode")
            partial_data["pitching"] = pdf
        except FileNotFoundError:
            partial_data["pitching"] = pd.DataFrame()

        try:
            bdf = pd.read_csv(f"{season} {batter_file}")
            bdf["Season"] = season
            bdf["Player"] = bdf["Player"].str.replace("*", "").str.replace("#", "")
            bdf["Hashcode"] = bdf["Player"].apply(lambda x: self.create_hash(x, "Hitter"))
            bdf = bdf.set_index("Hashcode")
            partial_data["batting"] = bdf
        except FileNotFoundError:
            partial_data["batting"] = pd.DataFrame()

        return partial_data if partial_data else None

    def _merge_partial_season_to_historical(self, partial_data: dict) -> None:
        """
        Merge partial season data into historical DataFrames.
        The partial season is determined from max(load_seasons).
        """
        max_season = max(self.load_seasons)

        if "pitching" in partial_data and not partial_data["pitching"].empty:
            # Drop existing rows for the partial season (they'll be replaced)
            if "Season" in self.pitching_data_historical.columns:
                self.pitching_data_historical = self.pitching_data_historical[
                    self.pitching_data_historical["Season"] != max_season
                ]
            # Add required columns if missing
            for col in ["Streak_Adjustment", "Projection_Trusted"]:
                if col not in partial_data["pitching"].columns:
                    partial_data["pitching"][col] = 0 if col == "Streak_Adjustment" else False
            # Fix index: create proper Player_Season_Key format
            partial_data["pitching"]["Player_Season_Key"] = (
                partial_data["pitching"].index.astype(str) + "_" + str(max_season)
            )
            partial_data["pitching"] = partial_data["pitching"].set_index("Player_Season_Key")
            self.pitching_data_historical = pd.concat([self.pitching_data_historical, partial_data["pitching"]], axis=0)

        if "batting" in partial_data and not partial_data["batting"].empty:
            # Drop existing rows for the partial season (they'll be replaced)
            if "Season" in self.batting_data_historical.columns:
                self.batting_data_historical = self.batting_data_historical[
                    self.batting_data_historical["Season"] != max_season
                ]
            # Add required columns if missing
            for col in ["Streak_Adjustment", "Projection_Trusted"]:
                if col not in partial_data["batting"].columns:
                    partial_data["batting"][col] = 0 if col == "Streak_Adjustment" else False
            # Fix index: create proper Player_Season_Key format
            partial_data["batting"]["Player_Season_Key"] = (
                partial_data["batting"].index.astype(str) + "_" + str(max_season)
            )
            partial_data["batting"] = partial_data["batting"].set_index("Player_Season_Key")
            self.batting_data_historical = pd.concat([self.batting_data_historical, partial_data["batting"]], axis=0)

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


def _safe_rate(num, denom, default=0.0):
    return num / denom if denom and denom > 0 else default


def projection_integrity_check(load_seasons: list = None):
    """Compare projected rates vs historical baselines in a single compact table."""
    if load_seasons is None:
        load_seasons = [2023, 2024, 2025]
    ss = " ".join(str(s) for s in load_seasons)

    b_proj = pd.read_csv(f"{ss} player-projected-stats-pp-Batting.csv")
    b_hist = pd.read_csv(f"{ss} historical-Batting.csv")
    p_proj = pd.read_csv(f"{ss} player-projected-stats-pp-Pitching.csv")
    p_hist = pd.read_csv(f"{ss} historical-Pitching.csv")

    prior = load_seasons[-1]
    b25 = b_hist[b_hist["Season"] == prior]
    b2325 = b_hist[b_hist["Season"].isin(load_seasons)]
    p25 = p_hist[p_hist["Season"] == prior]
    p2325 = p_hist[p_hist["Season"].isin(load_seasons)]

    def r(df, nc, dc):
        return _safe_rate(df[nc].sum(), df[dc].sum())

    def _singles(df):
        return df["H"] - df.get("2B", 0).fillna(0) - df.get("3B", 0).fillna(0) - df.get("HR", 0).fillna(0)

    def _slg(df):
        tb = (
            _singles(df) + 2 * df.get("2B", 0).fillna(0) + 3 * df.get("3B", 0).fillna(0) + 4 * df.get("HR", 0).fillna(0)
        )
        return _safe_rate(tb.sum(), df["AB"].sum())

    def _babip(df):
        bip = df["PA"] - df["SO"] - df["BB"]
        return _safe_rate(df["H"].sum(), bip.sum())

    def _obp_b(df):
        return _safe_rate((df["H"] + df["BB"]).sum(), df["PA"].sum())

    rows = [
        ("Batters:", None, None, None, None, None),
        ("  AVG", r(b2325, "H", "AB"), r(b25, "H", "AB"), r(b_proj, "H", "AB"), None, None),
        ("  OBP", _obp_b(b2325), _obp_b(b25), _obp_b(b_proj), None, None),
        ("  BB/PA", r(b2325, "BB", "PA"), r(b25, "BB", "PA"), r(b_proj, "BB", "PA"), None, None),
        ("  SO/PA", r(b2325, "SO", "PA"), r(b25, "SO", "PA"), r(b_proj, "SO", "PA"), None, None),
        ("  SLG", _slg(b2325), _slg(b25), _slg(b_proj), None, None),
        ("Pitchers:", None, None, None, None, None),
        ("  H/PA", r(p2325, "H", "PA"), r(p25, "H", "PA"), r(p_proj, "H", "PA"), None, None),
        ("  BB/PA", r(p2325, "BB", "PA"), r(p25, "BB", "PA"), r(p_proj, "BB", "PA"), None, None),
        ("  SO/PA", r(p2325, "SO", "PA"), r(p25, "SO", "PA"), r(p_proj, "SO", "PA"), None, None),
        ("  OBP Against", _obp_b(p2325), _obp_b(p25), _obp_b(p_proj), None, None),
        ("  BABIP", _babip(p2325), _babip(p25), _babip(p_proj), None, None),
    ]

    rows = [
        (
            lb,
            a,
            b,
            c,
            _safe_rate(c - a, 1) if c is not None and a is not None else None,
            _safe_rate(c - b, 1) if c is not None and b is not None else None,
        )
        for lb, a, b, c, _, _ in rows
    ]

    print("\n" + "=" * 95)
    print(f"{'INTEGRITY CHECK: PROJECTION vs HISTORICAL BASELINES':^95}")
    print("=" * 95)
    print(f"{'':<20} {'2023-2025 Blend':>16} {'2025 Only':>14} {'2026 Proj':>14} {'vs Blend':>12} {'vs 2025':>12}")
    print("-" * 95)
    for label, a, b, c, dvb, dv5 in rows:
        if label.endswith(":"):
            print(f"\n{label}")
        else:
            print(
                f"  {label:<18} {a:.4f}               {b:.4f}             {c:.4f}         {dvb:+.4f}          {dv5:+.4f}"
            )
    print("-" * 95)


if __name__ == "__main__":
    print("=" * 90)
    print("BASEBALL STATISTICS PREPROCESSING")
    print("=" * 90)

    print("\n[1/2] Running preprocessing to generate projection files...")
    baseball_data = BaseballStatsPreProcess(
        load_seasons=[2020, 2021, 2022, 2023, 2024, 2025, 2026],
        new_season=2026,
        generate_random_data=False,
        min_games_for_trusted=80,
        load_batter_file="player-stats-Batters.csv",
        load_pitcher_file="player-stats-Pitching.csv",
    )

    print("\n[2/2] Running integrity checks...")
    projection_integrity_check(load_seasons=[2020, 2021, 2022, 2023, 2024, 2025, 2026])

    print("\n")
    print("=" * 90)
    print("PREPROCESSING COMPLETE")
    print("=" * 90)
