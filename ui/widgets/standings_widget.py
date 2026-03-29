"""
--- Copyright Notice ---
Copyright (c) 2024 Jim Maastricht

Standings widget for baseball season simulation UI.

Displays standings by division with an AL / NL toggle.
GB is calculated within each division.
"""

import tkinter as tk
from tkinter import ttk
from typing import Dict, Any

from ui.theme import (
    BG_PANEL,
    BG_ELEVATED,
    TEXT_HEADING,
    TEXT_PRIMARY,
    ACCENT_BLUE,
    ROW_EVEN,
    ROW_ODD,
    ROW_FOLLOWED,
    FG_FOLLOWED,
)

# Division header row styling
DIV_HEADER_BG = "#1a2744"


class StandingsWidget:
    """
    Standings widget with AL / NL league toggle and per-division GB.

    Features:
    - Radio-button toggle between American League and National League
    - Three division sections (East, Central, West) with styled header rows
    - GB calculated within each division
    - Highlights followed team
    - Right-click context menu for team actions
    """

    def __init__(self, parent: tk.Widget, on_team_select_callback=None):
        """
        Initialize standings widget.

        Args:
            parent: Parent tkinter widget
            on_team_select_callback: Optional callback to switch to a team's roster tab
        """
        self.standings_frame = tk.Frame(parent, relief=tk.SUNKEN, bd=1, bg=BG_PANEL)

        # Data caching
        self.standings_data_cache = None
        self._followed_team_cache = ""

        # Callback to switch to team view
        self.on_team_select_callback = on_team_select_callback

        # Section header
        tk.Label(
            self.standings_frame,
            text="STANDINGS",
            font=("Segoe UI", 12, "bold"),
            bg=BG_PANEL,
            fg=TEXT_HEADING,
        ).pack(pady=5)

        # AL / NL dropdown toggle
        toggle_frame = tk.Frame(self.standings_frame, bg=BG_PANEL)
        toggle_frame.pack(pady=(0, 4))

        tk.Label(
            toggle_frame,
            text="League:",
            font=("Segoe UI", 10, "bold"),
            bg=BG_PANEL,
            fg=TEXT_PRIMARY,
        ).pack(side=tk.LEFT, padx=(0, 5))

        self._active_league = tk.StringVar(value="AL")
        self._league_combo = ttk.Combobox(
            toggle_frame,
            textvariable=self._active_league,
            values=["AL", "NL"],
            width=6,
            state="readonly",
            font=("Segoe UI", 10),
        )
        self._league_combo.pack(side=tk.LEFT)
        self._league_combo.bind(
            "<<ComboboxSelected>>", lambda _: self._on_league_toggle()
        )

        # Treeview with scrollbar
        tree_frame = tk.Frame(self.standings_frame, bg=BG_PANEL)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=2)

        scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.tree = ttk.Treeview(
            tree_frame,
            columns=("team", "wl", "pct", "gb"),
            show="headings",
            height=30,
            yscrollcommand=scrollbar.set,
        )
        scrollbar.config(command=self.tree.yview)

        self.tree.heading("team", text="Team")
        self.tree.heading("wl", text="W-L")
        self.tree.heading("pct", text="Pct")
        self.tree.heading("gb", text="GB")

        self.tree.column("team", width=85, anchor=tk.CENTER)
        self.tree.column("wl", width=80, anchor=tk.CENTER)
        self.tree.column("pct", width=60, anchor=tk.CENTER)
        self.tree.column("gb", width=50, anchor=tk.CENTER)

        # Row tags
        self.tree.tag_configure(
            "div_header",
            background=DIV_HEADER_BG,
            foreground=ACCENT_BLUE,
            font=("Segoe UI", 9, "bold"),
        )
        self.tree.tag_configure("even", background=ROW_EVEN)
        self.tree.tag_configure("odd", background=ROW_ODD)
        self.tree.tag_configure(
            "followed",
            background=ROW_FOLLOWED,
            foreground=FG_FOLLOWED,
            font=("Segoe UI", 9, "bold"),
        )

        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Bind right-click for context menu
        self.tree.bind("<Button-3>", self._show_context_menu)

    def _on_league_toggle(self):
        """Redraw treeview when the league toggle changes."""
        if self.standings_data_cache:
            self._populate_tree(self._active_league.get())

    def update_standings(self, standings_data: Dict[str, Any], followed_team: str = ""):
        """
        Update standings display with new data.

        Args:
            standings_data: Dict with 'al' and 'nl' keys, each mapping division names
                ('East', 'Central', 'West') to dicts containing:
                - teams: List of team abbreviations
                - wins: List of win counts
                - losses: List of loss counts
                - pct: List of win percentages
                - gb: List of games back (within division)
            followed_team: Team abbreviation to highlight
        """
        self.standings_data_cache = standings_data
        self._followed_team_cache = followed_team
        self._populate_tree(self._active_league.get())

    def _populate_tree(self, league: str):
        """
        Populate the treeview for the selected league, with a header row per division.

        Args:
            league: 'al' or 'nl'
        """
        for item in self.tree.get_children():
            self.tree.delete(item)

        league_data = (self.standings_data_cache or {}).get(league.lower(), {})
        row_num = 0

        for division in ("East", "Central", "West"):
            div_data = league_data.get(division, {})
            teams = div_data.get("teams", [])
            if not teams:
                continue

            # Division header row
            self.tree.insert(
                "", tk.END, values=(division.upper(), "", "", ""), tags=("div_header",)
            )

            wins = div_data.get("wins", [])
            losses = div_data.get("losses", [])
            pcts = div_data.get("pct", [])
            gbs = div_data.get("gb", [])

            for i in range(len(teams)):
                team = teams[i]
                wl = f"{wins[i]}-{losses[i]}"
                pct = f"{pcts[i]:.3f}"
                gb = gbs[i]
                tag = "even" if row_num % 2 == 0 else "odd"
                tags = ("followed",) if team == self._followed_team_cache else (tag,)
                self.tree.insert("", tk.END, values=(team, wl, pct, gb), tags=tags)
                row_num += 1

    def set_followed_team(self, team: str):
        """
        Set the team to highlight in standings.

        Args:
            team: Team abbreviation to follow
        """
        self._followed_team_cache = team

    def _show_context_menu(self, event):
        """Show right-click context menu for team actions."""
        # Identify which item was clicked
        item_id = self.tree.identify_row(event.y)
        if not item_id:
            return

        # Get the values for the clicked row
        values = self.tree.item(item_id, "values")
        if not values or not values[0] or values[0] in ("EAST", "CENTRAL", "WEST"):
            return

        team_name = values[0]

        # Select the item
        self.tree.selection_set(item_id)

        # Create context menu
        menu = tk.Menu(self.tree, tearoff=0)
        menu.add_command(
            label=f"View {team_name} Roster",
            command=lambda: self._view_team_roster(team_name),
        )
        menu.add_command(
            label=f"Copy {team_name}", command=lambda: self._copy_team_name(team_name)
        )
        menu.add_separator()
        menu.add_command(
            label=f"Set as Followed Team",
            command=lambda: self._set_followed_team(team_name),
        )

        # Show the menu
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def _view_team_roster(self, team: str):
        """Switch to the selected team's roster tab."""
        if self.on_team_select_callback:
            self.on_team_select_callback(team, set_followed=False)

    def _copy_team_name(self, team: str):
        """Copy team name to clipboard."""
        self.tree.clipboard_clear()
        self.tree.clipboard_append(team)

    def _set_followed_team(self, team: str):
        """Set the team as the followed team."""
        if self.on_team_select_callback:
            self.on_team_select_callback(team, set_followed=True)
        else:
            self._followed_team_cache = team
            self._populate_tree(self._active_league.get())

    def get_frame(self) -> tk.Frame:
        """Get the main frame for adding to parent container."""
        return self.standings_frame
