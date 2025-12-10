"""
GM Assessment Dialog for tkinter UI.

Displays comprehensive AI GM roster assessment in a formatted dialog window.
"""

import tkinter as tk
from tkinter import scrolledtext, messagebox
from typing import Dict, Any

from bblogger import logger


class GMAssessmentDialog:
    """
    Dialog window for displaying AI GM roster assessments.

    Shows team strategy, top players, trade recommendations, and roster moves
    in a formatted, scrollable text widget. Provides copy-to-clipboard functionality.
    """

    def __init__(self, parent: tk.Tk, assessment_data: Dict[str, Any]):
        """
        Initialize and display the GM assessment dialog.

        Args:
            parent: Parent tkinter window
            assessment_data: Dictionary containing:
                - team: Team abbreviation
                - games_played: Number of games into season
                - wins: Win count
                - losses: Loss count
                - games_back: Games behind leader
                - assessment: Assessment dict with strategy, roster_values, recommendations
        """
        self.parent = parent
        self.assessment_data = assessment_data

        # Extract key info
        self.team = assessment_data.get('team', 'Unknown')
        self.games_played = assessment_data.get('games_played', 0)
        self.wins = assessment_data.get('wins', 0)
        self.losses = assessment_data.get('losses', 0)
        self.games_back = assessment_data.get('games_back', 0.0)
        self.assessment = assessment_data.get('assessment', {})

        # Create dialog window
        self.dialog = tk.Toplevel(parent)
        self.dialog.title(f"AI GM Assessment: {self.team}")
        self.dialog.geometry("900x700")

        # Make dialog modal-ish but non-blocking (user can still interact with main window)
        # self.dialog.transient(parent)  # Keep on top of parent
        # self.dialog.grab_set()  # Don't grab - allow interaction with main window

        # Build UI
        self._build_ui()

        # Format and display assessment
        self._display_assessment()

        logger.info(f"GM assessment dialog opened for {self.team}")

    def _build_ui(self):
        """Build the dialog UI components."""
        # Main frame
        main_frame = tk.Frame(self.dialog, padx=10, pady=10)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Header label
        header_text = (f"{self.team} - After {self.games_played} Games "
                      f"({self.wins}-{self.losses}, GB: {self.games_back:.1f})")
        header_label = tk.Label(
            main_frame,
            text=header_text,
            font=("Courier", 12, "bold"),
            bg="#e0e0e0",
            pady=5
        )
        header_label.pack(fill=tk.X)

        # Scrolled text widget for assessment
        self.text_widget = scrolledtext.ScrolledText(
            main_frame,
            font=("Courier", 10),
            wrap=tk.WORD,
            width=100,
            height=35
        )
        self.text_widget.pack(fill=tk.BOTH, expand=True, pady=(5, 0))

        # Configure text tags for formatting
        self.text_widget.tag_config("header", font=("Courier", 11, "bold"), foreground="#0044cc")
        self.text_widget.tag_config("section", font=("Courier", 10, "bold"), underline=True)
        self.text_widget.tag_config("value", foreground="#006600")
        self.text_widget.tag_config("warning", foreground="#cc6600")

        # Button frame
        button_frame = tk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(5, 0))

        # Copy to Clipboard button
        copy_btn = tk.Button(
            button_frame,
            text="Copy to Clipboard",
            command=self._copy_to_clipboard,
            width=20
        )
        copy_btn.pack(side=tk.LEFT, padx=5)

        # Close button
        close_btn = tk.Button(
            button_frame,
            text="Close",
            command=self.dialog.destroy,
            width=20
        )
        close_btn.pack(side=tk.RIGHT, padx=5)

    def _display_assessment(self):
        """Format and display the assessment in the text widget."""
        strategy = self.assessment.get('strategy')
        roster_values = self.assessment.get('roster_values', {'batters': [], 'pitchers': []})
        recommendations = self.assessment.get('recommendations', {})

        if not strategy:
            self.text_widget.insert(tk.END, "No assessment data available.\n")
            return

        # Insert formatted assessment
        self._insert_header()
        self._insert_strategy(strategy)
        self._insert_top_players(roster_values)
        self._insert_trade_candidates(recommendations.get('trade_away', []))
        self._insert_trade_targets(recommendations.get('trade_targets', []))
        self._insert_specific_targets(recommendations.get('specific_targets', []))
        self._insert_release_candidates(recommendations.get('release', []))
        self._insert_footer()

        # Make read-only
        self.text_widget.config(state=tk.DISABLED)

    def _insert_header(self):
        """Insert assessment header."""
        separator = "=" * 80
        self.text_widget.insert(tk.END, separator + "\n", "header")
        self.text_widget.insert(tk.END, f"AI GM ASSESSMENT: {self.team}\n", "header")
        self.text_widget.insert(tk.END, separator + "\n", "header")
        self.text_widget.insert(tk.END, "\n")

    def _insert_strategy(self, strategy):
        """Insert team strategy section."""
        self.text_widget.insert(tk.END, "TEAM STRATEGY:\n", "section")
        self.text_widget.insert(tk.END, f"  Stage: {strategy.stage}\n")
        self.text_widget.insert(tk.END, f"  Alpha: {strategy.alpha:.3f}\n")
        self.text_widget.insert(tk.END, f"  Win Pct: {strategy.win_pct:.3f}\n")
        self.text_widget.insert(tk.END, f"  Games Back: {strategy.games_back:.1f}\n")
        self.text_widget.insert(tk.END, "\n")

    def _insert_top_players(self, roster_values):
        """Insert top 5 most valuable players section."""
        self.text_widget.insert(tk.END, "TOP 5 MOST VALUABLE PLAYERS:\n", "section")
        self.text_widget.insert(tk.END, "(Value = weighted blend of current season + projected avg WAR)\n\n")

        # Combine and sort all players
        all_players = roster_values.get('batters', []) + roster_values.get('pitchers', [])
        all_players.sort(key=lambda x: x.total_value, reverse=True)

        if not all_players:
            self.text_widget.insert(tk.END, "  No player data available\n\n")
            return

        for i, player in enumerate(all_players[:5], 1):
            line = (f"{i}. {player.player_name:20s} ({player.position:5s}, Age {player.age:2d}): "
                   f"Value={player.total_value:5.2f} "
                   f"(Sim_WAR={player.sim_war:4.2f}, Current={player.immediate_value:4.2f}, "
                   f"Future Avg={player.future_value:4.2f}/yr) "
                   f"${player.salary/1e6:6.2f}M\n")
            self.text_widget.insert(tk.END, line, "value")

        self.text_widget.insert(tk.END, "\n")

    def _insert_trade_candidates(self, trade_away_list):
        """Insert trade candidates section."""
        if not trade_away_list:
            return

        self.text_widget.insert(tk.END, "TRADE CANDIDATES (Consider Dealing):\n", "section")

        for i, trade in enumerate(trade_away_list[:5], 1):
            line = f"{i}. {trade['player']:20s} - {trade['reason']}\n"
            self.text_widget.insert(tk.END, line, "warning")

        self.text_widget.insert(tk.END, "\n")

    def _insert_trade_targets(self, trade_targets_list):
        """Insert trade targets section."""
        if not trade_targets_list:
            return

        self.text_widget.insert(tk.END, "TRADE TARGETS (Acquire Players Matching):\n", "section")

        for i, target in enumerate(trade_targets_list, 1):
            line = f"{i}. {target['profile']:30s} - {target['reason']}\n"
            self.text_widget.insert(tk.END, line)

        self.text_widget.insert(tk.END, "\n")

    def _insert_specific_targets(self, specific_targets_list):
        """Insert specific players to target section."""
        if not specific_targets_list:
            return

        self.text_widget.insert(tk.END, "SPECIFIC PLAYERS TO TARGET:\n", "section")

        for i, target in enumerate(specific_targets_list[:5], 1):
            line = (f"{i}. {target['player']:20s} "
                   f"({target['team']}, {target['position']:6s}, Age {target['age']:2d}) - "
                   f"{target['reason']}\n")
            self.text_widget.insert(tk.END, line, "value")

        self.text_widget.insert(tk.END, "\n")

    def _insert_release_candidates(self, release_list):
        """Insert release candidates section."""
        if not release_list:
            return

        self.text_widget.insert(tk.END, "RELEASE CANDIDATES:\n", "section")

        for i, release in enumerate(release_list[:3], 1):
            sim_war = release.get('sim_war', 0.0)
            immediate_value = release.get('immediate_value', 0.0)
            line = (f"{i}. {release['player']:20s} - "
                   f"Sim_WAR: {sim_war:4.2f}, Value: {immediate_value:4.2f}\n"
                   f"   {release['reason']}\n")
            self.text_widget.insert(tk.END, line, "warning")

        self.text_widget.insert(tk.END, "\n")

    def _insert_footer(self):
        """Insert assessment footer."""
        separator = "=" * 80
        self.text_widget.insert(tk.END, separator + "\n", "header")

    def _copy_to_clipboard(self):
        """Copy the entire assessment text to clipboard."""
        try:
            # Get all text from widget
            text_content = self.text_widget.get("1.0", tk.END)

            # Clear clipboard and append text
            self.dialog.clipboard_clear()
            self.dialog.clipboard_append(text_content)

            # Show confirmation
            messagebox.showinfo(
                "Copied",
                "Assessment copied to clipboard!",
                parent=self.dialog
            )
            logger.debug("Assessment copied to clipboard")

        except Exception as e:
            logger.error(f"Error copying to clipboard: {e}")
            messagebox.showerror(
                "Error",
                f"Failed to copy to clipboard: {str(e)}",
                parent=self.dialog
            )


def show_gm_assessment(parent: tk.Tk, assessment_data: Dict[str, Any]):
    """
    Factory function to create and show GM assessment dialog.

    Args:
        parent: Parent tkinter window
        assessment_data: Assessment data dictionary
    """
    GMAssessmentDialog(parent, assessment_data)
