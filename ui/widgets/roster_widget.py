"""
--- Copyright Notice ---
Copyright (c) 2024 Jim Maastricht

Roster widget for baseball season simulation UI.

Displays team roster with position players and pitchers in separate tabs.
"""

import tkinter as tk
from tkinter import ttk
import pandas as pd
from bblogger import logger


class RosterWidget:
    """
    Roster widget showing team roster with position players and pitchers.

    Features:
    - Nested notebook with Position Players and Pitchers tabs
    - Displays player stats (batting or pitching)
    - Shows player condition and injury status
    - Color-codes injured players
    """

    def __init__(self, parent: tk.Widget):
        """
        Initialize roster widget.

        Args:
            parent: Parent tkinter widget (notebook or frame)
        """
        self.frame = tk.Frame(parent)

        # Create notebook for Roster sub-sections
        roster_notebook = ttk.Notebook(self.frame)
        roster_notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Sub-section 1: Position Players
        pos_players_frame = tk.Frame(roster_notebook)
        roster_notebook.add(pos_players_frame, text="Pos Players")
        self.pos_players_tree = self._create_roster_treeview(pos_players_frame, is_batter=True)

        # Sub-section 2: Pitchers
        pitchers_frame = tk.Frame(roster_notebook)
        roster_notebook.add(pitchers_frame, text="Pitchers")
        self.pitchers_tree = self._create_roster_treeview(pitchers_frame, is_batter=False)

    def _create_roster_treeview(self, parent: tk.Widget, is_batter: bool = True) -> ttk.Treeview:
        """
        Create Treeview for roster data.

        Args:
            parent: Parent widget
            is_batter: True for batters, False for pitchers

        Returns:
            ttk.Treeview: Configured treeview
        """
        if is_batter:
            columns = ("Player", "Pos", "AB", "R", "H", "2B", "3B", "HR", "RBI", "BB", "K",
                      "AVG", "OBP", "SLG", "OPS", "Condition", "Status")
        else:
            columns = ("Player", "G", "GS", "W", "L", "IP", "H", "R", "ER", "HR", "BB", "SO",
                      "ERA", "WHIP", "SV", "Condition", "Status")

        tree = ttk.Treeview(parent, columns=columns, show="headings", height=15)

        # Configure columns
        for col in columns:
            tree.heading(col, text=col)
            if col == "Player":
                tree.column(col, width=150, anchor=tk.W)
            elif col in ["Pos", "Status"]:
                tree.column(col, width=70, anchor=tk.CENTER)
            elif col in ["AB", "R", "H", "2B", "3B", "HR", "RBI", "BB", "K", "G", "GS", "W", "L",
                        "ER", "SV", "SO", "Condition"]:
                tree.column(col, width=45, anchor=tk.CENTER)
            elif col in ["AVG", "OBP", "SLG", "OPS", "ERA", "WHIP"]:
                tree.column(col, width=55, anchor=tk.CENTER)
            elif col == "IP":
                tree.column(col, width=50, anchor=tk.CENTER)
            else:
                tree.column(col, width=50, anchor=tk.CENTER)

        # Add scrollbar
        scrollbar = ttk.Scrollbar(parent, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        tree.pack(fill=tk.BOTH, expand=True)

        # Configure tags for injury highlighting
        tree.tag_configure("day_to_day", background="#fff4cc")  # Yellow for day-to-day (<10 days)
        tree.tag_configure("injured", background="#ffcccc")  # Red for IL (>=10 days)

        return tree

    def update_roster(self, team: str, baseball_data):
        """
        Fetch and display roster data for team.

        Args:
            team: Team abbreviation
            baseball_data: BaseballStats instance with get_batting_data/get_pitching_data methods
        """
        try:
            # Get batting data (current season)
            batting_df = baseball_data.get_batting_data(team, prior_season=False)

            # Get pitching data (current season)
            pitching_df = baseball_data.get_pitching_data(team, prior_season=False)

            # Sort batters by PA if column exists, otherwise use AB, then G
            if 'PA' in batting_df.columns and batting_df['PA'].sum() > 0:
                sorted_batters = batting_df.sort_values('PA', ascending=False)
            elif 'AB' in batting_df.columns and batting_df['AB'].sum() > 0:
                sorted_batters = batting_df.sort_values('AB', ascending=False)
            elif 'G' in batting_df.columns and batting_df['G'].sum() > 0:
                sorted_batters = batting_df.sort_values('G', ascending=False)
            else:
                # No stats yet, just use as-is
                sorted_batters = batting_df

            # Update position players tree
            self._update_roster_tree(self.pos_players_tree, sorted_batters, is_batter=True)

            # Sort pitchers by IP (innings pitched)
            if 'IP' in pitching_df.columns and pitching_df['IP'].sum() > 0:
                sorted_pitchers = pitching_df.sort_values('IP', ascending=False)
            else:
                sorted_pitchers = pitching_df.sort_values('Player') if 'Player' in pitching_df.columns else pitching_df

            # Update pitchers tree
            self._update_roster_tree(self.pitchers_tree, sorted_pitchers, is_batter=False)

            logger.info(f"Roster updated for {team}: {len(batting_df)} batters, {len(pitching_df)} pitchers")

        except Exception as e:
            logger.error(f"Error updating roster: {e}")
            import traceback
            logger.error(traceback.format_exc())

    @staticmethod
    def _condition_to_text(condition: int) -> str:
        """
        Convert numeric condition (0-100) to descriptive text.

        Args:
            condition: Condition value (0-100)

        Returns:
            str: Descriptive text
        """
        if condition >= 95:
            return "Excellent"
        elif condition >= 85:
            return "Good"
        elif condition >= 70:
            return "Fair"
        elif condition >= 50:
            return "Tired"
        else:
            return "Fatigued"

    def _update_roster_tree(self, tree: ttk.Treeview, data_df: pd.DataFrame, is_batter: bool = True):
        """
        Update roster Treeview with data.

        Args:
            tree: Treeview widget to update
            data_df: DataFrame with player data
            is_batter: True for batters, False for pitchers
        """
        # Clear existing
        for item in tree.get_children():
            tree.delete(item)

        # Handle empty DataFrame
        if data_df.empty:
            logger.debug(f"Empty roster data for {'batter' if is_batter else 'pitcher'}")
            return

        # Insert rows
        for idx, row in data_df.iterrows():
            try:
                # Determine injury days and condition display
                injured_days = int(row.get('Injured Days', 0))
                if injured_days > 0:
                    condition_display = "Injured"
                else:
                    condition_display = self._condition_to_text(int(row.get('Condition', 100)))

                if is_batter:
                    # Clean up position formatting (remove brackets and quotes)
                    pos = row.get('Pos', 'Unknown')
                    if isinstance(pos, list):
                        pos = pos[0] if pos else 'Unknown'
                    pos = str(pos).replace('[', '').replace(']', '').replace("'", '').replace('"', '').strip()

                    values = (
                        row.get('Player', 'Unknown'),
                        pos,
                        int(row.get('AB', 0)),
                        int(row.get('R', 0)),
                        int(row.get('H', 0)),
                        int(row.get('2B', 0)),
                        int(row.get('3B', 0)),
                        int(row.get('HR', 0)),
                        int(row.get('RBI', 0)),
                        int(row.get('BB', 0)),
                        int(row.get('SO', 0)),
                        f"{float(row.get('AVG', 0)):.3f}",
                        f"{float(row.get('OBP', 0)):.3f}",
                        f"{float(row.get('SLG', 0)):.3f}",
                        f"{float(row.get('OPS', 0)):.3f}",
                        condition_display,
                        row.get('Status', 'Healthy')
                    )
                else:
                    values = (
                        row.get('Player', 'Unknown'),
                        int(row.get('G', 0)),
                        int(row.get('GS', 0)),
                        int(row.get('W', 0)),
                        int(row.get('L', 0)),
                        f"{float(row.get('IP', 0)):.1f}",
                        int(row.get('H', 0)),
                        int(row.get('R', 0)),
                        int(row.get('ER', 0)),
                        int(row.get('HR', 0)),
                        int(row.get('BB', 0)),
                        int(row.get('SO', 0)),
                        f"{float(row.get('ERA', 0)):.2f}",
                        f"{float(row.get('WHIP', 0)):.2f}",
                        int(row.get('SV', 0)),
                        condition_display,
                        row.get('Status', 'Healthy')
                    )

                # Determine injury tag based on Injured Days
                tags = ()
                if injured_days > 0:
                    if injured_days < 10:
                        tags = ("day_to_day",)
                    else:
                        tags = ("injured",)

                tree.insert("", tk.END, values=values, tags=tags)
            except Exception as e:
                logger.warning(f"Error inserting roster row for {row.get('Player', 'Unknown')}: {e}")

    def get_frame(self) -> tk.Frame:
        """Get the main frame for adding to parent container."""
        return self.frame
