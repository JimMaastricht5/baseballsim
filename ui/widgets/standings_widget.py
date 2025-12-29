"""
--- Copyright Notice ---
Copyright (c) 2024 Jim Maastricht

Standings widget for baseball season simulation UI.

Displays separate American League and National League standings with sorting.
"""

import tkinter as tk
from tkinter import ttk
from typing import Dict, Any, Callable


class StandingsWidget:
    """
    Standings widget with separate AL and NL treeviews.

    Features:
    - Separate treeviews for AL and NL
    - Sortable by team, W-L, Pct, GB
    - Highlights followed team
    - Displays team record, winning percentage, and games back
    """

    def __init__(self, parent: tk.Widget):
        """
        Initialize standings widget.

        Args:
            parent: Parent tkinter widget (PanedWindow or frame)
        """
        self.standings_frame = tk.Frame(parent, relief=tk.SUNKEN, bd=1)

        # Header label
        standings_label = tk.Label(self.standings_frame, text="STANDINGS", font=("Arial", 12, "bold"))
        standings_label.pack(pady=5)

        # Data caching for sorting
        self.standings_data_cache = None
        self.standings_sort_column = "gb"  # Default sort by games back
        self.standings_sort_reverse = True  # Descending by default
        self.standings_sort_league = None  # Track which league is being sorted

        # AL Standings
        al_label = tk.Label(self.standings_frame, text="AMERICAN LEAGUE", font=("Arial", 10, "bold"))
        al_label.pack(pady=(5, 2))

        al_tree_frame = tk.Frame(self.standings_frame)
        al_tree_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=2)

        al_scrollbar = ttk.Scrollbar(al_tree_frame, orient=tk.VERTICAL)
        al_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.al_standings_tree = ttk.Treeview(
            al_tree_frame,
            columns=("team", "wl", "pct", "gb"),
            show="headings",
            height=15,
            yscrollcommand=al_scrollbar.set
        )
        al_scrollbar.config(command=self.al_standings_tree.yview)

        # Define column headings
        self.al_standings_tree.heading("team", text="Team", command=lambda: self._sort_standings("team", "al"))
        self.al_standings_tree.heading("wl", text="W-L", command=lambda: self._sort_standings("wl", "al"))
        self.al_standings_tree.heading("pct", text="Pct", command=lambda: self._sort_standings("pct", "al"))
        self.al_standings_tree.heading("gb", text="GB", command=lambda: self._sort_standings("gb", "al"))

        # Configure column widths
        self.al_standings_tree.column("team", width=60, anchor=tk.CENTER)
        self.al_standings_tree.column("wl", width=80, anchor=tk.CENTER)
        self.al_standings_tree.column("pct", width=60, anchor=tk.CENTER)
        self.al_standings_tree.column("gb", width=50, anchor=tk.CENTER)

        # Add tag for followed teams
        self.al_standings_tree.tag_configure("followed", background="#e6f3ff", font=("Arial", 10, "bold"))
        self.al_standings_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # NL Standings
        nl_label = tk.Label(self.standings_frame, text="NATIONAL LEAGUE", font=("Arial", 10, "bold"))
        nl_label.pack(pady=(10, 2))

        nl_tree_frame = tk.Frame(self.standings_frame)
        nl_tree_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=2)

        nl_scrollbar = ttk.Scrollbar(nl_tree_frame, orient=tk.VERTICAL)
        nl_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.nl_standings_tree = ttk.Treeview(
            nl_tree_frame,
            columns=("team", "wl", "pct", "gb"),
            show="headings",
            height=15,
            yscrollcommand=nl_scrollbar.set
        )
        nl_scrollbar.config(command=self.nl_standings_tree.yview)

        # Define column headings
        self.nl_standings_tree.heading("team", text="Team", command=lambda: self._sort_standings("team", "nl"))
        self.nl_standings_tree.heading("wl", text="W-L", command=lambda: self._sort_standings("wl", "nl"))
        self.nl_standings_tree.heading("pct", text="Pct", command=lambda: self._sort_standings("pct", "nl"))
        self.nl_standings_tree.heading("gb", text="GB", command=lambda: self._sort_standings("gb", "nl"))

        # Configure column widths
        self.nl_standings_tree.column("team", width=60, anchor=tk.CENTER)
        self.nl_standings_tree.column("wl", width=80, anchor=tk.CENTER)
        self.nl_standings_tree.column("pct", width=60, anchor=tk.CENTER)
        self.nl_standings_tree.column("gb", width=50, anchor=tk.CENTER)

        # Add tag for followed teams
        self.nl_standings_tree.tag_configure("followed", background="#e6f3ff", font=("Arial", 10, "bold"))
        self.nl_standings_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    def update_standings(self, standings_data: Dict[str, Any], followed_team: str = ''):
        """
        Update standings display with new data.

        Args:
            standings_data: Dict with 'al' and 'nl' keys, each containing:
                - teams: List of team abbreviations
                - wins: List of win counts
                - losses: List of loss counts
                - pct: List of win percentages
                - gb: List of games back
            followed_team: Team abbreviation to highlight
        """
        # Cache the data for sorting
        self.standings_data_cache = standings_data

        # Update AL standings
        self._populate_league_standings(
            self.al_standings_tree,
            standings_data.get('al', {}),
            followed_team
        )

        # Update NL standings
        self._populate_league_standings(
            self.nl_standings_tree,
            standings_data.get('nl', {}),
            followed_team
        )

    def _populate_league_standings(self, tree: ttk.Treeview, league_data: Dict, followed_team: str):
        """
        Populate a standings treeview with league data.

        Args:
            tree: The treeview widget to populate
            league_data: Dict with 'teams', 'wins', 'losses', 'pct', 'gb'
            followed_team: Team abbreviation to highlight
        """
        # Clear existing items
        for item in tree.get_children():
            tree.delete(item)

        teams = league_data.get('teams', [])
        wins = league_data.get('wins', [])
        losses = league_data.get('losses', [])
        pcts = league_data.get('pct', [])
        gbs = league_data.get('gb', [])

        # Insert data into treeview
        for i in range(len(teams)):
            team = teams[i]
            wl = f"{wins[i]}-{losses[i]}"
            pct = f"{pcts[i]:.3f}"
            gb = gbs[i]

            # Determine if this team is followed
            tags = ("followed",) if team == followed_team else ()

            tree.insert(
                "",
                tk.END,
                values=(team, wl, pct, gb),
                tags=tags
            )

    def _sort_standings(self, column: str, league: str):
        """
        Sort standings by the specified column for a specific league.

        Args:
            column: Column to sort by ('team', 'wl', 'pct', 'gb')
            league: League to sort ('al' or 'nl')
        """
        if not self.standings_data_cache:
            return

        # Toggle sort direction if clicking same column in same league
        if self.standings_sort_column == column and self.standings_sort_league == league:
            self.standings_sort_reverse = not self.standings_sort_reverse
        else:
            # New column or league - use appropriate default direction
            self.standings_sort_column = column
            self.standings_sort_league = league
            if column in ("pct", "wl"):
                self.standings_sort_reverse = True  # Descending for pct and wins
            elif column == "gb":
                self.standings_sort_reverse = False  # Ascending for games back
            else:
                self.standings_sort_reverse = False  # Ascending for team names

        # Get data for the specific league
        league_data = self.standings_data_cache.get(league, {})
        teams = league_data.get('teams', [])
        wins = league_data.get('wins', [])
        losses = league_data.get('losses', [])
        pcts = league_data.get('pct', [])
        gbs = league_data.get('gb', [])

        # Create list of tuples for sorting
        data = list(zip(teams, wins, losses, pcts, gbs))

        # Sort based on column
        if column == "team":
            data.sort(key=lambda x: x[0], reverse=self.standings_sort_reverse)
        elif column == "wl":
            data.sort(key=lambda x: x[1], reverse=self.standings_sort_reverse)
        elif column == "pct":
            data.sort(key=lambda x: x[3], reverse=self.standings_sort_reverse)
        elif column == "gb":
            # Special handling for GB (leader is '-', need to sort numerically)
            def gb_key(x):
                gb_val = x[4]
                if gb_val == '-':
                    return -1.0  # Leader goes first
                try:
                    return float(gb_val)
                except ValueError:
                    return 999.0  # Put invalid values at end
            data.sort(key=gb_key, reverse=self.standings_sort_reverse)

        # Select the appropriate tree
        tree = self.al_standings_tree if league == 'al' else self.nl_standings_tree

        # Clear and repopulate treeview
        for item in tree.get_children():
            tree.delete(item)

        # Get followed team for highlighting (need to pass from parent)
        followed_team = getattr(self, '_followed_team_cache', '')

        for team, w, l, pct, gb in data:
            wl = f"{w}-{l}"
            pct_str = f"{pct:.3f}"
            tags = ("followed",) if team == followed_team else ()

            tree.insert(
                "",
                tk.END,
                values=(team, wl, pct_str, gb),
                tags=tags
            )

    def set_followed_team(self, team: str):
        """
        Set the team to highlight in standings.

        Args:
            team: Team abbreviation to follow
        """
        self._followed_team_cache = team

    def get_frame(self) -> tk.Frame:
        """Get the main frame for adding to parent container."""
        return self.standings_frame
