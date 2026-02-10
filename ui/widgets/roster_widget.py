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
        self.baseball_data = None  # Will be set in update_roster

        # Store DataFrames for sorting
        self.batters_df = None
        self.pitchers_df = None

        # Track sort state for each tree: {tree_id: {'column': str, 'ascending': bool}}
        self.sort_state = {}

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

        # Add separator
        separator = ttk.Separator(self.frame, orient=tk.HORIZONTAL)
        separator.pack(fill=tk.X, padx=5, pady=5)

        # Add historical stats section at the bottom
        history_label = tk.Label(self.frame, text="Player Historical Performance (Click player to view)",
                                font=("Arial", 10, "bold"))
        history_label.pack(padx=5, pady=(0, 5))

        # Create frame for historical stats treeview
        history_frame = tk.Frame(self.frame)
        history_frame.pack(fill=tk.BOTH, expand=False, padx=5, pady=5)

        self.history_tree = self._create_history_treeview(history_frame)

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

    def _create_history_treeview(self, parent: tk.Widget) -> ttk.Treeview:
        """
        Create Treeview for historical player stats.

        Args:
            parent: Parent widget

        Returns:
            ttk.Treeview: Configured treeview for historical data
        """
        # Common columns for both batters and pitchers
        columns = ("Season", "Team", "Age", "G")

        tree = ttk.Treeview(parent, columns=columns, show="headings", height=5)

        # Configure columns
        for col in columns:
            tree.heading(col, text=col)
            if col == "Season":
                tree.column(col, width=70, anchor=tk.CENTER)
            elif col == "Team":
                tree.column(col, width=60, anchor=tk.CENTER)
            elif col in ["Age", "G"]:
                tree.column(col, width=50, anchor=tk.CENTER)
            else:
                tree.column(col, width=70, anchor=tk.CENTER)

        # Add scrollbar
        scrollbar = ttk.Scrollbar(parent, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        tree.pack(fill=tk.BOTH, expand=True)

        return tree

    def update_roster(self, team: str, baseball_data):
        """
        Fetch and display roster data for team.

        Args:
            team: Team abbreviation
            baseball_data: BaseballStats instance with get_batting_data/get_pitching_data methods
        """
        # Store reference to baseball_data for later use in click handlers
        self.baseball_data = baseball_data

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

        # Fetch historical data
        try:
            historical_df = self.baseball_data.get_player_historical_data(player_name, is_batter)

            if historical_df.empty:
                logger.info(f"No historical data found for {player_name}")
                # Clear the history tree
                for item in self.history_tree.get_children():
                    self.history_tree.delete(item)
                return

            # Update history tree with new data
            self._update_history_tree(historical_df, is_batter)

        except Exception as e:
            logger.error(f"Error fetching historical data for {player_name}: {e}")
            import traceback
            logger.error(traceback.format_exc())

    def _update_history_tree(self, historical_df: pd.DataFrame, is_batter: bool):
        """
        Update the history tree with player's historical stats.

        Args:
            historical_df: DataFrame with historical stats
            is_batter: True if batter, False if pitcher
        """
        # Clear existing data
        for item in self.history_tree.get_children():
            self.history_tree.delete(item)

        # Define columns based on player type
        if is_batter:
            columns = ("Season", "Team", "Age", "G", "AB", "R", "H", "HR", "RBI", "AVG", "OBP", "SLG", "OPS")
        else:
            columns = ("Season", "Team", "Age", "G", "GS", "IP", "W", "L", "ERA", "WHIP", "SO")

        # Reconfigure tree columns
        self.history_tree['columns'] = columns
        self.history_tree['show'] = 'headings'

        # Configure column headings and widths
        for col in columns:
            self.history_tree.heading(col, text=col)
            if col in ["Season", "Team"]:
                self.history_tree.column(col, width=60, anchor=tk.CENTER)
            elif col in ["Age", "G", "GS", "W", "L"]:
                self.history_tree.column(col, width=40, anchor=tk.CENTER)
            elif col in ["AB", "R", "H", "HR", "RBI", "SO"]:
                self.history_tree.column(col, width=45, anchor=tk.CENTER)
            elif col in ["AVG", "OBP", "SLG", "OPS", "ERA", "WHIP"]:
                self.history_tree.column(col, width=55, anchor=tk.CENTER)
            elif col == "IP":
                self.history_tree.column(col, width=50, anchor=tk.CENTER)
            else:
                self.history_tree.column(col, width=50, anchor=tk.CENTER)

        # Insert rows from historical data
        for idx, row in historical_df.iterrows():
            try:
                if is_batter:
                    values = (
                        int(row.get('Season', 0)),
                        row.get('Team', ''),
                        int(row.get('Age', 0)),
                        int(row.get('G', 0)),
                        int(row.get('AB', 0)),
                        int(row.get('R', 0)),
                        int(row.get('H', 0)),
                        int(row.get('HR', 0)),
                        int(row.get('RBI', 0)),
                        f"{float(row.get('AVG', 0)):.3f}",
                        f"{float(row.get('OBP', 0)):.3f}",
                        f"{float(row.get('SLG', 0)):.3f}",
                        f"{float(row.get('OPS', 0)):.3f}"
                    )
                else:
                    values = (
                        int(row.get('Season', 0)),
                        row.get('Team', ''),
                        int(row.get('Age', 0)),
                        int(row.get('G', 0)),
                        int(row.get('GS', 0)),
                        f"{float(row.get('IP', 0)):.1f}",
                        int(row.get('W', 0)),
                        int(row.get('L', 0)),
                        f"{float(row.get('ERA', 0)):.2f}",
                        f"{float(row.get('WHIP', 0)):.2f}",
                        int(row.get('SO', 0))
                    )

                self.history_tree.insert("", tk.END, values=values)
            except Exception as e:
                logger.warning(f"Error inserting historical row: {e}")

    def get_frame(self) -> tk.Frame:
        """Get the main frame for adding to parent container."""
        return self.frame
