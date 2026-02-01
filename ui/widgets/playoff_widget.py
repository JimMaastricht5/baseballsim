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

        Args:
            play_data: Dict with 'text', 'away_team', 'home_team', etc.
        """
        if not self.ws_active:
            return

        text = play_data.get('text', '')
        if not text:
            return

        # Determine tag based on content
        if 'Inning' in text or 'Top' in text or 'Bottom' in text:
            tag = "inning"
        elif 'Score:' in text or 'Final:' in text:
            tag = "score"
        else:
            tag = "normal"

        # Store play-by-play for current game (game_number is 0-indexed during play, will increment when game completes)
        current_game = self.game_number + 1  # Convert to 1-indexed
        if current_game not in self.game_pbp_data:
            self.game_pbp_data[current_game] = []
        self.game_pbp_data[current_game].append((text, tag))

        # Only display if this is the currently selected game
        if current_game == self.current_game_pbp:
            self.pbp_text.configure(state=tk.NORMAL)
            self.pbp_text.insert(tk.END, text + "\n", tag)
            self.pbp_text.see(tk.END)  # Auto-scroll to bottom
            self.pbp_text.configure(state=tk.DISABLED)

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

        # Update series score
        if away_r > home_r:
            self.series_score[away] = self.series_score.get(away, 0) + 1
        else:
            self.series_score[home] = self.series_score.get(home, 0) + 1

        # Update game selector dropdown with completed games
        game_list = [f"Game {i+1}" for i in range(self.game_number)]
        self.game_selector['values'] = game_list

        # Add to box scores
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

    def world_series_completed(self, ws_data: Dict[str, Any]):
        """
        Handle World Series completion signal.

        Args:
            ws_data: Dict with 'champion', 'season', 'series_result'
        """
        champion = ws_data.get('champion', '')

        # Add championship message to play-by-play
        self.pbp_text.configure(state=tk.NORMAL)
        self.pbp_text.insert(tk.END, "\n" + "=" * 40 + "\n", "header")
        self.pbp_text.insert(tk.END, f"{champion} WINS THE WORLD SERIES!\n", "header")
        self.pbp_text.insert(tk.END, "=" * 40 + "\n", "header")
        self.pbp_text.configure(state=tk.DISABLED)

        # Add to box scores
        self.box_text.configure(state=tk.NORMAL)
        self.box_text.insert(tk.END, "\n" + "=" * 30 + "\n", "header")
        self.box_text.insert(tk.END, f"{champion} - World Series Champion!\n", "header")
        self.box_text.insert(tk.END, "=" * 30 + "\n", "header")
        self.box_text.configure(state=tk.DISABLED)

    def get_frame(self) -> tk.Frame:
        """Return the main frame for packing."""
        return self.frame
