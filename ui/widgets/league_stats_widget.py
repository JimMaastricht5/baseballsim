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
import bbstats
from bbstats import calculate_stats_difference

from ui.theme import (
    BG_PANEL,
    BG_ELEVATED,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    TEXT_HEADING,
    ACCENT_GOLD,
    STREAK_HOT,
    STREAK_COLD,
    STREAK_NORMAL,
)

LEAGUE_MIN_SALARY = 740000


def get_streak_indicator(streak_value) -> tuple:
    """
    Generate streak indicator text and color based on streak value.

    Args:
        streak_value: The Streak_Adjustment value (float from -0.10 to 0.10)

    Returns:
        Tuple of (display_text, color)
    """
    if pd.isna(streak_value):
        return ("-", STREAK_NORMAL)

    try:
        streak = float(streak_value)
    except (ValueError, TypeError):
        return ("-", STREAK_NORMAL)

    if streak >= 0.025:
        return ("▲", STREAK_HOT)
    elif streak <= -0.025:
        return ("▼", STREAK_COLD)
    else:
        return ("-", STREAK_NORMAL)


def estimate_years_remaining(age: int, salary: float, is_pitcher: bool = False) -> int:
    """
    Estimate contract years remaining based on age and salary.
    """
    if salary <= LEAGUE_MIN_SALARY * 1.2:
        return 1
    if age < 26:
        if salary >= 20_000_000:
            return 5
        elif salary >= 10_000_000:
            return 4
        elif salary >= 5_000_000:
            return 3
        return 2
    elif age < 33:
        if salary >= 20_000_000:
            return 5
        elif salary >= 10_000_000:
            return 4
        elif salary >= 5_000_000:
            return 3
        return 2
    elif age < 38:
        if salary >= 15_000_000:
            return 3
        elif salary >= 5_000_000:
            return 2
        return 1
    return 1


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

    def __init__(self, parent: tk.Widget, comparison_mode_var: tk.StringVar = None):
        """
        Initialize league stats widget.

        Args:
            parent: Parent tkinter widget (notebook or frame)
            comparison_mode_var: StringVar for comparison mode ("current" or "difference")
        """
        self.frame = tk.Frame(parent, bg=BG_PANEL)
        self.baseball_data = None  # Will be set in update_stats

        # Create our own comparison mode var if not provided
        if comparison_mode_var is None:
            self.comparison_mode_var = tk.StringVar(value="current")
        else:
            self.comparison_mode_var = comparison_mode_var

        # Store DataFrames - full and filtered versions
        self.batters_df_full = None  # Full unfiltered data
        self.pitchers_df_full = None  # Full unfiltered data
        self.batters_df = None  # Currently displayed (filtered/sorted)
        self.pitchers_df = None  # Currently displayed (filtered/sorted)

        # Cached 2025 prorated data for comparison (Phase 4: Stats Enhancement)
        self.batters_df_2025 = None
        self.pitchers_df_2025 = None

        # Track sort state for each tree: {tree_id: {'column': str, 'ascending': bool}}
        self.sort_state = {}

        # Current filter settings
        self.selected_team = "All Teams"
        self.search_text = ""

        # Create notebook for League Stats sub-sections
        stats_notebook = ttk.Notebook(self.frame)
        stats_notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Sub-section 1: Position Players
        pos_players_frame = tk.Frame(stats_notebook, bg=BG_PANEL)
        stats_notebook.add(pos_players_frame, text="Position Players")
        self._create_pos_players_tab(pos_players_frame)

        # Sub-section 2: Pitchers
        pitchers_frame = tk.Frame(stats_notebook, bg=BG_PANEL)
        stats_notebook.add(pitchers_frame, text="Pitchers")
        self._create_pitchers_tab(pitchers_frame)

    def _create_pos_players_tab(self, parent: tk.Frame):
        """
        Create position players tab with filters.

        Args:
            parent: Parent frame
        """
        # Create control panel at top
        control_frame = tk.Frame(parent, bg=BG_PANEL)
        control_frame.pack(fill=tk.X, padx=5, pady=5)

        # Team filter
        tk.Label(
            control_frame,
            text="Team:",
            font=("Segoe UI", 10),
            bg=BG_PANEL,
            fg=TEXT_PRIMARY,
        ).pack(side=tk.LEFT, padx=(0, 5))
        self.batting_team_var = tk.StringVar(value="All Teams")
        self.batting_team_combo = ttk.Combobox(
            control_frame,
            textvariable=self.batting_team_var,
            width=15,
            state="readonly",
        )
        self.batting_team_combo.pack(side=tk.LEFT, padx=(0, 10))
        self.batting_team_combo.bind(
            "<<ComboboxSelected>>", lambda e: self._apply_filters(is_batter=True)
        )

        # Player search
        tk.Label(
            control_frame,
            text="Find Player:",
            font=("Segoe UI", 10),
            bg=BG_PANEL,
            fg=TEXT_PRIMARY,
        ).pack(side=tk.LEFT, padx=(0, 5))
        self.batting_search_var = tk.StringVar()
        self.batting_search_var.trace(
            "w", lambda *args: self._apply_filters(is_batter=True)
        )
        batting_search_entry = tk.Entry(
            control_frame,
            textvariable=self.batting_search_var,
            width=20,
            font=("Segoe UI", 10),
            bg=BG_ELEVATED,
            fg=TEXT_PRIMARY,
            insertbackground=TEXT_PRIMARY,
            relief=tk.FLAT,
        )
        batting_search_entry.pack(side=tk.LEFT, padx=(0, 5))

        # Clear button
        clear_btn = ttk.Button(
            control_frame,
            text="Clear Filters",
            command=lambda: self._clear_filters(is_batter=True),
            style="Nav.TButton",
        )
        clear_btn.pack(side=tk.LEFT, padx=5)

        # Comparison mode toggle (Phase 3 revision)
        tk.Label(
            control_frame,
            text="  |  View:",
            font=("Segoe UI", 10),
            bg=BG_PANEL,
            fg=TEXT_PRIMARY,
        ).pack(side=tk.LEFT, padx=(10, 5))
        self.batting_comparison_btn = tk.Button(
            control_frame,
            text="Show Difference from 2025",
            command=self._toggle_comparison_mode,
            bg=BG_ELEVATED,
            fg=TEXT_PRIMARY,
            activebackground=BG_PANEL,
            activeforeground=TEXT_PRIMARY,
            relief=tk.RAISED,
            font=("Segoe UI", 9),
        )
        self.batting_comparison_btn.pack(side=tk.LEFT, padx=5)

        # Info label
        self.batting_info_label = tk.Label(
            control_frame, text="", font=("Segoe UI", 9), bg=BG_PANEL, fg=TEXT_SECONDARY
        )
        self.batting_info_label.pack(side=tk.LEFT, padx=10)

        # Create treeview
        self.pos_players_tree = self._create_stats_treeview(parent, is_batter=True)

        # Add league totals section
        separator = ttk.Separator(parent, orient=tk.HORIZONTAL)
        separator.pack(fill=tk.X, padx=5, pady=10)

        totals_label = tk.Label(
            parent,
            text="League Batting Totals",
            font=("Segoe UI", 11, "bold"),
            bg=BG_PANEL,
            fg=TEXT_HEADING,
        )
        totals_label.pack(padx=5, pady=(0, 5))

        self.batting_totals_frame = tk.Frame(
            parent, bg=BG_PANEL, relief=tk.FLAT, borderwidth=0
        )
        self.batting_totals_frame.pack(fill=tk.X, padx=5, pady=5)

        self.batting_totals_labels = {}  # Store label references for updating
        # Historical stats shown in popup window when player is clicked

    def _create_pitchers_tab(self, parent: tk.Frame):
        """
        Create pitchers tab with filters.

        Args:
            parent: Parent frame
        """
        # Create control panel at top
        control_frame = tk.Frame(parent, bg=BG_PANEL)
        control_frame.pack(fill=tk.X, padx=5, pady=5)

        # Team filter
        tk.Label(
            control_frame,
            text="Team:",
            font=("Segoe UI", 10),
            bg=BG_PANEL,
            fg=TEXT_PRIMARY,
        ).pack(side=tk.LEFT, padx=(0, 5))
        self.pitching_team_var = tk.StringVar(value="All Teams")
        self.pitching_team_combo = ttk.Combobox(
            control_frame,
            textvariable=self.pitching_team_var,
            width=15,
            state="readonly",
        )
        self.pitching_team_combo.pack(side=tk.LEFT, padx=(0, 10))
        self.pitching_team_combo.bind(
            "<<ComboboxSelected>>", lambda e: self._apply_filters(is_batter=False)
        )

        # Player search
        tk.Label(
            control_frame,
            text="Find Player:",
            font=("Segoe UI", 10),
            bg=BG_PANEL,
            fg=TEXT_PRIMARY,
        ).pack(side=tk.LEFT, padx=(0, 5))
        self.pitching_search_var = tk.StringVar()
        self.pitching_search_var.trace(
            "w", lambda *args: self._apply_filters(is_batter=False)
        )
        pitching_search_entry = tk.Entry(
            control_frame,
            textvariable=self.pitching_search_var,
            width=20,
            font=("Segoe UI", 10),
            bg=BG_ELEVATED,
            fg=TEXT_PRIMARY,
            insertbackground=TEXT_PRIMARY,
            relief=tk.FLAT,
        )
        pitching_search_entry.pack(side=tk.LEFT, padx=(0, 5))

        # Clear button
        clear_btn = ttk.Button(
            control_frame,
            text="Clear Filters",
            command=lambda: self._clear_filters(is_batter=False),
            style="Nav.TButton",
        )
        clear_btn.pack(side=tk.LEFT, padx=5)

        # Comparison mode toggle (Phase 3 revision)
        tk.Label(
            control_frame,
            text="  |  View:",
            font=("Segoe UI", 10),
            bg=BG_PANEL,
            fg=TEXT_PRIMARY,
        ).pack(side=tk.LEFT, padx=(10, 5))
        self.pitching_comparison_btn = tk.Button(
            control_frame,
            text="Show Difference from 2025",
            command=self._toggle_comparison_mode,
            bg=BG_ELEVATED,
            fg=TEXT_PRIMARY,
            activebackground=BG_PANEL,
            activeforeground=TEXT_PRIMARY,
            relief=tk.RAISED,
            font=("Segoe UI", 9),
        )
        self.pitching_comparison_btn.pack(side=tk.LEFT, padx=5)

        # Info label
        self.pitching_info_label = tk.Label(
            control_frame, text="", font=("Segoe UI", 9), bg=BG_PANEL, fg=TEXT_SECONDARY
        )
        self.pitching_info_label.pack(side=tk.LEFT, padx=10)

        # Create treeview
        self.pitchers_tree = self._create_stats_treeview(parent, is_batter=False)

        # Add league totals section
        separator = ttk.Separator(parent, orient=tk.HORIZONTAL)
        separator.pack(fill=tk.X, padx=5, pady=10)

        totals_label = tk.Label(
            parent,
            text="League Pitching Totals",
            font=("Segoe UI", 11, "bold"),
            bg=BG_PANEL,
            fg=TEXT_HEADING,
        )
        totals_label.pack(padx=5, pady=(0, 5))

        self.pitching_totals_frame = tk.Frame(
            parent, bg=BG_PANEL, relief=tk.FLAT, borderwidth=0
        )
        self.pitching_totals_frame.pack(fill=tk.X, padx=5, pady=5)

        self.pitching_totals_labels = {}  # Store label references for updating
        # Historical stats shown in popup window when player is clicked

    def _create_stats_treeview(
        self, parent: tk.Widget, is_batter: bool = True
    ) -> ttk.Treeview:
        """
        Create Treeview for league stats data.

        Args:
            parent: Parent widget
            is_batter: True for batters, False for pitchers

        Returns:
            ttk.Treeview: Configured treeview
        """
        if is_batter:
            columns = (
                "Player",
                "Team",
                "Pos",
                "G",
                "AB",
                "R",
                "H",
                "2B",
                "3B",
                "HR",
                "RBI",
                "BB",
                "K",
                "AVG",
                "OBP",
                "SLG",
                "OPS",
                "Salary",
                "Years",
                "Str",
            )
        else:
            columns = (
                "Player",
                "Team",
                "G",
                "GS",
                "W",
                "L",
                "IP",
                "H",
                "R",
                "ER",
                "HR",
                "BB",
                "SO",
                "ERA",
                "WHIP",
                "SV",
                "Salary",
                "Years",
                "Str",
            )

        tree = ttk.Treeview(parent, columns=columns, show="headings", height=17)

        # Initialize sort state for this tree
        tree_id = str(id(tree))
        self.sort_state[tree_id] = {"column": None, "ascending": True}

        # Configure columns
        for col in columns:
            # Bind heading click to sort function
            tree.heading(
                col,
                text=col,
                command=lambda c=col, t=tree, b=is_batter: self._sort_by_column(
                    t, c, b
                ),
            )

            if col == "Player":
                tree.column(col, width=150, anchor=tk.W)
            elif col in ["Team", "Pos"]:
                tree.column(col, width=60, anchor=tk.CENTER)
            elif col in [
                "AB",
                "R",
                "H",
                "2B",
                "3B",
                "HR",
                "RBI",
                "BB",
                "K",
                "G",
                "GS",
                "W",
                "L",
                "ER",
                "SV",
                "SO",
                "Years",
            ]:
                tree.column(col, width=45, anchor=tk.CENTER)
            elif col in ["AVG", "OBP", "SLG", "OPS", "ERA", "WHIP"]:
                tree.column(col, width=55, anchor=tk.CENTER)
            elif col == "IP":
                tree.column(col, width=50, anchor=tk.CENTER)
            elif col == "Salary":
                tree.column(col, width=65, anchor=tk.CENTER)
            elif col == "Str":
                tree.column(col, width=30, anchor=tk.CENTER)
            else:
                tree.column(col, width=50, anchor=tk.CENTER)

        # Add scrollbar
        scrollbar = ttk.Scrollbar(parent, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        tree.pack(fill=tk.BOTH, expand=True)

        # Configure tags for streak highlighting
        tree.tag_configure("streak_hot", foreground=STREAK_HOT)
        tree.tag_configure("streak_cold", foreground=STREAK_COLD)
        tree.tag_configure("streak_normal", foreground=STREAK_NORMAL)

        # Bind double-click to open history popup (single click just highlights)
        tree.bind(
            "<Double-Button-1>",
            lambda e, t=tree, b=is_batter: self._on_player_click(t, b),
        )

        # Bind right-click and Ctrl+C for clipboard copy
        tree.bind("<Button-3>", lambda e, t=tree: self._show_copy_menu(e, t))
        tree.bind("<Control-c>", lambda e, t=tree: self._copy_selected_rows(t))

        return tree

    def update_stats(self, baseball_data, team_win_loss: dict = None):
        """
        Fetch and display league-wide stats.

        Args:
            baseball_data: BaseballStats instance with get_batting_data/get_pitching_data methods
            team_win_loss: Dictionary mapping team names to [wins, losses] for calculating actual games played
        """
        # Store reference to baseball_data
        self.baseball_data = baseball_data
        self.team_win_loss = team_win_loss  # Store for games played calculation

        try:
            # Get batting data for all teams (current season)
            batting_df = baseball_data.get_batting_data(
                team_name=None, prior_season=False
            )

            # Get pitching data for all teams (current season)
            pitching_df = baseball_data.get_pitching_data(
                team_name=None, prior_season=False
            )

            # Store full DataFrames (don't filter out 0 AB/IP - show all players at season start)
            self.batters_df_full = batting_df.copy()
            self.pitchers_df_full = pitching_df.copy()

            # Get list of teams for filter dropdowns
            teams = ["All Teams"] + sorted(batting_df["Team"].unique().tolist())
            self.batting_team_combo["values"] = teams
            self.pitching_team_combo["values"] = teams

            # Apply initial filters (will also sort and display)
            self._apply_filters(is_batter=True)
            self._apply_filters(is_batter=False)

            # Update totals displays
            self._update_totals_display(is_batter=True)
            self._update_totals_display(is_batter=False)

            logger.info(
                f"League stats updated: {len(batting_df)} batters, {len(pitching_df)} pitchers"
            )

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
            df = df[df["Team"] == team]

        # Apply name search
        if search:
            df = df[df["Player"].str.lower().str.contains(search, na=False)]

        # Apply current sort if any
        tree = self.pos_players_tree if is_batter else self.pitchers_tree
        tree_id = str(id(tree))
        if (
            tree_id in self.sort_state
            and self.sort_state[tree_id]["column"] is not None
        ):
            sort_state = self.sort_state[tree_id]
            df = self._apply_sort(
                df, sort_state["column"], sort_state["ascending"], is_batter
            )
        else:
            # Default sort: OPS for batters, IP descending for pitchers
            if is_batter and "OPS" in df.columns:
                df = df.sort_values("OPS", ascending=False)
            elif not is_batter and "IP" in df.columns:
                df = df.sort_values("IP", ascending=False)

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
        if (
            tree_id in self.sort_state
            and self.sort_state[tree_id]["column"] is not None
        ):
            self._update_sort_indicators(
                tree,
                self.sort_state[tree_id]["column"],
                self.sort_state[tree_id]["ascending"],
                is_batter,
            )

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

    def _update_stats_tree(
        self, tree: ttk.Treeview, data_df: pd.DataFrame, is_batter: bool = True
    ):
        """
        Update stats Treeview with data (Phase 4: Supports comparison mode).

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
            logger.debug(
                f"Empty league data for {'batter' if is_batter else 'pitcher'}"
            )
            return

        # Check comparison mode and calculate differences if needed
        mode = self.comparison_mode_var.get() if self.comparison_mode_var else "current"
        display_df = data_df

        if mode == "difference":
            display_df = self._calculate_difference_df(data_df, is_batter)

        # Insert rows
        for idx, row in display_df.iterrows():
            try:
                if is_batter:
                    # Clean up position formatting
                    pos = row.get("Pos", "Unknown")
                    if isinstance(pos, list):
                        pos = pos[0] if pos else "Unknown"
                    pos = (
                        str(pos)
                        .replace("[", "")
                        .replace("]", "")
                        .replace("'", "")
                        .replace('"', "")
                        .strip()
                    )

                    # Get salary and calculate years remaining
                    salary = row.get("Salary", LEAGUE_MIN_SALARY)
                    age = row.get("Age", 30)
                    years_rem = estimate_years_remaining(age, salary, is_pitcher=False)
                    salary_display = f"${salary / 1e6:.1f}M" if salary else "-"

                    if mode == "difference":
                        # Format with +/- prefix for difference mode
                        streak_text, _ = get_streak_indicator(
                            row.get("Streak_Adjustment")
                        )
                        values = (
                            row.get("Player", "Unknown"),
                            row.get("Team", ""),
                            pos,
                            self._format_diff_value(row.get("G", 0)),
                            self._format_diff_value(row.get("AB", 0)),
                            self._format_diff_value(row.get("R", 0)),
                            self._format_diff_value(row.get("H", 0)),
                            self._format_diff_value(row.get("2B", 0)),
                            self._format_diff_value(row.get("3B", 0)),
                            self._format_diff_value(row.get("HR", 0)),
                            self._format_diff_value(row.get("RBI", 0)),
                            self._format_diff_value(row.get("BB", 0)),
                            self._format_diff_value(row.get("SO", 0)),
                            self._format_diff_value(row.get("AVG", 0), decimals=3),
                            self._format_diff_value(row.get("OBP", 0), decimals=3),
                            self._format_diff_value(row.get("SLG", 0), decimals=3),
                            self._format_diff_value(row.get("OPS", 0), decimals=3),
                            salary_display,
                            years_rem,
                            streak_text,
                        )
                    else:
                        # Standard format for current stats
                        streak_text, _ = get_streak_indicator(
                            row.get("Streak_Adjustment")
                        )
                        values = (
                            row.get("Player", "Unknown"),
                            row.get("Team", ""),
                            pos,
                            int(row.get("G", 0)),
                            int(row.get("AB", 0)),
                            int(row.get("R", 0)),
                            int(row.get("H", 0)),
                            int(row.get("2B", 0)),
                            int(row.get("3B", 0)),
                            int(row.get("HR", 0)),
                            int(row.get("RBI", 0)),
                            int(row.get("BB", 0)),
                            int(row.get("SO", 0)),
                            f"{float(row.get('AVG', 0)):.3f}",
                            f"{float(row.get('OBP', 0)):.3f}",
                            f"{float(row.get('SLG', 0)):.3f}",
                            f"{float(row.get('OPS', 0)):.3f}",
                            salary_display,
                            years_rem,
                            streak_text,
                        )
                else:
                    # Get salary and calculate years remaining
                    salary = row.get("Salary", LEAGUE_MIN_SALARY)
                    age = row.get("Age", 30)
                    years_rem = estimate_years_remaining(age, salary, is_pitcher=True)
                    salary_display = f"${salary / 1e6:.1f}M" if salary else "-"

                    if mode == "difference":
                        # Format with +/- prefix for difference mode
                        streak_text, _ = get_streak_indicator(
                            row.get("Streak_Adjustment")
                        )
                        values = (
                            row.get("Player", "Unknown"),
                            row.get("Team", ""),
                            self._format_diff_value(row.get("G", 0)),
                            self._format_diff_value(row.get("GS", 0)),
                            self._format_diff_value(row.get("W", 0)),
                            self._format_diff_value(row.get("L", 0)),
                            self._format_diff_value(row.get("IP", 0), decimals=1),
                            self._format_diff_value(row.get("H", 0)),
                            self._format_diff_value(row.get("R", 0)),
                            self._format_diff_value(row.get("ER", 0)),
                            self._format_diff_value(row.get("HR", 0)),
                            self._format_diff_value(row.get("BB", 0)),
                            self._format_diff_value(row.get("SO", 0)),
                            self._format_diff_value(row.get("ERA", 0), decimals=2),
                            self._format_diff_value(row.get("WHIP", 0), decimals=2),
                            self._format_diff_value(row.get("SV", 0)),
                            salary_display,
                            years_rem,
                            streak_text,
                        )
                    else:
                        # Standard format for current stats
                        streak_text, _ = get_streak_indicator(
                            row.get("Streak_Adjustment")
                        )
                        values = (
                            row.get("Player", "Unknown"),
                            row.get("Team", ""),
                            int(row.get("G", 0)),
                            int(row.get("GS", 0)),
                            int(row.get("W", 0)),
                            int(row.get("L", 0)),
                            f"{float(row.get('IP', 0)):.1f}",
                            int(row.get("H", 0)),
                            int(row.get("R", 0)),
                            int(row.get("ER", 0)),
                            int(row.get("HR", 0)),
                            int(row.get("BB", 0)),
                            int(row.get("SO", 0)),
                            f"{float(row.get('ERA', 0)):.2f}",
                            f"{float(row.get('WHIP', 0)):.2f}",
                            int(row.get("SV", 0)),
                            salary_display,
                            years_rem,
                            streak_text,
                        )

                # Determine streak tag
                streak_value = row.get("Streak_Adjustment")
                streak_tag = ()
                if streak_value is not None:
                    try:
                        streak = float(streak_value)
                        if streak >= 0.025:
                            streak_tag = ("streak_hot",)
                        elif streak <= -0.025:
                            streak_tag = ("streak_cold",)
                    except (ValueError, TypeError):
                        pass

                tree.insert("", tk.END, values=values, tags=streak_tag)
            except Exception as e:
                logger.warning(
                    f"Error inserting stats row for {row.get('Player', 'Unknown')}: {e}"
                )

    def _apply_sort(
        self, df: pd.DataFrame, column: str, ascending: bool, is_batter: bool
    ) -> pd.DataFrame:
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
            "K": "SO"  # Display column "K" maps to DataFrame column "SO"
        }

        # Get the actual DataFrame column name
        df_column = column_mapping.get(column, column)

        # Determine if column is numeric or text
        numeric_cols = [
            "G",
            "AB",
            "R",
            "H",
            "2B",
            "3B",
            "HR",
            "RBI",
            "BB",
            "SO",
            "K",
            "AVG",
            "OBP",
            "SLG",
            "OPS",
            "GS",
            "W",
            "L",
            "IP",
            "ER",
            "ERA",
            "WHIP",
            "SV",
        ]

        try:
            if df_column in df.columns:
                # Handle numeric vs text sorting
                if column in numeric_cols or df_column in numeric_cols:
                    # Convert to numeric, handling any non-numeric values
                    sorted_df = df.copy()
                    sorted_df[df_column] = pd.to_numeric(
                        sorted_df[df_column], errors="coerce"
                    )
                    sorted_df = sorted_df.sort_values(
                        df_column, ascending=ascending, na_position="last"
                    )
                else:
                    # Text sorting
                    sorted_df = df.sort_values(
                        df_column, ascending=ascending, na_position="last"
                    )

                return sorted_df
            else:
                logger.warning(
                    f"Column {column} (mapped to {df_column}) not found in DataFrame"
                )
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
            self.sort_state[tree_id] = {"column": None, "ascending": True}

        current_state = self.sort_state[tree_id]

        # Determine sort direction
        if current_state["column"] == column:
            # Toggle direction if clicking same column
            ascending = not current_state["ascending"]
        else:
            # Default to descending for new column (most useful for stats)
            # Exception: ERA and WHIP should default to ascending (lower is better)
            if column in ["ERA", "WHIP"]:
                ascending = True
            else:
                ascending = False

        # Update sort state
        self.sort_state[tree_id] = {"column": column, "ascending": ascending}

        # Reapply filters (which will also apply the new sort)
        self._apply_filters(is_batter)

        logger.debug(f"Sorted by {column}, ascending={ascending}")

    def _update_sort_indicators(
        self, tree: ttk.Treeview, sorted_column: str, ascending: bool, is_batter: bool
    ):
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
            columns = (
                "Player",
                "Team",
                "Pos",
                "AB",
                "R",
                "H",
                "2B",
                "3B",
                "HR",
                "RBI",
                "BB",
                "K",
                "AVG",
                "OBP",
                "SLG",
                "OPS",
            )
        else:
            columns = (
                "Player",
                "Team",
                "G",
                "GS",
                "W",
                "L",
                "IP",
                "H",
                "R",
                "ER",
                "HR",
                "BB",
                "SO",
                "ERA",
                "WHIP",
                "SV",
            )

        # Update all column headings
        for col in columns:
            if col == sorted_column:
                # Add sort indicator to sorted column
                indicator = " ↑" if ascending else " ↓"
                tree.heading(
                    col,
                    text=f"{col}{indicator}",
                    command=lambda c=col: self._sort_by_column(tree, c, is_batter),
                )
            else:
                # Remove indicator from other columns
                tree.heading(
                    col,
                    text=col,
                    command=lambda c=col: self._sort_by_column(tree, c, is_batter),
                )

    def _on_player_click(self, tree: ttk.Treeview, is_batter: bool):
        """
        Handle player row click - open popup with historical stats.

        Args:
            tree: The treeview that was clicked
            is_batter: True if batter tree, False if pitcher tree
        """
        selection = tree.selection()
        if not selection:
            return

        item = selection[0]
        values = tree.item(item, "values")
        if not values:
            return

        player_name = values[0]
        logger.info(f"Player clicked: {player_name} (is_batter={is_batter})")

        if not self.baseball_data:
            logger.warning("baseball_data not available for historical lookup")
            return

        try:
            historical_df = self.baseball_data.get_player_historical_data(
                player_name, is_batter
            )

            if historical_df.empty:
                logger.info(f"No historical data found for {player_name}")
                return

            projected_row = self.baseball_data.get_player_projected_data(
                player_name, is_batter
            )
            self._show_history_popup(
                player_name, historical_df, is_batter, projected_row
            )

        except Exception as e:
            logger.error(f"Error fetching historical data for {player_name}: {e}")
            import traceback

            logger.error(traceback.format_exc())

    def _show_history_popup(
        self, player_name: str, historical_df, is_batter: bool, projected_row=None
    ):
        """
        Open a popup window showing player historical stats with projected row at top.

        Args:
            player_name: Player name for window title
            historical_df: DataFrame with historical stats
            is_batter: True for batting columns, False for pitching columns
            projected_row: Optional Series with projected new-season stats
        """
        popup = tk.Toplevel()
        popup.title(f"{player_name} - Historical Stats")
        popup.geometry("1100x350")
        popup.resizable(True, True)
        popup.configure(bg=BG_PANEL)

        if is_batter:
            columns = (
                "Season",
                "Team",
                "Age",
                "G",
                "AB",
                "R",
                "H",
                "2B",
                "3B",
                "HR",
                "RBI",
                "BB",
                "K",
                "AVG",
                "OBP",
                "SLG",
                "OPS",
            )
        else:
            columns = (
                "Season",
                "Team",
                "Age",
                "G",
                "GS",
                "IP",
                "W",
                "L",
                "H",
                "R",
                "ER",
                "HR",
                "BB",
                "SO",
                "ERA",
                "WHIP",
            )

        tree_frame = tk.Frame(popup, bg=BG_PANEL)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(10, 5))

        scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        tree = ttk.Treeview(
            tree_frame,
            columns=columns,
            show="headings",
            height=8,
            yscrollcommand=scrollbar.set,
        )
        scrollbar.config(command=tree.yview)
        tree.tag_configure("projected", foreground="#d4a017")

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

        # Clipboard copy helpers for this popup
        def _copy_history():
            sel = tree.selection()
            if not sel:
                return
            header = "\t".join(columns)
            rows = ["\t".join(str(v) for v in tree.item(i, "values")) for i in sel]
            tree.clipboard_clear()
            tree.clipboard_append(header + "\n" + "\n".join(rows))

        def _show_history_copy_menu(event):
            item = tree.identify_row(event.y)
            if item:
                tree.selection_set(item)
            menu = tk.Menu(tree, tearoff=0)
            menu.add_command(label="Copy Row", command=_copy_history)
            try:
                menu.tk_popup(event.x_root, event.y_root)
            finally:
                menu.grab_release()

        tree.bind("<Button-3>", _show_history_copy_menu)
        tree.bind("<Control-c>", lambda e: _copy_history())

        # Insert projected row at top if available
        if projected_row is not None:
            try:
                r = projected_row
                if is_batter:
                    avg_val = r.get("AVG", r.get("BA", 0))
                    values = (
                        "Projected",
                        r.get("Team", ""),
                        int(r.get("Age", 0)),
                        int(r.get("G", 0)),
                        int(r.get("AB", 0)),
                        int(r.get("R", 0)),
                        int(r.get("H", 0)),
                        int(r.get("2B", 0)),
                        int(r.get("3B", 0)),
                        int(r.get("HR", 0)),
                        int(r.get("RBI", 0)),
                        int(r.get("BB", 0)),
                        int(r.get("SO", 0)),
                        f"{float(avg_val):.3f}",
                        f"{float(r.get('OBP', 0)):.3f}",
                        f"{float(r.get('SLG', 0)):.3f}",
                        f"{float(r.get('OPS', 0)):.3f}",
                    )
                else:
                    values = (
                        "Projected",
                        r.get("Team", ""),
                        int(r.get("Age", 0)),
                        int(r.get("G", 0)),
                        int(r.get("GS", 0)),
                        f"{float(r.get('IP', 0)):.1f}",
                        int(r.get("W", 0)),
                        int(r.get("L", 0)),
                        int(r.get("H", 0)),
                        int(r.get("R", 0)),
                        int(r.get("ER", 0)),
                        int(r.get("HR", 0)),
                        int(r.get("BB", 0)),
                        int(r.get("SO", 0)),
                        f"{float(r.get('ERA', 0)):.2f}",
                        f"{float(r.get('WHIP', 0)):.2f}",
                    )
                tree.insert("", tk.END, values=values, tags=("projected",))
            except Exception as e:
                logger.warning(f"Error inserting projected row: {e}")

        # Filter out current season from historical (projected row shows current season)
        current_season = getattr(self.baseball_data, "new_season", None)
        if current_season and "Season" in historical_df.columns:
            historical_df = historical_df[historical_df["Season"] != current_season]

        for idx, row in historical_df.iterrows():
            try:
                if is_batter:
                    values = (
                        int(row.get("Season", 0)),
                        row.get("Team", ""),
                        int(row.get("Age", 0)),
                        int(row.get("G", 0)),
                        int(row.get("AB", 0)),
                        int(row.get("R", 0)),
                        int(row.get("H", 0)),
                        int(row.get("2B", 0)),
                        int(row.get("3B", 0)),
                        int(row.get("HR", 0)),
                        int(row.get("RBI", 0)),
                        int(row.get("BB", 0)),
                        int(row.get("SO", 0)),
                        f"{float(row.get('AVG', 0)):.3f}",
                        f"{float(row.get('OBP', 0)):.3f}",
                        f"{float(row.get('SLG', 0)):.3f}",
                        f"{float(row.get('OPS', 0)):.3f}",
                    )
                else:
                    values = (
                        int(row.get("Season", 0)),
                        row.get("Team", ""),
                        int(row.get("Age", 0)),
                        int(row.get("G", 0)),
                        int(row.get("GS", 0)),
                        f"{float(row.get('IP', 0)):.1f}",
                        int(row.get("W", 0)),
                        int(row.get("L", 0)),
                        int(row.get("H", 0)),
                        int(row.get("R", 0)),
                        int(row.get("ER", 0)),
                        int(row.get("HR", 0)),
                        int(row.get("BB", 0)),
                        int(row.get("SO", 0)),
                        f"{float(row.get('ERA', 0)):.2f}",
                        f"{float(row.get('WHIP', 0)):.2f}",
                    )
                tree.insert("", tk.END, values=values)
            except Exception as e:
                logger.warning(f"Error inserting historical row: {e}")

        ttk.Button(
            popup, text="Close", command=popup.destroy, width=10, style="Nav.TButton"
        ).pack(pady=5)
        popup.focus_set()

    def _toggle_comparison_mode(self):
        """Toggle between current stats and difference view (Phase 3 revision)."""
        current_mode = self.comparison_mode_var.get()
        new_mode = "difference" if current_mode == "current" else "current"
        self.comparison_mode_var.set(new_mode)

        # Update button appearance and text (dark-theme appropriate colours)
        if new_mode == "difference":
            self.batting_comparison_btn.config(
                text="Show Current Stats",
                bg="#3d2d00",
                fg=ACCENT_GOLD,
                relief=tk.SUNKEN,
            )
            self.pitching_comparison_btn.config(
                text="Show Current Stats",
                bg="#3d2d00",
                fg=ACCENT_GOLD,
                relief=tk.SUNKEN,
            )
        else:
            self.batting_comparison_btn.config(
                text="Show Difference from 2025",
                bg=BG_ELEVATED,
                fg=TEXT_PRIMARY,
                relief=tk.RAISED,
            )
            self.pitching_comparison_btn.config(
                text="Show Difference from 2025",
                bg=BG_ELEVATED,
                fg=TEXT_PRIMARY,
                relief=tk.RAISED,
            )

        # Refresh display
        self.refresh_display()

    def refresh_display(self):
        """
        Refresh display when comparison mode changes (Phase 4: Stats Enhancement).
        Re-applies filters and updates the display.
        """
        if self.batters_df_full is not None:
            self._apply_filters(is_batter=True)
        if self.pitchers_df_full is not None:
            self._apply_filters(is_batter=False)

    def _load_2025_data(self):
        """Load and cache 2025 historical data for comparison (Phase 4: Stats Enhancement)."""
        if self.baseball_data is None:
            return

        # Determine games played from W-L records (same logic as _update_totals_display)
        games_played = 0
        if self.team_win_loss:
            games_played = max(
                (
                    wins + losses
                    for team, (wins, losses) in self.team_win_loss.items()
                    if team != "OFF DAY"
                ),
                default=0,
            )

        # Calculate prorated 2025 stats for league-wide view (no team filter)
        self.batters_df_2025, self.pitchers_df_2025 = (
            self.baseball_data.calculate_prorated_2025_stats(
                team_name=None,
                current_games_played=games_played if games_played > 0 else None,
            )
        )

        logger.info(
            f"Loaded 2025 league data: {len(self.batters_df_2025)} batters, {len(self.pitchers_df_2025)} pitchers (games_played={games_played})"
        )

    def _calculate_difference_df(
        self, current_df: pd.DataFrame, is_batter: bool
    ) -> pd.DataFrame:
        """
        Calculate current - prorated 2025 for each player (Phase 4: Stats Enhancement).

        Args:
            current_df: Current season DataFrame
            is_batter: True for batters, False for pitchers

        Returns:
            DataFrame with difference values
        """
        # Always reload to get correct proration for current games_played
        self._load_2025_data()

        hist_df = self.batters_df_2025 if is_batter else self.pitchers_df_2025

        if hist_df is None or hist_df.empty:
            logger.warning("No 2025 historical data available for comparison")
            return current_df

        return calculate_stats_difference(current_df, hist_df, is_batter)

    def _format_diff_value(self, value, decimals=0):
        """
        Format difference value with +/- prefix (Phase 4: Stats Enhancement).

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
        Update the totals display with three-row format (Current / 2025 Prorated / Difference).

        Args:
            is_batter: True for batting totals, False for pitching totals
        """
        if is_batter:
            df = self.batters_df_full
            frame = self.batting_totals_frame
            labels_dict = self.batting_totals_labels
        else:
            df = self.pitchers_df_full
            frame = self.pitching_totals_frame
            labels_dict = self.pitching_totals_labels

        if df is None or df.empty or self.baseball_data is None:
            return

        # Clear existing widgets
        for widget in frame.winfo_children():
            widget.destroy()
        labels_dict.clear()

        # Calculate current totals
        if is_batter:
            current_totals = bbstats.team_batting_totals(df)
            columns = [
                "",
                "AB",
                "R",
                "H",
                "2B",
                "3B",
                "HR",
                "RBI",
                "BB",
                "SO",
                "AVG",
                "OBP",
                "SLG",
                "OPS",
            ]
        else:
            current_totals = bbstats.team_pitching_totals(df)
            # For pitching, sum G (total pitcher appearances) instead of max
            if "G" in df.columns:
                current_totals["G"] = df["G"].sum()
            columns = [
                "",
                "G",
                "GS",
                "W",
                "L",
                "IP",
                "H",
                "R",
                "ER",
                "HR",
                "BB",
                "SO",
                "ERA",
                "WHIP",
                "SV",
            ]

        # Create treeview for totals with scrollbar
        totals_frame = tk.Frame(frame, bg=BG_PANEL)
        totals_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        totals_tree = ttk.Treeview(
            totals_frame, columns=columns, show="headings", height=3
        )

        # Add vertical scrollbar for totals
        totals_scroll = ttk.Scrollbar(
            totals_frame, orient=tk.VERTICAL, command=totals_tree.yview
        )
        totals_tree.configure(yscrollcommand=totals_scroll.set)

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

        # Pack tree and scrollbar
        totals_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        totals_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        # Determine games played from W-L records (maximum games played across all teams)
        games_played = 0
        if self.team_win_loss:
            # For league stats, use max games (W+L) across all teams
            games_played = max(
                (
                    wins + losses
                    for team, (wins, losses) in self.team_win_loss.items()
                    if team != "OFF DAY"
                ),
                default=0,
            )

        # Get prorated 2025 stats for league (explicitly pass games_played so we know the proration basis)
        batting_2025, pitching_2025 = self.baseball_data.calculate_prorated_2025_stats(
            team_name=None,
            current_games_played=games_played if games_played > 0 else None,
        )

        if (is_batter and not batting_2025.empty) or (
            not is_batter and not pitching_2025.empty
        ):
            # Calculate 2025 totals
            if is_batter:
                prorated_totals = bbstats.team_batting_totals(batting_2025)
            else:
                prorated_totals = bbstats.team_pitching_totals(pitching_2025)
                # For pitching, sum G (total pitcher appearances) instead of max
                if "G" in pitching_2025.columns:
                    prorated_totals["G"] = pitching_2025["G"].sum()

            # Calculate differences
            diff_totals = current_totals.copy()
            for col in columns[1:]:  # Skip empty label column
                if col in current_totals.columns and col in prorated_totals.columns:
                    diff_totals[col] = (
                        current_totals[col].values[0] - prorated_totals[col].values[0]
                    )

            # Create labels with game counts
            current_label = (
                f"2026 ({games_played} games)" if games_played > 0 else "Current"
            )
            if games_played >= 162:
                season_label = f"2025 (prorated {games_played} games)"
            else:
                season_label = (
                    f"2025 (prorated {games_played} games)"
                    if games_played > 0
                    else "2025 (Prorated)"
                )

            # Insert three rows
            row_data = [
                (current_label, current_totals, False),
                (season_label, prorated_totals, False),
                ("Difference", diff_totals, True),
            ]

            for label, data, is_diff in row_data:
                values = [label]
                for col in columns[1:]:
                    if col in data.columns:
                        values.append(
                            self._format_total_value(data[col].values[0], col, is_diff)
                        )
                    else:
                        values.append("")
                totals_tree.insert("", tk.END, values=tuple(values))
        else:
            # No 2025 data, show current only
            current_label = (
                f"2026 ({games_played} games)" if games_played > 0 else "Current"
            )
            values = [current_label]
            for col in columns[1:]:
                if col in current_totals.columns:
                    values.append(
                        self._format_total_value(
                            current_totals[col].values[0], col, False
                        )
                    )
                else:
                    values.append("")
            totals_tree.insert("", tk.END, values=tuple(values))

        # Right-click and Ctrl+C to copy rows
        totals_tree.bind(
            "<Button-3>", lambda e, t=totals_tree: self._show_copy_menu(e, t)
        )
        totals_tree.bind(
            "<Control-c>", lambda e, t=totals_tree: self._copy_selected_rows(t)
        )

    def _format_total_value(self, value, col_name: str, is_difference: bool = False):
        """Format a total value for display."""
        if pd.isna(value):
            return "N/A"

        # Determine decimal places
        if col_name in ["AVG", "OBP", "SLG", "OPS"]:
            formatted = f"{value:.3f}"
        elif col_name in ["ERA", "WHIP"]:
            formatted = f"{value:.2f}"
        elif col_name == "IP":
            formatted = f"{value:.1f}"
        else:
            formatted = f"{int(value)}"

        # Add +/- prefix for differences
        if is_difference and value > 0:
            return f"+{formatted}"
        return formatted

    def _copy_selected_rows(self, tree: ttk.Treeview):
        """Copy selected row(s) to clipboard as tab-separated values with column headers."""
        selected = tree.selection()
        if not selected:
            return
        columns = tree["columns"]
        header = "\t".join(columns)
        rows = [
            "\t".join(str(v) for v in tree.item(item, "values")) for item in selected
        ]
        tree.clipboard_clear()
        tree.clipboard_append(header + "\n" + "\n".join(rows))

    def _show_copy_menu(self, event, tree: ttk.Treeview):
        """Show right-click context menu with view history and copy options."""
        item = tree.identify_row(event.y)
        if not item:
            return

        tree.selection_set(item)
        values = tree.item(item, "values")
        if not values:
            return

        player_name = values[0] if values else ""

        # Determine if this is the batters or pitchers tree
        is_batter = tree == self.pos_players_tree

        menu = tk.Menu(tree, tearoff=0)
        menu.add_command(
            label=f"View {player_name} History",
            command=lambda: self._on_player_click(tree, is_batter),
        )
        menu.add_separator()
        menu.add_command(
            label="Copy Player Name",
            command=lambda: self._copy_to_clipboard(player_name),
        )
        menu.add_command(
            label="Copy Full Row", command=lambda: self._copy_selected_rows(tree)
        )

        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def _copy_to_clipboard(self, text: str):
        """Copy text to clipboard."""
        self.frame.clipboard_clear()
        self.frame.clipboard_append(text)

    def get_frame(self) -> tk.Frame:
        """Get the main frame for adding to parent container."""
        return self.frame
