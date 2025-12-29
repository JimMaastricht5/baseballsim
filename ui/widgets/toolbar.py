"""
--- Copyright Notice ---
Copyright (c) 2024 Jim Maastricht

Toolbar widget for baseball season simulation UI.

Provides control buttons for simulation management and team selection.
"""

import tkinter as tk
from tkinter import ttk
from typing import Dict, Callable


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
        self.toolbar = tk.Frame(parent, relief=tk.RAISED, bd=2)
        self.toolbar.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)

        # Team selection label and dropdown
        tk.Label(self.toolbar, text="Team to Follow:", font=("Arial", 10, "bold")).pack(side=tk.LEFT, padx=5)
        self.team_var = tk.StringVar(value=initial_team)
        self.team_combo = ttk.Combobox(
            self.toolbar,
            textvariable=self.team_var,
            width=6,
            state="readonly",
            font=("Arial", 10)
        )
        # Will be populated with all teams when simulation is ready
        self.team_combo['values'] = ['ARI', 'ATL', 'BAL', 'BOS', 'CHC', 'CHW', 'CIN', 'CLE',
                                      'COL', 'DET', 'HOU', 'KCR', 'LAA', 'LAD', 'MIA', 'MIL',
                                      'MIN', 'NYM', 'NYY', 'OAK', 'PHI', 'PIT', 'SDP', 'SEA',
                                      'SFG', 'STL', 'TBR', 'TEX', 'TOR', 'WSN']
        self.team_combo.pack(side=tk.LEFT, padx=5)

        # Separator
        ttk.Separator(self.toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=10)

        # Start button
        self.start_btn = tk.Button(
            self.toolbar, text="Start Season", command=callbacks['start_season'],
            width=12, bg="green", fg="white", font=("Arial", 10, "bold")
        )
        self.start_btn.pack(side=tk.LEFT, padx=5)

        # Separator
        ttk.Separator(self.toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=10)

        # Pause button
        self.pause_btn = tk.Button(
            self.toolbar, text="Pause", command=callbacks['pause_season'],
            width=10, font=("Arial", 10)
        )
        self.pause_btn.pack(side=tk.LEFT, padx=5)

        # Resume button
        self.resume_btn = tk.Button(
            self.toolbar, text="Resume", command=callbacks['resume_season'],
            width=10, font=("Arial", 10)
        )
        self.resume_btn.pack(side=tk.LEFT, padx=5)

        # Next Day button
        self.next_day_btn = tk.Button(
            self.toolbar, text="Next Day", command=callbacks['next_day'],
            width=10, font=("Arial", 10)
        )
        self.next_day_btn.pack(side=tk.LEFT, padx=5)

        # Next Series button (3 days)
        self.next_series_btn = tk.Button(
            self.toolbar, text="Next Series", command=callbacks['next_series'],
            width=10, font=("Arial", 10)
        )
        self.next_series_btn.pack(side=tk.LEFT, padx=5)

        # Next Week button (7 days)
        self.next_week_btn = tk.Button(
            self.toolbar, text="Next Week", command=callbacks['next_week'],
            width=10, font=("Arial", 10)
        )
        self.next_week_btn.pack(side=tk.LEFT, padx=5)

    def get_selected_team(self) -> str:
        """Get currently selected team from dropdown."""
        return self.team_var.get()

    def update_button_states(self, simulation_running: bool, paused: bool):
        """
        Update button enabled/disabled states based on simulation state.

        Args:
            simulation_running: Whether a simulation is currently running
            paused: Whether the simulation is paused
        """
        # Disable team selection once simulation starts
        self.team_combo.config(state="disabled" if simulation_running else "readonly")

        self.start_btn.config(state=tk.DISABLED if simulation_running else tk.NORMAL)
        self.pause_btn.config(state=tk.NORMAL if simulation_running and not paused else tk.DISABLED)
        self.resume_btn.config(state=tk.NORMAL if simulation_running and paused else tk.DISABLED)
        self.next_day_btn.config(state=tk.NORMAL if simulation_running else tk.DISABLED)
        self.next_series_btn.config(state=tk.NORMAL if simulation_running else tk.DISABLED)
        self.next_week_btn.config(state=tk.NORMAL if simulation_running else tk.DISABLED)
