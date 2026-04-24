"""
--- Copyright Notice ---
Copyright (c) 2024 Jim Maastricht

Games Played widget for baseball season simulation UI.

Displays formatted game summaries for followed team games using structured data.
"""

import tkinter as tk
from tkinter import ttk
from typing import Dict, List, Tuple, Optional, Any
from bblogger import logger

from ui.theme import (
    BG_PANEL,
    BG_WIDGET,
    BG_WIDGET_ALT,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    ACCENT_BLUE,
    ACCENT_GOLD,
    TEXT_HEADING,
)
from ui.models.game_data import AWAY, HOME, InningScore


class ScrollableFrame(ttk.Frame):
    """A Frame that can be scrolled vertically."""

    def __init__(self, parent, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)

        self.canvas = tk.Canvas(
            self,
            bg=BG_WIDGET,
            highlightthickness=0,
        )
        self.scrollbar = ttk.Scrollbar(
            self, orient=tk.VERTICAL, command=self.canvas.yview
        )
        self.canvas.config(yscrollcommand=self.scrollbar.set)

        self.scrollable_frame = ttk.Frame(self.canvas, style="Scrollable.TFrame")

        self.canvas_window = self.canvas.create_window(
            (0, 0),
            window=self.scrollable_frame,
            anchor=tk.NW,
        )

        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.canvas.bind("<Configure>", self._on_canvas_configure)
        self.scrollable_frame.bind("<Configure>", self._on_frame_configure)

    def _on_canvas_configure(self, event):
        """Resize the inner frame to match canvas width."""
        self.canvas.itemconfig(
            self.canvas_window, width=event.width - self.scrollbar.winfo_width()
        )
        self._update_scrollregion()

    def _on_frame_configure(self, event):
        """Update scroll region when frame changes."""
        self._update_scrollregion()

    def _update_scrollregion(self):
        """Update scroll region to encompass all content."""
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _on_mousewheel(self, event):
        """Handle mousewheel scrolling."""
        if event.num == 4:
            self.canvas.yview_scroll(-3, "units")
        elif event.num == 5:
            self.canvas.yview_scroll(3, "units")
        else:
            self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def see(self, widget):
        """Scroll to make widget visible."""
        self.canvas.yview_moveto(0.0)

    def update_scrollregion(self):
        """Public method to force scroll region update (call after adding content)."""
        self._update_scrollregion()


class CollapsibleSection:
    """A collapsible section with a clickable header."""

    def __init__(
        self, parent, title: str, default_expanded: bool = True, on_toggle=None
    ):
        self.parent = parent
        self.title = title
        self.expanded = default_expanded
        self.on_toggle = on_toggle

        self.header_frame = tk.Frame(parent, bg=BG_WIDGET, cursor="hand2")

        self.caret = tk.Label(
            self.header_frame,
            text="▼" if self.expanded else "▶",
            font=("Segoe UI", 10, "bold"),
            bg=BG_WIDGET,
            fg=ACCENT_BLUE,
            width=2,
            cursor="hand2",
        )
        self.caret.pack(side=tk.LEFT, padx=(10, 5))

        self.title_label = tk.Label(
            self.header_frame,
            text=title,
            font=("Segoe UI", 12, "bold"),
            bg=BG_WIDGET,
            fg=ACCENT_BLUE,
            anchor="w",
            cursor="hand2",
        )
        self.title_label.pack(side=tk.LEFT, fill=tk.X, expand=True)

        self.frame = tk.Frame(parent, bg=BG_WIDGET)

    def pack_header(self, pady=(10, 0)):
        """Pack the header (call after all sections are created for proper ordering)."""
        self.header_frame.pack(fill=tk.X, padx=5, pady=pady)
        if self.expanded:
            self.frame.pack(fill=tk.X, padx=5, pady=(0, 5))

    def toggle(self, event=None):
        """Toggle the expanded/collapsed state."""
        self.expanded = not self.expanded
        self.caret.config(text="▼" if self.expanded else "▶")

        if self.expanded:
            self.frame.pack(fill=tk.X, padx=5, pady=(0, 5))
        else:
            self.frame.pack_forget()

        if self.on_toggle:
            self.on_toggle()

    def is_expanded(self) -> bool:
        """Return whether section is expanded."""
        return self.expanded


class CollapsibleSectionManager:
    """Manages collapsible sections to ensure proper pack ordering."""

    def __init__(self, parent):
        self.parent = parent
        self.sections = []

    def add_section(self, section):
        """Add a section and pack it in order."""
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


class GamesPlayedWidget:
    """
    Games Played widget showing formatted game summaries for followed team.

    Features:
    - Day dropdown to select which day to view
    - Formatted display with score by inning, box scores, and play-by-play
    - Uses structured GameRecap data when available
    - Falls back to text recap when no structured data
    - Treeview grids for batting and pitching box scores
    """

    def __init__(self, parent: tk.Widget):
        """
        Initialize games played widget.

        Args:
            parent: Parent tkinter widget (notebook or frame)
        """
        self.frame = tk.Frame(parent, bg=BG_PANEL)

        # Storage for game data by day
        # Format: {day_num: [(away, home, game_recap, structured_game), ...]}
        self.pbp_by_day = {}

        # Control frame with day dropdown
        pbp_control_frame = tk.Frame(self.frame, bg=BG_PANEL)
        pbp_control_frame.pack(fill=tk.X, padx=10, pady=5)

        tk.Label(
            pbp_control_frame,
            text="Day:",
            font=("Segoe UI", 12, "bold"),
            bg=BG_PANEL,
            fg=TEXT_PRIMARY,
        ).pack(side=tk.LEFT, padx=5)
        self.pbp_day_var = tk.StringVar(value="Select Day")
        self.pbp_day_combo = ttk.Combobox(
            pbp_control_frame,
            textvariable=self.pbp_day_var,
            width=15,
            state="readonly",
            font=("Segoe UI", 11),
        )
        self.pbp_day_combo["values"] = ["Select Day"]
        self.pbp_day_combo.bind("<<ComboboxSelected>>", self._on_day_changed)
        self.pbp_day_combo.pack(side=tk.LEFT, padx=5)

        # Info label
        self.pbp_info_label = tk.Label(
            pbp_control_frame,
            text="Select a day to view play-by-play for followed games",
            font=("Segoe UI", 11),
            bg=BG_PANEL,
            fg=TEXT_SECONDARY,
        )
        self.pbp_info_label.pack(side=tk.LEFT, padx=20)

        # Configure ttk styles
        self._configure_styles()

        # Scrollable frame for game display
        self.scrollable_frame = ScrollableFrame(self.frame, style="Scrollable.TFrame")
        self.scrollable_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        self._on_scroll_frame_enter()
        self.scrollable_frame.canvas.bind(
            "<Enter>", lambda e: self._on_scroll_frame_enter()
        )
        self.scrollable_frame.canvas.bind(
            "<Leave>", lambda e: self._on_scroll_frame_leave()
        )

    def _on_scroll_frame_enter(self, event=None):
        """Bind mousewheel when mouse enters scrollable area."""
        self.scrollable_frame.canvas.bind(
            "<MouseWheel>", self.scrollable_frame._on_mousewheel
        )
        for child in self.scrollable_frame.scrollable_frame.winfo_children():
            try:
                child.bind("<MouseWheel>", self.scrollable_frame._on_mousewheel)
            except tk.TclError:
                pass

    def _on_scroll_frame_leave(self, event=None):
        """Unbind mousewheel when mouse leaves scrollable area."""
        self.scrollable_frame.canvas.unbind("<MouseWheel>")
        for child in self.scrollable_frame.scrollable_frame.winfo_children():
            try:
                child.unbind("<MouseWheel>")
            except tk.TclError:
                pass

    def _configure_styles(self):
        """Configure custom ttk styles."""
        style = ttk.Style()

        # Game header style
        style.configure(
            "GameHeader.TLabel",
            font=("Segoe UI", 14, "bold"),
            foreground=ACCENT_GOLD,
            background=BG_WIDGET,
            padding=5,
        )

        # Section header style
        style.configure(
            "SectionHeader.TLabel",
            font=("Segoe UI", 12, "bold"),
            foreground=ACCENT_BLUE,
            background=BG_WIDGET,
            padding=(5, 10, 5, 3),
        )

        # Team header style
        style.configure(
            "TeamHeader.TLabel",
            font=("Segoe UI", 11, "bold"),
            foreground=ACCENT_BLUE,
            background=BG_WIDGET,
            padding=(10, 5, 5, 2),
        )

        # Score summary style
        style.configure(
            "ScoreSummary.TLabel",
            font=("Segoe UI", 11),
            foreground=TEXT_PRIMARY,
            background=BG_WIDGET,
            padding=(10, 0, 5, 5),
        )

        # Pitcher decision style
        style.configure(
            "PitcherDecision.TLabel",
            font=("Segoe UI", 11, "bold"),
            foreground=ACCENT_GOLD,
            background=BG_WIDGET,
            padding=(10, 5, 5, 5),
        )

        # Play-by-play header style
        style.configure(
            "PlayHeader.TLabel",
            font=("Segoe UI", 11, "bold"),
            foreground=ACCENT_BLUE,
            background=BG_WIDGET,
            padding=(10, 10, 5, 3),
        )

        # Play item style
        style.configure(
            "PlayItem.TLabel",
            font=("Segoe UI", 9),
            foreground=TEXT_PRIMARY,
            background=BG_WIDGET,
            padding=(15, 1, 5, 1),
        )

        # Treeview styles
        style.configure(
            "BoxScore.Treeview",
            font=("Segoe UI", 9),
            rowheight=18,
            background=BG_WIDGET,
            fieldbackground=BG_WIDGET,
            foreground=TEXT_PRIMARY,
        )
        style.configure(
            "BoxScore.Treeview.Heading",
            font=("Segoe UI", 10, "bold"),
            background=BG_PANEL,
            foreground=TEXT_PRIMARY,
        )
        style.configure(
            "BoxScoreAlt.Treeview",
            font=("Segoe UI", 9),
            rowheight=18,
            background=BG_WIDGET_ALT,
            fieldbackground=BG_WIDGET_ALT,
            foreground=TEXT_PRIMARY,
        )

        # Inning score table style
        style.configure(
            "InningScore.Treeview",
            font=("Segoe UI", 9),
            rowheight=18,
            background=BG_WIDGET,
            fieldbackground=BG_WIDGET,
            foreground=TEXT_PRIMARY,
        )
        style.configure(
            "InningScore.Treeview.Heading",
            font=("Segoe UI", 10, "bold"),
            background=BG_PANEL,
            foreground=TEXT_PRIMARY,
        )

        # Totals row style
        style.configure(
            "Totals.Treeview",
            font=("Segoe UI", 9, "bold"),
            rowheight=20,
            background="#2a2a3a",
            fieldbackground="#2a2a3a",
            foreground=ACCENT_GOLD,
        )

    def _create_treeview(
        self, parent, columns: List[str], heading_names: List[str], width: int = 700
    ) -> ttk.Treeview:
        """Create a styled Treeview table."""
        tree = ttk.Treeview(
            parent,
            columns=columns,
            show="tree headings",
            style="BoxScore.Treeview",
            height=12,
        )

        # Set column widths
        name_width = 180
        col_width = (width - name_width) // (len(columns) - 1)
        tree.column("#0", width=name_width, anchor=tk.W)
        tree.heading("#0", text="Player")

        for col in columns[1:]:
            tree.column(col, width=col_width, anchor=tk.CENTER)
            idx = columns.index(col) - 1
            tree.heading(
                col, text=heading_names[idx] if idx < len(heading_names) else col
            )

        # Add scrollbar
        vsb = ttk.Scrollbar(parent, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=vsb.set)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        tree.pack(side=tk.LEFT, fill=tk.X, expand=True)

        return tree

    def _add_treeview_row(
        self,
        tree: ttk.Treeview,
        values: List,
        tags: Optional[Tuple[str]] = None,
    ):
        """Add a row to treeview with alternating colors."""
        tag = "alt" if len(tree.get_children()) % 2 == 1 else ""
        if tags:
            tag = " ".join([tag, *tags]) if tag else " ".join(tags)
        tree.insert("", tk.END, values=values, tags=(tag,) if tag else ())

    def add_game_recap(
        self,
        day_num: int,
        away_team: str,
        home_team: str,
        game_recap: str,
        structured_game: Any = None,
        date_str: str = None,
    ):
        """
        Add a game recap to the play-by-play storage.

        Args:
            day_num: Day number (0-indexed)
            away_team: Away team abbreviation
            home_team: Home team abbreviation
            game_recap: Full game play-by-play text (fallback)
            structured_game: GameRecap Pydantic object (preferred)
            date_str: Date string for this game (e.g., "April 5, 2026")
        """
        if day_num not in self.pbp_by_day:
            self.pbp_by_day[day_num] = []

        self.pbp_by_day[day_num].append(
            (away_team, home_team, game_recap, structured_game)
        )

        # Store date if provided
        if date_str:
            if not hasattr(self, '_day_dates'):
                self._day_dates = {}
            self._day_dates[day_num] = date_str

        # Update dropdown with date if available, otherwise use Day # (most recent first)
        day_options = []
        for d in sorted(self.pbp_by_day.keys(), reverse=True):
            if hasattr(self, '_day_dates') and d in self._day_dates:
                day_options.append(self._day_dates[d])
            else:
                day_options.append(f"Day {d + 1}")
        self.pbp_day_combo["values"] = ["Select Day"] + day_options

        logger.debug(
            f"Added game recap for Day {day_num + 1}: {away_team} @ {home_team}"
        )

    def _on_day_changed(self, event=None):
        """Handle day dropdown change."""
        selected = self.pbp_day_var.get()

        if selected == "Select Day":
            return

        # Determine day number - check if it's a date string or "Day X" format
        day_num = None
        if selected.startswith("Day "):
            try:
                day_num = int(selected.split()[1]) - 1  # Convert back to 0-indexed
            except (ValueError, IndexError):
                logger.error(f"Invalid day selection: {selected}")
                return
        else:
            # It's a date string - look up day number from _day_dates
            if hasattr(self, '_day_dates'):
                for d, date_str in self._day_dates.items():
                    if date_str == selected:
                        day_num = d
                        break

        if day_num is None:
            logger.error(f"Could not find day number for: {selected}")
            return

        # Get games for this day
        games = self.pbp_by_day.get(day_num, [])

        if not games:
            self._clear_display()
            label = ttk.Label(
                self.scrollable_frame.scrollable_frame,
                text=f"No followed games on {selected}",
                style="ScoreSummary.TLabel",
            )
            label.pack(padx=10, pady=20)
            return

        # Clear previous display
        self._clear_display()

        # Display all games for this day
        for idx, (away, home, game_recap, structured_game) in enumerate(games):
            # Add separator between games
            if idx > 0:
                separator = tk.Frame(
                    self.scrollable_frame.scrollable_frame,
                    bg=TEXT_SECONDARY,
                    height=2,
                )
                separator.pack(fill=tk.X, padx=10, pady=10)

            if structured_game:
                self._display_structured_game(structured_game)
            else:
                self._display_text_recap(away, home, game_recap)

        # Update scroll region and scroll to top
        self.scrollable_frame.update_scrollregion()
        self.scrollable_frame.canvas.yview_moveto(0)

        # Deferred update to ensure all content is rendered and mousewheel is bound
        self.scrollable_frame.after(50, self.scrollable_frame.update_scrollregion)
        self.scrollable_frame.after(100, self._on_scroll_frame_enter)

        logger.debug(f"Displayed {len(games)} games for Day {day_num + 1}")

    def _clear_display(self):
        """Clear all widgets from the scrollable frame."""
        for widget in self.scrollable_frame.scrollable_frame.winfo_children():
            widget.destroy()

    def _display_structured_game(self, structured_game):
        """
        Display a game using structured data with Treeview grids and collapsible sections.

        Args:
            structured_game: GameRecap Pydantic object
        """
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
            style="GameHeader.TLabel",
        ).pack(anchor=tk.W, padx=10, pady=(10, 5))

        ttk.Label(
            header_frame,
            text=f"Final: {away} {away_score} - {home} {home_score}  |  {inning_text}",
            style="ScoreSummary.TLabel",
        ).pack(anchor=tk.W, padx=10, pady=(0, 5))

        # Inning scores (always expanded by default)
        self._display_inning_scores(structured_game, away, home)

        # Create manager for collapsible sections
        section_manager = CollapsibleSectionManager(
            self.scrollable_frame.scrollable_frame
        )

        # Box Score: Away Team (collapsed by default)
        away_section = CollapsibleSection(
            self.scrollable_frame.scrollable_frame,
            f"Box Score: {away}",
            default_expanded=False,
            on_toggle=lambda: self.scrollable_frame.update_scrollregion(),
        )
        section_manager.add_section(away_section)
        self._display_away_team_box_score(
            away_section.frame,
            away,
            structured_game.away_box_score,
        )

        # Box Score: Home Team (collapsed by default)
        home_section = CollapsibleSection(
            self.scrollable_frame.scrollable_frame,
            f"Box Score: {home}",
            default_expanded=False,
            on_toggle=lambda: self.scrollable_frame.update_scrollregion(),
        )
        section_manager.add_section(home_section)
        self._display_home_team_box_score(
            home_section.frame,
            home,
            structured_game.home_box_score,
        )

        # Play-by-play (expanded by default)
        pbp_section = CollapsibleSection(
            self.scrollable_frame.scrollable_frame,
            "Play-By-Play",
            default_expanded=True,
            on_toggle=lambda: self.scrollable_frame.update_scrollregion(),
        )
        section_manager.add_section(pbp_section)
        self._display_play_by_play_in_section(pbp_section.frame, structured_game)

        # Override toggle to use manager
        def make_toggle(section, manager):
            def toggle_wrapper(event=None):
                manager.toggle_section(section)

            return toggle_wrapper

        away_section.caret.bind(
            "<Button-1>", make_toggle(away_section, section_manager)
        )
        away_section.title_label.bind(
            "<Button-1>", make_toggle(away_section, section_manager)
        )
        home_section.caret.bind(
            "<Button-1>", make_toggle(home_section, section_manager)
        )
        home_section.title_label.bind(
            "<Button-1>", make_toggle(home_section, section_manager)
        )
        pbp_section.caret.bind("<Button-1>", make_toggle(pbp_section, section_manager))
        pbp_section.title_label.bind(
            "<Button-1>", make_toggle(pbp_section, section_manager)
        )

        # Pack sections in order (after all are created for correct ordering)
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
            style="SectionHeader.TLabel",
        ).pack(anchor=tk.W, padx=10, pady=(10, 0))

        num_innings = len(structured_game.inning_scores)

        # Team + inning columns + R, H, E columns
        inning_cols = [f"inn_{i}" for i in range(1, num_innings + 1)]
        columns = ["Team"] + inning_cols + ["R", "H", "E"]

        team_width = 50
        inning_width = 25
        rh_width = 30

        tree_frame = tk.Frame(
            self.scrollable_frame.scrollable_frame, bg=BG_WIDGET, height=55
        )
        tree_frame.pack(anchor=tk.W, padx=10, pady=5)

        tree = ttk.Treeview(
            tree_frame,
            columns=columns,
            show="headings",
            style="InningScore.Treeview",
            height=2,
        )

        tree.column("#0", width=0, stretch=False)
        tree.heading("#0", text="")

        tree.column("Team", width=team_width, anchor=tk.W)
        tree.heading("Team", text="")

        # Set inning column headings
        for i, col in enumerate(inning_cols):
            tree.column(col, width=inning_width, anchor=tk.CENTER)
            tree.heading(col, text=str(i + 1))

        # R, H, E columns
        tree.column("R", width=rh_width, anchor=tk.CENTER)
        tree.heading("R", text="R")
        tree.column("H", width=rh_width, anchor=tk.CENTER)
        tree.heading("H", text="H")
        tree.column("E", width=rh_width, anchor=tk.CENTER)
        tree.heading("E", text="E")

        tree.pack(side=tk.LEFT, anchor=tk.W)

        # Add away team row
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
        tree.insert("", tk.END, values=away_values, tags=("away",))

        # Add home team row
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
        tree.insert("", tk.END, values=home_values, tags=("home",))

    def _display_batting_box_scores(self, structured_game):
        """Display batting box scores using Treeview grids."""
        away_bs = structured_game.away_box_score
        home_bs = structured_game.home_box_score

        if not away_bs and not home_bs:
            return

        ttk.Label(
            self.scrollable_frame.scrollable_frame,
            text="BATTING",
            style="SectionHeader.TLabel",
        ).pack(anchor=tk.W, padx=10, pady=(15, 0))

        columns = ["Pos", "AB", "R", "H", "2B", "3B", "HR", "RBI", "BB", "K"]
        headings = ["Pos", "AB", "R", "H", "2B", "3B", "HR", "RBI", "BB", "K"]

        # Away team
        self._display_team_batting(
            structured_game.away_team, away_bs, columns, headings
        )

        # Home team
        self._display_team_batting(
            structured_game.home_team, home_bs, columns, headings
        )

    def _display_team_batting(
        self, team: str, box_score, columns: List, headings: List
    ):
        """Display batting box score for one team."""
        ttk.Label(
            self.scrollable_frame.scrollable_frame,
            text=f"  {team}",
            style="TeamHeader.TLabel",
        ).pack(anchor=tk.W)

        name_width = 145
        stat_width = 42
        all_columns = ["Player"] + columns
        all_headings = ["Player"] + headings

        if not box_score or not box_score.batters:
            num_rows = 1
        else:
            num_rows = len(box_score.batters)
            if box_score.totals_batting:
                num_rows += 1

        frame_height = num_rows * 20 + 10

        tree_frame = tk.Frame(
            self.scrollable_frame.scrollable_frame, bg=BG_WIDGET, height=frame_height
        )
        tree_frame.pack(anchor=tk.W, padx=10, pady=2)

        tree = ttk.Treeview(
            tree_frame,
            columns=all_columns,
            show="headings",
            style="BoxScore.Treeview",
            height=num_rows,
        )

        tree.column("#0", width=0, stretch=False)
        for i, col in enumerate(all_columns):
            if i == 0:
                tree.column(col, width=name_width, anchor=tk.W)
            else:
                tree.column(col, width=stat_width, anchor=tk.CENTER)
            tree.heading(col, text=all_headings[i])

        tree.pack(anchor=tk.W)

        if not box_score:
            tree.insert("", tk.END, values=["No data"] + [""] * len(all_columns))
            return

        for idx, batter in enumerate(box_score.batters):
            stats = batter.stats
            name = batter.name[:24] if len(batter.name) > 24 else batter.name
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

        # Totals row
        if box_score.totals_batting:
            totals = box_score.totals_batting
            totals_values = [
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
            ]
            tree.insert("", tk.END, values=totals_values, tags=("totals",))

        # Configure tag styles
        tree.tag_configure("alt", background=BG_WIDGET_ALT)
        tree.tag_configure("totals", background="#2a2a3a", foreground=ACCENT_GOLD)

    def _display_pitching_box_scores(self, structured_game):
        """Display pitching box scores using Treeview grids."""
        away_bs = structured_game.away_box_score
        home_bs = structured_game.home_box_score

        if not away_bs and not home_bs:
            return

        ttk.Label(
            self.scrollable_frame.scrollable_frame,
            text="PITCHING",
            style="SectionHeader.TLabel",
        ).pack(anchor=tk.W, padx=10, pady=(15, 0))

        columns = ["IP", "H", "ER", "SO", "BB", "HR", "W", "L", "HLD", "SV"]
        headings = ["IP", "H", "ER", "SO", "BB", "HR", "W", "L", "HLD", "SV"]

        # Away team
        self._display_team_pitching(
            structured_game.away_team, away_bs, columns, headings
        )

        # Home team
        self._display_team_pitching(
            structured_game.home_team, home_bs, columns, headings
        )

    def _display_team_pitching(
        self, team: str, box_score, columns: List, headings: List
    ):
        """Display pitching box score for one team."""
        ttk.Label(
            self.scrollable_frame.scrollable_frame,
            text=f"  {team}",
            style="TeamHeader.TLabel",
        ).pack(anchor=tk.W)

        name_width = 145
        stat_width = 36
        all_columns = ["Pitcher"] + columns
        all_headings = ["Pitcher"] + headings

        if not box_score or not box_score.pitchers:
            num_rows = 1
        else:
            num_rows = len(box_score.pitchers)

        frame_height = num_rows * 20 + 10

        tree_frame = tk.Frame(
            self.scrollable_frame.scrollable_frame, bg=BG_WIDGET, height=frame_height
        )
        tree_frame.pack(anchor=tk.W, padx=10, pady=2)

        tree = ttk.Treeview(
            tree_frame,
            columns=all_columns,
            show="headings",
            style="BoxScore.Treeview",
            height=num_rows,
        )

        tree.column("#0", width=0, stretch=False)
        for i, col in enumerate(all_columns):
            if i == 0:
                tree.column(col, width=name_width, anchor=tk.W)
            else:
                tree.column(col, width=stat_width, anchor=tk.CENTER)
            tree.heading(col, text=all_headings[i])

        tree.pack(anchor=tk.W)

        if not box_score or not box_score.pitchers:
            tree.insert("", tk.END, values=["No data"] + [""] * len(all_columns))
            return

        for idx, pitcher in enumerate(box_score.pitchers):
            stats = pitcher.stats
            name = pitcher.name[:24] if len(pitcher.name) > 24 else pitcher.name
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
                int(stats.HLD),
                int(stats.SV),
            ]
            tree.insert(
                "", tk.END, values=values, tags=("alt",) if idx % 2 == 1 else ()
            )

        # Configure tag styles
        tree.tag_configure("alt", background=BG_WIDGET_ALT)

    def _display_pitcher_decisions(self, structured_game):
        """Display win/loss/hold/save pitcher summary."""
        ttk.Label(
            self.scrollable_frame.scrollable_frame,
            text="PITCHER DECISIONS",
            style="SectionHeader.TLabel",
        ).pack(anchor=tk.W, padx=10, pady=(15, 0))

        decisions = []
        if structured_game.winning_pitcher:
            decisions.append(f"W: {structured_game.winning_pitcher}")
        if structured_game.losing_pitcher:
            decisions.append(f"L: {structured_game.losing_pitcher}")

        away_bs = structured_game.away_box_score
        home_bs = structured_game.home_box_score

        hld_pitchers = []
        sv_pitchers = []

        for box_score in [away_bs, home_bs]:
            if box_score and box_score.pitchers:
                for pitcher in box_score.pitchers:
                    stats = pitcher.stats
                    if stats.HLD > 0:
                        hld_pitchers.append(pitcher.name)
                    if stats.SV > 0:
                        sv_pitchers.append(pitcher.name)

        for name in hld_pitchers:
            decisions.append(f"HLD: {name}")
        for name in sv_pitchers:
            decisions.append(f"SV: {name}")

        decision_text = "   ".join(decisions) if decisions else "No decision recorded"

        ttk.Label(
            self.scrollable_frame.scrollable_frame,
            text=decision_text,
            style="PitcherDecision.TLabel",
        ).pack(anchor=tk.W, padx=10)

    def _display_away_team_box_score(self, parent_frame, team, box_score):
        """Display away team batting and pitching inside a collapsible section."""
        # Batting sub-section
        batting_label = tk.Label(
            parent_frame,
            text="  Batting",
            font=("Segoe UI", 10, "bold"),
            bg=BG_WIDGET,
            fg=ACCENT_BLUE,
            anchor="w",
        )
        batting_label.pack(anchor=tk.W, padx=20, pady=(5, 0))
        self._display_team_batting_in_section(
            parent_frame, team, box_score, show_team_header=False
        )

        # Pitching sub-section
        pitching_label = tk.Label(
            parent_frame,
            text="  Pitching",
            font=("Segoe UI", 10, "bold"),
            bg=BG_WIDGET,
            fg=ACCENT_BLUE,
            anchor="w",
        )
        pitching_label.pack(anchor=tk.W, padx=20, pady=(10, 5))
        self._display_team_pitching_in_section(
            parent_frame, team, box_score, show_team_header=False
        )

    def _display_home_team_box_score(self, parent_frame, team, box_score):
        """Display home team batting and pitching inside a collapsible section."""
        # Batting sub-section
        batting_label = tk.Label(
            parent_frame,
            text="  Batting",
            font=("Segoe UI", 10, "bold"),
            bg=BG_WIDGET,
            fg=ACCENT_BLUE,
            anchor="w",
        )
        batting_label.pack(anchor=tk.W, padx=20, pady=(5, 0))
        self._display_team_batting_in_section(
            parent_frame, team, box_score, show_team_header=False
        )

        # Pitching sub-section
        pitching_label = tk.Label(
            parent_frame,
            text="  Pitching",
            font=("Segoe UI", 10, "bold"),
            bg=BG_WIDGET,
            fg=ACCENT_BLUE,
            anchor="w",
        )
        pitching_label.pack(anchor=tk.W, padx=20, pady=(10, 5))
        self._display_team_pitching_in_section(
            parent_frame, team, box_score, show_team_header=False
        )

    def _display_batting_box_scores_in_section(self, parent_frame, structured_game):
        """Display batting box scores inside a collapsible section frame."""
        away_bs = structured_game.away_box_score
        home_bs = structured_game.home_box_score

        if not away_bs and not home_bs:
            ttk.Label(
                parent_frame,
                text="  No batting data available",
                style="PlayItem.TLabel",
            ).pack(anchor=tk.W, padx=10)
            return

        self._display_team_batting_in_section(
            parent_frame, structured_game.away_team, away_bs
        )
        self._display_team_batting_in_section(
            parent_frame, structured_game.home_team, home_bs
        )

    def _display_team_batting_in_section(
        self, parent_frame, team, box_score, show_team_header=True
    ):
        """Display batting box score for one team inside a section."""
        if show_team_header:
            ttk.Label(
                parent_frame,
                text=f"  {team}",
                style="TeamHeader.TLabel",
            ).pack(anchor=tk.W, padx=10)

        name_width = 145
        stat_width = 42
        columns = ["Player", "Pos", "AB", "R", "H", "2B", "3B", "HR", "RBI", "BB", "K"]
        headings = columns

        if not box_score or not box_score.batters:
            num_rows = 1
        else:
            num_rows = len(box_score.batters)
            if box_score.totals_batting:
                num_rows += 1

        frame_height = num_rows * 20 + 10

        tree_frame = tk.Frame(parent_frame, bg=BG_WIDGET, height=frame_height)
        tree_frame.pack(anchor=tk.W, padx=10, pady=2)

        tree = ttk.Treeview(
            tree_frame,
            columns=columns,
            show="headings",
            style="BoxScore.Treeview",
            height=num_rows,
        )

        tree.column("#0", width=0, stretch=False)
        for i, col in enumerate(columns):
            if i == 0:
                tree.column(col, width=name_width, anchor=tk.W)
            elif i == 1:
                tree.column(col, width=50, anchor=tk.CENTER)
            else:
                tree.column(col, width=stat_width, anchor=tk.CENTER)
            tree.heading(col, text=headings[i])

        tree.pack(anchor=tk.W)

        if not box_score:
            tree.insert("", tk.END, values=["No data"] + [""] * len(columns))
            return

        for idx, batter in enumerate(box_score.batters):
            stats = batter.stats
            name = batter.name[:24] if len(batter.name) > 24 else batter.name
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
            totals_values = [
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
            ]
            tree.insert("", tk.END, values=totals_values, tags=("totals",))

        tree.tag_configure("alt", background=BG_WIDGET_ALT)
        tree.tag_configure("totals", background="#2a2a3a", foreground=ACCENT_GOLD)

    def _display_pitching_box_scores_in_section(self, parent_frame, structured_game):
        """Display pitching box scores inside a collapsible section frame."""
        away_bs = structured_game.away_box_score
        home_bs = structured_game.home_box_score

        if not away_bs and not home_bs:
            ttk.Label(
                parent_frame,
                text="  No pitching data available",
                style="PlayItem.TLabel",
            ).pack(anchor=tk.W, padx=10)
            return

        self._display_team_pitching_in_section(
            parent_frame, structured_game.away_team, away_bs
        )
        self._display_team_pitching_in_section(
            parent_frame, structured_game.home_team, home_bs
        )

    def _display_team_pitching_in_section(
        self, parent_frame, team, box_score, show_team_header=True
    ):
        """Display pitching box score for one team inside a section."""
        if show_team_header:
            ttk.Label(
                parent_frame,
                text=f"  {team}",
                style="TeamHeader.TLabel",
            ).pack(anchor=tk.W, padx=10)

        name_width = 145
        stat_width = 36
        columns = ["Pitcher", "IP", "H", "ER", "SO", "BB", "HR", "W", "L", "HLD", "SV"]
        headings = columns

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
            style="BoxScore.Treeview",
            height=num_rows,
        )

        tree.column("#0", width=0, stretch=False)
        for i, col in enumerate(columns):
            if i == 0:
                tree.column(col, width=name_width, anchor=tk.W)
            else:
                tree.column(col, width=stat_width, anchor=tk.CENTER)
            tree.heading(col, text=headings[i])

        tree.pack(anchor=tk.W)

        if not box_score or not box_score.pitchers:
            tree.insert("", tk.END, values=["No data"] + [""] * len(columns))
            return

        for idx, pitcher in enumerate(box_score.pitchers):
            stats = pitcher.stats
            name = pitcher.name[:24] if len(pitcher.name) > 24 else pitcher.name
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

    def _display_pitcher_decisions_in_section(self, parent_frame, structured_game):
        """Display pitcher decisions inside a collapsible section frame."""
        decisions = []
        if structured_game.winning_pitcher:
            decisions.append(f"W: {structured_game.winning_pitcher}")
        if structured_game.losing_pitcher:
            decisions.append(f"L: {structured_game.losing_pitcher}")

        away_bs = structured_game.away_box_score
        home_bs = structured_game.home_box_score

        hld_pitchers = []
        sv_pitchers = []

        for box_score in [away_bs, home_bs]:
            if box_score and box_score.pitchers:
                for pitcher in box_score.pitchers:
                    stats = pitcher.stats
                    if getattr(stats, "Hld", 0) > 0:
                        hld_pitchers.append(pitcher.name)
                    if getattr(stats, "Sv", 0) > 0:
                        sv_pitchers.append(pitcher.name)

        for name in hld_pitchers:
            decisions.append(f"HLD: {name}")
        for name in sv_pitchers:
            decisions.append(f"SV: {name}")

        decision_text = "   ".join(decisions) if decisions else "No decision recorded"

        ttk.Label(
            parent_frame,
            text=f"  {decision_text}",
            style="PitcherDecision.TLabel",
        ).pack(anchor=tk.W, padx=10)

    def _display_play_by_play_in_section(self, parent_frame, structured_game):
        """Display play-by-play inside a collapsible section frame."""
        if not structured_game.innings:
            ttk.Label(
                parent_frame,
                text="  No play-by-play data available",
                style="PlayItem.TLabel",
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
                    style="PlayHeader.TLabel",
                ).pack(anchor=tk.W)

                for play in half_data.plays:
                    if play.play_description:
                        ttk.Label(
                            parent_frame,
                            text=f"    {play.play_description}",
                            style="PlayItem.TLabel",
                        ).pack(anchor=tk.W)

                    # Track runs scored (runs_scored is a list of player names)
                    runs = getattr(play, "runs_scored", []) or []
                    num_runs = len(runs) if isinstance(runs, list) else runs
                    if half == "top":
                        away_runs += num_runs
                    else:
                        home_runs += num_runs

                # Show score at end of half inning
                ttk.Label(
                    parent_frame,
                    text=f"    === {away} {away_runs}, {home} {home_runs} ===",
                    font=("Segoe UI", 9, "bold"),
                    foreground=ACCENT_GOLD,
                ).pack(anchor=tk.W)

    def _display_play_by_play(self, structured_game):
        """Display play-by-play from structured innings data with scores at end of each half inning."""
        self._display_play_by_play_in_section(
            self.scrollable_frame.scrollable_frame, structured_game
        )

    def _display_text_recap(self, away: str, home: str, game_recap: str):
        """Display game recap as plain text (fallback when no structured data)."""
        header_frame = tk.Frame(self.scrollable_frame.scrollable_frame, bg=BG_WIDGET)
        header_frame.pack(fill=tk.X, padx=5, pady=(10, 0))

        ttk.Label(
            header_frame,
            text=f"{away} @ {home}",
            style="GameHeader.TLabel",
        ).pack(anchor=tk.W, padx=10, pady=(10, 5))

        if not game_recap:
            ttk.Label(
                self.scrollable_frame.scrollable_frame,
                text="  No recap available",
                style="PlayItem.TLabel",
            ).pack(anchor=tk.W)
            return

        # Display text with simple formatting
        for line in game_recap.split("\n"):
            if "Scored" in line or "score is" in line or "Final" in line:
                ttk.Label(
                    self.scrollable_frame.scrollable_frame,
                    text=f"  {line}",
                    style="ScoreSummary.TLabel",
                ).pack(anchor=tk.W)
            else:
                ttk.Label(
                    self.scrollable_frame.scrollable_frame,
                    text=f"  {line}",
                    style="PlayItem.TLabel",
                ).pack(anchor=tk.W)

    def get_frame(self) -> tk.Frame:
        """Get the main frame for adding to parent container."""
        return self.frame
