"""
--- Copyright Notice ---
Copyright (c) 2024 Jim Maastricht

Toolbar widget for baseball season simulation UI.

Provides control buttons for simulation management and team selection.
"""

import tkinter as tk
from tkinter import ttk
from typing import Dict, Callable

from ui.theme import BG_DARK, TEXT_PRIMARY


class ToolbarWidget:
    """
    Toolbar widget with control buttons and team selection.

    Provides buttons for: Start Season, Pause, Resume, Next Day, Next Series, Next Week.
    Also includes team selection dropdown.
    """

    def __init__(self, parent: tk.Widget, initial_team: str, callbacks: Dict[str, Callable]):
        """
        Initialize toolbar widget.

        Args:
            parent: Parent tkinter widget
            initial_team: Initial team selection
            callbacks: Dict of callback functions with keys:
                - 'start_season': Called when Start button clicked
                - 'pause_season': Called when Pause button clicked
                - 'resume_season': Called when Resume button clicked
                - 'next_day': Called when Next Day button clicked
                - 'next_series': Called when Next Series button clicked
                - 'next_week': Called when Next Week button clicked
        """
        self.callbacks = callbacks

        # Create toolbar frame
        self.toolbar = tk.Frame(parent, relief=tk.RAISED, bd=2, bg=BG_DARK)
        self.toolbar.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)

        # Team selection label and dropdown
        tk.Label(self.toolbar, text="Team to Follow:", font=("Segoe UI", 10, "bold"),
                 bg=BG_DARK, fg=TEXT_PRIMARY).pack(side=tk.LEFT, padx=5)
        self.team_var = tk.StringVar(value=initial_team)
        self.team_combo = ttk.Combobox(
            self.toolbar,
            textvariable=self.team_var,
            width=6,
            state="readonly",
            font=("Segoe UI", 10)
        )
        # Will be populated with all teams when simulation is ready
        self.team_combo['values'] = ['ARI', 'ATL', 'BAL', 'BOS', 'CHC', 'CHW', 'CIN', 'CLE',
                                      'COL', 'DET', 'HOU', 'KCR', 'LAA', 'LAD', 'MIA', 'MIL',
                                      'MIN', 'NYM', 'NYY', 'OAK', 'PHI', 'PIT', 'SDP', 'SEA',
                                      'SFG', 'STL', 'TBR', 'TEX', 'TOR', 'WSN']
        self.team_combo.pack(side=tk.LEFT, padx=5)

        # Separator
        ttk.Separator(self.toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=10)

        # Number of games label and spinbox
        tk.Label(self.toolbar, text="Games:", font=("Segoe UI", 10, "bold"),
                 bg=BG_DARK, fg=TEXT_PRIMARY).pack(side=tk.LEFT, padx=5)
        self.games_var = tk.StringVar(value="162")
        self.games_spinbox = tk.Spinbox(
            self.toolbar,
            from_=1,
            to=162,
            textvariable=self.games_var,
            width=5,
            font=("Segoe UI", 10)
        )
        self.games_spinbox.pack(side=tk.LEFT, padx=5)

        # OBP Adjustment label and dropdown
        tk.Label(self.toolbar, text="OBP Adjustment:", font=("Segoe UI", 10, "bold"),
                 bg=BG_DARK, fg=TEXT_PRIMARY).pack(side=tk.LEFT, padx=5)
        self.obp_var = tk.StringVar(value="-0.05")
        obp_values = [f"{v / 100:.2f}" for v in range(0, -11, -1)]
        obp_values[0] = "0.0"
        self.obp_combo = ttk.Combobox(
            self.toolbar,
            textvariable=self.obp_var,
            values=obp_values,
            width=6,
            state="readonly",
            font=("Segoe UI", 10)
        )
        self.obp_combo.pack(side=tk.LEFT, padx=5)

        # Separator
        ttk.Separator(self.toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=10)

        # Start button
        self.start_btn = ttk.Button(
            self.toolbar, text="▶  Start Season",
            command=callbacks['start_season'], width=14, style="Start.TButton"
        )
        self.start_btn.pack(side=tk.LEFT, padx=5)

        # Separator
        ttk.Separator(self.toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=10)

        # Pause button
        self.pause_btn = ttk.Button(
            self.toolbar, text="⏸  Pause",
            command=callbacks['pause_season'], width=10, style="Pause.TButton"
        )
        self.pause_btn.pack(side=tk.LEFT, padx=5)

        # Resume button
        self.resume_btn = ttk.Button(
            self.toolbar, text="▶  Resume",
            command=callbacks['resume_season'], width=10, style="Nav.TButton"
        )
        self.resume_btn.pack(side=tk.LEFT, padx=5)

        # Next Day button
        self.next_day_btn = ttk.Button(
            self.toolbar, text="Next Day",
            command=callbacks['next_day'], width=10, style="Nav.TButton"
        )
        self.next_day_btn.pack(side=tk.LEFT, padx=5)

        # Next Series button (3 days)
        self.next_series_btn = ttk.Button(
            self.toolbar, text="Next Series",
            command=callbacks['next_series'], width=10, style="Nav.TButton"
        )
        self.next_series_btn.pack(side=tk.LEFT, padx=5)

        # Next Week button (7 days)
        self.next_week_btn = ttk.Button(
            self.toolbar, text="Next Week",
            command=callbacks['next_week'], width=10, style="Nav.TButton"
        )
        self.next_week_btn.pack(side=tk.LEFT, padx=5)

    def get_selected_team(self) -> str:
        """Get currently selected team from dropdown."""
        return self.team_var.get()

    def get_num_games(self) -> int:
        """Get currently set number of games to simulate."""
        try:
            return int(self.games_var.get())
        except ValueError:
            return 162

    def get_obp_adjustment(self) -> float:
        """Get currently selected OBP adjustment value."""
        return float(self.obp_var.get())

    def update_button_states(self, simulation_running: bool, paused: bool):
        """
        Update button enabled/disabled states based on simulation state.

        Args:
            simulation_running: Whether a simulation is currently running
            paused: Whether the simulation is paused
        """
        # Disable team selection, games, and OBP adjustment once simulation starts
        self.team_combo.config(state="disabled" if simulation_running else "readonly")
        self.games_spinbox.config(state="disabled" if simulation_running else "normal")
        self.obp_combo.config(state="disabled" if simulation_running else "readonly")

        self.start_btn.config(state=tk.DISABLED if simulation_running else tk.NORMAL)
        self.pause_btn.config(state=tk.NORMAL if simulation_running and not paused else tk.DISABLED)
        self.resume_btn.config(state=tk.NORMAL if simulation_running and paused else tk.DISABLED)
        self.next_day_btn.config(state=tk.NORMAL if simulation_running else tk.DISABLED)
        self.next_series_btn.config(state=tk.NORMAL if simulation_running else tk.DISABLED)
        self.next_week_btn.config(state=tk.NORMAL if simulation_running else tk.DISABLED)
