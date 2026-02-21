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

    def __init__(self, parent: tk.Widget, comparison_mode_var: tk.StringVar = None):
        """
        Initialize roster widget.

        Args:
            parent: Parent tkinter widget (notebook or frame)
            comparison_mode_var: StringVar for comparison mode ("current" or "difference")
        """
        self.frame = tk.Frame(parent)
        self.baseball_data = None  # Will be set in update_roster

        # Create our own comparison mode var if not provided
        if comparison_mode_var is None:
            self.comparison_mode_var = tk.StringVar(value="current")
        else:
            self.comparison_mode_var = comparison_mode_var

        # Store DataFrames for sorting
        self.batters_df = None
        self.pitchers_df = None

        # Cached 2025 prorated data for comparison (Phase 5: Stats Enhancement)
        self.team_batting_2025 = None
        self.team_pitching_2025 = None
        self.current_team = None  # Track currently displayed team

        # Track sort state for each tree: {tree_id: {'column': str, 'ascending': bool}}
        self.sort_state = {}

        # Search/filter state
        self.batting_search_var = tk.StringVar()
        self.pitching_search_var = tk.StringVar()
        self.batters_df_full = None  # Unfiltered data
        self.pitchers_df_full = None  # Unfiltered data

        # Create notebook for Roster sub-sections
        roster_notebook = ttk.Notebook(self.frame)
        roster_notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Sub-section 1: Position Players
        pos_players_frame = tk.Frame(roster_notebook)
        roster_notebook.add(pos_players_frame, text="Pos Players")

        # Add control panel with search, filters, and toggle button
        batting_control_frame = tk.Frame(pos_players_frame)
        batting_control_frame.pack(fill=tk.X, padx=5, pady=5)

        # Player search
        tk.Label(batting_control_frame, text="Find Player:").pack(side=tk.LEFT, padx=(0, 5))
        self.batting_search_var.trace('w', lambda *args: self._apply_filter(is_batter=True))
        batting_search_entry = tk.Entry(batting_control_frame, textvariable=self.batting_search_var, width=20)
        batting_search_entry.pack(side=tk.LEFT, padx=(0, 5))

        # Clear button
        clear_btn = tk.Button(batting_control_frame, text="Clear Filters",
                             command=lambda: self._clear_filter(is_batter=True))
        clear_btn.pack(side=tk.LEFT, padx=5)

        # Toggle button
        tk.Label(batting_control_frame, text="  |  View:").pack(side=tk.LEFT, padx=(10, 5))
        self.batting_comparison_btn = tk.Button(batting_control_frame, text="Show Difference from 2025",
                                               command=self._toggle_comparison_mode,
                                               bg="#e8f4f8", relief=tk.RAISED)
        self.batting_comparison_btn.pack(side=tk.LEFT, padx=5)

        self.pos_players_tree = self._create_roster_treeview(pos_players_frame, is_batter=True)

        # Add team batting totals section
        separator = ttk.Separator(pos_players_frame, orient=tk.HORIZONTAL)
        separator.pack(fill=tk.X, padx=5, pady=10)

        totals_label = tk.Label(pos_players_frame, text="Team Batting Totals", font=("Arial", 11, "bold"))
        totals_label.pack(padx=5, pady=(0, 5))

        self.batting_totals_frame = tk.Frame(pos_players_frame, relief=tk.SUNKEN, borderwidth=1)
        self.batting_totals_frame.pack(fill=tk.X, padx=5, pady=5)

        self.batting_totals_labels = {}  # Store label references for updating

        # Sub-section 2: Pitchers
        pitchers_frame = tk.Frame(roster_notebook)
        roster_notebook.add(pitchers_frame, text="Pitchers")

        # Add control panel with search, filters, and toggle button
        pitching_control_frame = tk.Frame(pitchers_frame)
        pitching_control_frame.pack(fill=tk.X, padx=5, pady=5)

        # Player search
        tk.Label(pitching_control_frame, text="Find Player:").pack(side=tk.LEFT, padx=(0, 5))
        self.pitching_search_var.trace('w', lambda *args: self._apply_filter(is_batter=False))
        pitching_search_entry = tk.Entry(pitching_control_frame, textvariable=self.pitching_search_var, width=20)
        pitching_search_entry.pack(side=tk.LEFT, padx=(0, 5))

        # Clear button
        clear_btn = tk.Button(pitching_control_frame, text="Clear Filters",
                             command=lambda: self._clear_filter(is_batter=False))
        clear_btn.pack(side=tk.LEFT, padx=5)

        # Toggle button
        tk.Label(pitching_control_frame, text="  |  View:").pack(side=tk.LEFT, padx=(10, 5))
        self.pitching_comparison_btn = tk.Button(pitching_control_frame, text="Show Difference from 2025",
                                                command=self._toggle_comparison_mode,
                                                bg="#e8f4f8", relief=tk.RAISED)
        self.pitching_comparison_btn.pack(side=tk.LEFT, padx=5)

        self.pitchers_tree = self._create_roster_treeview(pitchers_frame, is_batter=False)

        # Add team pitching totals section
        separator = ttk.Separator(pitchers_frame, orient=tk.HORIZONTAL)
        separator.pack(fill=tk.X, padx=5, pady=10)

        totals_label = tk.Label(pitchers_frame, text="Team Pitching Totals", font=("Arial", 11, "bold"))
        totals_label.pack(padx=5, pady=(0, 5))

        self.pitching_totals_frame = tk.Frame(pitchers_frame, relief=tk.SUNKEN, borderwidth=1)
        self.pitching_totals_frame.pack(fill=tk.X, padx=5, pady=5)

        self.pitching_totals_labels = {}  # Store label references for updating

        # Historical stats are shown in a popup window when a player is clicked

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

        # Initialize sort state for this tree
        tree_id = str(id(tree))
        self.sort_state[tree_id] = {'column': None, 'ascending': True}

        # Configure columns
        for col in columns:
            # Bind heading click to sort function
            tree.heading(col, text=col, command=lambda c=col, t=tree, b=is_batter: self._sort_by_column(t, c, b))

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

        # Bind click handler for player selection
        tree.bind('<<TreeviewSelect>>', lambda e: self._on_player_click(tree, is_batter))

        return tree

    def _show_history_popup(self, player_name: str, historical_df, is_batter: bool):
        """
        Open a popup window showing player historical stats.

        Args:
            player_name: Player name for window title
            historical_df: DataFrame with historical stats
            is_batter: True for batting columns, False for pitching columns
        """
        popup = tk.Toplevel()
        popup.title(f"{player_name} - Historical Stats")
        popup.geometry("680x280")
        popup.resizable(True, True)

        if is_batter:
            columns = ("Season", "Team", "Age", "G", "AB", "R", "H", "HR", "RBI", "AVG", "OBP", "SLG", "OPS")
        else:
            columns = ("Season", "Team", "Age", "G", "GS", "IP", "W", "L", "ERA", "WHIP", "SO")

        tree_frame = tk.Frame(popup)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(10, 5))

        scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        tree = ttk.Treeview(tree_frame, columns=columns, show="headings", height=8,
                            yscrollcommand=scrollbar.set)
        scrollbar.config(command=tree.yview)

        for col in columns:
            tree.heading(col, text=col)
            if col in ["Season", "Team"]:
                tree.column(col, width=60, anchor=tk.CENTER)
            elif col in ["Age", "G", "GS", "W", "L"]:
                tree.column(col, width=40, anchor=tk.CENTER)
            elif col in ["AB", "R", "H", "HR", "RBI", "SO"]:
                tree.column(col, width=45, anchor=tk.CENTER)
            elif col in ["AVG", "OBP", "SLG", "OPS", "ERA", "WHIP"]:
                tree.column(col, width=55, anchor=tk.CENTER)
            elif col == "IP":
                tree.column(col, width=50, anchor=tk.CENTER)
            else:
                tree.column(col, width=50, anchor=tk.CENTER)

        tree.pack(fill=tk.BOTH, expand=True)

        for idx, row in historical_df.iterrows():
            try:
                if is_batter:
                    values = (
                        int(row.get('Season', 0)), row.get('Team', ''), int(row.get('Age', 0)),
                        int(row.get('G', 0)), int(row.get('AB', 0)), int(row.get('R', 0)),
                        int(row.get('H', 0)), int(row.get('HR', 0)), int(row.get('RBI', 0)),
                        f"{float(row.get('AVG', 0)):.3f}", f"{float(row.get('OBP', 0)):.3f}",
                        f"{float(row.get('SLG', 0)):.3f}", f"{float(row.get('OPS', 0)):.3f}"
                    )
                else:
                    values = (
                        int(row.get('Season', 0)), row.get('Team', ''), int(row.get('Age', 0)),
                        int(row.get('G', 0)), int(row.get('GS', 0)),
                        f"{float(row.get('IP', 0)):.1f}",
                        int(row.get('W', 0)), int(row.get('L', 0)),
                        f"{float(row.get('ERA', 0)):.2f}", f"{float(row.get('WHIP', 0)):.2f}",
                        int(row.get('SO', 0))
                    )
                tree.insert("", tk.END, values=values)
            except Exception as e:
                logger.warning(f"Error inserting historical row: {e}")

        tk.Button(popup, text="Close", command=popup.destroy, width=10).pack(pady=5)
        popup.focus_set()

    def update_roster(self, team: str, baseball_data):
        """
        Fetch and display roster data for team.

        Args:
            team: Team abbreviation
            baseball_data: BaseballStats instance with get_batting_data/get_pitching_data methods
        """
        # Store reference to baseball_data for later use in click handlers
        self.baseball_data = baseball_data
        self.current_team = team  # Phase 5: Stats Enhancement - track current team

        try:
            # Get batting data (current season)
            batting_df = baseball_data.get_batting_data(team, prior_season=False)

            # Get pitching data (current season)
            pitching_df = baseball_data.get_pitching_data(team, prior_season=False)

            # Store full unfiltered data
            self.batters_df_full = batting_df.copy()
            self.pitchers_df_full = pitching_df.copy()

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

            # Store DataFrames for sorting
            self.batters_df = sorted_batters.copy()

            # Check if user had a custom sort applied, and reapply it
            tree_id = str(id(self.pos_players_tree))
            if tree_id in self.sort_state and self.sort_state[tree_id]['column'] is not None:
                # Reapply user's sort
                sort_state = self.sort_state[tree_id]
                sorted_batters = self._apply_sort(sorted_batters, sort_state['column'],
                                                   sort_state['ascending'], is_batter=True)
                self.batters_df = sorted_batters.copy()

            # Update position players tree
            self._update_roster_tree(self.pos_players_tree, sorted_batters, is_batter=True)

            # Update sort indicators if there was a custom sort
            if tree_id in self.sort_state and self.sort_state[tree_id]['column'] is not None:
                self._update_sort_indicators(self.pos_players_tree,
                                             self.sort_state[tree_id]['column'],
                                             self.sort_state[tree_id]['ascending'],
                                             is_batter=True)

            # Sort pitchers by IP (innings pitched)
            if 'IP' in pitching_df.columns and pitching_df['IP'].sum() > 0:
                sorted_pitchers = pitching_df.sort_values('IP', ascending=False)
            else:
                sorted_pitchers = pitching_df.sort_values('Player') if 'Player' in pitching_df.columns else pitching_df

            # Store DataFrames for sorting
            self.pitchers_df = sorted_pitchers.copy()

            # Check if user had a custom sort applied, and reapply it
            tree_id = str(id(self.pitchers_tree))
            if tree_id in self.sort_state and self.sort_state[tree_id]['column'] is not None:
                # Reapply user's sort
                sort_state = self.sort_state[tree_id]
                sorted_pitchers = self._apply_sort(sorted_pitchers, sort_state['column'],
                                                   sort_state['ascending'], is_batter=False)
                self.pitchers_df = sorted_pitchers.copy()

            # Update pitchers tree
            self._update_roster_tree(self.pitchers_tree, sorted_pitchers, is_batter=False)

            # Update sort indicators if there was a custom sort
            if tree_id in self.sort_state and self.sort_state[tree_id]['column'] is not None:
                self._update_sort_indicators(self.pitchers_tree,
                                             self.sort_state[tree_id]['column'],
                                             self.sort_state[tree_id]['ascending'],
                                             is_batter=False)

            # Update totals displays
            self._update_totals_display(is_batter=True)
            self._update_totals_display(is_batter=False)

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
        Update roster Treeview with data (Phase 5: Supports comparison mode).

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

        # Check comparison mode and calculate differences if needed
        mode = self.comparison_mode_var.get() if self.comparison_mode_var else "current"
        display_df = data_df

        if mode == "difference":
            display_df = self._calculate_difference_df(data_df, is_batter)

        # Insert rows
        for idx, row in display_df.iterrows():
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

                    if mode == "difference":
                        # Format with +/- prefix for difference mode
                        values = (
                            row.get('Player', 'Unknown'),
                            pos,
                            self._format_diff_value(row.get('AB', 0)),
                            self._format_diff_value(row.get('R', 0)),
                            self._format_diff_value(row.get('H', 0)),
                            self._format_diff_value(row.get('2B', 0)),
                            self._format_diff_value(row.get('3B', 0)),
                            self._format_diff_value(row.get('HR', 0)),
                            self._format_diff_value(row.get('RBI', 0)),
                            self._format_diff_value(row.get('BB', 0)),
                            self._format_diff_value(row.get('SO', 0)),
                            self._format_diff_value(row.get('AVG', 0), decimals=3),
                            self._format_diff_value(row.get('OBP', 0), decimals=3),
                            self._format_diff_value(row.get('SLG', 0), decimals=3),
                            self._format_diff_value(row.get('OPS', 0), decimals=3),
                            condition_display,
                            row.get('Status', 'Healthy')
                        )
                    else:
                        # Standard format for current stats
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
                    if mode == "difference":
                        # Format with +/- prefix for difference mode
                        values = (
                            row.get('Player', 'Unknown'),
                            self._format_diff_value(row.get('G', 0)),
                            self._format_diff_value(row.get('GS', 0)),
                            self._format_diff_value(row.get('W', 0)),
                            self._format_diff_value(row.get('L', 0)),
                            self._format_diff_value(row.get('IP', 0), decimals=1),
                            self._format_diff_value(row.get('H', 0)),
                            self._format_diff_value(row.get('R', 0)),
                            self._format_diff_value(row.get('ER', 0)),
                            self._format_diff_value(row.get('HR', 0)),
                            self._format_diff_value(row.get('BB', 0)),
                            self._format_diff_value(row.get('SO', 0)),
                            self._format_diff_value(row.get('ERA', 0), decimals=2),
                            self._format_diff_value(row.get('WHIP', 0), decimals=2),
                            self._format_diff_value(row.get('SV', 0)),
                            condition_display,
                            row.get('Status', 'Healthy')
                        )
                    else:
                        # Standard format for current stats
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

    def _apply_sort(self, df: pd.DataFrame, column: str, ascending: bool, is_batter: bool) -> pd.DataFrame:
        """
        Apply sort to a DataFrame.

        Args:
            df: DataFrame to sort
            column: Column name to sort by
            ascending: Sort direction
            is_batter: True if batter data, False if pitcher data

        Returns:
            Sorted DataFrame
        """
        if df is None or df.empty:
            return df

        # Map display column names to DataFrame column names
        column_mapping = {
            'K': 'SO'  # Display column "K" maps to DataFrame column "SO"
        }

        # Get the actual DataFrame column name
        df_column = column_mapping.get(column, column)

        # Determine if column is numeric or text
        numeric_cols = ['G', 'AB', 'R', 'H', '2B', '3B', 'HR', 'RBI', 'BB', 'SO', 'K',
                       'AVG', 'OBP', 'SLG', 'OPS', 'GS', 'W', 'L', 'IP', 'ER', 'ERA',
                       'WHIP', 'SV', 'Condition', 'Age']

        try:
            if df_column in df.columns:
                # Handle numeric vs text sorting
                if column in numeric_cols or df_column in numeric_cols:
                    # Convert to numeric, handling any non-numeric values
                    sorted_df = df.copy()
                    sorted_df[df_column] = pd.to_numeric(sorted_df[df_column], errors='coerce')
                    sorted_df = sorted_df.sort_values(df_column, ascending=ascending, na_position='last')
                else:
                    # Text sorting
                    sorted_df = df.sort_values(df_column, ascending=ascending, na_position='last')

                return sorted_df
            else:
                logger.warning(f"Column {column} (mapped to {df_column}) not found in DataFrame")
                return df

        except Exception as e:
            logger.error(f"Error applying sort by column {column}: {e}")
            return df

    def _sort_by_column(self, tree: ttk.Treeview, column: str, is_batter: bool):
        """
        Sort roster tree by the specified column.

        Args:
            tree: The treeview to sort
            column: Column name to sort by
            is_batter: True if batter tree, False if pitcher tree
        """
        # Get tree ID and current sort state
        tree_id = str(id(tree))
        if tree_id not in self.sort_state:
            self.sort_state[tree_id] = {'column': None, 'ascending': True}

        current_state = self.sort_state[tree_id]

        # Determine sort direction
        if current_state['column'] == column:
            # Toggle direction if clicking same column
            ascending = not current_state['ascending']
        else:
            # Default to descending for new column (most useful for stats)
            ascending = False

        # Get the appropriate DataFrame
        df = self.batters_df if is_batter else self.pitchers_df
        if df is None or df.empty:
            logger.warning("No data available to sort")
            return

        # Apply the sort using helper method
        sorted_df = self._apply_sort(df, column, ascending, is_batter)

        # Update the stored DataFrame
        if is_batter:
            self.batters_df = sorted_df
        else:
            self.pitchers_df = sorted_df

        # Update the tree display
        self._update_roster_tree(tree, sorted_df, is_batter)

        # Update sort state
        self.sort_state[tree_id] = {'column': column, 'ascending': ascending}

        # Update column headings to show sort indicator
        self._update_sort_indicators(tree, column, ascending, is_batter)

        # Map display column names to DataFrame column names for logging
        column_mapping = {'K': 'SO'}
        df_column = column_mapping.get(column, column)
        logger.debug(f"Sorted by {column} (DataFrame column: {df_column}), ascending={ascending}")

    def _update_sort_indicators(self, tree: ttk.Treeview, sorted_column: str, ascending: bool, is_batter: bool):
        """
        Update column heading text to show sort indicators.

        Args:
            tree: The treeview to update
            sorted_column: The column that is currently sorted
            ascending: Whether sort is ascending
            is_batter: True if batter tree, False if pitcher tree
        """
        # Define columns based on player type
        if is_batter:
            columns = ("Player", "Pos", "AB", "R", "H", "2B", "3B", "HR", "RBI", "BB", "K",
                      "AVG", "OBP", "SLG", "OPS", "Condition", "Status")
        else:
            columns = ("Player", "G", "GS", "W", "L", "IP", "H", "R", "ER", "HR", "BB", "SO",
                      "ERA", "WHIP", "SV", "Condition", "Status")

        # Update all column headings
        for col in columns:
            if col == sorted_column:
                # Add sort indicator to sorted column
                indicator = " ↑" if ascending else " ↓"
                tree.heading(col, text=f"{col}{indicator}",
                           command=lambda c=col: self._sort_by_column(tree, c, is_batter))
            else:
                # Remove indicator from other columns
                tree.heading(col, text=col,
                           command=lambda c=col: self._sort_by_column(tree, c, is_batter))

    def _on_player_click(self, tree: ttk.Treeview, is_batter: bool):
        """
        Handle player row click - fetch and display historical stats.

        Args:
            tree: The treeview that was clicked
            is_batter: True if batter tree, False if pitcher tree
        """
        # Get selected item
        selection = tree.selection()
        if not selection:
            return

        # Get player name from selected row (first column)
        item = selection[0]
        values = tree.item(item, 'values')
        if not values:
            return

        player_name = values[0]  # Player name is first column
        logger.info(f"Player clicked: {player_name} (is_batter={is_batter})")

        # Check if baseball_data is available
        if not self.baseball_data:
            logger.warning("baseball_data not available for historical lookup")
            return

        # Fetch historical data and show in popup
        try:
            historical_df = self.baseball_data.get_player_historical_data(player_name, is_batter)

            if historical_df.empty:
                logger.info(f"No historical data found for {player_name}")
                return

            self._show_history_popup(player_name, historical_df, is_batter)

        except Exception as e:
            logger.error(f"Error fetching historical data for {player_name}: {e}")
            import traceback
            logger.error(traceback.format_exc())

    def _apply_filter(self, is_batter: bool = True):
        """Apply search filter to roster display."""
        if is_batter:
            if self.batters_df_full is None:
                return
            search_text = self.batting_search_var.get().lower()
            if search_text:
                filtered_df = self.batters_df_full[
                    self.batters_df_full['Player'].str.lower().str.contains(search_text, na=False)
                ]
            else:
                filtered_df = self.batters_df_full

            self.batters_df = filtered_df.copy()
            self._update_roster_tree(self.pos_players_tree, filtered_df, is_batter=True)
        else:
            if self.pitchers_df_full is None:
                return
            search_text = self.pitching_search_var.get().lower()
            if search_text:
                filtered_df = self.pitchers_df_full[
                    self.pitchers_df_full['Player'].str.lower().str.contains(search_text, na=False)
                ]
            else:
                filtered_df = self.pitchers_df_full

            self.pitchers_df = filtered_df.copy()
            self._update_roster_tree(self.pitchers_tree, filtered_df, is_batter=False)

    def _clear_filter(self, is_batter: bool = True):
        """Clear search filter."""
        if is_batter:
            self.batting_search_var.set("")
        else:
            self.pitching_search_var.set("")

    def _toggle_comparison_mode(self):
        """Toggle between current stats and difference view (Phase 3 revision)."""
        current_mode = self.comparison_mode_var.get()
        new_mode = "difference" if current_mode == "current" else "current"
        self.comparison_mode_var.set(new_mode)

        # Update button appearance and text
        if new_mode == "difference":
            self.batting_comparison_btn.config(text="Show Current Stats", bg="#fff3cd", relief=tk.SUNKEN)
            self.pitching_comparison_btn.config(text="Show Current Stats", bg="#fff3cd", relief=tk.SUNKEN)
        else:
            self.batting_comparison_btn.config(text="Show Difference from 2025", bg="#e8f4f8", relief=tk.RAISED)
            self.pitching_comparison_btn.config(text="Show Difference from 2025", bg="#e8f4f8", relief=tk.RAISED)

        # Refresh display
        self.refresh_display()

    def refresh_display(self):
        """
        Refresh display when comparison mode changes (Phase 5: Stats Enhancement).
        Reloads the current team's roster.
        """
        if self.current_team and self.baseball_data:
            self.update_roster(self.current_team, self.baseball_data)

    def _load_team_2025_data(self, team_name: str, games_played: int):
        """
        Load and cache 2025 data for specific team (Phase 5: Stats Enhancement).

        Args:
            team_name: Team abbreviation
            games_played: Games played by team
        """
        if self.baseball_data is None:
            return

        batting_2025, pitching_2025 = self.baseball_data.calculate_prorated_2025_stats(
            team_name, games_played
        )

        self.team_batting_2025 = batting_2025
        self.team_pitching_2025 = pitching_2025

        logger.debug(f"Loaded 2025 team data for {team_name}: {len(batting_2025)} batters, {len(pitching_2025)} pitchers")

    def _calculate_difference_df(self, current_df: pd.DataFrame, is_batter: bool) -> pd.DataFrame:
        """
        Calculate current - prorated 2025 for team players (Phase 5: Stats Enhancement).

        Args:
            current_df: Current season DataFrame
            is_batter: True for batters, False for pitchers

        Returns:
            DataFrame with difference values
        """
        # Load 2025 data if not cached
        if self.current_team and self.baseball_data:
            if hasattr(self.baseball_data, 'team_games_played'):
                games_played = self.baseball_data.team_games_played.get(self.current_team, 0)
                if games_played > 0:
                    if is_batter and self.team_batting_2025 is None:
                        self._load_team_2025_data(self.current_team, games_played)
                    elif not is_batter and self.team_pitching_2025 is None:
                        self._load_team_2025_data(self.current_team, games_played)

        hist_df = self.team_batting_2025 if is_batter else self.team_pitching_2025

        if hist_df is None or hist_df.empty:
            logger.warning(f"No 2025 historical data available for {self.current_team}")
            return current_df

        diff_df = current_df.copy()

        # Join on Hashcode (index)
        for idx in diff_df.index:
            if idx in hist_df.index:
                hist_row = hist_df.loc[idx]

                # Counting stats: absolute difference
                if is_batter:
                    count_cols = ['AB', 'R', 'H', '2B', '3B', 'HR', 'RBI', 'BB', 'SO']
                    rate_cols = ['AVG', 'OBP', 'SLG', 'OPS']
                else:
                    count_cols = ['G', 'GS', 'W', 'L', 'IP', 'H', 'R', 'ER', 'HR', 'BB', 'SO', 'SV']
                    rate_cols = ['ERA', 'WHIP']

                for col in count_cols:
                    if col in diff_df.columns and col in hist_row.index:
                        diff_df.at[idx, col] = diff_df.at[idx, col] - hist_row[col]

                # Rate stats: difference
                for col in rate_cols:
                    if col in diff_df.columns and col in hist_row.index:
                        diff_df.at[idx, col] = diff_df.at[idx, col] - hist_row[col]

        return diff_df

    def _format_diff_value(self, value, decimals=0):
        """
        Format difference value with +/- prefix (Phase 5: Stats Enhancement).

        Args:
            value: Numeric value to format
            decimals: Number of decimal places

        Returns:
            Formatted string with +/- prefix
        """
        if pd.isna(value):
            return "N/A"

        if decimals == 0:
            formatted = f"{int(value)}"
        else:
            formatted = f"{value:.{decimals}f}"

        if value > 0:
            return f"+{formatted}"
        else:
            return formatted  # Already has negative sign

    def _update_totals_display(self, is_batter: bool = True):
        """
        Update the team totals display with three-row format (Current / 2025 Prorated / Difference).

        Args:
            is_batter: True for batting totals, False for pitching totals
        """
        import bbstats

        if is_batter:
            df = self.batters_df_full
            frame = self.batting_totals_frame
            labels_dict = self.batting_totals_labels
        else:
            df = self.pitchers_df_full
            frame = self.pitching_totals_frame
            labels_dict = self.pitching_totals_labels

        if df is None or df.empty or self.baseball_data is None or self.current_team is None:
            return

        # Clear existing widgets
        for widget in frame.winfo_children():
            widget.destroy()
        labels_dict.clear()

        # Get games played for this team
        games_played = 0
        if hasattr(self.baseball_data, 'team_games_played'):
            games_played = self.baseball_data.team_games_played.get(self.current_team, 0)

        # Add games played header
        if games_played > 0:
            header_label = tk.Label(frame, text=f"({games_played} games played)",
                                   font=("Arial", 8, "italic"), fg="gray")
            header_label.pack(pady=(2, 5))

        # Calculate current totals
        if is_batter:
            current_totals = bbstats.team_batting_totals(df)
            # Override G with actual team games played
            if games_played > 0:
                current_totals['G'] = games_played
            columns = ["", "G", "AB", "R", "H", "2B", "3B", "HR", "RBI", "BB", "SO", "AVG", "OBP", "SLG", "OPS"]
        else:
            current_totals = bbstats.team_pitching_totals(df)
            # For pitching, sum G (total pitcher appearances) and override with team games
            if 'G' in df.columns:
                # Option 1: Total pitcher appearances (sum)
                # current_totals['G'] = df['G'].sum()
                # Option 2: Team games played (more meaningful for comparison)
                if games_played > 0:
                    current_totals['G'] = games_played
            columns = ["", "G", "GS", "W", "L", "IP", "H", "R", "ER", "HR", "BB", "SO", "ERA", "WHIP", "SV"]

        # Create treeview for totals
        totals_tree = ttk.Treeview(frame, columns=columns, show="headings", height=3)

        # Configure columns
        for col in columns:
            totals_tree.heading(col, text=col)
            if col == "":
                totals_tree.column(col, width=150, anchor=tk.W)
            elif col in ["AVG", "OBP", "SLG", "OPS", "ERA", "WHIP"]:
                totals_tree.column(col, width=55, anchor=tk.CENTER)
            elif col == "IP":
                totals_tree.column(col, width=50, anchor=tk.CENTER)
            else:
                totals_tree.column(col, width=45, anchor=tk.CENTER)

        # Get prorated 2025 stats for team
        batting_2025, pitching_2025 = self.baseball_data.calculate_prorated_2025_stats(
            team_name=self.current_team, current_games_played=games_played
        )

        if games_played > 0 and ((is_batter and not batting_2025.empty) or (not is_batter and not pitching_2025.empty)):
            # Calculate 2025 totals
            if is_batter:
                prorated_totals = bbstats.team_batting_totals(batting_2025)
                # Override G with actual team games played
                prorated_totals['G'] = games_played
            else:
                prorated_totals = bbstats.team_pitching_totals(pitching_2025)
                # Override G with team games played for consistency
                prorated_totals['G'] = games_played

            # Calculate differences
            diff_totals = current_totals.copy()
            for col in columns[1:]:  # Skip empty label column
                if col in current_totals.columns and col in prorated_totals.columns:
                    diff_totals[col] = current_totals[col].values[0] - prorated_totals[col].values[0]

            # Insert three rows
            # Determine label based on whether we have full season data
            season_label = "2025 (Full Season)" if games_played >= 162 else "2025 (Prorated)"
            row_data = [
                ("Current", current_totals, False),
                (season_label, prorated_totals, False),
                ("Difference", diff_totals, True)
            ]

            for label, data, is_diff in row_data:
                values = [label]
                for col in columns[1:]:
                    if col in data.columns:
                        values.append(self._format_total_value(data[col].values[0], col, is_diff))
                    else:
                        values.append("")
                totals_tree.insert("", tk.END, values=tuple(values))
        else:
            # No 2025 data or no games played, show current only
            values = ["Current"]
            for col in columns[1:]:
                if col in current_totals.columns:
                    values.append(self._format_total_value(current_totals[col].values[0], col, False))
                else:
                    values.append("")
            totals_tree.insert("", tk.END, values=tuple(values))

        totals_tree.pack(fill=tk.BOTH, expand=False, padx=5, pady=5)

    def _format_total_value(self, value, col_name: str, is_difference: bool = False):
        """Format a total value for display."""
        if pd.isna(value):
            return "N/A"

        # Determine decimal places
        if col_name in ['AVG', 'OBP', 'SLG', 'OPS']:
            formatted = f"{value:.3f}"
        elif col_name in ['ERA', 'WHIP']:
            formatted = f"{value:.2f}"
        elif col_name == 'IP':
            formatted = f"{value:.1f}"
        else:
            formatted = f"{int(value)}"

        # Add +/- prefix for differences
        if is_difference and value > 0:
            return f"+{formatted}"
        return formatted

    def get_frame(self) -> tk.Frame:
        """Get the main frame for adding to parent container."""
        return self.frame
