"""
--- Copyright Notice ---
Copyright (c) 2024 Jim Maastricht

Main window for the baseball season simulation UI using tkinter.

Provides the primary interface with toolbar controls, standings display,
game results, and tabs for schedule and injuries.
"""

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import queue
import pandas as pd

from ui.season_worker import SeasonWorker
import bbgame
from bblogger import logger


class SeasonMainWindow:
    """
    Main application window for season simulation using tkinter.

    Layout:
    - Title bar with window title
    - Toolbar frame with control buttons (Start, Pause, Resume, Next Day, Stop)
    - Horizontal paned window:
      - Left (30%): Standings display (Text widget)
      - Right (70%): Notebook with Today's Games, Schedule, Injuries tabs
    - Status bar frame with day counter and simulation status
    """

    def __init__(self, root, load_seasons, new_season, season_length, series_length,
                 rotation_len, season_chatty, season_print_lineup_b, season_print_box_score_b,
                 season_team_to_follow):
        """
        Initialize the main window and UI components.

        Args:
            root (tk.Tk): The root tkinter window
        """
        self.root = root
        self.load_seasons = load_seasons
        self.new_season = new_season
        self.season_length = season_length
        self.series_length = series_length
        self.rotation_len = rotation_len
        self.season_chatty = season_chatty
        self.season_print_lineup_b = season_print_lineup_b
        self.season_print_box_score_b = season_print_box_score_b
        self.season_team_to_follow = season_team_to_follow or 'MIL'  # Single string, defaults to 'MIL'
        self.root.title("Baseball Season Simulator")
        self.root.geometry("1500x900")

        # Season worker (created when simulation starts)
        self.worker = None

        # Track games for progressive display
        self.current_day_schedule = []  # List of (away_team, home_tuple) tuples
        self.current_day_results = {}   # Dict: {(away, home): game_data}
        self.followed_game_recaps = []  # List of (away, home, recap_text) for followed games
        self.previous_day_results = {}  # Dict: {(away, home): game_data} from previous day
        self.current_day_num = 0  # Track current day number for header

        # Setup UI components
        self._create_toolbar()
        self._create_main_content()
        self._create_status_bar()

        # Initial button states
        self._update_button_states(simulation_running=False, paused=False)

        # Start queue polling
        self._poll_queues()

        logger.info("Main window initialized")

    def _create_toolbar(self):
        """Create toolbar frame with control buttons."""
        toolbar = tk.Frame(self.root, relief=tk.RAISED, bd=2)
        toolbar.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)

        # Team selection label and dropdown
        tk.Label(toolbar, text="Team to Follow:", font=("Arial", 10, "bold")).pack(side=tk.LEFT, padx=5)
        self.team_var = tk.StringVar(value=self.season_team_to_follow)
        self.team_combo = ttk.Combobox(
            toolbar,
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
        ttk.Separator(toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=10)

        # Start button
        self.start_btn = tk.Button(
            toolbar, text="Start Season", command=self.start_season,
            width=12, bg="green", fg="white", font=("Arial", 10, "bold")
        )
        self.start_btn.pack(side=tk.LEFT, padx=5)

        # Separator
        ttk.Separator(toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=10)

        # Pause button
        self.pause_btn = tk.Button(
            toolbar, text="Pause", command=self.pause_season,
            width=10, font=("Arial", 10)
        )
        self.pause_btn.pack(side=tk.LEFT, padx=5)

        # Resume button
        self.resume_btn = tk.Button(
            toolbar, text="Resume", command=self.resume_season,
            width=10, font=("Arial", 10)
        )
        self.resume_btn.pack(side=tk.LEFT, padx=5)

        # Next Day button
        self.next_day_btn = tk.Button(
            toolbar, text="Next Day", command=self.next_day,
            width=10, font=("Arial", 10)
        )
        self.next_day_btn.pack(side=tk.LEFT, padx=5)

        # Next Series button (3 days)
        self.next_series_btn = tk.Button(
            toolbar, text="Next Series", command=self.next_series,
            width=10, font=("Arial", 10)
        )
        self.next_series_btn.pack(side=tk.LEFT, padx=5)

        # Next Week button (7 days)
        self.next_week_btn = tk.Button(
            toolbar, text="Next Week", command=self.next_week,
            width=10, font=("Arial", 10)
        )
        self.next_week_btn.pack(side=tk.LEFT, padx=5)

    def _create_main_content(self):
        """Create the main layout with paned window, standings, and tabs."""
        # Horizontal paned window for standings (left) and content (right)
        paned_window = tk.PanedWindow(self.root, orient=tk.HORIZONTAL, sashrelief=tk.RAISED)
        paned_window.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Left panel: Standings with separate AL and NL Treeviews
        standings_frame = tk.Frame(paned_window, relief=tk.SUNKEN, bd=1)
        standings_label = tk.Label(standings_frame, text="STANDINGS", font=("Arial", 12, "bold"))
        standings_label.pack(pady=5)

        # AL Standings
        al_label = tk.Label(standings_frame, text="AMERICAN LEAGUE", font=("Arial", 10, "bold"))
        al_label.pack(pady=(5, 2))

        al_tree_frame = tk.Frame(standings_frame)
        al_tree_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=2)

        al_scrollbar = ttk.Scrollbar(al_tree_frame, orient=tk.VERTICAL)
        al_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.al_standings_tree = ttk.Treeview(
            al_tree_frame,
            columns=("team", "wl", "pct", "gb"),
            show="headings",
            height=15,
            yscrollcommand=al_scrollbar.set
        )
        al_scrollbar.config(command=self.al_standings_tree.yview)

        # Define column headings
        self.al_standings_tree.heading("team", text="Team", command=lambda: self._sort_standings("team", "al"))
        self.al_standings_tree.heading("wl", text="W-L", command=lambda: self._sort_standings("wl", "al"))
        self.al_standings_tree.heading("pct", text="Pct", command=lambda: self._sort_standings("pct", "al"))
        self.al_standings_tree.heading("gb", text="GB", command=lambda: self._sort_standings("gb", "al"))

        # Configure column widths
        self.al_standings_tree.column("team", width=60, anchor=tk.CENTER)
        self.al_standings_tree.column("wl", width=80, anchor=tk.CENTER)
        self.al_standings_tree.column("pct", width=60, anchor=tk.CENTER)
        self.al_standings_tree.column("gb", width=50, anchor=tk.CENTER)

        # Add tag for followed teams
        self.al_standings_tree.tag_configure("followed", background="#e6f3ff", font=("Arial", 10, "bold"))
        self.al_standings_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # NL Standings
        nl_label = tk.Label(standings_frame, text="NATIONAL LEAGUE", font=("Arial", 10, "bold"))
        nl_label.pack(pady=(10, 2))

        nl_tree_frame = tk.Frame(standings_frame)
        nl_tree_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=2)

        nl_scrollbar = ttk.Scrollbar(nl_tree_frame, orient=tk.VERTICAL)
        nl_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.nl_standings_tree = ttk.Treeview(
            nl_tree_frame,
            columns=("team", "wl", "pct", "gb"),
            show="headings",
            height=15,
            yscrollcommand=nl_scrollbar.set
        )
        nl_scrollbar.config(command=self.nl_standings_tree.yview)

        # Define column headings
        self.nl_standings_tree.heading("team", text="Team", command=lambda: self._sort_standings("team", "nl"))
        self.nl_standings_tree.heading("wl", text="W-L", command=lambda: self._sort_standings("wl", "nl"))
        self.nl_standings_tree.heading("pct", text="Pct", command=lambda: self._sort_standings("pct", "nl"))
        self.nl_standings_tree.heading("gb", text="GB", command=lambda: self._sort_standings("gb", "nl"))

        # Configure column widths
        self.nl_standings_tree.column("team", width=60, anchor=tk.CENTER)
        self.nl_standings_tree.column("wl", width=80, anchor=tk.CENTER)
        self.nl_standings_tree.column("pct", width=60, anchor=tk.CENTER)
        self.nl_standings_tree.column("gb", width=50, anchor=tk.CENTER)

        # Add tag for followed teams
        self.nl_standings_tree.tag_configure("followed", background="#e6f3ff", font=("Arial", 10, "bold"))
        self.nl_standings_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Store current standings data for sorting
        self.standings_data_cache = None
        self.standings_sort_column = "gb"  # Default sort by win percentage
        self.standings_sort_reverse = True  # Descending by default
        self.standings_sort_league = None  # Track which league is being sorted

        paned_window.add(standings_frame, minsize=300)

        # Right panel: Notebook with tabs
        notebook_frame = tk.Frame(paned_window)
        self.notebook = ttk.Notebook(notebook_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        # Tab 1: Today's Games
        games_frame = tk.Frame(self.notebook)
        self.games_text = scrolledtext.ScrolledText(
            games_frame, wrap=tk.WORD, font=("Courier", 9), state=tk.DISABLED
        )

        # Configure text tags for formatting
        self.games_text.tag_configure("header", font=("Arial", 12, "bold"), foreground="#2e5090")
        self.games_text.tag_configure("day_header", font=("Arial", 12, "bold"), foreground="#1a3d6b", spacing3=10)
        self.games_text.tag_configure("followed_game", background="#ffffcc", spacing1=5, spacing3=5)
        self.games_text.tag_configure("separator", foreground="#888888")

        self.games_text.pack(fill=tk.BOTH, expand=True)
        self.notebook.add(games_frame, text="Today's Games")

        # Tab 2: Schedule (ScrolledText for upcoming games with wrapping)
        schedule_frame = tk.Frame(self.notebook)

        # Header
        schedule_header = tk.Label(
            schedule_frame, text="Upcoming Games (Next 14 Days)",
            font=("Arial", 11, "bold"), pady=5
        )
        schedule_header.pack()

        # Create ScrolledText for schedule (supports text wrapping)
        self.schedule_text = scrolledtext.ScrolledText(
            schedule_frame,
            wrap=tk.WORD,
            font=("Courier", 9),
            state=tk.DISABLED,
            padx=10,
            pady=5
        )

        # Configure text tags for formatting
        self.schedule_text.tag_configure("day_header", font=("Arial", 12, "bold"), foreground="#1a3d6b", spacing1=5, spacing3=3)
        self.schedule_text.tag_configure("current_day", background="#ffeecc", font=("Arial", 12, "bold"), foreground="#1a3d6b", spacing1=5, spacing3=3)
        self.schedule_text.tag_configure("matchup", font=("Courier", 9), lmargin1=20, lmargin2=20)

        self.schedule_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.notebook.add(schedule_frame, text="Schedule")

        # Tab 3: League IL (Treeview for sortable injury list)
        injuries_frame = tk.Frame(self.notebook)

        # Header with injury count
        injuries_header_frame = tk.Frame(injuries_frame)
        injuries_header_frame.pack(fill=tk.X, pady=5)

        self.injuries_header_label = tk.Label(
            injuries_header_frame, text="League IL Report",
            font=("Arial", 11, "bold")
        )
        self.injuries_header_label.pack()

        # Control frame with team filter dropdown
        injuries_control_frame = tk.Frame(injuries_frame)
        injuries_control_frame.pack(fill=tk.X, padx=10, pady=5)

        tk.Label(injuries_control_frame, text="Team:", font=("Arial", 10, "bold")).pack(side=tk.LEFT, padx=5)
        self.injuries_team_var = tk.StringVar(value="All Teams")
        self.injuries_team_combo = ttk.Combobox(
            injuries_control_frame,
            textvariable=self.injuries_team_var,
            width=15,
            state="readonly"
        )
        self.injuries_team_combo['values'] = ['All Teams']  # Populated when simulation starts
        self.injuries_team_combo.bind('<<ComboboxSelected>>', self._on_injuries_team_changed)
        self.injuries_team_combo.pack(side=tk.LEFT, padx=5)

        # Create Treeview for injuries
        injuries_tree_frame = tk.Frame(injuries_frame)
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

        # Store injury data for sorting
        self.injuries_data_cache = []
        self.injuries_sort_column = "status"  # Default sort by status
        self.injuries_sort_reverse = False  # Ascending

        self.notebook.add(injuries_frame, text="League IL")

        # Tab 4: Team Tab with nested sub-tabs
        team_tab_frame = tk.Frame(self.notebook)
        self.notebook.add(team_tab_frame, text=self.season_team_to_follow)

        # Create inner notebook for team sub-tabs
        self.team_notebook = ttk.Notebook(team_tab_frame)
        self.team_notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Sub-tab 1: Roster (NEW)
        roster_frame = self._create_roster_subtab(self.team_notebook)
        self.team_notebook.add(roster_frame, text="Roster")

        # Sub-tab 2: Games Played (MOVED and RENAMED from Play-by-Play)
        games_played_frame = self._create_games_played_subtab(self.team_notebook)
        self.team_notebook.add(games_played_frame, text="Games Played")

        # Sub-tab 3: GM Assessment (MOVED from old tab 4)
        gm_frame = self._create_gm_assessment_subtab(self.team_notebook)
        self.team_notebook.add(gm_frame, text="GM Assessment")

        # Tab 5: Admin (Player Management)
        admin_frame = tk.Frame(self.notebook)

        # Header with instructions
        admin_header = tk.Label(
            admin_frame,
            text="Player Management - Move players between teams",
            font=("Arial", 11, "bold"),
            pady=5
        )
        admin_header.pack()

        # Search frame
        search_frame = tk.Frame(admin_frame)
        search_frame.pack(fill=tk.X, padx=10, pady=5)

        tk.Label(search_frame, text="Search:", font=("Arial", 10)).pack(side=tk.LEFT, padx=5)
        self.admin_search_var = tk.StringVar()
        self.admin_search_var.trace('w', lambda *args: self._filter_admin_players())
        search_entry = tk.Entry(search_frame, textvariable=self.admin_search_var, width=30, font=("Arial", 10))
        search_entry.pack(side=tk.LEFT, padx=5)

        tk.Label(search_frame, text="Team Filter:", font=("Arial", 10)).pack(side=tk.LEFT, padx=15)
        self.admin_team_filter_var = tk.StringVar(value="All Teams")
        self.admin_team_filter_var.trace('w', lambda *args: self._filter_admin_players())
        team_filter_combo = ttk.Combobox(
            search_frame,
            textvariable=self.admin_team_filter_var,
            width=15,
            state="readonly"
        )
        team_filter_combo['values'] = ['All Teams']  # Will be populated when worker starts
        team_filter_combo.pack(side=tk.LEFT, padx=5)
        self.admin_team_filter_combo = team_filter_combo

        # Player list frame with treeview
        list_frame = tk.Frame(admin_frame)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # Scrollbars for treeview
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

        # Store full player list for filtering
        self.admin_all_players = []

        # Action frame
        action_frame = tk.Frame(admin_frame)
        action_frame.pack(fill=tk.X, padx=10, pady=10)

        tk.Label(action_frame, text="Move selected player to:", font=("Arial", 10, "bold")).pack(side=tk.LEFT, padx=5)
        self.admin_dest_team_var = tk.StringVar()
        dest_team_combo = ttk.Combobox(
            action_frame,
            textvariable=self.admin_dest_team_var,
            width=15,
            state="readonly"
        )
        dest_team_combo['values'] = []  # Will be populated when worker starts
        dest_team_combo.pack(side=tk.LEFT, padx=5)
        self.admin_dest_team_combo = dest_team_combo

        move_btn = tk.Button(
            action_frame,
            text="Move Player",
            command=self._admin_move_player,
            bg="#4CAF50",
            fg="white",
            font=("Arial", 10, "bold"),
            width=15
        )
        move_btn.pack(side=tk.LEFT, padx=20)

        save_btn = tk.Button(
            action_frame,
            text="Save Changes to CSV",
            command=self._admin_save_changes,
            bg="#2196F3",
            fg="white",
            font=("Arial", 10, "bold"),
            width=20
        )
        save_btn.pack(side=tk.LEFT, padx=10)

        # Status message
        self.admin_status_label = tk.Label(
            admin_frame,
            text="Ready. Select a player and destination team, then click 'Move Player'.",
            font=("Arial", 9),
            fg="#666666",
            anchor=tk.W
        )
        self.admin_status_label.pack(fill=tk.X, padx=10, pady=5)

        self.notebook.add(admin_frame, text="Admin")

        # Storage for play-by-play data by day (used by team sub-tab)
        self.pbp_by_day = {}  # Dict: {day_num: [(away, home, game_recap), ...]}

        paned_window.add(notebook_frame, minsize=600)

        # Set initial sash position (30% for standings, 70% for content)
        self.root.update_idletasks()
        paned_window.sash_place(0, 360, 1)

    def _create_roster_subtab(self, parent):
        """Create Roster sub-tab with position players and pitchers."""
        frame = tk.Frame(parent)

        # Create notebook for Roster sub-sections
        roster_notebook = ttk.Notebook(frame)
        roster_notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Sub-section 1: Position Players (combined lineup and bench)
        pos_players_frame = tk.Frame(roster_notebook)
        roster_notebook.add(pos_players_frame, text="Pos Players")
        self.pos_players_tree = self._create_roster_treeview(pos_players_frame, is_batter=True)

        # Sub-section 2: Pitchers
        pitchers_frame = tk.Frame(roster_notebook)
        roster_notebook.add(pitchers_frame, text="Pitchers")
        self.pitchers_tree = self._create_roster_treeview(pitchers_frame, is_batter=False)

        return frame

    def _create_roster_treeview(self, parent, is_batter=True):
        """Create Treeview for roster data."""
        if is_batter:
            columns = ("Player", "Pos", "AB", "R", "H", "2B", "3B", "HR", "RBI", "BB", "K", "AVG", "OBP", "SLG", "OPS", "Condition", "Status")
        else:
            columns = ("Player", "G", "GS", "W", "L", "IP", "H", "R", "ER", "HR", "BB", "SO", "ERA", "WHIP", "SV", "Condition", "Status")

        tree = ttk.Treeview(parent, columns=columns, show="headings", height=15)

        # Configure columns
        for col in columns:
            tree.heading(col, text=col)
            if col == "Player":
                tree.column(col, width=150, anchor=tk.W)
            elif col in ["Pos", "Status"]:
                tree.column(col, width=70, anchor=tk.CENTER)
            elif col in ["AB", "R", "H", "2B", "3B", "HR", "RBI", "BB", "K", "G", "GS", "W", "L", "ER", "SV", "SO", "Condition"]:
                tree.column(col, width=45, anchor=tk.CENTER)
            elif col in ["AVG", "OBP", "SLG", "OPS", "ERA", "WHIP"]:
                tree.column(col, width=55, anchor=tk.CENTER)
            elif col == "IP":
                tree.column(col, width=50, anchor=tk.CENTER)
            else:
                tree.column(col, width=50, anchor=tk.CENTER)

        # Add scrollbar
        scrollbar = ttk.Scrollbar(parent, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        tree.pack(fill=tk.BOTH, expand=True)

        # Configure tags for injury highlighting
        tree.tag_configure("day_to_day", background="#fff4cc")  # Yellow for day-to-day (<10 days)
        tree.tag_configure("injured", background="#ffcccc")  # Red for IL (>=10 days)

        return tree

    def _create_gm_assessment_subtab(self, parent):
        """Create GM Assessment sub-tab (moved from standalone tab)."""
        frame = tk.Frame(parent)

        # Header
        gm_header_frame = tk.Frame(frame)
        gm_header_frame.pack(fill=tk.X, pady=5)

        self.gm_header_label = tk.Label(
            gm_header_frame, text="No GM Assessment Yet",
            font=("Arial", 11, "bold")
        )
        self.gm_header_label.pack()

        # ScrolledText for assessment history
        self.gm_text = scrolledtext.ScrolledText(
            frame, wrap=tk.WORD, font=("Courier", 9), state=tk.DISABLED
        )

        # Configure text tags for formatting
        self.gm_text.tag_configure("header", font=("Courier", 11, "bold"), foreground="#0044cc")
        self.gm_text.tag_configure("section", font=("Courier", 10, "bold"), underline=True)
        self.gm_text.tag_configure("value", foreground="#006600")
        self.gm_text.tag_configure("warning", foreground="#cc6600")
        self.gm_text.tag_configure("separator", foreground="#888888")

        self.gm_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        return frame

    def _create_games_played_subtab(self, parent):
        """Create Games Played sub-tab (moved from Play-by-Play tab)."""
        frame = tk.Frame(parent)

        # Control frame with day dropdown
        pbp_control_frame = tk.Frame(frame)
        pbp_control_frame.pack(fill=tk.X, padx=10, pady=5)

        tk.Label(pbp_control_frame, text="Day:", font=("Arial", 10, "bold")).pack(side=tk.LEFT, padx=5)
        self.pbp_day_var = tk.StringVar(value="Select Day")
        self.pbp_day_combo = ttk.Combobox(
            pbp_control_frame,
            textvariable=self.pbp_day_var,
            width=15,
            state="readonly"
        )
        self.pbp_day_combo['values'] = ['Select Day']  # Populated as days complete
        self.pbp_day_combo.bind('<<ComboboxSelected>>', self._on_pbp_day_changed)
        self.pbp_day_combo.pack(side=tk.LEFT, padx=5)

        # Info label
        self.pbp_info_label = tk.Label(
            pbp_control_frame,
            text="Select a day to view play-by-play for followed games",
            font=("Arial", 9),
            fg="#666666"
        )
        self.pbp_info_label.pack(side=tk.LEFT, padx=20)

        # ScrolledText for play-by-play
        self.pbp_text = scrolledtext.ScrolledText(
            frame, wrap=tk.WORD, font=("Courier", 9), state=tk.DISABLED
        )

        # Configure text tags for formatting
        self.pbp_text.tag_configure("game_header", font=("Arial", 11, "bold"),
                                   foreground="#1a3d6b", spacing1=10, spacing3=5)
        self.pbp_text.tag_configure("play", font=("Courier", 9))
        self.pbp_text.tag_configure("score_update", font=("Courier", 9, "bold"),
                                   foreground="#006600")

        self.pbp_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        return frame

    def on_roster_update(self):
        """Fetch and display roster data for followed team."""
        if not self.worker or not self.worker.season:
            logger.debug("Roster update skipped - no worker or season available")
            return

        try:
            team = self.season_team_to_follow
            baseball_data = self.worker.season.baseball_data

            # Get batting data (current season)
            batting_df = baseball_data.get_batting_data(team, prior_season=False)

            # Get pitching data (current season)
            pitching_df = baseball_data.get_pitching_data(team, prior_season=False)

            # Sort batters by PA if column exists, otherwise use AB, then G
            # Try PA first, fall back to AB, then G (games)
            if 'PA' in batting_df.columns and batting_df['PA'].sum() > 0:
                sorted_batters = batting_df.sort_values('PA', ascending=False)
            elif 'AB' in batting_df.columns and batting_df['AB'].sum() > 0:
                sorted_batters = batting_df.sort_values('AB', ascending=False)
            elif 'G' in batting_df.columns and batting_df['G'].sum() > 0:
                sorted_batters = batting_df.sort_values('G', ascending=False)
            else:
                # No stats yet, just use as-is
                sorted_batters = batting_df

            # Update position players tree (all batters combined)
            self._update_roster_tree(self.pos_players_tree, sorted_batters, is_batter=True)

            # Sort pitchers by IP (innings pitched)
            # NOTE: Display ALL pitchers on team roster, including those with 0 IP
            if 'IP' in pitching_df.columns and pitching_df['IP'].sum() > 0:
                # Sort by IP descending (pitchers with 0 IP will appear at bottom)
                sorted_pitchers = pitching_df.sort_values('IP', ascending=False)
            else:
                # No IP stats yet, sort by player name for consistency
                sorted_pitchers = pitching_df.sort_values('Player') if 'Player' in pitching_df.columns else pitching_df

            # Update pitchers tree (includes all team pitchers regardless of IP)
            self._update_roster_tree(self.pitchers_tree, sorted_pitchers, is_batter=False)

            logger.info(f"Roster updated for {team}: {len(batting_df)} batters, {len(pitching_df)} pitchers")

        except Exception as e:
            logger.error(f"Error updating roster: {e}")
            import traceback
            logger.error(traceback.format_exc())

    @staticmethod
    def _condition_to_text(condition):
        """Convert numeric condition (0-100) to descriptive text."""
        if condition >= 95:
            return "Excellent"
        elif condition >= 85:
            return "Good"
        elif condition >= 70:
            return "Fair"
        elif condition >= 50:
            return "Tired"
        else:
            return "Fatigued"

    def _update_roster_tree(self, tree, data_df, is_batter=True):
        """Update roster Treeview with data."""
        # Clear existing
        for item in tree.get_children():
            tree.delete(item)

        # Handle empty DataFrame
        if data_df.empty:
            logger.debug(f"Empty roster data for {'batter' if is_batter else 'pitcher'}")
            return

        # Insert rows
        for idx, row in data_df.iterrows():
            try:
                # Determine injury days and condition display
                injured_days = int(row.get('Injured Days', 0))
                if injured_days > 0:
                    condition_display = "Injured"
                else:
                    condition_display = self._condition_to_text(int(row.get('Condition', 100)))

                if is_batter:
                    # Clean up position formatting (remove brackets and quotes)
                    pos = row.get('Pos', 'Unknown')
                    if isinstance(pos, list):
                        pos = pos[0] if pos else 'Unknown'
                    # Convert to string and remove all brackets, quotes, and spaces
                    pos = str(pos).replace('[', '').replace(']', '').replace("'", '').replace('"', '').strip()

                    values = (
                        row.get('Player', 'Unknown'),
                        pos,
                        int(row.get('AB', 0)),
                        int(row.get('R', 0)),
                        int(row.get('H', 0)),
                        int(row.get('2B', 0)),
                        int(row.get('3B', 0)),
                        int(row.get('HR', 0)),
                        int(row.get('RBI', 0)),
                        int(row.get('BB', 0)),
                        int(row.get('SO', 0)),
                        f"{float(row.get('AVG', 0)):.3f}",
                        f"{float(row.get('OBP', 0)):.3f}",
                        f"{float(row.get('SLG', 0)):.3f}",
                        f"{float(row.get('OPS', 0)):.3f}",
                        condition_display,
                        row.get('Status', 'Healthy')
                    )
                else:
                    values = (
                        row.get('Player', 'Unknown'),
                        int(row.get('G', 0)),
                        int(row.get('GS', 0)),
                        int(row.get('W', 0)),
                        int(row.get('L', 0)),
                        f"{float(row.get('IP', 0)):.1f}",
                        int(row.get('H', 0)),
                        int(row.get('R', 0)),
                        int(row.get('ER', 0)),
                        int(row.get('HR', 0)),
                        int(row.get('BB', 0)),
                        int(row.get('SO', 0)),
                        f"{float(row.get('ERA', 0)):.2f}",
                        f"{float(row.get('WHIP', 0)):.2f}",
                        int(row.get('SV', 0)),
                        condition_display,
                        row.get('Status', 'Healthy')
                    )

                # Determine injury tag based on Injured Days
                tags = ()
                if injured_days > 0:
                    if injured_days < 10:
                        tags = ("day_to_day",)
                    else:
                        tags = ("injured",)

                tree.insert("", tk.END, values=values, tags=tags)
            except Exception as e:
                logger.warning(f"Error inserting roster row for {row.get('Player', 'Unknown')}: {e}")

    def _create_status_bar(self):
        """Create status bar frame with day counter, progress bar, and status message."""
        status_frame = tk.Frame(self.root, relief=tk.SUNKEN, bd=1)
        status_frame.pack(side=tk.BOTTOM, fill=tk.X)

        # Day counter label
        self.day_label = tk.Label(
            status_frame, text="Day: 0 / 162", font=("Arial", 10), anchor=tk.W
        )
        self.day_label.pack(side=tk.LEFT, padx=10)

        # Progress bar
        self.progress_bar = ttk.Progressbar(
            status_frame,
            length=200,
            mode='determinate',
            maximum=162
        )
        self.progress_bar.pack(side=tk.LEFT, padx=10)

        # Progress percentage label
        self.progress_label = tk.Label(
            status_frame, text="0%", font=("Arial", 10), width=5
        )
        self.progress_label.pack(side=tk.LEFT, padx=5)

        # Status message
        self.status_label = tk.Label(
            status_frame, text="Ready to start season simulation",
            font=("Arial", 10), anchor=tk.W
        )
        self.status_label.pack(side=tk.LEFT, padx=10, fill=tk.X, expand=True)

    def start_season(self):
        """
        Start the season simulation.

        Creates a SeasonWorker, and starts the worker thread.
        """
        if self.worker and self.worker.is_alive():
            messagebox.showwarning("Already Running",
                                   "A season simulation is already running.")
            return

        # Get the selected team from dropdown
        selected_team = self.team_var.get()
        if not selected_team:
            messagebox.showwarning("No Team Selected",
                                   "Please select a team to follow before starting.")
            return

        logger.info(f"Starting season simulation, following team: {selected_team}")

        # Update the season_team_to_follow to the selected team
        self.season_team_to_follow = selected_team

        # Create worker with simulation parameters
        self.worker = SeasonWorker(
            self.load_seasons,
            self.new_season,
            self.rotation_len,
            self.series_length,
            self.season_length,
            self.season_chatty,
            self.season_print_lineup_b,
            self.season_print_box_score_b,
            selected_team  # Use selected team from dropdown
        )

        # Reset progress indicators
        self.progress_bar['value'] = 0
        self.progress_label.config(text="0%")
        self.day_label.config(text="Day: 0 / 162")

        # Start worker thread
        self.worker.daemon = True  # Thread will exit when main program exits
        self.worker.start()

        # Update the team tab label to the selected team
        for i in range(self.notebook.index("end")):
            if self.notebook.tab(i, "text") in ['ARI', 'ATL', 'BAL', 'BOS', 'CHC', 'CHW', 'CIN', 'CLE',
                                                 'COL', 'DET', 'HOU', 'KCR', 'LAA', 'LAD', 'MIA', 'MIL',
                                                 'MIN', 'NYM', 'NYY', 'OAK', 'PHI', 'PIT', 'SDP', 'SEA',
                                                 'SFG', 'STL', 'TBR', 'TEX', 'TOR', 'WSN']:
                # Found the team tab - update its label
                self.notebook.tab(i, text=selected_team)
                break

        # Load admin players after a short delay (wait for season to initialize)
        self.root.after(1000, self._load_admin_players)

        # Populate injury team dropdown
        self.root.after(1000, self._populate_injuries_teams)

        # Load initial roster data for followed team
        self.root.after(2000, self.on_roster_update)

        # Update UI state
        self._update_button_states(simulation_running=True, paused=False)
        self.status_label.config(text="Simulation started...")

    def pause_season(self):
        """Pause the simulation."""
        if self.worker and self.worker.is_alive():
            logger.info("Pausing simulation")
            self.worker.pause()
            self._update_button_states(simulation_running=True, paused=True)
            self.status_label.config(text="Simulation paused")

    def resume_season(self):
        """Resume the simulation from paused state."""
        if self.worker and self.worker.is_alive():
            logger.info("Resuming simulation")
            self.worker.resume()
            self._update_button_states(simulation_running=True, paused=False)
            self.status_label.config(text="Simulation resumed")

    def next_day(self):
        """Advance exactly one day, then pause."""
        if self.worker and self.worker.is_alive():
            logger.info("Advancing one day")
            self.worker.step_one_day()
            self._update_button_states(simulation_running=True, paused=False)
            self.status_label.config(text="Advancing one day...")

    def next_series(self):
        """Advance exactly three days (one series), then pause."""
        if self.worker and self.worker.is_alive():
            logger.info("Advancing three days (series)")
            self.worker.step_n_days(3)
            self._update_button_states(simulation_running=True, paused=False)
            self.status_label.config(text="Advancing 3 days (series)...")

    def next_week(self):
        """Advance exactly seven days (one week), then pause."""
        if self.worker and self.worker.is_alive():
            logger.info("Advancing seven days (week)")
            self.worker.step_n_days(7)
            self._update_button_states(simulation_running=True, paused=False)
            self.status_label.config(text="Advancing 7 days (week)...")

    def _update_button_states(self, simulation_running, paused):
        """
        Update button enabled/disabled states based on simulation state.

        Args:
            simulation_running (bool): Whether a simulation is currently running
            paused (bool): Whether the simulation is paused
        """
        # Disable team selection once simulation starts
        self.team_combo.config(state="disabled" if simulation_running else "readonly")

        self.start_btn.config(state=tk.DISABLED if simulation_running else tk.NORMAL)
        self.pause_btn.config(state=tk.NORMAL if simulation_running and not paused else tk.DISABLED)
        self.resume_btn.config(state=tk.NORMAL if simulation_running and paused else tk.DISABLED)
        self.next_day_btn.config(state=tk.NORMAL if simulation_running else tk.DISABLED)
        self.next_series_btn.config(state=tk.NORMAL if simulation_running else tk.DISABLED)
        self.next_week_btn.config(state=tk.NORMAL if simulation_running else tk.DISABLED)

    def _poll_queues(self):
        """
        Poll all signal queues for messages from the worker thread.

        This method is called periodically via root.after() to check for
        messages from the worker thread and update the UI accordingly.
        """
        if self.worker:
            signals = self.worker.signals

            # Check day_started queue
            try:
                msg = signals.day_started_queue.get_nowait()
                self.on_day_started(msg[1], msg[2])  # day_num, schedule_text
            except queue.Empty:
                pass
            except Exception as e:
                logger.error(f"Error handling day_started: {e}")

            # Check game_completed queue
            try:
                msg = signals.game_completed_queue.get_nowait()
                self.on_game_completed(msg[1])  # game_data
            except queue.Empty:
                pass
            except Exception as e:
                logger.error(f"Error handling game_completed: {e}")

            # Check day_completed queue
            try:
                msg = signals.day_completed_queue.get_nowait()
                self.on_day_completed(msg[1], msg[2])  # game_results, standings_data
            except queue.Empty:
                pass
            except Exception as e:
                logger.error(f"Error handling day_completed: {e}")

            # Check gm_assessment queue
            try:
                msg = signals.gm_assessment_queue.get_nowait()
                self.on_gm_assessment(msg[1])  # assessment_data
            except queue.Empty:
                pass
            except Exception as e:
                logger.error(f"Error handling gm_assessment: {e}")

            # Check injury_update queue
            try:
                msg = signals.injury_update_queue.get_nowait()
                self.on_injury_update(msg[1])  # injury_list
            except queue.Empty:
                pass
            except Exception as e:
                logger.error(f"Error handling injury_update: {e}")

            # Check simulation_complete queue
            try:
                msg = signals.simulation_complete_queue.get_nowait()
                self.on_simulation_complete()
            except queue.Empty:
                pass
            except Exception as e:
                logger.error(f"Error handling simulation_complete: {e}")

            # Note: play_by_play queue polling removed - now using game_completed for full recaps

            # Check error queue
            try:
                msg = signals.error_queue.get_nowait()
                self.on_error(msg[1])  # error_message
            except queue.Empty:
                pass
            except Exception as e:
                logger.error(f"Error handling error message: {e}")

        # Schedule next poll in 100ms
        self.root.after(100, self._poll_queues)

    # Event handlers (same logic as archived Qt version, but update tkinter widgets)

    def on_day_started(self, day_num, schedule_text):
        """Handle day_started message."""
        logger.debug(f"Day {day_num + 1} started")

        # Store current day number for header
        self.current_day_num = day_num

        # Update day counter
        self.day_label.config(text=f"Day: {day_num + 1} / 162")

        # Update progress bar
        self.progress_bar['value'] = day_num + 1
        progress_pct = ((day_num + 1) / 162) * 100
        self.progress_label.config(text=f"{progress_pct:.0f}%")

        # Update status
        self.status_label.config(text=f"Simulating day {day_num + 1}...")

        # Get today's schedule from worker
        if self.worker and self.worker.season:
            todays_games = self.worker.season.schedule[day_num]
            self.current_day_schedule = [
                (m[0], m[1]) for m in todays_games
                if 'OFF DAY' not in m
            ]
        else:
            self.current_day_schedule = []

        # Display yesterday's results and today's schedule
        self.games_text.config(state=tk.NORMAL)
        self.games_text.delete(1.0, tk.END)

        # Show yesterday's final scores (if not day 1)
        if day_num > 0 and self.previous_day_results:
            self.games_text.insert(tk.END, f"═══ Day {day_num} Results ═══\n\n", "day_header")
            self._display_yesterday_results()
            self.games_text.insert(tk.END, "\n\n")

        # Show today's schedule header
        self.games_text.insert(tk.END, f"═══ Day {day_num + 1} Schedule ═══\n\n", "day_header")

        # Clear results tracking for new day
        self.current_day_results = {}
        self.followed_game_recaps = []

        # Display initial grid with blanks for today's games
        self._display_games_grid()
        self.games_text.config(state=tk.DISABLED)

        # Update schedule view (show next 14 days)
        self._update_schedule_display(day_num)

    def on_game_completed(self, game_data):
        """Handle game_completed message (followed team)."""
        logger.debug(f"Followed game completed: {game_data['away_team']} @ {game_data['home_team']}")

        away = game_data['away_team']
        home = game_data['home_team']
        day_num = game_data.get('day_num', 0)

        # Store result for Today's Games tab
        self.current_day_results[(away, home)] = game_data

        # Store recap for Play-by-Play tab (grouped by day)
        if day_num not in self.pbp_by_day:
            self.pbp_by_day[day_num] = []
        self.pbp_by_day[day_num].append((away, home, game_data['game_recap']))

        # Update dropdown with this day if not already present
        current_days = [int(val.split()[1]) for val in self.pbp_day_combo['values'] if val.startswith('Day')]
        if day_num + 1 not in current_days:  # day_num is 0-indexed, display as 1-indexed
            # Sort days in descending order (most recent first)
            days_list = ['Select Day'] + [f'Day {d + 1}' for d in sorted(list(self.pbp_by_day.keys()), reverse=True)]
            self.pbp_day_combo['values'] = days_list
            logger.debug(f"Added Day {day_num + 1} to play-by-play dropdown")

        # Rebuild grid to show updated score
        self._rebuild_games_display()

    def on_day_completed(self, game_results, standings_data):
        """Handle day_completed message."""
        logger.debug(f"Day completed with {len(game_results)} other games")

        # Store all non-followed game results
        for game_data in game_results:
            away = game_data['away_team']
            home = game_data['home_team']
            self.current_day_results[(away, home)] = game_data

        # Rebuild grid to show all scores
        self._rebuild_games_display()

        # Save current day's results as previous day (for next day's display)
        self.previous_day_results = self.current_day_results.copy()

        # Update standings display
        self._update_standings_display(standings_data)

        # Update roster to reflect latest stats
        self.on_roster_update()

        # Update button states if worker is paused (e.g., after step_one_day)
        if self.worker and self.worker._paused:
            self._update_button_states(simulation_running=True, paused=True)
            self.status_label.config(text=f"Day complete - Paused")
            # When paused, update display to show completed day results + next day schedule
            self._display_paused_state()
        else:
            self.status_label.config(text=f"Day complete")

    def _update_standings_display(self, standings_data):
        """Update standings Treeview widgets (AL and NL separately)."""
        # Cache the data for sorting
        self.standings_data_cache = standings_data

        # Get followed team for highlighting (single string)
        followed_team = self.worker.team_to_follow if self.worker else ''

        # Update AL standings
        self._populate_league_standings(
            self.al_standings_tree,
            standings_data.get('al', {}),
            followed_team
        )

        # Update NL standings
        self._populate_league_standings(
            self.nl_standings_tree,
            standings_data.get('nl', {}),
            followed_team
        )

    def _populate_league_standings(self, tree, league_data, followed_team):
        """
        Populate a standings treeview with league data.

        Args:
            tree: The treeview widget to populate
            league_data: Dict with 'teams', 'wins', 'losses', 'pct', 'gb'
            followed_team: Team abbreviation to highlight
        """
        # Clear existing items
        for item in tree.get_children():
            tree.delete(item)

        teams = league_data.get('teams', [])
        wins = league_data.get('wins', [])
        losses = league_data.get('losses', [])
        pcts = league_data.get('pct', [])
        gbs = league_data.get('gb', [])

        # Insert data into treeview
        for i in range(len(teams)):
            team = teams[i]
            wl = f"{wins[i]}-{losses[i]}"
            pct = f"{pcts[i]:.3f}"
            gb = gbs[i]

            # Determine if this team is followed
            tags = ("followed",) if team == followed_team else ()

            tree.insert(
                "",
                tk.END,
                values=(team, wl, pct, gb),
                tags=tags
            )

    def _sort_standings(self, column, league):
        """
        Sort standings by the specified column for a specific league.

        Args:
            column (str): Column to sort by ('team', 'wl', 'pct', 'gb')
            league (str): League to sort ('al' or 'nl')
        """
        if not self.standings_data_cache:
            return

        # Toggle sort direction if clicking same column in same league
        if self.standings_sort_column == column and self.standings_sort_league == league:
            self.standings_sort_reverse = not self.standings_sort_reverse
        else:
            # New column or league - use appropriate default direction
            self.standings_sort_column = column
            self.standings_sort_league = league
            if column in ("pct", "wl"):
                self.standings_sort_reverse = True  # Descending for pct and wins
            elif column == "gb":
                self.standings_sort_reverse = False  # Ascending for games back
            else:
                self.standings_sort_reverse = False  # Ascending for team names

        # Get data for the specific league
        league_data = self.standings_data_cache.get(league, {})
        teams = league_data.get('teams', [])
        wins = league_data.get('wins', [])
        losses = league_data.get('losses', [])
        pcts = league_data.get('pct', [])
        gbs = league_data.get('gb', [])

        # Create list of tuples for sorting
        data = list(zip(teams, wins, losses, pcts, gbs))

        # Sort based on column
        if column == "team":
            data.sort(key=lambda x: x[0], reverse=self.standings_sort_reverse)
        elif column == "wl":
            data.sort(key=lambda x: x[1], reverse=self.standings_sort_reverse)
        elif column == "pct":
            data.sort(key=lambda x: x[3], reverse=self.standings_sort_reverse)
        elif column == "gb":
            # Special handling for GB (leader is '-', need to sort numerically)
            def gb_key(x):
                gb_val = x[4]
                if gb_val == '-':
                    return -1.0  # Leader goes first
                try:
                    return float(gb_val)
                except ValueError:
                    return 999.0  # Put invalid values at end
            data.sort(key=gb_key, reverse=self.standings_sort_reverse)

        # Select the appropriate tree
        tree = self.al_standings_tree if league == 'al' else self.nl_standings_tree

        # Clear and repopulate treeview
        for item in tree.get_children():
            tree.delete(item)

        followed_team = self.worker.team_to_follow if self.worker else ''

        for team, w, l, pct, gb in data:
            wl = f"{w}-{l}"
            pct_str = f"{pct:.3f}"
            tags = ("followed",) if team == followed_team else ()

            tree.insert(
                "",
                tk.END,
                values=(team, wl, pct_str, gb),
                tags=tags
            )

    def on_gm_assessment(self, assessment_data):
        """Handle gm_assessment_ready message."""
        team = assessment_data.get('team', 'Unknown')
        games = assessment_data.get('games_played', 0)
        wins = assessment_data.get('wins', 0)
        losses = assessment_data.get('losses', 0)
        games_back = assessment_data.get('games_back', 0.0)
        assessment = assessment_data.get('assessment', {})

        logger.info(f"GM assessment ready for {team} at {games} games")

        # Update header label
        self.gm_header_label.config(text=f"Latest GM Assessment: {team} (After {games} Games)")

        # Clear the text widget and display the latest assessment
        self.gm_text.config(state=tk.NORMAL)
        self.gm_text.delete(1.0, tk.END)

        # Format and display assessment
        self._display_gm_assessment(team, games, wins, losses, games_back, assessment)

        self.gm_text.config(state=tk.DISABLED)

    def _display_gm_assessment(self, team, games, wins, losses, games_back, assessment):
        """
        Format and display GM assessment in the text widget.

        Args:
            team (str): Team abbreviation
            games (int): Games played
            wins (int): Win count
            losses (int): Loss count
            games_back (float): Games behind leader
            assessment (dict): Assessment data with strategy, roster_values, recommendations
        """
        strategy = assessment.get('strategy')
        roster_values = assessment.get('roster_values', {'batters': [], 'pitchers': []})
        recommendations = assessment.get('recommendations', {})

        if not strategy:
            self.gm_text.insert(tk.END, "No assessment data available.\n")
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

    def on_injury_update(self, injury_list):
        """Handle injury_update message."""
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

    def on_simulation_complete(self):
        """Handle simulation_complete message."""
        logger.info("Season simulation completed")
        self._update_button_states(simulation_running=False, paused=False)
        self.status_label.config(text="Season complete!")
        messagebox.showinfo("Season Complete",
                            "The season simulation has completed successfully.")

    def on_error(self, error_message):
        """Handle error_occurred message."""
        logger.error(f"Simulation error: {error_message}")
        messagebox.showerror("Simulation Error", error_message)
        self._update_button_states(simulation_running=False, paused=False)
        self.status_label.config(text="Error occurred")

    def _on_pbp_day_changed(self, event=None):
        """Handle day dropdown change in play-by-play tab."""
        selected = self.pbp_day_var.get()

        if selected == "Select Day":
            return

        # Extract day number from "Day X" format
        try:
            day_num = int(selected.split()[1]) - 1  # Convert back to 0-indexed
        except (ValueError, IndexError):
            logger.error(f"Invalid day selection: {selected}")
            return

        # Get games for this day
        games = self.pbp_by_day.get(day_num, [])

        if not games:
            self.pbp_text.config(state=tk.NORMAL)
            self.pbp_text.delete(1.0, tk.END)
            self.pbp_text.insert(tk.END, f"No followed games on {selected}\n")
            self.pbp_text.config(state=tk.DISABLED)
            return

        # Display all games for this day
        self.pbp_text.config(state=tk.NORMAL)
        self.pbp_text.delete(1.0, tk.END)

        for away, home, game_recap in games:
            # Add game header
            header = f"▼ {away} @ {home} ▼\n"
            self.pbp_text.insert(tk.END, "\n" if self.pbp_text.get(1.0, tk.END).strip() else "")
            self.pbp_text.insert(tk.END, header, "game_header")

            # Add game recap (already formatted with play-by-play)
            # Apply simple formatting: highlight score lines
            for line in game_recap.split('\n'):
                if "Scored" in line or "score is" in line:
                    self.pbp_text.insert(tk.END, line + '\n', "score_update")
                else:
                    self.pbp_text.insert(tk.END, line + '\n', "play")

            # Add separator between games
            self.pbp_text.insert(tk.END, "\n" + "="*80 + "\n")

        self.pbp_text.see(1.0)  # Scroll to top of day's games
        self.pbp_text.config(state=tk.DISABLED)

        logger.debug(f"Displayed {len(games)} games for Day {day_num + 1}")

    def _display_yesterday_results(self):
        """Display yesterday's final scores in a compact format."""
        if not self.previous_day_results:
            return

        # Get all games from previous day (recreate schedule from results)
        games = sorted(self.previous_day_results.keys())

        games_per_row = 5
        game_separator = '     '

        for row_start in range(0, len(games), games_per_row):
            row_games = games[row_start:row_start + games_per_row]

            # Header row
            header_parts = ['     R   H   E'] * len(row_games)
            self.games_text.insert(tk.END, game_separator.join(header_parts) + "\n")

            # Away team row
            away_parts = []
            for away, home in row_games:
                data = self.previous_day_results[(away, home)]
                away_parts.append(f"{away:>3} {data['away_r']:>2}  {data['away_h']:>2}   {data['away_e']:>1}")
            self.games_text.insert(tk.END, game_separator.join(away_parts) + "\n")

            # Home team row
            home_parts = []
            for away, home in row_games:
                data = self.previous_day_results[(away, home)]
                home_parts.append(f"{home:>3} {data['home_r']:>2}  {data['home_h']:>2}   {data['home_e']:>1}")
            self.games_text.insert(tk.END, game_separator.join(home_parts) + "\n\n")

    def _display_games_grid(self):
        """
        Display all games for the day in columnar format with R H E headers.

        Shows actual R H E values for completed games, dashes for pending games.
        All games (followed and non-followed) are displayed the same way.
        """
        if not self.current_day_schedule:
            self.games_text.insert(tk.END, "No games scheduled today\n\n")
            return

        games_per_row = 5
        game_separator = '     '  # 5 spaces between games (matches format_compact_games)

        for row_start in range(0, len(self.current_day_schedule), games_per_row):
            row_games = self.current_day_schedule[row_start:row_start + games_per_row]

            # Header row: "     R   H   E" repeated for each game (matches format_compact_games)
            header_parts = []
            for _ in row_games:
                header_parts.append('     R   H   E')
            self.games_text.insert(tk.END, game_separator.join(header_parts) + "\n")

            # Away team row
            away_parts = []
            for away, home in row_games:
                game_key = (away, home)
                if game_key in self.current_day_results:
                    data = self.current_day_results[game_key]
                    # Format: Team(3) Space R(2) 2spaces H(2) 3spaces E(1)
                    away_parts.append(f"{away:>3} {data['away_r']:>2}  {data['away_h']:>2}   {data['away_e']:>1}")
                else:
                    # Use same spacing but with dashes
                    away_parts.append(f"{away:>3}  -   -    -")
            self.games_text.insert(tk.END, game_separator.join(away_parts) + "\n")

            # Home team row
            home_parts = []
            for away, home in row_games:
                game_key = (away, home)
                if game_key in self.current_day_results:
                    data = self.current_day_results[game_key]
                    # Format: Team(3) Space R(2) 2spaces H(2) 3spaces E(1)
                    home_parts.append(f"{home:>3} {data['home_r']:>2}  {data['home_h']:>2}   {data['home_e']:>1}")
                else:
                    # Use same spacing but with dashes
                    home_parts.append(f"{home:>3}  -   -    -")
            self.games_text.insert(tk.END, game_separator.join(home_parts) + "\n\n")

    def _rebuild_games_display(self):
        """Rebuild the entire games display with current results."""
        self.games_text.config(state=tk.NORMAL)

        # Clear and rebuild
        self.games_text.delete(1.0, tk.END)

        # Show yesterday's results if available (same as on_day_started)
        if self.current_day_num > 0 and self.previous_day_results:
            self.games_text.insert(tk.END, f"═══ Day {self.current_day_num} Results ═══\n\n", "day_header")
            self._display_yesterday_results()
            self.games_text.insert(tk.END, "\n\n")

        # Restore today's schedule header with proper formatting
        self.games_text.insert(tk.END, f"═══ Day {self.current_day_num + 1} Schedule ═══\n\n", "day_header")

        # Display updated grid
        self._display_games_grid()

        self.games_text.see(tk.END)  # Auto-scroll
        self.games_text.config(state=tk.DISABLED)

    def _display_paused_state(self):
        """
        Display completed day results and next day schedule when paused.

        Shows:
        - The just-completed day's final results
        - The next day's schedule
        """
        if not self.worker or not self.worker.season:
            return

        self.games_text.config(state=tk.NORMAL)
        self.games_text.delete(1.0, tk.END)

        # Show completed day's results (the day that just finished)
        completed_day = self.current_day_num + 1  # current_day_num is 0-indexed
        self.games_text.insert(tk.END, f"═══ Day {completed_day} Results ═══\n\n", "day_header")

        # Display all games from the completed day (stored in current_day_results)
        if self.current_day_results:
            self._display_completed_day_results()
        else:
            self.games_text.insert(tk.END, "No games played today\n\n")

        self.games_text.insert(tk.END, "\n\n")

        # Show next day's schedule if available
        next_day_num = self.current_day_num + 1  # This is the next day to be simulated
        if next_day_num < len(self.worker.season.schedule):
            self.games_text.insert(tk.END, f"═══ Day {next_day_num + 1} Schedule ═══\n\n", "day_header")
            self._display_next_day_schedule(next_day_num)
        else:
            self.games_text.insert(tk.END, "═══ Season Complete ═══\n", "day_header")

        self.games_text.see(1.0)  # Scroll to top
        self.games_text.config(state=tk.DISABLED)

    def _display_completed_day_results(self):
        """Display the completed day's results in compact grid format."""
        games = sorted(self.current_day_results.keys())
        games_per_row = 5
        game_separator = '     '

        for row_start in range(0, len(games), games_per_row):
            row_games = games[row_start:row_start + games_per_row]

            # Header row
            header_parts = ['     R   H   E'] * len(row_games)
            self.games_text.insert(tk.END, game_separator.join(header_parts) + "\n")

            # Away team row
            away_parts = []
            for away, home in row_games:
                data = self.current_day_results[(away, home)]
                away_parts.append(f"{away:>3} {data['away_r']:>2}  {data['away_h']:>2}   {data['away_e']:>1}")
            self.games_text.insert(tk.END, game_separator.join(away_parts) + "\n")

            # Home team row
            home_parts = []
            for away, home in row_games:
                data = self.current_day_results[(away, home)]
                home_parts.append(f"{home:>3} {data['home_r']:>2}  {data['home_h']:>2}   {data['home_e']:>1}")
            self.games_text.insert(tk.END, game_separator.join(home_parts) + "\n\n")

    def _display_next_day_schedule(self, day_num):
        """Display the next day's schedule."""
        next_day_games = self.worker.season.schedule[day_num]

        # Filter out OFF DAY entries
        matchups = [(m[0], m[1]) for m in next_day_games if 'OFF DAY' not in m]

        if not matchups:
            self.games_text.insert(tk.END, "No games scheduled\n\n")
            return

        games_per_row = 5
        game_separator = '     '

        for row_start in range(0, len(matchups), games_per_row):
            row_games = matchups[row_start:row_start + games_per_row]

            # Header row
            header_parts = ['     R   H   E'] * len(row_games)
            self.games_text.insert(tk.END, game_separator.join(header_parts) + "\n")

            # Away team row (with dashes for unplayed games)
            away_parts = []
            for away, home in row_games:
                away_parts.append(f"{away:>3}  -   -    -")
            self.games_text.insert(tk.END, game_separator.join(away_parts) + "\n")

            # Home team row (with dashes for unplayed games)
            home_parts = []
            for away, home in row_games:
                home_parts.append(f"{home:>3}  -   -    -")
            self.games_text.insert(tk.END, game_separator.join(home_parts) + "\n\n")

    def _update_schedule_display(self, current_day):
        """
        Update the schedule display to show upcoming games.

        Args:
            current_day (int): Current day number (0-indexed)
        """
        if not self.worker or not self.worker.season:
            return

        # Clear existing schedule
        self.schedule_text.config(state=tk.NORMAL)
        self.schedule_text.delete(1.0, tk.END)

        # Get schedule from worker's season
        schedule = self.worker.season.schedule
        total_days = len(schedule)

        # Show next 14 days (or until end of season)
        days_to_show = min(14, total_days - current_day)

        for i in range(days_to_show):
            day_index = current_day + i
            if day_index >= total_days:
                break

            day_games = schedule[day_index]

            # Day header (highlight current day)
            day_label = f"Day {day_index + 1}"
            if i == 0:
                day_label += " ◄ CURRENT"
                self.schedule_text.insert(tk.END, day_label + "\n", "current_day")
            else:
                self.schedule_text.insert(tk.END, day_label + "\n", "day_header")

            # Format matchups - show 4 per line for better readability
            matchup_strings = []
            for matchup in day_games:
                if 'OFF DAY' in matchup:
                    off_team = matchup[0] if matchup[0] != 'OFF DAY' else matchup[1]
                    matchup_strings.append(f"{off_team:4s} OFF")
                else:
                    matchup_strings.append(f"{matchup[0]:3s} @ {matchup[1]:3s}")

            # Display matchups in rows of 4
            for j in range(0, len(matchup_strings), 4):
                row_matchups = matchup_strings[j:j+4]
                matchups_line = "   ".join(row_matchups)
                self.schedule_text.insert(tk.END, "  " + matchups_line + "\n", "matchup")

            # Add spacing between days
            self.schedule_text.insert(tk.END, "\n")

        self.schedule_text.config(state=tk.DISABLED)

    def _sort_injuries(self, column):
        """
        Sort injuries by the specified column.

        Args:
            column (str): Column to sort by
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

    def _on_injuries_team_changed(self, event=None):
        """Handle team dropdown change in injuries tab."""
        # Just redisplay with current filter - on_injury_update already handles filtering
        if self.injuries_data_cache:
            self._sort_injuries(self.injuries_sort_column)

    def _populate_injuries_teams(self):
        """Populate injuries team dropdown with all teams."""
        if not self.worker or not self.worker.season:
            logger.debug("Cannot populate injury teams - no worker or season available")
            return

        try:
            # Get all team names from the season
            all_teams = self.worker.season.baseball_data.get_all_team_names()

            # Update dropdown values
            team_values = ['All Teams'] + sorted(all_teams)
            self.injuries_team_combo['values'] = team_values

            logger.debug(f"Populated injury team dropdown with {len(all_teams)} teams")
        except Exception as e:
            logger.error(f"Error populating injury teams: {e}")

    def _load_admin_players(self):
        """
        Load all players from baseball_data into the admin tab.
        Called when simulation starts.
        """
        if not self.worker or not self.worker.season:
            self.admin_status_label.config(text="Start simulation to load players", fg="#ff6600")
            return

        try:
            baseball_data = self.worker.season.baseball_data
            self.admin_all_players = []

            # Load batters
            batting_df = baseball_data.new_season_batting_data
            for idx, row in batting_df.iterrows():
                self.admin_all_players.append({
                    'player': row['Player'],
                    'pos': row.get('Pos', 'Unknown'),
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

            # Sort by player name
            self.admin_all_players.sort(key=lambda x: x['player'])

            # Populate team dropdowns
            all_teams = sorted(set(p['team'] for p in self.admin_all_players))
            self.admin_team_filter_combo['values'] = ['All Teams'] + all_teams
            self.admin_dest_team_combo['values'] = all_teams

            # Display all players initially
            self._filter_admin_players()

            self.admin_status_label.config(
                text=f"Loaded {len(self.admin_all_players)} players. Ready to make moves.",
                fg="#006600"
            )
            logger.info(f"Admin tab loaded {len(self.admin_all_players)} players")

        except Exception as e:
            logger.error(f"Error loading admin players: {e}")
            self.admin_status_label.config(text=f"Error loading players: {e}", fg="#cc0000")

    def _filter_admin_players(self):
        """
        Filter and display players based on search text and team filter.
        """
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

        # Update status
        if search_text or team_filter != "All Teams":
            self.admin_status_label.config(
                text=f"Showing {len(filtered_players)} of {len(self.admin_all_players)} players",
                fg="#666666"
            )

    def _admin_move_player(self):
        """
        Move selected player to destination team.
        """
        # Check if simulation is running (not paused)
        if self.worker and self.worker.is_alive() and not self.worker._paused:
            messagebox.showwarning(
                "Simulation Running",
                "Please pause the simulation before moving players."
            )
            return

        # Check if worker/season exists
        if not self.worker or not self.worker.season:
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
            baseball_data = self.worker.season.baseball_data
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

    def _admin_save_changes(self):
        """
        Save all player movements to CSV files.
        """
        if not self.worker or not self.worker.season:
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
            baseball_data = self.worker.season.baseball_data
            new_season = baseball_data.new_season

            # Save the files
            baseball_data.save_new_season_stats()

            # Show success message
            messagebox.showinfo(
                "Save Successful",
                f"Player movements saved successfully!\n\n"
                f"Files updated:\n"
                f"  - {new_season} New-Season-stats-pp-Batting.csv\n"
                f"  - {new_season} New-Season-stats-pp-Pitching.csv"
            )

            self.admin_status_label.config(
                text="Changes saved to CSV files successfully!",
                fg="#006600"
            )
            logger.info("Saved player movements to New-Season-stats CSV files")

        except Exception as e:
            logger.error(f"Error saving changes: {e}")
            messagebox.showerror(
                "Save Failed",
                f"Error saving changes: {str(e)}"
            )

    def on_close(self):
        """Handle window close event."""
        try:
            if self.worker and self.worker.is_alive():
                result = messagebox.askyesno(
                    "Simulation Running",
                    "A simulation is currently running. Stop it and exit?"
                )

                if result:
                    logger.info("Stopping worker thread before exit")
                    self.worker.stop()
                    self.worker.join(timeout=5.0)
                    if self.worker.is_alive():
                        logger.warning("Worker thread did not exit cleanly")
                    self.root.destroy()
            else:
                self.root.destroy()
        except Exception as e:
            logger.error(f"Error during close: {e}")
            # Force destroy even if there's an error
            try:
                self.root.destroy()
            except:
                pass
