"""
--- Copyright Notice ---
Copyright (c) 2024 Jim Maastricht

Admin widget for baseball season simulation UI.

Provides player management functionality - move players between teams.
"""

import tkinter as tk
from tkinter import ttk, messagebox
from typing import List, Dict, Any, Callable
from bblogger import logger


class AdminWidget:
    """
    Admin widget for player management.

    Features:
    - Search players by name
    - Filter by team
    - Move players between teams
    - Save changes to CSV files
    """

    def __init__(self, parent: tk.Widget, get_worker_callback: Callable):
        """
        Initialize admin widget.

        Args:
            parent: Parent tkinter widget (notebook or frame)
            get_worker_callback: Callback function to get worker instance
        """
        self.frame = tk.Frame(parent)
        self.get_worker = get_worker_callback
        self.admin_all_players = []  # Cached player list

        # Header with instructions
        admin_header = tk.Label(
            self.frame,
            text="Player Management - Move players between teams",
            font=("Arial", 11, "bold"),
            pady=5
        )
        admin_header.pack()

        # Search frame
        search_frame = tk.Frame(self.frame)
        search_frame.pack(fill=tk.X, padx=10, pady=5)

        tk.Label(search_frame, text="Search:", font=("Arial", 10)).pack(side=tk.LEFT, padx=5)
        self.admin_search_var = tk.StringVar()
        self.admin_search_var.trace('w', lambda *args: self._filter_players())
        search_entry = tk.Entry(search_frame, textvariable=self.admin_search_var, width=30, font=("Arial", 10))
        search_entry.pack(side=tk.LEFT, padx=5)

        tk.Label(search_frame, text="Team Filter:", font=("Arial", 10)).pack(side=tk.LEFT, padx=15)
        self.admin_team_filter_var = tk.StringVar(value="All Teams")
        self.admin_team_filter_var.trace('w', lambda *args: self._filter_players())
        self.admin_team_filter_combo = ttk.Combobox(
            search_frame,
            textvariable=self.admin_team_filter_var,
            width=15,
            state="readonly"
        )
        self.admin_team_filter_combo['values'] = ['All Teams']
        self.admin_team_filter_combo.pack(side=tk.LEFT, padx=5)

        # Player list frame with treeview
        list_frame = tk.Frame(self.frame)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # Scrollbars
        tree_scroll_y = ttk.Scrollbar(list_frame, orient=tk.VERTICAL)
        tree_scroll_y.pack(side=tk.RIGHT, fill=tk.Y)

        tree_scroll_x = ttk.Scrollbar(list_frame, orient=tk.HORIZONTAL)
        tree_scroll_x.pack(side=tk.BOTTOM, fill=tk.X)

        # Treeview for players
        self.admin_players_tree = ttk.Treeview(
            list_frame,
            columns=("player", "pos", "team", "age", "type", "hashcode"),
            show="headings",
            height=20,
            yscrollcommand=tree_scroll_y.set,
            xscrollcommand=tree_scroll_x.set
        )
        tree_scroll_y.config(command=self.admin_players_tree.yview)
        tree_scroll_x.config(command=self.admin_players_tree.xview)

        # Define column headings
        self.admin_players_tree.heading("player", text="Player Name")
        self.admin_players_tree.heading("pos", text="Position")
        self.admin_players_tree.heading("team", text="Current Team")
        self.admin_players_tree.heading("age", text="Age")
        self.admin_players_tree.heading("type", text="Type")
        self.admin_players_tree.heading("hashcode", text="Hashcode")

        # Configure column widths
        self.admin_players_tree.column("player", width=200, anchor=tk.W)
        self.admin_players_tree.column("pos", width=60, anchor=tk.CENTER)
        self.admin_players_tree.column("team", width=80, anchor=tk.CENTER)
        self.admin_players_tree.column("age", width=50, anchor=tk.CENTER)
        self.admin_players_tree.column("type", width=80, anchor=tk.CENTER)
        self.admin_players_tree.column("hashcode", width=100, anchor=tk.CENTER)

        self.admin_players_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Action frame
        action_frame = tk.Frame(self.frame)
        action_frame.pack(fill=tk.X, padx=10, pady=10)

        tk.Label(action_frame, text="Move selected player to:", font=("Arial", 10, "bold")).pack(side=tk.LEFT, padx=5)
        self.admin_dest_team_var = tk.StringVar()
        self.admin_dest_team_combo = ttk.Combobox(
            action_frame,
            textvariable=self.admin_dest_team_var,
            width=15,
            state="readonly"
        )
        self.admin_dest_team_combo['values'] = []
        self.admin_dest_team_combo.pack(side=tk.LEFT, padx=5)

        move_btn = tk.Button(
            action_frame,
            text="Move Player",
            command=self.move_player,
            bg="#4CAF50",
            fg="white",
            font=("Arial", 10, "bold"),
            width=15
        )
        move_btn.pack(side=tk.LEFT, padx=20)

        save_btn = tk.Button(
            action_frame,
            text="Save Changes to CSV",
            command=self.save_changes,
            bg="#2196F3",
            fg="white",
            font=("Arial", 10, "bold"),
            width=20
        )
        save_btn.pack(side=tk.LEFT, padx=10)

        # Status message
        self.admin_status_label = tk.Label(
            self.frame,
            text="Ready. Select a player and destination team, then click 'Move Player'.",
            font=("Arial", 9),
            fg="#666666",
            anchor=tk.W
        )
        self.admin_status_label.pack(fill=tk.X, padx=10, pady=5)

    def load_players(self):
        """
        Load all players from baseball_data.
        Called when simulation starts.
        """
        worker = self.get_worker()
        if not worker or not worker.season:
            self.admin_status_label.config(text="Start simulation to load players", fg="#ff6600")
            return

        try:
            baseball_data = worker.season.baseball_data
            self.admin_all_players = []

            # Load batters
            batting_df = baseball_data.new_season_batting_data
            for idx, row in batting_df.iterrows():
                pos = row.get('Pos', 'Unknown')
                if isinstance(pos, list):
                    pos = pos[0] if pos else 'Unknown'
                pos = str(pos).replace('[', '').replace(']', '').replace("'", '').replace('"', '').strip()

                self.admin_all_players.append({
                    'player': row['Player'],
                    'pos': pos,
                    'team': row['Team'],
                    'age': int(row.get('Age', 0)),
                    'type': 'Batter',
                    'hashcode': idx
                })

            # Load pitchers
            pitching_df = baseball_data.new_season_pitching_data
            for idx, row in pitching_df.iterrows():
                self.admin_all_players.append({
                    'player': row['Player'],
                    'pos': 'P',
                    'team': row['Team'],
                    'age': int(row.get('Age', 0)),
                    'type': 'Pitcher',
                    'hashcode': idx
                })

            # Populate team dropdowns
            all_teams = sorted(set(p['team'] for p in self.admin_all_players))
            self.admin_team_filter_combo['values'] = ['All Teams'] + all_teams
            self.admin_dest_team_combo['values'] = all_teams

            # Display players
            self._filter_players()

            self.admin_status_label.config(
                text=f"Loaded {len(self.admin_all_players)} players. Select a player to move.",
                fg="#006600"
            )
            logger.info(f"Loaded {len(self.admin_all_players)} players for admin management")

        except Exception as e:
            logger.error(f"Error loading admin players: {e}")
            import traceback
            logger.error(traceback.format_exc())
            self.admin_status_label.config(text=f"Error loading players: {e}", fg="#ff0000")

    def _filter_players(self):
        """Filter and display players based on search text and team filter."""
        if not self.admin_all_players:
            return

        # Get filter values
        search_text = self.admin_search_var.get().lower()
        team_filter = self.admin_team_filter_var.get()

        # Clear current display
        for item in self.admin_players_tree.get_children():
            self.admin_players_tree.delete(item)

        # Filter players
        filtered_players = []
        for player in self.admin_all_players:
            # Filter by search text (player name)
            if search_text and search_text not in player['player'].lower():
                continue

            # Filter by team
            if team_filter != "All Teams" and player['team'] != team_filter:
                continue

            filtered_players.append(player)

        # Display filtered players
        for player in filtered_players:
            self.admin_players_tree.insert(
                "",
                tk.END,
                values=(
                    player['player'],
                    player['pos'],
                    player['team'],
                    player['age'],
                    player['type'],
                    player['hashcode']
                )
            )

        # Update status with count
        if search_text or team_filter != "All Teams":
            self.admin_status_label.config(
                text=f"Showing {len(filtered_players)} of {len(self.admin_all_players)} players",
                fg="#666666"
            )

    def move_player(self):
        """Move selected player to destination team."""
        worker = self.get_worker()

        # Check if simulation is running (not paused)
        if worker and worker.is_alive() and not worker._paused:
            messagebox.showwarning(
                "Simulation Running",
                "Please pause the simulation before moving players."
            )
            return

        # Check if worker/season exists
        if not worker or not worker.season:
            messagebox.showwarning(
                "No Simulation",
                "Please start a simulation before moving players."
            )
            return

        # Get selected player
        selected_items = self.admin_players_tree.selection()
        if not selected_items:
            messagebox.showwarning(
                "No Player Selected",
                "Please select a player to move."
            )
            return

        selected_item = selected_items[0]
        values = self.admin_players_tree.item(selected_item, 'values')
        player_name = values[0]
        current_team = values[2]
        hashcode = int(values[5])

        # Get destination team
        dest_team = self.admin_dest_team_var.get()
        if not dest_team:
            messagebox.showwarning(
                "No Destination Team",
                "Please select a destination team."
            )
            return

        # Check if moving to same team
        if current_team == dest_team:
            messagebox.showinfo(
                "Same Team",
                f"{player_name} is already on {current_team}."
            )
            return

        # Confirm move
        confirm = messagebox.askyesno(
            "Confirm Move",
            f"Move {player_name} from {current_team} to {dest_team}?"
        )

        if not confirm:
            return

        try:
            # Perform move
            baseball_data = worker.season.baseball_data
            baseball_data.move_a_player_between_teams(hashcode, dest_team)

            # Update in-memory list
            for player in self.admin_all_players:
                if player['hashcode'] == hashcode:
                    player['team'] = dest_team
                    break

            # Update treeview
            self.admin_players_tree.item(selected_item, values=(
                values[0], values[1], dest_team, values[3], values[4], values[5]
            ))

            self.admin_status_label.config(
                text=f"Moved {player_name} from {current_team} to {dest_team}. Click 'Save Changes' to persist.",
                fg="#006600"
            )
            logger.info(f"Moved player {hashcode} ({player_name}) from {current_team} to {dest_team}")

        except Exception as e:
            logger.error(f"Error moving player: {e}")
            messagebox.showerror(
                "Move Failed",
                f"Error moving player: {str(e)}"
            )

    def save_changes(self):
        """Save all player movements to CSV files."""
        worker = self.get_worker()
        if not worker or not worker.season:
            messagebox.showwarning(
                "No Simulation",
                "Please start a simulation before saving."
            )
            return

        # Confirm save
        confirm = messagebox.askyesno(
            "Confirm Save",
            "Save all player movements to New-Season-stats CSV files?\n\n"
            "This will overwrite the existing files."
        )

        if not confirm:
            return

        try:
            baseball_data = worker.season.baseball_data
            new_season = baseball_data.new_season

            # Save the files
            baseball_data.save_new_season_stats()

            # Show success message
            messagebox.showinfo(
                "Save Successful",
                f"Player movements saved to:\n"
                f"- {new_season} New-Season-stats-pp-Batting.csv\n"
                f"- {new_season} New-Season-stats-pp-Pitching.csv"
            )

            self.admin_status_label.config(
                text="Changes saved successfully to CSV files.",
                fg="#006600"
            )
            logger.info("Admin player changes saved to CSV files")

        except Exception as e:
            logger.error(f"Error saving admin changes: {e}")
            import traceback
            logger.error(traceback.format_exc())
            messagebox.showerror(
                "Save Failed",
                f"Error saving changes: {str(e)}"
            )

    def get_frame(self) -> tk.Frame:
        """Get the main frame for adding to parent container."""
        return self.frame
