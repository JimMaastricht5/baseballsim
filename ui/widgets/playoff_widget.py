"""
--- Copyright Notice ---
Copyright (c) 2024 Jim Maastricht

Playoff widget for baseball season simulation UI.

Displays World Series games with structured data, collapsible sections, and box scores.
"""

import tkinter as tk
from tkinter import ttk
from typing import Dict, Any, Optional

from ui.theme import (
    BG_PANEL,
    BG_WIDGET,
    BG_WIDGET_ALT,
    BG_DARK,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    ACCENT_BLUE,
    ACCENT_GOLD,
)
from ui.widgets.games_played_widget import (
    ScrollableFrame,
)
from ui.models.game_data import AWAY, HOME, InningScore


class PlayoffWidget:
    """
    Playoff widget showing playoff games with structured data.

    Features:
    - Table view of all playoff games
    - Series score tracking
    - Score by inning
    - Box scores for completed games
    """

    def __init__(self, parent: tk.Widget):
        """
        Initialize playoff widget.

        Args:
            parent: Parent tkinter widget (notebook or frame)
        """
        self.frame = tk.Frame(parent, bg=BG_PANEL)
        self.ws_active = False
        self.ws_info = {}
        self.series_score = {}
        self.game_number = 0
        self.current_game = 1
        self.games_data = {}  # {game_num: structured_game}

        # Track all playoff series: {series_key: {away, home, games: [], winner: None}}
        self.playoff_series = {}  # e.g., {"AL WC A": {"away": "NYY", "home": "BOS", "games": [], "wins": {}}}

        # Current round tracking
        self.current_round = "Wild Card"
        self.round_games = []  # Games for current round

        # Create header section
        self.header_frame = tk.Frame(self.frame, bg="#0d2040", height=40)
        self.header_frame.pack(fill=tk.X, pady=(0, 5))
        self.header_frame.pack_propagate(False)

        self.header_label = tk.Label(
            self.header_frame,
            text="2026 Playoffs",
            font=("Segoe UI", 16, "bold"),
            bg="#0d2040",
            fg=ACCENT_GOLD,
        )
        self.header_label.pack(pady=5)

        # Configure styles
        self._configure_styles()

        # Scrollable frame for game display
        self.scrollable_frame = ScrollableFrame(self.frame, style="Scrollable.TFrame")
        self.scrollable_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Show initial message
        self._show_waiting_message()

    def _configure_styles(self):
        """Configure custom ttk styles."""
        style = ttk.Style()

        style.configure(
            "WSGameHeader.TLabel",
            font=("Segoe UI", 14, "bold"),
            foreground=ACCENT_GOLD,
            background=BG_WIDGET,
            padding=5,
        )

        style.configure(
            "WSScoreSummary.TLabel",
            font=("Segoe UI", 12),
            foreground=TEXT_PRIMARY,
            background=BG_WIDGET,
            padding=(10, 0, 5, 5),
        )

        style.configure(
            "WSSectionHeader.TLabel",
            font=("Segoe UI", 11, "bold"),
            foreground=ACCENT_BLUE,
            background=BG_WIDGET,
            padding=(5, 10, 5, 3),
        )

        style.configure(
            "WSTeamHeader.TLabel",
            font=("Segoe UI", 10, "bold"),
            foreground=ACCENT_BLUE,
            background=BG_WIDGET,
            padding=(10, 5, 5, 2),
        )

        style.configure(
            "WSPlayHeader.TLabel",
            font=("Segoe UI", 10, "bold"),
            foreground=ACCENT_BLUE,
            background=BG_WIDGET,
            padding=(10, 8, 5, 2),
        )

        style.configure(
            "WSPlayItem.TLabel",
            font=("Segoe UI", 9),
            foreground=TEXT_PRIMARY,
            background=BG_WIDGET,
            padding=(15, 1, 5, 1),
        )

        style.configure(
            "WSBoxScore.Treeview",
            font=("Segoe UI", 9),
            rowheight=18,
            background=BG_WIDGET,
            fieldbackground=BG_WIDGET,
            foreground=TEXT_PRIMARY,
        )
        style.configure(
            "WSBoxScore.Treeview.Heading",
            font=("Segoe UI", 9, "bold"),
            background=BG_PANEL,
            foreground=TEXT_PRIMARY,
        )
        style.configure(
            "WSInningScore.Treeview",
            font=("Segoe UI", 9),
            rowheight=20,
            background=BG_WIDGET,
            fieldbackground=BG_WIDGET,
            foreground=TEXT_PRIMARY,
        )
        style.configure(
            "WSInningScore.Treeview.Heading",
            font=("Segoe UI", 9, "bold"),
            background=BG_PANEL,
            foreground=TEXT_PRIMARY,
        )

        # Playoff games table style
        style.configure(
            "PlayoffTree.Treeview",
            font=("Segoe UI", 10),
            rowheight=25,
            background=BG_WIDGET,
            fieldbackground=BG_WIDGET,
            foreground=TEXT_PRIMARY,
        )
        style.configure(
            "PlayoffTree.Treeview.Heading",
            font=("Segoe UI", 10, "bold"),
            background=BG_PANEL,
            foreground=TEXT_PRIMARY,
        )

    def _show_waiting_message(self):
        """Display message when waiting for World Series to start."""
        label = tk.Label(
            self.scrollable_frame.scrollable_frame,
            text="Waiting for Playoffs to begin...\n\nComplete the regular season to unlock playoff games.",
            font=("Segoe UI", 12),
            fg=TEXT_SECONDARY,
            bg=BG_WIDGET,
        )
        label.pack(pady=50)

    def _on_game_selected(self, event=None):
        """Handle game selection from dropdown - now disabled."""
        pass  # Using table display instead

    def _display_todays_games(self):
        """Display all playoff games as a clear table."""
        for widget in self.scrollable_frame.scrollable_frame.winfo_children():
            widget.destroy()

        if not self.games_data:
            self._show_waiting_message()
            return

        # Create Treeview table for games
        columns = ("game", "matchup", "score", "series")
        tree = ttk.Treeview(
            self.scrollable_frame.scrollable_frame,
            columns=columns,
            show="headings",
            style="PlayoffTree.Treeview",
            height=len(self.games_data),
        )

        # Configure columns
        tree.column("#0", width=0, stretch=False)
        tree.column("game", width=40, anchor=tk.CENTER, stretch=False)
        tree.column("matchup", width=280, anchor=tk.W, stretch=False)
        tree.column("score", width=120, anchor=tk.CENTER, stretch=False)
        tree.column("series", width=60, anchor=tk.CENTER, stretch=False)

        # Configure headings
        tree.heading("game", text="#")
        tree.heading("matchup", text="Matchup")
        tree.heading("score", text="Score")
        tree.heading("series", text="Series")

        # Configure tags for alternating rows
        tree.tag_configure("odd", background=BG_WIDGET)
        tree.tag_configure("even", background=BG_WIDGET_ALT)
        tree.tag_configure("winner", foreground=ACCENT_GOLD)

        tree.pack(fill=tk.BOTH, expand=True)

        # Get round name helper
        def get_round_name(game_num):
            if game_num <= 4:
                return "WC"
            elif game_num <= 8:
                return "DS"
            elif game_num <= 10:
                return "LCS"
            else:
                return "WS"

        # Get matchup helper - find series between these teams
        def get_series_status(away, home, current_game_num):
            """Calculate series wins for both teams up to current game."""
            away_wins = 0
            home_wins = 0
            for gn, g in self.games_data.items():
                if gn > current_game_num:
                    continue
                if (g.away_team == away and g.home_team == home) or (
                    g.away_team == home and g.home_team == away
                ):
                    if g.final_score[0] > g.final_score[1]:
                        if g.away_team == away:
                            away_wins += 1
                        else:
                            home_wins += 1
                    elif g.final_score[1] > g.final_score[0]:
                        if g.home_team == home:
                            home_wins += 1
                        else:
                            away_wins += 1
            return away_wins, home_wins

        # Populate table
        for idx, (game_num, structured_game) in enumerate(
            sorted(self.games_data.items())
        ):
            away = structured_game.away_team
            home = structured_game.home_team
            away_score, home_score = structured_game.final_score

            # Determine winner for display
            if away_score > home_score:
                score_text = f"{away} {away_score} - {home} {home_score}"
                tags = ("odd" if idx % 2 == 0 else "even", "winner")
            else:
                score_text = f"{away} {away_score} - {home} {home_score}"
                tags = ("odd" if idx % 2 == 0 else "even",)

            # Series status - only count games up to this game
            away_wins, home_wins = get_series_status(away, home, game_num)
            series_text = f"{away_wins}-{home_wins}"

            # Matchup with round
            round_name = get_round_name(game_num)
            matchup_text = f"{round_name}: {away} @ {home}"

            # Insert row
            tree.insert(
                "",
                tk.END,
                values=(idx + 1, matchup_text, score_text, series_text),
                tags=tags,
            )

        self.scrollable_frame.update_scrollregion()

    def _display_game_card(self, parent_frame, structured_game, game_num):
        """Display a single game card with series info and expandable details."""
        # This method is no longer used - using _display_todays_games() table instead
        pass

    def _display_game(self, game_num: int):
        """Display the selected game with structured data."""
        # This method is no longer used - using _display_todays_games() table instead
        pass

    def _update_series_display(self):
        """Update the series status display in the header."""
        for label in self.series_labels.values():
            label.destroy()
        self.series_labels.clear()

        # Collect all unique series matchups from games_data
        series_info = {}  # {(away, home): (away_wins, home_wins)}

        for game in self.games_data.values():
            away = game.away_team
            home = game.home_team
            key = (away, home)

            if key not in series_info:
                series_info[key] = [0, 0]  # away_wins, home_wins

            away_score, home_score = game.final_score
            if away_score > home_score:
                series_info[key][0] += 1
            elif home_score > away_score:
                series_info[key][1] += 1

        # Display each series
        for idx, (matchup, (away_wins, home_wins)) in enumerate(series_info.items()):
            away, home = matchup
            series_text = f"{away} {away_wins} - {home_wins} {home}"

            label = tk.Label(
                self.series_status_frame,
                text=series_text,
                font=("Segoe UI", 10, "bold"),
                bg="#0d2040",
                fg=ACCENT_GOLD if away_wins > home_wins else TEXT_PRIMARY,
            )
            label.pack(side=tk.LEFT, padx=10)
            self.series_labels[f"{away}vs{home}"] = label

    def _display_game_details(self, parent_frame, structured_game):
        """Display box score and play-by-play for a game card."""
        away = structured_game.away_team
        home = structured_game.home_team

        # Box Score: Away Team
        ttk.Label(
            parent_frame,
            text=f"Box Score: {away}",
            style="WSPlayHeader.TLabel",
        ).pack(anchor=tk.W, padx=5, pady=(5, 0))
        self._display_away_team_box_score(
            parent_frame, away, structured_game.away_box_score
        )

        # Box Score: Home Team
        ttk.Label(
            parent_frame,
            text=f"Box Score: {home}",
            style="WSPlayHeader.TLabel",
        ).pack(anchor=tk.W, padx=5, pady=(5, 0))
        self._display_home_team_box_score(
            parent_frame, home, structured_game.home_box_score
        )

        # Play-By-Play (collapsed)
        ttk.Label(
            parent_frame,
            text="Play-By-Play",
            style="WSPlayHeader.TLabel",
        ).pack(anchor=tk.W, padx=5, pady=(5, 0))
        self._display_play_by_play(parent_frame, structured_game)

    def _display_structured_game(self, structured_game):
        """Display a game using structured data."""
        away = structured_game.away_team
        home = structured_game.home_team
        away_score, home_score = structured_game.final_score

        inning_text = f"{structured_game.final_inning}"
        if structured_game.is_extra_innings:
            inning_text += " (Extra Innings)"

        # Game header
        header_frame = tk.Frame(self.scrollable_frame.scrollable_frame, bg=BG_WIDGET)
        header_frame.pack(fill=tk.X, padx=5, pady=(10, 0))

        ttk.Label(
            header_frame,
            text=f"{away} @ {home}",
            style="WSGameHeader.TLabel",
        ).pack(anchor=tk.W, padx=10, pady=(10, 5))

        ttk.Label(
            header_frame,
            text=f"Final: {away} {away_score} - {home} {home_score}  |  {inning_text}",
            style="WSScoreSummary.TLabel",
        ).pack(anchor=tk.W, padx=10, pady=(0, 5))

        # Inning scores
        self._display_inning_scores(structured_game, away, home)

        # Create section manager for proper pack ordering
        section_manager = CollapsibleSectionManager(
            self.scrollable_frame.scrollable_frame
        )

        # Box Score: Away Team
        away_section = CollapsibleSection(
            self.scrollable_frame.scrollable_frame,
            f"Box Score: {away}",
            default_expanded=False,
            on_toggle=lambda: self.scrollable_frame.update_scrollregion(),
        )
        section_manager.add_section(away_section)
        self._display_away_team_box_score(
            away_section.frame, away, structured_game.away_box_score
        )

        # Box Score: Home Team
        home_section = CollapsibleSection(
            self.scrollable_frame.scrollable_frame,
            f"Box Score: {home}",
            default_expanded=False,
            on_toggle=lambda: self.scrollable_frame.update_scrollregion(),
        )
        section_manager.add_section(home_section)
        self._display_home_team_box_score(
            home_section.frame, home, structured_game.home_box_score
        )

        # Play-By-Play (collapsed by default)
        pbp_section = CollapsibleSection(
            self.scrollable_frame.scrollable_frame,
            "Play-By-Play",
            default_expanded=False,
            on_toggle=lambda: self.scrollable_frame.update_scrollregion(),
        )
        section_manager.add_section(pbp_section)
        self._display_play_by_play(pbp_section.frame, structured_game)

        # Bind toggles to use manager
        def make_toggle(section, manager):
            def toggle_wrapper(event=None):
                manager.toggle_section(section)

            return toggle_wrapper

        for section in [away_section, home_section, pbp_section]:
            section.caret.bind("<Button-1>", make_toggle(section, section_manager))
            section.title_label.bind(
                "<Button-1>", make_toggle(section, section_manager)
            )

        # Pack sections
        away_section.pack_header(pady=(15, 0))
        home_section.pack_header()
        pbp_section.pack_header()

    def _display_inning_scores(self, structured_game, away, home):
        """Display score by inning using Treeview."""
        if not structured_game.inning_scores:
            return

        ttk.Label(
            self.scrollable_frame.scrollable_frame,
            text="SCORE BY INNING",
            style="WSSectionHeader.TLabel",
        ).pack(anchor=tk.W, padx=10, pady=(10, 0))

        num_innings = len(structured_game.inning_scores)
        inning_cols = [f"inn_{i}" for i in range(1, num_innings + 1)]
        columns = ["Team"] + inning_cols + ["R", "H", "E"]

        team_width = 50
        inning_width = 28
        rh_width = 30

        tree_frame = tk.Frame(self.scrollable_frame.scrollable_frame, bg=BG_WIDGET)
        tree_frame.pack(fill=tk.X, padx=10, pady=5)

        tree = ttk.Treeview(
            tree_frame,
            columns=columns,
            show="headings",
            style="WSInningScore.Treeview",
            height=2,
        )

        tree.column("#0", width=0, stretch=False)
        tree.heading("#0", text="")

        tree.column("Team", width=team_width, anchor=tk.W, stretch=False)
        tree.heading("Team", text="")

        for i, col in enumerate(inning_cols):
            tree.column(col, width=inning_width, anchor=tk.CENTER, stretch=False)
            tree.heading(col, text=str(i + 1))

        tree.column("R", width=rh_width, anchor=tk.CENTER, stretch=False)
        tree.heading("R", text="R")
        tree.column("H", width=rh_width, anchor=tk.CENTER, stretch=False)
        tree.heading("H", text="H")
        tree.column("E", width=rh_width, anchor=tk.CENTER, stretch=False)
        tree.heading("E", text="E")

        tree.pack(fill=tk.X, expand=True)

        # Away row
        away_values = [away]
        for inn in structured_game.inning_scores:
            away_values.append(str(inn.away_runs))
        if structured_game.away_box_score:
            away_values.extend(
                [
                    str(structured_game.final_score[0]),
                    str(structured_game.away_box_score.total_hits),
                    str(structured_game.away_box_score.total_errors),
                ]
            )
        else:
            away_values.extend(["", "", ""])
        tree.insert("", tk.END, values=away_values)

        # Home row
        home_values = [home]
        for inn in structured_game.inning_scores:
            home_values.append(str(inn.home_runs))
        if structured_game.home_box_score:
            home_values.extend(
                [
                    str(structured_game.final_score[1]),
                    str(structured_game.home_box_score.total_hits),
                    str(structured_game.home_box_score.total_errors),
                ]
            )
        else:
            home_values.extend(["", "", ""])
        tree.insert("", tk.END, values=home_values)

    def _display_away_team_box_score(self, parent_frame, team, box_score):
        """Display away team batting and pitching inside a collapsible section."""
        batting_label = tk.Label(
            parent_frame,
            text="  Batting",
            font=("Segoe UI", 10, "bold"),
            bg=BG_WIDGET,
            fg=ACCENT_BLUE,
            anchor="w",
        )
        batting_label.pack(anchor=tk.W, padx=20, pady=(5, 0))
        self._display_batting_in_section(
            parent_frame, team, box_score, show_header=False
        )

        pitching_label = tk.Label(
            parent_frame,
            text="  Pitching",
            font=("Segoe UI", 10, "bold"),
            bg=BG_WIDGET,
            fg=ACCENT_BLUE,
            anchor="w",
        )
        pitching_label.pack(anchor=tk.W, padx=20, pady=(10, 5))
        self._display_pitching_in_section(
            parent_frame, team, box_score, show_header=False
        )

    def _display_home_team_box_score(self, parent_frame, team, box_score):
        """Display home team batting and pitching inside a collapsible section."""
        batting_label = tk.Label(
            parent_frame,
            text="  Batting",
            font=("Segoe UI", 10, "bold"),
            bg=BG_WIDGET,
            fg=ACCENT_BLUE,
            anchor="w",
        )
        batting_label.pack(anchor=tk.W, padx=20, pady=(5, 0))
        self._display_batting_in_section(
            parent_frame, team, box_score, show_header=False
        )

        pitching_label = tk.Label(
            parent_frame,
            text="  Pitching",
            font=("Segoe UI", 10, "bold"),
            bg=BG_WIDGET,
            fg=ACCENT_BLUE,
            anchor="w",
        )
        pitching_label.pack(anchor=tk.W, padx=20, pady=(10, 5))
        self._display_pitching_in_section(
            parent_frame, team, box_score, show_header=False
        )

    def _display_batting_in_section(
        self, parent_frame, team, box_score, show_header=True
    ):
        """Display batting box score in a section."""
        if show_header:
            ttk.Label(
                parent_frame,
                text=f"  {team}",
                style="WSTeamHeader.TLabel",
            ).pack(anchor=tk.W, padx=10)

        name_width = 140
        stat_width = 40
        columns = ["Player", "Pos", "AB", "R", "H", "2B", "3B", "HR", "RBI", "BB", "K"]

        if not box_score or not box_score.batters:
            num_rows = 1
        else:
            num_rows = len(box_score.batters)
            if box_score.totals_batting:
                num_rows += 1

        tree_frame = tk.Frame(parent_frame, bg=BG_WIDGET)
        tree_frame.pack(anchor=tk.W, padx=10, pady=2)

        tree = ttk.Treeview(
            tree_frame,
            columns=columns,
            show="headings",
            style="WSBoxScore.Treeview",
            height=num_rows,
        )

        tree.column("#0", width=0, stretch=False)
        for i, col in enumerate(columns):
            if i == 0:
                tree.column(col, width=name_width, anchor=tk.W)
            elif i == 1:
                tree.column(col, width=45, anchor=tk.CENTER)
            else:
                tree.column(col, width=stat_width, anchor=tk.CENTER)
            tree.heading(col, text=col)

        tree.pack(anchor=tk.W)

        if not box_score:
            tree.insert("", tk.END, values=["No data"] + [""] * len(columns))
            return

        for idx, batter in enumerate(box_score.batters):
            stats = batter.stats
            name = batter.name[:22] if len(batter.name) > 22 else batter.name
            position = getattr(batter, "position", getattr(batter, "pos", ""))
            values = [
                name,
                position,
                int(stats.AB),
                int(stats.R),
                int(stats.H),
                int(stats.D),
                int(stats.T),
                int(stats.HR),
                int(stats.RBI),
                int(getattr(stats, "BB", 0)),
                int(getattr(stats, "SO", 0)),
            ]
            tree.insert(
                "", tk.END, values=values, tags=("alt",) if idx % 2 == 1 else ()
            )

        if box_score.totals_batting:
            totals = box_score.totals_batting
            tree.insert(
                "",
                tk.END,
                values=[
                    "TOTALS",
                    "",
                    int(totals.AB),
                    int(totals.R),
                    int(totals.H),
                    int(totals.D),
                    int(totals.T),
                    int(totals.HR),
                    int(totals.RBI),
                    int(getattr(totals, "BB", 0)),
                    int(getattr(totals, "SO", 0)),
                ],
                tags=("totals",),
            )

        tree.tag_configure("alt", background=BG_WIDGET_ALT)
        tree.tag_configure("totals", background="#2a2a3a", foreground=ACCENT_GOLD)

    def _display_pitching_in_section(
        self, parent_frame, team, box_score, show_header=True
    ):
        """Display pitching box score in a section."""
        if show_header:
            ttk.Label(
                parent_frame,
                text=f"  {team}",
                style="WSTeamHeader.TLabel",
            ).pack(anchor=tk.W, padx=10)

        name_width = 140
        stat_width = 35
        columns = ["Pitcher", "IP", "H", "ER", "SO", "BB", "HR", "W", "L", "HLD", "SV"]

        if not box_score or not box_score.pitchers:
            num_rows = 1
        else:
            num_rows = len(box_score.pitchers)

        tree_frame = tk.Frame(parent_frame, bg=BG_WIDGET)
        tree_frame.pack(anchor=tk.W, padx=10, pady=2)

        tree = ttk.Treeview(
            tree_frame,
            columns=columns,
            show="headings",
            style="WSBoxScore.Treeview",
            height=num_rows,
        )

        tree.column("#0", width=0, stretch=False)
        for i, col in enumerate(columns):
            if i == 0:
                tree.column(col, width=name_width, anchor=tk.W)
            else:
                tree.column(col, width=stat_width, anchor=tk.CENTER)
            tree.heading(col, text=col)

        tree.pack(anchor=tk.W)

        if not box_score or not box_score.pitchers:
            tree.insert("", tk.END, values=["No data"] + [""] * len(columns))
            return

        for idx, pitcher in enumerate(box_score.pitchers):
            stats = pitcher.stats
            name = pitcher.name[:22] if len(pitcher.name) > 22 else pitcher.name
            values = [
                name,
                f"{stats.IP:.1f}",
                int(stats.H),
                int(stats.ER),
                int(stats.SO),
                int(stats.BB),
                int(stats.HR),
                int(stats.W),
                int(stats.L),
                int(getattr(stats, "HLD", 0)),
                int(getattr(stats, "SV", 0)),
            ]
            tree.insert(
                "", tk.END, values=values, tags=("alt",) if idx % 2 == 1 else ()
            )

        tree.tag_configure("alt", background=BG_WIDGET_ALT)

    def _display_play_by_play(self, parent_frame, structured_game):
        """Display play-by-play as flat list (no collapsible sections per inning)."""
        if not structured_game.innings:
            ttk.Label(
                parent_frame,
                text="  No play-by-play data available",
                style="WSPlayItem.TLabel",
            ).pack(anchor=tk.W, padx=10)
            return

        away = structured_game.away_team
        home = structured_game.home_team
        away_runs = 0
        home_runs = 0

        for i, inning_data in enumerate(structured_game.innings):
            inning_num = i + 1

            for half, half_data in inning_data.items():
                if not half_data.plays:
                    continue

                half_label = "Top" if half == "top" else "Bot"
                ttk.Label(
                    parent_frame,
                    text=f"  {half_label} {inning_num}:",
                    style="WSPlayHeader.TLabel",
                ).pack(anchor=tk.W)

                for play in half_data.plays:
                    if play.play_description:
                        ttk.Label(
                            parent_frame,
                            text=f"    {play.play_description}",
                            style="WSPlayItem.TLabel",
                        ).pack(anchor=tk.W)

                    runs = getattr(play, "runs_scored", []) or []
                    num_runs = len(runs) if isinstance(runs, list) else runs
                    if half == "top":
                        away_runs += num_runs
                    else:
                        home_runs += num_runs

                # Score at end of half inning
                tk.Label(
                    parent_frame,
                    text=f"  === {away} {away_runs}, {home} {home_runs} ===",
                    font=("Segoe UI", 9, "bold"),
                    foreground=ACCENT_GOLD,
                    bg=BG_WIDGET,
                ).pack(anchor=tk.W)

    def world_series_started(self, ws_data: Dict[str, Any]):
        """
        Handle playoff/World Series start signal.

        Args:
            ws_data: Dict with 'al_winner', 'nl_winner', 'season', etc.
        """
        season = ws_data.get("season", "")
        playoff_mode = ws_data.get("playoff_mode", False)

        if playoff_mode:
            self.ws_active = True
            self.ws_info = ws_data
            self.series_score = {}
            self.game_number = 0
            self.current_game = 1
            self.games_data = {}
            self.header_label.config(text=f"{season} Playoffs")
        else:
            al = ws_data.get("al_winner", "")
            nl = ws_data.get("nl_winner", "")
            self.ws_active = True
            self.ws_info = ws_data
            self.series_score = {al: 0, nl: 0}
            self.header_label.config(text=f"{season} World Series: {al} vs {nl}")

    def add_play_by_play(self, play_data: Dict[str, Any]):
        """Handle play-by-play (for future real-time updates)."""
        pass

    def add_game_result(self, game_data: Dict[str, Any]):
        """
        Add a completed game's data.

        Args:
            game_data: Dict with game results and structured_game
        """
        if not self.ws_active:
            return

        self.game_number += 1
        away = game_data.get("away_team", "")
        home = game_data.get("home_team", "")
        away_r = game_data.get("away_r", 0)
        home_r = game_data.get("home_r", 0)
        structured_game = game_data.get("structured_game")

        # Update series score
        if away_r > home_r:
            self.series_score[away] = self.series_score.get(away, 0) + 1
        else:
            self.series_score[home] = self.series_score.get(home, 0) + 1

        # Store structured game data
        if structured_game:
            self.games_data[self.game_number] = structured_game

        # Display all games in table format
        self._display_todays_games()

    def world_series_completed(self, ws_data: Dict[str, Any]):
        """
        Handle World Series completion signal.

        Args:
            ws_data: Dict with 'champion', 'season', 'series_result'
        """
        # Keep the game table visible, just add champion banner
        champion = ws_data.get("champion", "")

        # Add champion banner at the bottom (games are already displayed)

        # Then add champion banner at the top
        result_frame = tk.Frame(self.scrollable_frame.scrollable_frame, bg=BG_WIDGET)
        result_frame.pack(pady=(10, 20))

        tk.Label(
            result_frame,
            text=f"{'=' * 40}",
            font=("Segoe UI", 14, "bold"),
            bg=BG_WIDGET,
            fg=ACCENT_GOLD,
        ).pack()

        tk.Label(
            result_frame,
            text=f"{champion}",
            font=("Segoe UI", 20, "bold"),
            bg=BG_WIDGET,
            fg=ACCENT_GOLD,
        ).pack(pady=10)

        tk.Label(
            result_frame,
            text="WORLD SERIES CHAMPION!",
            font=("Segoe UI", 16, "bold"),
            bg=BG_WIDGET,
            fg=ACCENT_GOLD,
        ).pack()

        tk.Label(
            result_frame,
            text=f"{'=' * 40}",
            font=("Segoe UI", 14, "bold"),
            bg=BG_WIDGET,
            fg=ACCENT_GOLD,
        ).pack()

        self.scrollable_frame.update_scrollregion()

    def get_frame(self) -> tk.Frame:
        """Return the main frame for packing."""
        return self.frame


class CollapsibleSectionManager:
    """Manages collapsible sections to ensure proper pack ordering."""

    def __init__(self, parent):
        self.parent = parent
        self.sections = []

    def add_section(self, section):
        """Add a section."""
        self.sections.append(section)

    def toggle_section(self, section):
        """Toggle a section and re-pack all sections in order."""
        section.toggle()
        self._repack_all()

    def _repack_all(self):
        """Repack all sections in their original order."""
        for section in self.sections:
            section.frame.pack_forget()
            section.header_frame.pack_forget()

        for section in self.sections:
            section.header_frame.pack(fill=tk.X, padx=5, pady=(10, 0))
            if section.expanded:
                section.frame.pack(fill=tk.X, padx=5, pady=(0, 5))
