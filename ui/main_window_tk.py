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

    def __init__(self, root):
        """
        Initialize the main window and UI components.

        Args:
            root (tk.Tk): The root tkinter window
        """
        self.root = root
        self.root.title("Baseball Season Simulator")
        self.root.geometry("1200x800")

        # Season worker (created when simulation starts)
        self.worker = None

        # Track games for progressive display
        self.current_day_schedule = []  # List of (away_team, home_tuple) tuples
        self.current_day_results = {}   # Dict: {(away, home): game_data}
        self.followed_game_recaps = []  # List of (away, home, recap_text) for followed games
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

        # Start button
        self.start_btn = tk.Button(
            toolbar, text="Start Season", command=self.start_season,
            width=12, bg="green", fg="white", font=("Arial", 10, "bold")
        )
        self.start_btn.pack(side=tk.LEFT, padx=5)

        # Separator
        ttk.Separator(toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=5)

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

        # Separator
        ttk.Separator(toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=5)

        # Stop button
        self.stop_btn = tk.Button(
            toolbar, text="Stop", command=self.stop_season,
            width=10, bg="red", fg="white", font=("Arial", 10, "bold")
        )
        self.stop_btn.pack(side=tk.LEFT, padx=5)

    def _create_main_content(self):
        """Create the main layout with paned window, standings, and tabs."""
        # Horizontal paned window for standings (left) and content (right)
        paned_window = tk.PanedWindow(self.root, orient=tk.HORIZONTAL, sashrelief=tk.RAISED)
        paned_window.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Left panel: Standings with Treeview
        standings_frame = tk.Frame(paned_window, relief=tk.SUNKEN, bd=1)
        standings_label = tk.Label(standings_frame, text="STANDINGS", font=("Arial", 12, "bold"))
        standings_label.pack(pady=5)

        # Create Treeview for standings with scrollbar
        tree_frame = tk.Frame(standings_frame)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Scrollbar
        scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Treeview with columns
        self.standings_tree = ttk.Treeview(
            tree_frame,
            columns=("team", "wl", "pct", "gb"),
            show="headings",  # Don't show the default first column
            height=25,
            yscrollcommand=scrollbar.set
        )
        scrollbar.config(command=self.standings_tree.yview)

        # Define column headings and properties
        self.standings_tree.heading("team", text="Team", command=lambda: self._sort_standings("team"))
        self.standings_tree.heading("wl", text="W-L", command=lambda: self._sort_standings("wl"))
        self.standings_tree.heading("pct", text="Pct", command=lambda: self._sort_standings("pct"))
        self.standings_tree.heading("gb", text="GB", command=lambda: self._sort_standings("gb"))

        # Configure column widths and alignment
        self.standings_tree.column("team", width=60, anchor=tk.CENTER)
        self.standings_tree.column("wl", width=80, anchor=tk.CENTER)
        self.standings_tree.column("pct", width=60, anchor=tk.CENTER)
        self.standings_tree.column("gb", width=50, anchor=tk.CENTER)

        # Add tag for followed teams (highlight)
        self.standings_tree.tag_configure("followed", background="#e6f3ff", font=("Arial", 10, "bold"))

        self.standings_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Store current standings data for sorting
        self.standings_data_cache = None
        self.standings_sort_column = "pct"  # Default sort by win percentage
        self.standings_sort_reverse = True  # Descending by default

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

        # Tab 3: Injuries (Treeview for sortable injury list)
        injuries_frame = tk.Frame(self.notebook)

        # Header with injury count
        injuries_header_frame = tk.Frame(injuries_frame)
        injuries_header_frame.pack(fill=tk.X, pady=5)

        self.injuries_header_label = tk.Label(
            injuries_header_frame, text="Injury Report",
            font=("Arial", 11, "bold")
        )
        self.injuries_header_label.pack()

        # Create Treeview for injuries
        injuries_tree_frame = tk.Frame(injuries_frame)
        injuries_tree_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        injuries_scrollbar = ttk.Scrollbar(injuries_tree_frame, orient=tk.VERTICAL)
        injuries_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.injuries_tree = ttk.Treeview(
            injuries_tree_frame,
            columns=("player", "team", "pos", "injury", "days", "status"),
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
        self.injuries_tree.heading("days", text="Days Left", command=lambda: self._sort_injuries("days"))
        self.injuries_tree.heading("status", text="Status", command=lambda: self._sort_injuries("status"))

        # Configure column widths
        self.injuries_tree.column("player", width=150, anchor=tk.W)
        self.injuries_tree.column("team", width=60, anchor=tk.CENTER)
        self.injuries_tree.column("pos", width=50, anchor=tk.CENTER)
        self.injuries_tree.column("injury", width=200, anchor=tk.W)
        self.injuries_tree.column("days", width=80, anchor=tk.CENTER)
        self.injuries_tree.column("status", width=100, anchor=tk.CENTER)

        # Tags for injury status
        self.injuries_tree.tag_configure("IL", background="#ffcccc")  # Red for IL
        self.injuries_tree.tag_configure("Day-to-Day", background="#fff4cc")  # Yellow for day-to-day

        self.injuries_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Store injury data for sorting
        self.injuries_data_cache = []
        self.injuries_sort_column = "days"  # Default sort by days remaining
        self.injuries_sort_reverse = True  # Descending

        self.notebook.add(injuries_frame, text="Injuries")

        # Tab 4: GM Assessments (ScrolledText for assessment history)
        gm_assessment_frame = tk.Frame(self.notebook)

        # Header
        gm_header_frame = tk.Frame(gm_assessment_frame)
        gm_header_frame.pack(fill=tk.X, pady=5)

        self.gm_header_label = tk.Label(
            gm_header_frame, text="No GM Assessment Yet",
            font=("Arial", 11, "bold")
        )
        self.gm_header_label.pack()

        # ScrolledText for assessment history
        self.gm_text = scrolledtext.ScrolledText(
            gm_assessment_frame, wrap=tk.WORD, font=("Courier", 9), state=tk.DISABLED
        )

        # Configure text tags for formatting
        self.gm_text.tag_configure("header", font=("Courier", 11, "bold"), foreground="#0044cc")
        self.gm_text.tag_configure("section", font=("Courier", 10, "bold"), underline=True)
        self.gm_text.tag_configure("value", foreground="#006600")
        self.gm_text.tag_configure("warning", foreground="#cc6600")
        self.gm_text.tag_configure("separator", foreground="#888888")

        self.gm_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.notebook.add(gm_assessment_frame, text="GM Assessments")

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

        paned_window.add(notebook_frame, minsize=600)

        # Set initial sash position (30% for standings, 70% for content)
        self.root.update_idletasks()
        paned_window.sash_place(0, 360, 1)

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

        logger.info("Starting season simulation")

        # Create worker with simulation parameters
        self.worker = SeasonWorker(
            load_seasons=[2023, 2024, 2025],
            new_season=2026,
            team_to_follow=['NYM'],  # Default followed team
            random_data=False,
            rotation_len=5,
            num_games=162,
            only_nl_b=False
        )

        # Reset progress indicators
        self.progress_bar['value'] = 0
        self.progress_label.config(text="0%")
        self.day_label.config(text="Day: 0 / 162")

        # Start worker thread
        self.worker.daemon = True  # Thread will exit when main program exits
        self.worker.start()

        # Load admin players after a short delay (wait for season to initialize)
        self.root.after(1000, self._load_admin_players)

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

    def stop_season(self):
        """Stop the simulation entirely."""
        if self.worker and self.worker.is_alive():
            logger.info("Stopping simulation")
            self.worker.stop()
            self.worker.join(timeout=5.0)  # Wait up to 5 seconds for thread to finish
            self._update_button_states(simulation_running=False, paused=False)
            self.status_label.config(text="Simulation stopped")

    def _update_button_states(self, simulation_running, paused):
        """
        Update button enabled/disabled states based on simulation state.

        Args:
            simulation_running (bool): Whether a simulation is currently running
            paused (bool): Whether the simulation is paused
        """
        self.start_btn.config(state=tk.DISABLED if simulation_running else tk.NORMAL)
        self.pause_btn.config(state=tk.NORMAL if simulation_running and not paused else tk.DISABLED)
        self.resume_btn.config(state=tk.NORMAL if simulation_running and paused else tk.DISABLED)
        self.next_day_btn.config(state=tk.NORMAL if simulation_running else tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL if simulation_running else tk.DISABLED)

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

        # Clear results tracking
        self.current_day_results = {}
        self.followed_game_recaps = []

        # Display initial grid with blanks
        self.games_text.config(state=tk.NORMAL)
        self.games_text.delete(1.0, tk.END)
        self.games_text.insert(tk.END, f"═══ Day {day_num + 1} ═══\n\n", "day_header")
        self._display_games_grid()
        self.games_text.config(state=tk.DISABLED)

        # Update schedule view (show next 14 days)
        self._update_schedule_display(day_num)

    def on_game_completed(self, game_data):
        """Handle game_completed message (followed team)."""
        logger.debug(f"Followed game completed: {game_data['away_team']} @ {game_data['home_team']}")

        away = game_data['away_team']
        home = game_data['home_team']

        # Store result
        self.current_day_results[(away, home)] = game_data

        # Store recap for later display
        self.followed_game_recaps.append((away, home, game_data['game_recap']))

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

        # Update standings display
        self._update_standings_display(standings_data)

        # Update button states if worker is paused (e.g., after step_one_day)
        if self.worker and self.worker._paused:
            self._update_button_states(simulation_running=True, paused=True)
            self.status_label.config(text="Day complete - Paused")
        else:
            self.status_label.config(text="Day complete")

    def _update_standings_display(self, standings_data):
        """Update standings Treeview widget."""
        # Cache the data for sorting
        self.standings_data_cache = standings_data

        # Clear existing items
        for item in self.standings_tree.get_children():
            self.standings_tree.delete(item)

        teams = standings_data.get('teams', [])
        wins = standings_data.get('wins', [])
        losses = standings_data.get('losses', [])
        pcts = standings_data.get('pct', [])
        gbs = standings_data.get('gb', [])

        # Get followed teams for highlighting
        followed_teams = self.worker.team_to_follow if self.worker else []

        # Insert data into treeview
        for i in range(len(teams)):
            team = teams[i]
            wl = f"{wins[i]}-{losses[i]}"
            pct = f"{pcts[i]:.3f}"
            gb = gbs[i]

            # Determine if this team is followed
            tags = ("followed",) if team in followed_teams else ()

            self.standings_tree.insert(
                "",
                tk.END,
                values=(team, wl, pct, gb),
                tags=tags
            )

    def _sort_standings(self, column):
        """
        Sort standings by the specified column.

        Args:
            column (str): Column to sort by ('team', 'wl', 'pct', 'gb')
        """
        if not self.standings_data_cache:
            return

        # Toggle sort direction if clicking same column
        if self.standings_sort_column == column:
            self.standings_sort_reverse = not self.standings_sort_reverse
        else:
            # New column - use appropriate default direction
            self.standings_sort_column = column
            if column in ("pct", "wl"):
                self.standings_sort_reverse = True  # Descending for pct and wins
            elif column == "gb":
                self.standings_sort_reverse = False  # Ascending for games back
            else:
                self.standings_sort_reverse = False  # Ascending for team names

        # Get data
        teams = self.standings_data_cache.get('teams', [])
        wins = self.standings_data_cache.get('wins', [])
        losses = self.standings_data_cache.get('losses', [])
        pcts = self.standings_data_cache.get('pct', [])
        gbs = self.standings_data_cache.get('gb', [])

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

        # Clear and repopulate treeview
        for item in self.standings_tree.get_children():
            self.standings_tree.delete(item)

        followed_teams = self.worker.team_to_follow if self.worker else []

        for team, w, l, pct, gb in data:
            wl = f"{w}-{l}"
            pct_str = f"{pct:.3f}"
            tags = ("followed",) if team in followed_teams else ()

            self.standings_tree.insert(
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

        # Switch to GM Assessments tab
        self.notebook.select(3)  # Tab 4 (0-indexed, so index 3)

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

        # Cache injury data for sorting
        self.injuries_data_cache = injury_list

        # Update header with count
        count_text = f"Injury Report ({len(injury_list)} injured)"
        self.injuries_header_label.config(text=count_text)

        # Clear existing items
        for item in self.injuries_tree.get_children():
            self.injuries_tree.delete(item)

        # Insert injury data
        for injury in injury_list:
            status = injury['status']
            tags = (status,)  # Use status as tag for color coding

            self.injuries_tree.insert(
                "",
                tk.END,
                values=(
                    injury['player'],
                    injury['team'],
                    injury['position'],
                    injury['injury'],
                    injury['days_remaining'],
                    status
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

    def _display_games_grid(self):
        """
        Display all games for the day in columnar format with R H E headers.

        Shows actual R H E values for completed games, dashes for pending games.
        Followed game recaps appear below the grid.
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

        # Add followed game recaps below grid
        if self.followed_game_recaps:
            self.games_text.insert(tk.END, "\n" + "=" * 60 + "\n")
            self.games_text.insert(tk.END, "FOLLOWED GAME DETAILS\n", "header")
            self.games_text.insert(tk.END, "=" * 60 + "\n\n")
            for away, home, recap in self.followed_game_recaps:
                self.games_text.insert(tk.END, f"▼ {away} @ {home} ▼\n", "header")
                self.games_text.insert(tk.END, "─" * 60 + "\n", "separator")
                self.games_text.insert(tk.END, recap, "followed_game")
                self.games_text.insert(tk.END, "\n")
                self.games_text.insert(tk.END, "─" * 60 + "\n\n", "separator")

    def _rebuild_games_display(self):
        """Rebuild the entire games display with current results."""
        self.games_text.config(state=tk.NORMAL)

        # Clear and rebuild
        self.games_text.delete(1.0, tk.END)

        # Restore day header with proper formatting
        self.games_text.insert(tk.END, f"═══ Day {self.current_day_num + 1} ═══\n\n", "day_header")

        # Display updated grid
        self._display_games_grid()

        self.games_text.see(tk.END)  # Auto-scroll
        self.games_text.config(state=tk.DISABLED)

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
            if column == "days":
                self.injuries_sort_reverse = True  # Longest injuries first
            else:
                self.injuries_sort_reverse = False  # Ascending for text

        # Sort data
        data = self.injuries_data_cache.copy()

        if column == "player":
            data.sort(key=lambda x: x['player'], reverse=self.injuries_sort_reverse)
        elif column == "team":
            data.sort(key=lambda x: x['team'], reverse=self.injuries_sort_reverse)
        elif column == "pos":
            data.sort(key=lambda x: x['position'], reverse=self.injuries_sort_reverse)
        elif column == "injury":
            data.sort(key=lambda x: x['injury'], reverse=self.injuries_sort_reverse)
        elif column == "days":
            data.sort(key=lambda x: x['days_remaining'], reverse=self.injuries_sort_reverse)
        elif column == "status":
            data.sort(key=lambda x: x['status'], reverse=self.injuries_sort_reverse)

        # Clear and repopulate
        for item in self.injuries_tree.get_children():
            self.injuries_tree.delete(item)

        for injury in data:
            status = injury['status']
            tags = (status,)

            self.injuries_tree.insert(
                "",
                tk.END,
                values=(
                    injury['player'],
                    injury['team'],
                    injury['position'],
                    injury['injury'],
                    injury['days_remaining'],
                    status
                ),
                tags=tags
            )

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
