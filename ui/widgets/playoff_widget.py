"""
--- Copyright Notice ---
Copyright (c) 2024 Jim Maastricht

Playoff widget for baseball season simulation UI.

Displays World Series games with play-by-play and box scores.
"""

import tkinter as tk
from tkinter import scrolledtext, ttk
from typing import Dict, Any


class PlayoffWidget:
    """
    Playoff widget showing World Series games with play-by-play and box scores.

    Features:
    - Shows World Series matchup info
    - Real-time play-by-play updates
    - Box scores for completed games
    - Series score tracking
    """

    def __init__(self, parent: tk.Widget):
        """
        Initialize playoff widget.

        Args:
            parent: Parent tkinter widget (notebook or frame)
        """
        self.frame = tk.Frame(parent)
        self.ws_active = False
        self.ws_info = {}
        self.series_score = {}  # Track wins per team
        self.game_number = 0
        self.current_game_pbp = 1  # Currently selected game for play-by-play
        self.game_pbp_data = {}  # Store play-by-play for each game: {game_num: [text_lines]}
        self.completed_games = set()  # Track which games have ended (no more play-by-play)

        # Create header section
        self.header_frame = tk.Frame(self.frame, bg="#1a3d6b", height=60)
        self.header_frame.pack(fill=tk.X, pady=(0, 5))
        self.header_frame.pack_propagate(False)

        self.header_label = tk.Label(
            self.header_frame,
            text="World Series",
            font=("Arial", 16, "bold"),
            bg="#1a3d6b",
            fg="white"
        )
        self.header_label.pack(pady=10)

        # Create paned window for box scores and play-by-play
        paned = tk.PanedWindow(self.frame, orient=tk.HORIZONTAL, sashrelief=tk.RAISED)
        paned.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Left panel: Box scores
        box_frame = tk.Frame(paned)
        paned.add(box_frame, minsize=400)

        box_label = tk.Label(box_frame, text="BOX SCORES", font=("Arial", 11, "bold"),
                            bg="#f8f4e8", anchor=tk.W, padx=5)
        box_label.pack(fill=tk.X, pady=(0, 2))

        self.box_text = scrolledtext.ScrolledText(
            box_frame, wrap=tk.WORD, font=("Courier", 9), state=tk.DISABLED
        )
        self.box_text.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)

        # Configure text tags for box scores
        self.box_text.tag_configure("header", font=("Arial", 11, "bold"), foreground="#1a3d6b")
        self.box_text.tag_configure("game_header", font=("Courier", 10, "bold"), foreground="#2e5090")
        self.box_text.tag_configure("normal", font=("Courier", 9))

        # Right panel: Play-by-play
        pbp_frame = tk.Frame(paned)
        paned.add(pbp_frame, minsize=400)

        # Header with label and game selector
        pbp_header_frame = tk.Frame(pbp_frame, bg="#e8f4f8")
        pbp_header_frame.pack(fill=tk.X, pady=(0, 2))

        pbp_label = tk.Label(pbp_header_frame, text="PLAY-BY-PLAY", font=("Arial", 11, "bold"),
                            bg="#e8f4f8", anchor=tk.W, padx=5)
        pbp_label.pack(side=tk.LEFT)

        # Game selector dropdown
        game_selector_frame = tk.Frame(pbp_header_frame, bg="#e8f4f8")
        game_selector_frame.pack(side=tk.RIGHT, padx=5)

        tk.Label(game_selector_frame, text="Game:", bg="#e8f4f8", font=("Arial", 9)).pack(side=tk.LEFT, padx=(0, 5))

        self.game_selector = ttk.Combobox(game_selector_frame, width=8, state='readonly')
        self.game_selector['values'] = ['Game 1']
        self.game_selector.current(0)
        self.game_selector.bind('<<ComboboxSelected>>', self._on_game_selected)
        self.game_selector.pack(side=tk.LEFT)

        self.pbp_text = scrolledtext.ScrolledText(
            pbp_frame, wrap=tk.WORD, font=("Courier", 9), state=tk.DISABLED
        )
        self.pbp_text.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)

        # Configure text tags for play-by-play
        self.pbp_text.tag_configure("header", font=("Arial", 11, "bold"), foreground="#1a3d6b")
        self.pbp_text.tag_configure("inning", font=("Courier", 9, "bold"), foreground="#2e5090")
        self.pbp_text.tag_configure("normal", font=("Courier", 9))
        self.pbp_text.tag_configure("score", font=("Courier", 9, "bold"), foreground="#c8102e")

        # Show initial message
        self._show_waiting_message()

    def _show_waiting_message(self):
        """Display message when waiting for World Series to start."""
        self.pbp_text.configure(state=tk.NORMAL)
        self.pbp_text.delete(1.0, tk.END)
        self.pbp_text.insert(tk.END, "\n\n")
        self.pbp_text.insert(tk.END, "    Waiting for World Series to begin...\n\n", "header")
        self.pbp_text.insert(tk.END, "    Complete the regular season to unlock playoff games.", "normal")
        self.pbp_text.configure(state=tk.DISABLED)

    def _on_game_selected(self, event):
        """Handle game selection from dropdown."""
        selected = self.game_selector.get()
        if selected and selected.startswith('Game '):
            game_num = int(selected.split()[1])
            self.current_game_pbp = game_num
            self._display_game_pbp(game_num)

    def _display_game_pbp(self, game_num: int):
        """Display play-by-play for the selected game."""
        self.pbp_text.configure(state=tk.NORMAL)
        self.pbp_text.delete(1.0, tk.END)

        # Show game header
        if self.ws_active and self.ws_info:
            al = self.ws_info.get('al_winner', '')
            nl = self.ws_info.get('nl_winner', '')
            self.pbp_text.insert(tk.END, f"Game {game_num}: {al} vs {nl}\n", "header")
            self.pbp_text.insert(tk.END, "-" * 40 + "\n\n", "normal")

        # Display stored play-by-play for this game
        if game_num in self.game_pbp_data:
            for text, tag in self.game_pbp_data[game_num]:
                self.pbp_text.insert(tk.END, text + "\n", tag)
        else:
            self.pbp_text.insert(tk.END, "No play-by-play data for this game yet.\n", "normal")

        self.pbp_text.configure(state=tk.DISABLED)

    def world_series_started(self, ws_data: Dict[str, Any]):
        """
        Handle World Series start signal.

        Args:
            ws_data: Dict with 'al_winner', 'nl_winner', 'season', 'al_record', 'nl_record'
        """
        self.ws_active = True
        self.ws_info = ws_data
        self.series_score = {ws_data['al_winner']: 0, ws_data['nl_winner']: 0}
        self.game_number = 0
        self.current_game_pbp = 1
        self.game_pbp_data = {}  # Reset play-by-play storage

        # Update header
        al = ws_data['al_winner']
        nl = ws_data['nl_winner']
        self.header_label.config(
            text=f"{ws_data['season']} World Series: {al} vs {nl}"
        )

        # Initialize game selector with Game 1
        self.game_selector['values'] = ['Game 1']
        self.game_selector.current(0)

        # Display initial play-by-play for Game 1
        self._display_game_pbp(1)

        # Clear box scores
        self.box_text.configure(state=tk.NORMAL)
        self.box_text.delete(1.0, tk.END)
        self.box_text.insert(tk.END, f"{ws_data['season']} World Series Box Scores\n\n", "header")
        self.box_text.configure(state=tk.DISABLED)

    def add_play_by_play(self, play_data: Dict[str, Any]):
        """
        Add play-by-play text to the display.

        For World Series games, we now display everything at once when the game completes,
        so this method just tracks which game is active.

        Args:
            play_data: Dict with 'text', 'away_team', 'home_team', 'ws_game_num', etc.
        """
        from bblogger import logger
        logger.debug(f"Playoff widget add_play_by_play called: ws_active={self.ws_active}")

        if not self.ws_active:
            logger.debug("World Series not active, returning")
            return

        # Get the game number from play_data
        ws_game_num = play_data.get('ws_game_num')
        if ws_game_num is None:
            return

        # Auto-select new games when they start
        if ws_game_num not in self.game_pbp_data:
            self.game_pbp_data[ws_game_num] = []
            # New game detected - update dropdown and auto-select it
            game_list = [f"Game {i}" for i in range(1, ws_game_num + 1)]
            self.game_selector['values'] = game_list
            self.game_selector.current(ws_game_num - 1)  # Select the new game (0-indexed)
            self.current_game_pbp = ws_game_num
            # Clear the play-by-play display for the new game
            self.pbp_text.configure(state=tk.NORMAL)
            self.pbp_text.delete(1.0, tk.END)
            self.pbp_text.insert(tk.END, "Game in progress...\n", "normal")
            self.pbp_text.configure(state=tk.DISABLED)
            logger.info(f"Auto-selected Game {ws_game_num} in dropdown")

        # Don't display play-by-play incrementally - we'll show everything at once when game completes

    def add_game_result(self, game_data: Dict[str, Any]):
        """
        Add a completed game's box score to the display.

        Args:
            game_data: Dict with game results and box score info
        """
        if not self.ws_active:
            return

        self.game_number += 1
        away = game_data.get('away_team', '')
        home = game_data.get('home_team', '')
        away_r = game_data.get('away_r', 0)
        home_r = game_data.get('home_r', 0)
        away_h = game_data.get('away_h', 0)
        home_h = game_data.get('home_h', 0)
        away_e = game_data.get('away_e', 0)
        home_e = game_data.get('home_e', 0)
        game_recap = game_data.get('game_recap', '')

        # Update series score
        if away_r > home_r:
            self.series_score[away] = self.series_score.get(away, 0) + 1
        else:
            self.series_score[home] = self.series_score.get(home, 0) + 1

        # Update game selector dropdown with completed games
        game_list = [f"Game {i+1}" for i in range(self.game_number)]
        self.game_selector['values'] = game_list

        # Add final box score to play-by-play for this game
        self._add_final_box_score_to_pbp(self.game_number, away, home, away_r, home_r,
                                          away_h, home_h, away_e, home_e, game_recap)

        # Add to box scores panel
        self.box_text.configure(state=tk.NORMAL)
        self.box_text.insert(tk.END, f"\nGame {self.game_number}\n", "game_header")
        self.box_text.insert(tk.END, f"{'Team':<6} {'R':>3} {'H':>3} {'E':>3}\n", "normal")
        self.box_text.insert(tk.END, f"{away:<6} {away_r:>3} {away_h:>3} {away_e:>3}\n", "normal")
        self.box_text.insert(tk.END, f"{home:<6} {home_r:>3} {home_h:>3} {home_e:>3}\n", "normal")

        # Show series score
        teams = list(self.series_score.keys())
        if len(teams) == 2:
            self.box_text.insert(tk.END,
                f"\nSeries: {teams[0]} {self.series_score[teams[0]]}, "
                f"{teams[1]} {self.series_score[teams[1]]}\n", "game_header")

        self.box_text.insert(tk.END, "-" * 30 + "\n", "normal")
        self.box_text.configure(state=tk.DISABLED)

    def _add_final_box_score_to_pbp(self, game_num: int, away: str, home: str,
                                      away_r: int, home_r: int, away_h: int, home_h: int,
                                      away_e: int, home_e: int, game_recap: str):
        """
        Display complete game recap (lineups + play-by-play + box scores) all at once.

        Args:
            game_num: Game number (1-7)
            away/home: Team abbreviations
            away_r/home_r: Runs scored
            away_h/home_h: Hits
            away_e/home_e: Errors
            game_recap: Full game text (contains everything)
        """
        from bblogger import logger

        # Mark this game as completed
        self.completed_games.add(game_num)

        # Ensure game_pbp_data entry exists for this game
        if game_num not in self.game_pbp_data:
            self.game_pbp_data[game_num] = []

        # Parse game_recap into sections: lineups, play-by-play, box scores
        sections = self._parse_game_recap(game_recap)

        # Clear any existing data for this game
        self.game_pbp_data[game_num] = []

        # Add all sections to game_pbp_data
        for text, tag in sections:
            self.game_pbp_data[game_num].append((text, tag))

        logger.info(f"Game {game_num} complete: added {len(sections)} sections to display")

        # If this is the currently displayed game, update the display
        if game_num == self.current_game_pbp:
            self._display_game_pbp(game_num)

    def _parse_game_recap(self, game_recap: str) -> list:
        """
        Parse game recap into sections for display.

        Args:
            game_recap: Full game text with lineups, play-by-play, and box scores

        Returns:
            List of (text, tag) tuples for display
        """
        if not game_recap:
            return [("No game data available.\n", "normal")]

        sections = []
        lines = game_recap.split('\n')

        # Find key section boundaries
        lineup_start = -1
        lineup_end = -1
        box_score_start = -1

        for i, line in enumerate(lines):
            if lineup_start == -1 and ('Starting lineup' in line or 'Lineup Card' in line):
                lineup_start = i
            elif lineup_start != -1 and lineup_end == -1 and ('Inning 1' in line or 'Top of the 1st' in line):
                lineup_end = i
            elif 'Player' in line and 'Team' in line and ('Pos' in line or 'Age' in line):
                box_score_start = i
                break

        # Extract lineups
        if lineup_start != -1 and lineup_end != -1:
            lineup_text = '\n'.join(lines[lineup_start:lineup_end])
            if lineup_text.strip():
                sections.append(("=" * 80 + "\n" + lineup_text + "\n" + "=" * 80 + "\n\n", "normal"))

        # Extract play-by-play (everything between lineups and box scores)
        pbp_start = lineup_end if lineup_end != -1 else 0
        pbp_end = box_score_start if box_score_start != -1 else len(lines)

        if pbp_start < pbp_end:
            pbp_text = '\n'.join(lines[pbp_start:pbp_end])
            if pbp_text.strip():
                sections.append((pbp_text + "\n", "normal"))

        # Extract box scores
        if box_score_start != -1:
            box_text = '\n'.join(lines[box_score_start:])
            if box_text.strip():
                sections.append(("\n" + "=" * 80 + "\n" + "FINAL BOX SCORE\n" + "=" * 80 + "\n" + box_text + "\n" + "=" * 80 + "\n", "normal"))

        return sections if sections else [("No game data available.\n", "normal")]

    def world_series_completed(self, ws_data: Dict[str, Any]):
        """
        Handle World Series completion signal.

        Args:
            ws_data: Dict with 'champion', 'season', 'series_result'
        """
        champion = ws_data.get('champion', '')

        # Championship message removed from play-by-play per user request

        # Add to box scores
        self.box_text.configure(state=tk.NORMAL)
        self.box_text.insert(tk.END, "\n" + "=" * 30 + "\n", "header")
        self.box_text.insert(tk.END, f"{champion} - World Series Champion!\n", "header")
        self.box_text.insert(tk.END, "=" * 30 + "\n", "header")
        self.box_text.configure(state=tk.DISABLED)

    def get_frame(self) -> tk.Frame:
        """Return the main frame for packing."""
        return self.frame
