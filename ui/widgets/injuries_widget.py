"""
--- Copyright Notice ---
Copyright (c) 2024 Jim Maastricht

Injuries widget for baseball season simulation UI.

Displays league-wide injury list with sorting and team filtering.
"""

import tkinter as tk
from tkinter import ttk
from typing import List, Dict, Any
from bblogger import logger


class InjuriesWidget:
    """
    Injuries widget showing league-wide IL report.

    Features:
    - Sortable treeview by any column
    - Team filter dropdown
    - Color-coded by injury severity (IL vs Day-to-Day)
    - Displays player, team, position, injury, and status
    """

    def __init__(self, parent: tk.Widget):
        """
        Initialize injuries widget.

        Args:
            parent: Parent tkinter widget (notebook or frame)
        """
        self.frame = tk.Frame(parent)

        # Data caching for sorting/filtering
        self.injuries_data_cache = []
        self.injuries_sort_column = "status"  # Default sort by status
        self.injuries_sort_reverse = False

        # Header with injury count
        injuries_header_frame = tk.Frame(self.frame)
        injuries_header_frame.pack(fill=tk.X, pady=5)

        self.injuries_header_label = tk.Label(
            injuries_header_frame, text="League IL Report",
            font=("Arial", 11, "bold")
        )
        self.injuries_header_label.pack()

        # Control frame with team filter dropdown
        injuries_control_frame = tk.Frame(self.frame)
        injuries_control_frame.pack(fill=tk.X, padx=10, pady=5)

        tk.Label(injuries_control_frame, text="Team:", font=("Arial", 10, "bold")).pack(side=tk.LEFT, padx=5)
        self.injuries_team_var = tk.StringVar(value="All Teams")
        self.injuries_team_combo = ttk.Combobox(
            injuries_control_frame,
            textvariable=self.injuries_team_var,
            width=15,
            state="readonly"
        )
        self.injuries_team_combo['values'] = ['All Teams']  # Populated later
        self.injuries_team_combo.bind('<<ComboboxSelected>>', self._on_team_changed)
        self.injuries_team_combo.pack(side=tk.LEFT, padx=5)

        # Create Treeview for injuries
        injuries_tree_frame = tk.Frame(self.frame)
        injuries_tree_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        injuries_scrollbar = ttk.Scrollbar(injuries_tree_frame, orient=tk.VERTICAL)
        injuries_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.injuries_tree = ttk.Treeview(
            injuries_tree_frame,
            columns=("player", "team", "pos", "injury", "status"),
            show="headings",
            height=20,
            yscrollcommand=injuries_scrollbar.set
        )
        injuries_scrollbar.config(command=self.injuries_tree.yview)

        # Define column headings with sort callbacks
        self.injuries_tree.heading("player", text="Player", command=lambda: self._sort_injuries("player"))
        self.injuries_tree.heading("team", text="Team", command=lambda: self._sort_injuries("team"))
        self.injuries_tree.heading("pos", text="Pos", command=lambda: self._sort_injuries("pos"))
        self.injuries_tree.heading("injury", text="Injury", command=lambda: self._sort_injuries("injury"))
        self.injuries_tree.heading("status", text="Status", command=lambda: self._sort_injuries("status"))

        # Configure column widths
        self.injuries_tree.column("player", width=150, anchor=tk.W)
        self.injuries_tree.column("team", width=60, anchor=tk.CENTER)
        self.injuries_tree.column("pos", width=50, anchor=tk.CENTER)
        self.injuries_tree.column("injury", width=250, anchor=tk.W)
        self.injuries_tree.column("status", width=120, anchor=tk.CENTER)

        # Tags for injury status
        self.injuries_tree.tag_configure("IL", background="#ffcccc")  # Red for IL
        self.injuries_tree.tag_configure("Day-to-Day", background="#fff4cc")  # Yellow for day-to-day

        self.injuries_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    def update_injuries(self, injury_list: List[Dict[str, Any]]):
        """
        Update injury list display.

        Args:
            injury_list: List of injury dicts with keys:
                - player, team, position, injury, days_remaining, status
        """
        logger.debug(f"Injury update: {len(injury_list)} injured players")

        # Cache injury data for sorting and filtering
        self.injuries_data_cache = injury_list

        # Apply team filter
        selected_team = self.injuries_team_var.get()
        if selected_team != "All Teams":
            filtered_list = [inj for inj in injury_list if inj['team'] == selected_team]
        else:
            filtered_list = injury_list

        # Update header with count
        if selected_team == "All Teams":
            count_text = f"League IL Report ({len(filtered_list)} injured)"
        else:
            count_text = f"League IL Report - {selected_team} ({len(filtered_list)} injured)"
        self.injuries_header_label.config(text=count_text)

        # Clear existing items
        for item in self.injuries_tree.get_children():
            self.injuries_tree.delete(item)

        # Insert injury data
        for injury in filtered_list:
            days = injury['days_remaining']

            # Clean up position formatting (remove brackets and quotes)
            pos = injury['position']
            if isinstance(pos, list):
                pos = pos[0] if pos else 'Unknown'
            pos = str(pos).replace('[', '').replace(']', '').replace("'", '').replace('"', '').strip()

            # Create descriptive status based on days remaining
            if days >= 60:
                status_text = "60-Day IL"
                tag_status = "IL"
            elif days >= 10:
                status_text = "10-Day IL"
                tag_status = "IL"
            else:
                status_text = "Day-to-Day"
                tag_status = "Day-to-Day"

            tags = (tag_status,)  # Use tag status for color coding

            self.injuries_tree.insert(
                "",
                tk.END,
                values=(
                    injury['player'],
                    injury['team'],
                    pos,
                    injury['injury'],
                    status_text
                ),
                tags=tags
            )

    def populate_team_filter(self, team_names: List[str]):
        """
        Populate team filter dropdown with team names.

        Args:
            team_names: List of team abbreviations
        """
        all_teams = ['All Teams'] + sorted(team_names)
        self.injuries_team_combo['values'] = all_teams

    def _sort_injuries(self, column: str):
        """
        Sort injuries by the specified column.

        Args:
            column: Column to sort by
        """
        if not self.injuries_data_cache:
            return

        # Toggle sort direction if clicking same column
        if self.injuries_sort_column == column:
            self.injuries_sort_reverse = not self.injuries_sort_reverse
        else:
            self.injuries_sort_column = column
            # Default directions
            if column == "status":
                self.injuries_sort_reverse = True  # Longest injuries first (by days_remaining)
            else:
                self.injuries_sort_reverse = False  # Ascending for text

        # Apply team filter first
        selected_team = self.injuries_team_var.get()
        if selected_team != "All Teams":
            data = [inj for inj in self.injuries_data_cache if inj['team'] == selected_team]
        else:
            data = self.injuries_data_cache.copy()

        if column == "player":
            data.sort(key=lambda x: x['player'], reverse=self.injuries_sort_reverse)
        elif column == "team":
            data.sort(key=lambda x: x['team'], reverse=self.injuries_sort_reverse)
        elif column == "pos":
            data.sort(key=lambda x: x['position'], reverse=self.injuries_sort_reverse)
        elif column == "injury":
            data.sort(key=lambda x: x['injury'], reverse=self.injuries_sort_reverse)
        elif column == "status":
            # Sort by days_remaining for status column (since status is now "10-Day IL", "60-Day IL", etc.)
            data.sort(key=lambda x: x['days_remaining'], reverse=self.injuries_sort_reverse)

        # Update header with filtered count
        selected_team = self.injuries_team_var.get()
        if selected_team == "All Teams":
            count_text = f"League IL Report ({len(data)} injured)"
        else:
            count_text = f"League IL Report - {selected_team} ({len(data)} injured)"
        self.injuries_header_label.config(text=count_text)

        # Clear and repopulate
        for item in self.injuries_tree.get_children():
            self.injuries_tree.delete(item)

        for injury in data:
            days = injury['days_remaining']

            # Clean up position formatting (remove brackets and quotes)
            pos = injury['position']
            if isinstance(pos, list):
                pos = pos[0] if pos else 'Unknown'
            pos = str(pos).replace('[', '').replace(']', '').replace("'", '').replace('"', '').strip()

            # Create descriptive status based on days remaining
            if days >= 60:
                status_text = "60-Day IL"
                tag_status = "IL"
            elif days >= 10:
                status_text = "10-Day IL"
                tag_status = "IL"
            else:
                status_text = "Day-to-Day"
                tag_status = "Day-to-Day"

            tags = (tag_status,)

            self.injuries_tree.insert(
                "",
                tk.END,
                values=(
                    injury['player'],
                    injury['team'],
                    pos,
                    injury['injury'],
                    status_text
                ),
                tags=tags
            )

    def _on_team_changed(self, event=None):
        """Handle team dropdown change."""
        # Just redisplay with current filter
        if self.injuries_data_cache:
            self._sort_injuries(self.injuries_sort_column)

    def get_frame(self) -> tk.Frame:
        """Get the main frame for adding to parent container."""
        return self.frame
