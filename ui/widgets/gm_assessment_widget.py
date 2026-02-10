"""
--- Copyright Notice ---
Copyright (c) 2024 Jim Maastricht

GM Assessment widget for baseball season simulation UI.

Displays AI GM roster assessment for followed team.
"""

import tkinter as tk
from tkinter import scrolledtext
from typing import Dict, Any, Callable
from bblogger import logger


class GMAssessmentWidget:
    """
    GM Assessment widget showing AI GM roster assessment.

    Features:
    - Displays team strategy (stage, alpha, win pct, games back)
    - Shows top 5 most valuable players
    - Lists trade candidates and targets
    - Shows release candidates
    - Update Assessment button to force new assessment
    """

    def __init__(self, parent: tk.Widget, update_callback: Callable):
        """
        Initialize GM assessment widget.

        Args:
            parent: Parent tkinter widget (notebook or frame)
            update_callback: Callback function when Update Assessment button clicked
        """
        self.frame = tk.Frame(parent)
        self.update_callback = update_callback

        # Header with button
        gm_header_frame = tk.Frame(self.frame)
        gm_header_frame.pack(fill=tk.X, pady=5)

        self.gm_header_label = tk.Label(
            gm_header_frame, text="No GM Assessment Yet",
            font=("Arial", 11, "bold")
        )
        self.gm_header_label.pack(side=tk.LEFT, padx=10)

        # Update Assessment button
        self.update_assessment_btn = tk.Button(
            gm_header_frame, text="Update Assessment", command=update_callback,
            width=16, bg="blue", fg="white", font=("Arial", 10, "bold")
        )
        self.update_assessment_btn.pack(side=tk.RIGHT, padx=10)
        self.update_assessment_btn.config(state=tk.DISABLED)  # Initially disabled

        # ScrolledText for assessment history
        self.gm_text = scrolledtext.ScrolledText(
            self.frame, wrap=tk.WORD, font=("Courier", 9), state=tk.DISABLED
        )

        # Configure text tags for formatting
        self.gm_text.tag_configure("header", font=("Courier", 11, "bold"), foreground="#0044cc")
        self.gm_text.tag_configure("section", font=("Courier", 10, "bold"), underline=True)
        self.gm_text.tag_configure("value", foreground="#006600")
        self.gm_text.tag_configure("warning", foreground="#cc6600")
        self.gm_text.tag_configure("separator", foreground="#888888")

        self.gm_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    def enable_button(self):
        """Enable the Update Assessment button."""
        self.update_assessment_btn.config(state=tk.NORMAL)

    def display_assessment(self, team: str, games: int, wins: int, losses: int,
                          games_back: float, assessment: Dict[str, Any]):
        """
        Format and display GM assessment.

        Args:
            team: Team abbreviation
            games: Games played
            wins: Win count
            losses: Loss count
            games_back: Games behind leader
            assessment: Assessment data with strategy, roster_values, recommendations
        """
        # Update header
        self.gm_header_label.config(text=f"Latest GM Assessment: {team} (After {games} Games)")

        # Enable text widget for editing
        self.gm_text.config(state=tk.NORMAL)

        # Clear previous assessment (replace, don't append)
        self.gm_text.delete(1.0, tk.END)

        # Extract data
        strategy = assessment.get('strategy')
        roster_values = assessment.get('roster_values', {'batters': [], 'pitchers': []})
        recommendations = assessment.get('recommendations', {})

        if not strategy:
            self.gm_text.insert(tk.END, "No assessment data available.\n")
            self.gm_text.config(state=tk.DISABLED)
            return

        # Header
        separator = "=" * 80
        self.gm_text.insert(tk.END, separator + "\n", "header")
        self.gm_text.insert(tk.END, f"AI GM ASSESSMENT: {team}\n", "header")
        self.gm_text.insert(tk.END, f"After {games} Games ({wins}-{losses}, GB: {games_back:.1f})\n", "header")
        self.gm_text.insert(tk.END, separator + "\n", "header")
        self.gm_text.insert(tk.END, "\n")

        # Strategy
        self.gm_text.insert(tk.END, "TEAM STRATEGY:\n", "section")
        self.gm_text.insert(tk.END, f"  Stage: {strategy.stage}\n")
        self.gm_text.insert(tk.END, f"  Alpha: {strategy.alpha:.3f}\n")
        self.gm_text.insert(tk.END, f"  Win Pct: {strategy.win_pct:.3f}\n")
        self.gm_text.insert(tk.END, f"  Games Back: {strategy.games_back:.1f}\n")
        self.gm_text.insert(tk.END, "\n")

        # Top 5 players
        self.gm_text.insert(tk.END, "TOP 5 MOST VALUABLE PLAYERS:\n", "section")
        self.gm_text.insert(tk.END, "(Value = weighted blend of current season + projected avg WAR)\n\n")

        all_players = roster_values.get('batters', []) + roster_values.get('pitchers', [])
        all_players.sort(key=lambda x: x.total_value, reverse=True)

        if not all_players:
            self.gm_text.insert(tk.END, "  No player data available\n\n")
        else:
            for i, player in enumerate(all_players[:5], 1):
                line = (f"{i}. {player.player_name:20s} ({player.position:5s}, Age {player.age:2d}): "
                       f"Value={player.total_value:5.2f} "
                       f"(Sim_WAR={player.sim_war:4.2f}, Current={player.immediate_value:4.2f}, "
                       f"Future Avg={player.future_value:4.2f}/yr) "
                       f"${player.salary/1e6:6.2f}M\n")
                self.gm_text.insert(tk.END, line, "value")
            self.gm_text.insert(tk.END, "\n")

        # Trade candidates
        trade_away_list = recommendations.get('trade_away', [])
        if trade_away_list:
            self.gm_text.insert(tk.END, "TRADE CANDIDATES (Consider Dealing):\n", "section")
            for i, trade in enumerate(trade_away_list[:5], 1):
                line = f"{i}. {trade['player']:20s} - {trade['reason']}\n"
                self.gm_text.insert(tk.END, line, "warning")
            self.gm_text.insert(tk.END, "\n")

        # Trade targets
        trade_targets_list = recommendations.get('trade_targets', [])
        if trade_targets_list:
            self.gm_text.insert(tk.END, "TRADE TARGETS (Acquire Players Matching):\n", "section")
            for i, target in enumerate(trade_targets_list, 1):
                line = f"{i}. {target['profile']:30s} - {target['reason']}\n"
                self.gm_text.insert(tk.END, line)
            self.gm_text.insert(tk.END, "\n")

        # Specific targets
        specific_targets_list = recommendations.get('specific_targets', [])
        if specific_targets_list:
            self.gm_text.insert(tk.END, "SPECIFIC PLAYERS TO TARGET:\n", "section")
            for i, target in enumerate(specific_targets_list[:5], 1):
                line = (f"{i}. {target['player']:20s} "
                       f"({target['team']}, {target['position']:6s}, Age {target['age']:2d}) - "
                       f"{target['reason']}\n")
                self.gm_text.insert(tk.END, line, "value")
            self.gm_text.insert(tk.END, "\n")

        # Release candidates
        release_list = recommendations.get('release', [])
        if release_list:
            self.gm_text.insert(tk.END, "RELEASE CANDIDATES:\n", "section")
            for i, release in enumerate(release_list[:3], 1):
                sim_war = release.get('sim_war', 0.0)
                immediate_value = release.get('immediate_value', 0.0)
                line = (f"{i}. {release['player']:20s} - "
                       f"Sim_WAR: {sim_war:4.2f}, Value: {immediate_value:4.2f}\n"
                       f"   {release['reason']}\n")
                self.gm_text.insert(tk.END, line, "warning")
            self.gm_text.insert(tk.END, "\n")

        # Footer
        self.gm_text.insert(tk.END, separator + "\n", "header")

        # Scroll to end to show latest assessment
        self.gm_text.see(tk.END)
        self.gm_text.config(state=tk.DISABLED)

        logger.info(f"Displayed GM assessment for {team} at {games} games")

    def get_frame(self) -> tk.Frame:
        """Get the main frame for adding to parent container."""
        return self.frame
