"""
--- Copyright Notice ---
Copyright (c) 2024 Jim Maastricht

League leaders widget for baseball season simulation UI.

Displays league leaders in key statistical categories.
"""

import tkinter as tk
from tkinter import ttk
import pandas as pd
from bblogger import logger

from ui.theme import BG_PANEL, BG_ELEVATED, TEXT_HEADING, TEXT_PRIMARY, TEXT_SECONDARY


class LeagueLeadersWidget:
    """
    League leaders widget showing top players in key categories.

    Features:
    - AL / NL / All league filter dropdown
    - Separate tabs for position players and pitchers
    - Shows top 10 players in each category
    - Uses MLB minimum PA/IP rules (3.1 PA per game, 1.0 IP per game)
    - Position players: AVG, OBP, OPS, HR
    - Pitchers: Wins, ERA, WHIP, K, Saves
    """

    def __init__(self, parent: tk.Widget):
        """
        Initialize league leaders widget.

        Args:
            parent: Parent tkinter widget (notebook or frame)
        """
        self.frame = tk.Frame(parent, bg=BG_PANEL)
        self.baseball_data = None
        self.games_played = 0

        # Cached raw DataFrames and minimums (for re-filtering without a full reload)
        self._raw_batting_df = None
        self._raw_pitching_df = None
        self._min_pa = 50
        self._min_ip = 20.0

        # Shared league filter variable (widgets created inside each tab)
        self._league_filter = tk.StringVar(value="All")

        # ── Notebook ──────────────────────────────────────────────────────────
        leaders_notebook = ttk.Notebook(self.frame)
        leaders_notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Tab 1: Position Players
        batting_frame = tk.Frame(leaders_notebook, bg=BG_PANEL)
        leaders_notebook.add(batting_frame, text="Position Players")
        self._create_batting_leaders(batting_frame)

        # Tab 2: Pitchers
        pitching_frame = tk.Frame(leaders_notebook, bg=BG_PANEL)
        leaders_notebook.add(pitching_frame, text="Pitchers")
        self._create_pitching_leaders(pitching_frame)

    def _create_batting_leaders(self, parent: tk.Frame):
        """Create batting leaders section."""
        title_frame = tk.Frame(parent, bg=BG_PANEL)
        title_frame.pack(pady=(10, 5))

        tk.Label(title_frame, text="Batting Leaders",
                 font=("Segoe UI", 12, "bold"), bg=BG_PANEL, fg=TEXT_HEADING).pack()

        self.batting_qual_label = tk.Label(title_frame,
                                           text="Qualification: 3.1 PA per team game",
                                           font=("Segoe UI", 9, "italic"),
                                           bg=BG_PANEL, fg=TEXT_SECONDARY)
        self.batting_qual_label.pack()

        filter_row = tk.Frame(title_frame, bg=BG_PANEL)
        filter_row.pack(pady=(4, 0))
        tk.Label(filter_row, text="League:", font=("Segoe UI", 9, "bold"),
                 bg=BG_PANEL, fg=TEXT_PRIMARY).pack(side=tk.LEFT, padx=(0, 4))
        ttk.Combobox(filter_row, textvariable=self._league_filter,
                     values=["All", "AL", "NL"], width=6, state="readonly",
                     font=("Segoe UI", 9)).pack(side=tk.LEFT)
        filter_row.winfo_children()[-1].bind(
            "<<ComboboxSelected>>", lambda _: self._apply_filter_and_update())

        batting_grid = tk.Frame(parent, bg=BG_PANEL)
        batting_grid.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        batting_grid.grid_columnconfigure(0, weight=1)
        batting_grid.grid_columnconfigure(1, weight=1)
        batting_grid.grid_rowconfigure(0, weight=1)
        batting_grid.grid_rowconfigure(1, weight=1)

        self.avg_tree = self._create_leader_tree(batting_grid, "Batting Average (AVG)",
                                                  ["Player", "Team", "AVG", "PA"], row=0, col=0)
        self.obp_tree = self._create_leader_tree(batting_grid, "On-Base Percentage (OBP)",
                                                  ["Player", "Team", "OBP", "PA"], row=0, col=1)
        self.ops_tree = self._create_leader_tree(batting_grid, "On-Base Plus Slugging (OPS)",
                                                  ["Player", "Team", "OPS", "PA"], row=1, col=0)
        self.hr_tree = self._create_leader_tree(batting_grid, "Home Runs (HR)",
                                                 ["Player", "Team", "HR", "PA"], row=1, col=1)

    def _create_pitching_leaders(self, parent: tk.Frame):
        """Create pitching leaders section."""
        title_frame = tk.Frame(parent, bg=BG_PANEL)
        title_frame.pack(pady=(10, 5))

        tk.Label(title_frame, text="Pitching Leaders",
                 font=("Segoe UI", 12, "bold"), bg=BG_PANEL, fg=TEXT_HEADING).pack()

        self.pitching_qual_label = tk.Label(title_frame,
                                            text="Qualification: 1.0 IP per team game",
                                            font=("Segoe UI", 9, "italic"),
                                            bg=BG_PANEL, fg=TEXT_SECONDARY)
        self.pitching_qual_label.pack()

        filter_row = tk.Frame(title_frame, bg=BG_PANEL)
        filter_row.pack(pady=(4, 0))
        tk.Label(filter_row, text="League:", font=("Segoe UI", 9, "bold"),
                 bg=BG_PANEL, fg=TEXT_PRIMARY).pack(side=tk.LEFT, padx=(0, 4))
        ttk.Combobox(filter_row, textvariable=self._league_filter,
                     values=["All", "AL", "NL"], width=6, state="readonly",
                     font=("Segoe UI", 9)).pack(side=tk.LEFT)
        filter_row.winfo_children()[-1].bind(
            "<<ComboboxSelected>>", lambda _: self._apply_filter_and_update())

        pitching_grid = tk.Frame(parent, bg=BG_PANEL)
        pitching_grid.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        pitching_grid.grid_columnconfigure(0, weight=1)
        pitching_grid.grid_columnconfigure(1, weight=1)
        pitching_grid.grid_rowconfigure(0, weight=1)
        pitching_grid.grid_rowconfigure(1, weight=1)
        pitching_grid.grid_rowconfigure(2, weight=1)

        self.wins_tree = self._create_leader_tree(pitching_grid, "Wins (W)",
                                                   ["Player", "Team", "W", "IP"], row=0, col=0)
        self.era_tree = self._create_leader_tree(pitching_grid, "Earned Run Average (ERA)",
                                                  ["Player", "Team", "ERA", "IP"], row=0, col=1)
        self.whip_tree = self._create_leader_tree(pitching_grid, "WHIP",
                                                   ["Player", "Team", "WHIP", "IP"], row=1, col=0)
        self.k_tree = self._create_leader_tree(pitching_grid, "Strikeouts (K)",
                                               ["Player", "Team", "SO", "IP"], row=1, col=1)
        self.saves_tree = self._create_leader_tree(pitching_grid, "Saves (SV)",
                                                    ["Player", "Team", "SV", "IP"], row=2, col=0)

    def _create_leader_tree(self, parent: tk.Frame, title: str, columns: list,
                           row: int, col: int) -> ttk.Treeview:
        """Create a leader board tree for a specific category."""
        container = tk.Frame(parent, relief=tk.RIDGE, borderwidth=1, bg=BG_PANEL)
        container.grid(row=row, column=col, sticky="nsew", padx=5, pady=5)

        tk.Label(container, text=title, font=("Segoe UI", 10, "bold"),
                 bg=BG_PANEL, fg=TEXT_HEADING).pack(pady=5)

        tree = ttk.Treeview(container, columns=columns, show="headings", height=10)

        for col_name in columns:
            tree.heading(col_name, text=col_name)
            if col_name == "Player":
                tree.column(col_name, width=120, anchor=tk.W)
            elif col_name == "Team":
                tree.column(col_name, width=50, anchor=tk.CENTER)
            elif col_name in ["AVG", "OBP", "OPS", "ERA", "WHIP"]:
                tree.column(col_name, width=55, anchor=tk.CENTER)
            elif col_name in ["PA", "IP"]:
                tree.column(col_name, width=50, anchor=tk.CENTER)
            else:
                tree.column(col_name, width=45, anchor=tk.CENTER)

        scrollbar = ttk.Scrollbar(container, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        return tree

    def update_leaders(self, baseball_data, games_played: int = 0):
        """
        Fetch and display league leaders.

        Args:
            baseball_data: BaseballStats instance
            games_played: Number of games played (for calculating PA/IP minimums)
        """
        self.baseball_data = baseball_data
        self.games_played = games_played

        try:
            self._raw_batting_df = baseball_data.get_batting_data(team_name=None, prior_season=False)
            self._raw_pitching_df = baseball_data.get_pitching_data(team_name=None, prior_season=False)

            self._min_pa = int(games_played * 3.1) if games_played > 0 else 50
            self._min_ip = float(games_played * 1.0) if games_played > 0 else 20.0

            self.batting_qual_label.config(
                text=f"Qualification: {self._min_pa} PA (3.1 per game × {games_played} games)")
            self.pitching_qual_label.config(
                text=f"Qualification: {self._min_ip:.1f} IP (1.0 per game × {games_played} games)")

            self._apply_filter_and_update()

            logger.info(f"League leaders updated (games={games_played}, "
                        f"min_pa={self._min_pa}, min_ip={self._min_ip:.1f})")

        except Exception as e:
            logger.error(f"Error updating league leaders: {e}")
            import traceback
            logger.error(traceback.format_exc())

    def _apply_filter_and_update(self):
        """Filter cached DataFrames by the selected league and repopulate trees."""
        if self._raw_batting_df is None or self._raw_pitching_df is None:
            return

        league = self._league_filter.get()

        if league == "All" or 'League' not in self._raw_batting_df.columns:
            batting_df = self._raw_batting_df
        else:
            batting_df = self._raw_batting_df[self._raw_batting_df['League'] == league]

        if league == "All" or 'League' not in self._raw_pitching_df.columns:
            pitching_df = self._raw_pitching_df
        else:
            pitching_df = self._raw_pitching_df[self._raw_pitching_df['League'] == league]

        self._update_batting_leaders(batting_df, self._min_pa)
        self._update_pitching_leaders(pitching_df, self._min_ip)

    def _update_batting_leaders(self, batting_df: pd.DataFrame, min_pa: int):
        """Update batting leader trees."""
        if 'PA' not in batting_df.columns:
            batting_df = batting_df.copy()
            batting_df['PA'] = (batting_df.get('AB', 0) +
                               batting_df.get('BB', 0) +
                               batting_df.get('HBP', 0) +
                               batting_df.get('SF', 0) +
                               batting_df.get('SH', 0))

        if 'AVG' in batting_df.columns and 'PA' in batting_df.columns:
            avg_leaders = batting_df[batting_df['PA'] >= min_pa].copy()
            avg_leaders['AVG'] = pd.to_numeric(avg_leaders['AVG'], errors='coerce')
            avg_leaders = avg_leaders.sort_values('AVG', ascending=False).head(10)
            self._populate_leader_tree(self.avg_tree, avg_leaders,
                                       ['Player', 'Team', 'AVG', 'PA'],
                                       format_rules={'AVG': '.3f'})

        if 'OBP' in batting_df.columns and 'PA' in batting_df.columns:
            obp_leaders = batting_df[batting_df['PA'] >= min_pa].copy()
            obp_leaders['OBP'] = pd.to_numeric(obp_leaders['OBP'], errors='coerce')
            obp_leaders = obp_leaders.sort_values('OBP', ascending=False).head(10)
            self._populate_leader_tree(self.obp_tree, obp_leaders,
                                       ['Player', 'Team', 'OBP', 'PA'],
                                       format_rules={'OBP': '.3f'})

        if 'OPS' in batting_df.columns and 'PA' in batting_df.columns:
            ops_leaders = batting_df[batting_df['PA'] >= min_pa].copy()
            ops_leaders['OPS'] = pd.to_numeric(ops_leaders['OPS'], errors='coerce')
            ops_leaders = ops_leaders.sort_values('OPS', ascending=False).head(10)
            self._populate_leader_tree(self.ops_tree, ops_leaders,
                                       ['Player', 'Team', 'OPS', 'PA'],
                                       format_rules={'OPS': '.3f'})

        if 'HR' in batting_df.columns and 'PA' in batting_df.columns:
            hr_leaders = batting_df[batting_df['PA'] > 0].copy()
            hr_leaders['HR'] = pd.to_numeric(hr_leaders['HR'], errors='coerce')
            hr_leaders = hr_leaders.sort_values('HR', ascending=False).head(10)
            self._populate_leader_tree(self.hr_tree, hr_leaders,
                                       ['Player', 'Team', 'HR', 'PA'],
                                       format_rules={})

    def _update_pitching_leaders(self, pitching_df: pd.DataFrame, min_ip: float):
        """Update pitching leader trees."""
        if 'W' in pitching_df.columns and 'IP' in pitching_df.columns:
            wins_leaders = pitching_df[pitching_df['IP'] > 0].copy()
            wins_leaders['W'] = pd.to_numeric(wins_leaders['W'], errors='coerce')
            wins_leaders = wins_leaders.sort_values('W', ascending=False).head(10)
            self._populate_leader_tree(self.wins_tree, wins_leaders,
                                       ['Player', 'Team', 'W', 'IP'],
                                       format_rules={'IP': '.1f'})

        if 'ERA' in pitching_df.columns and 'IP' in pitching_df.columns:
            era_leaders = pitching_df[pitching_df['IP'] >= min_ip].copy()
            era_leaders['ERA'] = pd.to_numeric(era_leaders['ERA'], errors='coerce')
            era_leaders = era_leaders.sort_values('ERA', ascending=True).head(10)
            self._populate_leader_tree(self.era_tree, era_leaders,
                                       ['Player', 'Team', 'ERA', 'IP'],
                                       format_rules={'ERA': '.2f', 'IP': '.1f'})

        if 'WHIP' in pitching_df.columns and 'IP' in pitching_df.columns:
            whip_leaders = pitching_df[pitching_df['IP'] >= min_ip].copy()
            whip_leaders['WHIP'] = pd.to_numeric(whip_leaders['WHIP'], errors='coerce')
            whip_leaders = whip_leaders.sort_values('WHIP', ascending=True).head(10)
            self._populate_leader_tree(self.whip_tree, whip_leaders,
                                       ['Player', 'Team', 'WHIP', 'IP'],
                                       format_rules={'WHIP': '.2f', 'IP': '.1f'})

        if 'SO' in pitching_df.columns and 'IP' in pitching_df.columns:
            k_leaders = pitching_df[pitching_df['IP'] > 0].copy()
            k_leaders['SO'] = pd.to_numeric(k_leaders['SO'], errors='coerce')
            k_leaders = k_leaders.sort_values('SO', ascending=False).head(10)
            self._populate_leader_tree(self.k_tree, k_leaders,
                                       ['Player', 'Team', 'SO', 'IP'],
                                       format_rules={'IP': '.1f'})

        if 'SV' in pitching_df.columns and 'IP' in pitching_df.columns:
            saves_leaders = pitching_df[pitching_df['IP'] > 0].copy()
            saves_leaders['SV'] = pd.to_numeric(saves_leaders['SV'], errors='coerce')
            saves_leaders = saves_leaders.sort_values('SV', ascending=False).head(10)
            self._populate_leader_tree(self.saves_tree, saves_leaders,
                                       ['Player', 'Team', 'SV', 'IP'],
                                       format_rules={'IP': '.1f'})

    def _populate_leader_tree(self, tree: ttk.Treeview, data_df: pd.DataFrame,
                              columns: list, format_rules: dict):
        """Populate a leader tree with data."""
        for item in tree.get_children():
            tree.delete(item)

        if data_df.empty:
            return

        for idx, row in data_df.iterrows():
            try:
                values = []
                for col in columns:
                    value = row.get(col, 0)
                    if col in format_rules:
                        value = f"{float(value):{format_rules[col]}}"
                    elif isinstance(value, (int, float)) and col not in ['Player', 'Team']:
                        if col in ['PA', 'W', 'SV', 'SO']:
                            value = int(value)
                        elif col in ['IP']:
                            value = f"{float(value):.1f}"
                        else:
                            value = int(value)
                    values.append(value)

                tree.insert("", tk.END, values=tuple(values))
            except Exception as e:
                logger.warning(f"Error inserting leader row for {row.get('Player', 'Unknown')}: {e}")

    def get_frame(self) -> tk.Frame:
        """Get the main frame for adding to parent container."""
        return self.frame
