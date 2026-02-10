"""
--- Copyright Notice ---
Copyright (c) 2024 Jim Maastricht

League stats widget for baseball season simulation UI.

Displays all players in the league with position players and pitchers in separate tabs.
"""

import tkinter as tk
from tkinter import ttk
import pandas as pd
from bblogger import logger


class LeagueStatsWidget:
    """
    League stats widget showing all players across all teams.

    Features:
    - Nested notebook with Position Players and Pitchers tabs
    - Displays player stats for entire league
    - Sortable columns
    - Filter by team
    - Find player by name
    """

    def __init__(self, parent: tk.Widget):
        """
        Initialize league stats widget.

        Args:
            parent: Parent tkinter widget (notebook or frame)
        """
        self.frame = tk.Frame(parent)
        self.baseball_data = None  # Will be set in update_stats

        # Store DataFrames - full and filtered versions
        self.batters_df_full = None  # Full unfiltered data
        self.pitchers_df_full = None  # Full unfiltered data
        self.batters_df = None  # Currently displayed (filtered/sorted)
        self.pitchers_df = None  # Currently displayed (filtered/sorted)

        # Track sort state for each tree: {tree_id: {'column': str, 'ascending': bool}}
        self.sort_state = {}

        # Current filter settings
        self.selected_team = "All Teams"
        self.search_text = ""

        # Create notebook for League Stats sub-sections
        stats_notebook = ttk.Notebook(self.frame)
        stats_notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Sub-section 1: Position Players
        pos_players_frame = tk.Frame(stats_notebook)
        stats_notebook.add(pos_players_frame, text="Position Players")
        self._create_pos_players_tab(pos_players_frame)

        # Sub-section 2: Pitchers
        pitchers_frame = tk.Frame(stats_notebook)
        stats_notebook.add(pitchers_frame, text="Pitchers")
        self._create_pitchers_tab(pitchers_frame)

    def _create_pos_players_tab(self, parent: tk.Frame):
        """
        Create position players tab with filters.

        Args:
            parent: Parent frame
        """
        # Create control panel at top
        control_frame = tk.Frame(parent)
        control_frame.pack(fill=tk.X, padx=5, pady=5)

        # Team filter
        tk.Label(control_frame, text="Team:").pack(side=tk.LEFT, padx=(0, 5))
        self.batting_team_var = tk.StringVar(value="All Teams")
        self.batting_team_combo = ttk.Combobox(control_frame, textvariable=self.batting_team_var,
                                               width=15, state="readonly")
        self.batting_team_combo.pack(side=tk.LEFT, padx=(0, 10))
        self.batting_team_combo.bind('<<ComboboxSelected>>', lambda e: self._apply_filters(is_batter=True))

        # Player search
        tk.Label(control_frame, text="Find Player:").pack(side=tk.LEFT, padx=(0, 5))
        self.batting_search_var = tk.StringVar()
        self.batting_search_var.trace('w', lambda *args: self._apply_filters(is_batter=True))
        batting_search_entry = tk.Entry(control_frame, textvariable=self.batting_search_var, width=20)
        batting_search_entry.pack(side=tk.LEFT, padx=(0, 5))

        # Clear button
        clear_btn = tk.Button(control_frame, text="Clear Filters",
                             command=lambda: self._clear_filters(is_batter=True))
        clear_btn.pack(side=tk.LEFT, padx=5)

        # Info label
        self.batting_info_label = tk.Label(control_frame, text="", fg="gray")
        self.batting_info_label.pack(side=tk.LEFT, padx=10)

        # Create treeview
        self.pos_players_tree = self._create_stats_treeview(parent, is_batter=True)

        # Add historical stats section at the bottom
        history_label = tk.Label(parent, text="Player Historical Performance (Click player to view)",
                                font=("Arial", 10, "bold"))
        history_label.pack(padx=5, pady=(10, 5))

        # Create frame for historical stats treeview
        history_frame = tk.Frame(parent)
        history_frame.pack(fill=tk.BOTH, expand=False, padx=5, pady=5)

        self.batters_history_tree = self._create_history_treeview(history_frame)

    def _create_pitchers_tab(self, parent: tk.Frame):
        """
        Create pitchers tab with filters.

        Args:
            parent: Parent frame
        """
        # Create control panel at top
        control_frame = tk.Frame(parent)
        control_frame.pack(fill=tk.X, padx=5, pady=5)

        # Team filter
        tk.Label(control_frame, text="Team:").pack(side=tk.LEFT, padx=(0, 5))
        self.pitching_team_var = tk.StringVar(value="All Teams")
        self.pitching_team_combo = ttk.Combobox(control_frame, textvariable=self.pitching_team_var,
                                                width=15, state="readonly")
        self.pitching_team_combo.pack(side=tk.LEFT, padx=(0, 10))
        self.pitching_team_combo.bind('<<ComboboxSelected>>', lambda e: self._apply_filters(is_batter=False))

        # Player search
        tk.Label(control_frame, text="Find Player:").pack(side=tk.LEFT, padx=(0, 5))
        self.pitching_search_var = tk.StringVar()
        self.pitching_search_var.trace('w', lambda *args: self._apply_filters(is_batter=False))
        pitching_search_entry = tk.Entry(control_frame, textvariable=self.pitching_search_var, width=20)
        pitching_search_entry.pack(side=tk.LEFT, padx=(0, 5))

        # Clear button
        clear_btn = tk.Button(control_frame, text="Clear Filters",
                             command=lambda: self._clear_filters(is_batter=False))
        clear_btn.pack(side=tk.LEFT, padx=5)

        # Info label
        self.pitching_info_label = tk.Label(control_frame, text="", fg="gray")
        self.pitching_info_label.pack(side=tk.LEFT, padx=10)

        # Create treeview
        self.pitchers_tree = self._create_stats_treeview(parent, is_batter=False)

        # Add historical stats section at the bottom
        history_label = tk.Label(parent, text="Player Historical Performance (Click player to view)",
                                font=("Arial", 10, "bold"))
        history_label.pack(padx=5, pady=(10, 5))

        # Create frame for historical stats treeview
        history_frame = tk.Frame(parent)
        history_frame.pack(fill=tk.BOTH, expand=False, padx=5, pady=5)

        self.pitchers_history_tree = self._create_history_treeview(history_frame)

    def _create_stats_treeview(self, parent: tk.Widget, is_batter: bool = True) -> ttk.Treeview:
        """
        Create Treeview for league stats data.

        Args:
            parent: Parent widget
            is_batter: True for batters, False for pitchers

        Returns:
            ttk.Treeview: Configured treeview
        """
        if is_batter:
            columns = ("Player", "Team", "Pos", "AB", "R", "H", "2B", "3B", "HR", "RBI", "BB", "K",
                      "AVG", "OBP", "SLG", "OPS")
        else:
            columns = ("Player", "Team", "G", "GS", "W", "L", "IP", "H", "R", "ER", "HR", "BB", "SO",
                      "ERA", "WHIP", "SV")

        tree = ttk.Treeview(parent, columns=columns, show="headings", height=20)

        # Initialize sort state for this tree
        tree_id = str(id(tree))
        self.sort_state[tree_id] = {'column': None, 'ascending': True}

        # Configure columns
        for col in columns:
            # Bind heading click to sort function
            tree.heading(col, text=col, command=lambda c=col, t=tree, b=is_batter: self._sort_by_column(t, c, b))

            if col == "Player":
                tree.column(col, width=150, anchor=tk.W)
            elif col in ["Team", "Pos"]:
                tree.column(col, width=60, anchor=tk.CENTER)
            elif col in ["AB", "R", "H", "2B", "3B", "HR", "RBI", "BB", "K", "G", "GS", "W", "L",
                        "ER", "SV", "SO"]:
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

        # Bind click event to show historical stats
        tree.bind('<ButtonRelease-1>', lambda e, t=tree, b=is_batter: self._on_player_click(t, b))

        return tree

    def update_stats(self, baseball_data):
        """
        Fetch and display league-wide stats.

        Args:
            baseball_data: BaseballStats instance with get_batting_data/get_pitching_data methods
        """
        # Store reference to baseball_data
        self.baseball_data = baseball_data

        try:
            # Get batting data for all teams (current season)
            batting_df = baseball_data.get_batting_data(team_name=None, prior_season=False)

            # Get pitching data for all teams (current season)
            pitching_df = baseball_data.get_pitching_data(team_name=None, prior_season=False)

            # Filter to players with at least some playing time
            if 'AB' in batting_df.columns:
                batting_df = batting_df[batting_df['AB'] > 0]
            if 'IP' in pitching_df.columns:
                pitching_df = pitching_df[pitching_df['IP'] > 0]

            # Store full DataFrames
            self.batters_df_full = batting_df.copy()
            self.pitchers_df_full = pitching_df.copy()

            # Get list of teams for filter dropdowns
            teams = ["All Teams"] + sorted(batting_df['Team'].unique().tolist())
            self.batting_team_combo['values'] = teams
            self.pitching_team_combo['values'] = teams

            # Apply initial filters (will also sort and display)
            self._apply_filters(is_batter=True)
            self._apply_filters(is_batter=False)

            logger.info(f"League stats updated: {len(batting_df)} batters, {len(pitching_df)} pitchers")

        except Exception as e:
            logger.error(f"Error updating league stats: {e}")
            import traceback
            logger.error(traceback.format_exc())

    def _apply_filters(self, is_batter: bool):
        """
        Apply team filter and name search to the data.

        Args:
            is_batter: True for batters, False for pitchers
        """
        if is_batter:
            if self.batters_df_full is None:
                return

            df = self.batters_df_full.copy()
            team = self.batting_team_var.get()
            search = self.batting_search_var.get().strip().lower()
        else:
            if self.pitchers_df_full is None:
                return

            df = self.pitchers_df_full.copy()
            team = self.pitching_team_var.get()
            search = self.pitching_search_var.get().strip().lower()

        # Apply team filter
        if team != "All Teams":
            df = df[df['Team'] == team]

        # Apply name search
        if search:
            df = df[df['Player'].str.lower().str.contains(search, na=False)]

        # Apply current sort if any
        tree = self.pos_players_tree if is_batter else self.pitchers_tree
        tree_id = str(id(tree))
        if tree_id in self.sort_state and self.sort_state[tree_id]['column'] is not None:
            sort_state = self.sort_state[tree_id]
            df = self._apply_sort(df, sort_state['column'], sort_state['ascending'], is_batter)
        else:
            # Default sort: OPS for batters, ERA for pitchers
            if is_batter and 'OPS' in df.columns:
                df = df.sort_values('OPS', ascending=False)
            elif not is_batter and 'ERA' in df.columns:
                df = df.sort_values('ERA', ascending=True)

        # Store filtered DataFrame
        if is_batter:
            self.batters_df = df
        else:
            self.pitchers_df = df

        # Update display
        self._update_stats_tree(tree, df, is_batter)

        # Update info label
        total = len(self.batters_df_full) if is_batter else len(self.pitchers_df_full)
        filtered = len(df)
        info_label = self.batting_info_label if is_batter else self.pitching_info_label

        if filtered < total:
            info_label.config(text=f"Showing {filtered} of {total} players")
        else:
            info_label.config(text=f"Showing all {total} players")

        # Update sort indicators if sort is active
        if tree_id in self.sort_state and self.sort_state[tree_id]['column'] is not None:
            self._update_sort_indicators(tree, self.sort_state[tree_id]['column'],
                                         self.sort_state[tree_id]['ascending'], is_batter)

    def _clear_filters(self, is_batter: bool):
        """
        Clear all filters and reset to default view.

        Args:
            is_batter: True for batters, False for pitchers
        """
        if is_batter:
            self.batting_team_var.set("All Teams")
            self.batting_search_var.set("")
        else:
            self.pitching_team_var.set("All Teams")
            self.pitching_search_var.set("")

        # Filters are automatically applied via trace on StringVar

    def _update_stats_tree(self, tree: ttk.Treeview, data_df: pd.DataFrame, is_batter: bool = True):
        """
        Update stats Treeview with data.

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
            logger.debug(f"Empty league data for {'batter' if is_batter else 'pitcher'}")
            return

        # Insert rows
        for idx, row in data_df.iterrows():
            try:
                if is_batter:
                    # Clean up position formatting
                    pos = row.get('Pos', 'Unknown')
                    if isinstance(pos, list):
                        pos = pos[0] if pos else 'Unknown'
                    pos = str(pos).replace('[', '').replace(']', '').replace("'", '').replace('"', '').strip()

                    values = (
                        row.get('Player', 'Unknown'),
                        row.get('Team', ''),
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
                        f"{float(row.get('OPS', 0)):.3f}"
                    )
                else:
                    values = (
                        row.get('Player', 'Unknown'),
                        row.get('Team', ''),
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
                        int(row.get('SV', 0))
                    )

                tree.insert("", tk.END, values=values)
            except Exception as e:
                logger.warning(f"Error inserting stats row for {row.get('Player', 'Unknown')}: {e}")

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
                       'WHIP', 'SV']

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
        Sort stats tree by the specified column.

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
            # Exception: ERA and WHIP should default to ascending (lower is better)
            if column in ['ERA', 'WHIP']:
                ascending = True
            else:
                ascending = False

        # Update sort state
        self.sort_state[tree_id] = {'column': column, 'ascending': ascending}

        # Reapply filters (which will also apply the new sort)
        self._apply_filters(is_batter)

        logger.debug(f"Sorted by {column}, ascending={ascending}")

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
            columns = ("Player", "Team", "Pos", "AB", "R", "H", "2B", "3B", "HR", "RBI", "BB", "K",
                      "AVG", "OBP", "SLG", "OPS")
        else:
            columns = ("Player", "Team", "G", "GS", "W", "L", "IP", "H", "R", "ER", "HR", "BB", "SO",
                      "ERA", "WHIP", "SV")

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

        # Determine which history tree to update
        history_tree = self.batters_history_tree if is_batter else self.pitchers_history_tree

        # Fetch historical data
        try:
            historical_df = self.baseball_data.get_player_historical_data(player_name, is_batter)

            if historical_df.empty:
                logger.info(f"No historical data found for {player_name}")
                # Clear the history tree
                for item in history_tree.get_children():
                    history_tree.delete(item)
                return

            # Update history tree with new data
            self._update_history_tree(history_tree, historical_df, is_batter)

        except Exception as e:
            logger.error(f"Error fetching historical data for {player_name}: {e}")
            import traceback
            logger.error(traceback.format_exc())

    def _update_history_tree(self, history_tree: ttk.Treeview, historical_df: pd.DataFrame, is_batter: bool):
        """
        Update the history tree with player's historical stats.

        Args:
            history_tree: The treeview to update
            historical_df: DataFrame with historical stats
            is_batter: True if batter, False if pitcher
        """
        # Clear existing data
        for item in history_tree.get_children():
            history_tree.delete(item)

        # Define columns based on player type
        if is_batter:
            columns = ("Season", "Team", "Age", "G", "AB", "R", "H", "HR", "RBI", "AVG", "OBP", "SLG", "OPS")
        else:
            columns = ("Season", "Team", "Age", "G", "GS", "IP", "W", "L", "ERA", "WHIP", "SO")

        # Reconfigure tree columns
        history_tree['columns'] = columns
        history_tree['show'] = 'headings'

        # Configure column headings and widths
        for col in columns:
            history_tree.heading(col, text=col)
            if col in ["Season", "Team"]:
                history_tree.column(col, width=60, anchor=tk.CENTER)
            elif col in ["Age", "G", "GS", "W", "L"]:
                history_tree.column(col, width=40, anchor=tk.CENTER)
            elif col in ["AB", "R", "H", "HR", "RBI", "SO"]:
                history_tree.column(col, width=45, anchor=tk.CENTER)
            elif col in ["AVG", "OBP", "SLG", "OPS", "ERA", "WHIP"]:
                history_tree.column(col, width=55, anchor=tk.CENTER)
            elif col == "IP":
                history_tree.column(col, width=50, anchor=tk.CENTER)
            else:
                history_tree.column(col, width=50, anchor=tk.CENTER)

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

                history_tree.insert("", tk.END, values=values)
            except Exception as e:
                logger.warning(f"Error inserting historical row: {e}")

    def get_frame(self) -> tk.Frame:
        """Get the main frame for adding to parent container."""
        return self.frame
