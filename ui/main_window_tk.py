"""
--- Copyright Notice ---
Copyright (c) 2024 Jim Maastricht

Refactored main window for the baseball season simulation UI using tkinter.

Provides the primary interface with modular widget components.
"""

import tkinter as tk
from tkinter import ttk, messagebox
import queue

from ui.widgets import (
    ToolbarWidget, StandingsWidget, GamesWidget, ScheduleWidget,
    InjuriesWidget, RosterWidget, AdminWidget, GamesPlayedWidget,
    GMAssessmentWidget, LeagueStatsWidget, LeagueLeadersWidget, PlayoffWidget
)
from ui.controllers import SimulationController
from bblogger import logger


class SeasonMainWindow:
    """
    Main application window for season simulation using tkinter.

    Uses modular widget components for better organization and maintainability.
    """

    def __init__(self, root, load_seasons, new_season, season_length, series_length,
                 rotation_len, season_chatty, season_print_lineup_b, season_print_box_score_b,
                 season_team_to_follow):
        """
        Initialize the main window and UI components.

        Args:
            root: The root tkinter window
            load_seasons: Years to load stats from
            new_season: Season year to simulate
            season_length: Games per team
            series_length: Games per series
            rotation_len: Pitcher rotation length
            season_chatty: Verbose output flag
            season_print_lineup_b: Print lineup flag
            season_print_box_score_b: Print box score flag
            season_team_to_follow: Team to follow (string)
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
        self.season_team_to_follow = season_team_to_follow or 'MIL'
        self.current_day = 0  # Track current simulation day for status messages
        self.world_series_active = False  # Track if World Series is running
        self.saved_standings = None  # Save regular season standings during playoffs

        self.root.title("Baseball Season Simulator")
        self.root.geometry("1500x900")

        # Configure tab styling (Baseball Theme)
        style = ttk.Style()
        style.theme_use('default')  # Use default theme as base

        # Configure the Notebook frame background
        style.configure('TNotebook', background='#f0f0f0', borderwidth=0)
        style.configure('TNotebook.Tab',
            background='#2d5016',      # Baseball field green (inactive tabs)
            foreground='#ffffff',      # White text on inactive tabs
            padding=[12, 6],           # Tab padding (horizontal, vertical)
            font=('TkDefaultFont', 10, 'bold'),
            borderwidth=1
        )
        # Configure selected/active tab appearance
        style.map('TNotebook.Tab',
            background=[('selected', '#1e90ff'), ('active', '#1e90ff')],  # Dodger blue (active/hovered tab)
            foreground=[('selected', '#ffffff'), ('active', '#ffffff')],   # White text on active tab
            expand=[('selected', [1, 1, 1, 0])]    # Slight expansion effect
        )

        # Create simulation controller
        self.controller = SimulationController(
            load_seasons, new_season, rotation_len, series_length,
            season_length, season_chatty, season_print_lineup_b,
            season_print_box_score_b
        )

        # Create widgets (order matters for packing!)
        self._create_toolbar()      # Packs at TOP
        self._create_status_bar()   # Packs at BOTTOM
        self._create_main_content() # Fills remaining space (BOTH + expand)

        # Initial button states
        self.toolbar.update_button_states(simulation_running=False, paused=False)

        # Start queue polling
        self._poll_queues()

        logger.info("Main window initialized with modular widgets")

    def _create_toolbar(self):
        """Create toolbar with control buttons."""
        toolbar_callbacks = {
            'start_season': self.start_season,
            'pause_season': self.pause_season,
            'resume_season': self.resume_season,
            'next_day': self.next_day,
            'next_series': self.next_series,
            'next_week': self.next_week
        }
        self.toolbar = ToolbarWidget(self.root, self.season_team_to_follow, toolbar_callbacks)

    def _create_main_content(self):
        """Create the main layout with paned window, standings, and tabs."""
        # Horizontal paned window for standings (left) and content (right)
        paned_window = tk.PanedWindow(self.root, orient=tk.HORIZONTAL, sashrelief=tk.RAISED)
        paned_window.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Left panel: Standings widget
        self.standings = StandingsWidget(paned_window)
        paned_window.add(self.standings.get_frame(), minsize=300)

        # Right panel: Notebook with tabs
        notebook_frame = tk.Frame(paned_window)
        self.notebook = ttk.Notebook(notebook_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        # Tab 1: Today's Games
        self.games_widget = GamesWidget(self.notebook, self.season_team_to_follow)
        self.notebook.add(self.games_widget.get_frame(), text="Today's Games")

        # Tab 2: Schedule
        self.schedule_widget = ScheduleWidget(self.notebook, self.season_team_to_follow)
        self.notebook.add(self.schedule_widget.get_frame(), text="Schedule")

        # Tab 3: Playoffs
        self.playoff_widget = PlayoffWidget(self.notebook)
        self.notebook.add(self.playoff_widget.get_frame(), text="Playoffs")

        # Tab 4: League Tab with nested sub-tabs
        league_tab_frame = tk.Frame(self.notebook)
        self.notebook.add(league_tab_frame, text="League")

        # Create inner notebook for league sub-tabs
        league_notebook = ttk.Notebook(league_tab_frame)
        league_notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # League Sub-tab 1: Leaders
        self.league_leaders_widget = LeagueLeadersWidget(league_notebook)
        league_notebook.add(self.league_leaders_widget.get_frame(), text="Leaders")

        # League Sub-tab 2: Stats
        self.league_stats_widget = LeagueStatsWidget(league_notebook)
        league_notebook.add(self.league_stats_widget.get_frame(), text="Stats")

        # League Sub-tab 3: IL (Injured List)
        self.injuries_widget = InjuriesWidget(league_notebook)
        league_notebook.add(self.injuries_widget.get_frame(), text="IL")

        # League Sub-tab 4: Admin (Player Management)
        self.admin_widget = AdminWidget(league_notebook, self.controller.get_worker)
        league_notebook.add(self.admin_widget.get_frame(), text="Admin")

        # Tab 5: Team Tab with nested sub-tabs
        team_tab_frame = tk.Frame(self.notebook)
        self.notebook.add(team_tab_frame, text=self.season_team_to_follow)

        # Create inner notebook for team sub-tabs
        team_notebook = ttk.Notebook(team_tab_frame)
        team_notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Team Sub-tab 1: Roster
        self.roster_widget = RosterWidget(team_notebook)
        team_notebook.add(self.roster_widget.get_frame(), text="Roster")

        # Team Sub-tab 2: Games Played
        self.games_played_widget = GamesPlayedWidget(team_notebook)
        team_notebook.add(self.games_played_widget.get_frame(), text="Games Played")

        # Team Sub-tab 3: GM Assessment
        self.gm_assessment_widget = GMAssessmentWidget(team_notebook, self.run_gm_assessments)
        team_notebook.add(self.gm_assessment_widget.get_frame(), text="GM Assessment")

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
            status_frame, text=f"Day: 0 / {self.season_length}", font=("Arial", 10), anchor=tk.W
        )
        self.day_label.pack(side=tk.LEFT, padx=10)

        # Progress bar
        self.progress_bar = ttk.Progressbar(
            status_frame,
            length=200,
            mode='determinate',
            maximum=self.season_length
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

    # =================================================================
    # SIMULATION CONTROL METHODS
    # =================================================================

    def start_season(self):
        """Start the season simulation."""
        selected_team = self.toolbar.get_selected_team()

        def on_started():
            """Callback after worker starts."""
            # Reset progress indicators
            self.current_day = 0
            self.progress_bar['value'] = 0
            self.progress_label.config(text="0%")
            self.day_label.config(text=f"Day: 0 / {self.season_length}")

            # Update season_team_to_follow
            self.season_team_to_follow = selected_team

            # Update team tab label
            for i in range(self.notebook.index("end")):
                tab_text = self.notebook.tab(i, "text")
                if tab_text in ['ARI', 'ATL', 'BAL', 'BOS', 'CHC', 'CHW', 'CIN', 'CLE',
                               'COL', 'DET', 'HOU', 'KCR', 'LAA', 'LAD', 'MIA', 'MIL',
                               'MIN', 'NYM', 'NYY', 'OAK', 'PHI', 'PIT', 'SDP', 'SEA',
                               'SFG', 'STL', 'TBR', 'TEX', 'TOR', 'WSN']:
                    self.notebook.tab(i, text=selected_team)
                    break

            # Initialize widgets after delay
            self.root.after(1000, self.admin_widget.load_players)
            self.root.after(1000, self._populate_injuries_teams)
            self.root.after(2000, self._update_roster)
            self.root.after(2000, self._update_league_stats)
            self.root.after(2000, self._update_league_leaders)
            self.root.after(2000, self.gm_assessment_widget.enable_button)

            # Update UI state
            self.toolbar.update_button_states(simulation_running=True, paused=False)
            self.status_label.config(text=self._format_status_with_day("Starting simulation..."))

        if self.controller.start_season(selected_team, on_started):
            logger.info(f"Season started for team: {selected_team}")

    def pause_season(self):
        """Pause the simulation."""
        if self.controller.pause_season():
            self.toolbar.update_button_states(simulation_running=True, paused=True)
            self.status_label.config(text=self._format_status_with_day("Simulation paused"))

    def resume_season(self):
        """Resume the simulation from paused state."""
        if self.controller.resume_season():
            self.toolbar.update_button_states(simulation_running=True, paused=False)
            self.status_label.config(text=self._format_status_with_day("Simulation resumed"))

    def next_day(self):
        """Advance exactly one day, then pause."""
        if self.controller.next_day():
            # Keep paused state - simulation will auto-pause after stepping
            self.toolbar.update_button_states(simulation_running=True, paused=True)
            self.status_label.config(text=self._format_status_with_day("Advancing one day..."))

    def next_series(self):
        """Advance exactly three days (one series), then pause."""
        if self.controller.next_series():
            # Simulation will auto-pause after stepping through all 3 days
            self.toolbar.update_button_states(simulation_running=True, paused=True)
            self.status_label.config(text=self._format_status_with_day("Advancing 3 days (series)..."))

    def next_week(self):
        """Advance exactly seven days (one week), then pause."""
        if self.controller.next_week():
            # Simulation will auto-pause after stepping through all 7 days
            self.toolbar.update_button_states(simulation_running=True, paused=True)
            self.status_label.config(text=self._format_status_with_day("Advancing 7 days (week)..."))

    def run_gm_assessments(self):
        """Force all teams to run GM assessments immediately."""
        self.controller.run_gm_assessments(
            lambda msg: self.status_label.config(text=self._format_status_with_day(msg))
        )

    # =================================================================
    # QUEUE POLLING AND EVENT HANDLING
    # =================================================================

    def _poll_queues(self):
        """
        Poll all signal queues for messages from the worker thread.

        This method is called periodically via root.after() to check for
        messages from the worker thread and update the UI accordingly.
        """
        worker = self.controller.get_worker()
        if worker:
            signals = worker.signals

            # Check day_started queue
            try:
                msg = signals.day_started_queue.get_nowait()
                self._on_day_started(msg[1], msg[2])
            except queue.Empty:
                pass
            except Exception as e:
                logger.error(f"Error handling day_started: {e}")

            # Check game_completed queue
            try:
                msg = signals.game_completed_queue.get_nowait()
                self._on_game_completed(msg[1])
            except queue.Empty:
                pass
            except Exception as e:
                logger.error(f"Error handling game_completed: {e}")

            # Check day_completed queue
            try:
                msg = signals.day_completed_queue.get_nowait()
                self._on_day_completed(msg[1], msg[2])
            except queue.Empty:
                pass
            except Exception as e:
                logger.error(f"Error handling day_completed: {e}")

            # Check GM assessment queue
            try:
                msg = signals.gm_assessment_queue.get_nowait()
                self._on_gm_assessment(msg[1])
            except queue.Empty:
                pass
            except Exception as e:
                logger.error(f"Error handling gm_assessment: {e}")

            # Check injury update queue
            try:
                msg = signals.injury_update_queue.get_nowait()
                self._on_injury_update(msg[1])
            except queue.Empty:
                pass
            except Exception as e:
                logger.error(f"Error handling injury_update: {e}")

            # Check play-by-play queue
            try:
                msg = signals.play_by_play_queue.get_nowait()
                self._on_play_by_play(msg[1])
            except queue.Empty:
                pass
            except Exception as e:
                logger.error(f"Error handling play_by_play: {e}")

            # Check world_series_started queue
            try:
                msg = signals.world_series_started_queue.get_nowait()
                self._on_world_series_started(msg[1])
            except queue.Empty:
                pass
            except Exception as e:
                logger.error(f"Error handling world_series_started: {e}")

            # Check world_series_completed queue
            try:
                msg = signals.world_series_completed_queue.get_nowait()
                self._on_world_series_completed(msg[1])
            except queue.Empty:
                pass
            except Exception as e:
                logger.error(f"Error handling world_series_completed: {e}")

            # Check season complete queue (regular season ended, prompt for playoffs)
            try:
                msg = signals.season_complete_queue.get_nowait()
                self._on_season_complete()
            except queue.Empty:
                pass
            except Exception as e:
                logger.error(f"Error handling season_complete: {e}")

            # Check simulation complete queue
            try:
                msg = signals.simulation_complete_queue.get_nowait()
                self._on_simulation_complete()
            except queue.Empty:
                pass
            except Exception as e:
                logger.error(f"Error handling simulation_complete: {e}")

            # Check error queue
            try:
                msg = signals.error_queue.get_nowait()
                self._on_error(msg[1])
            except queue.Empty:
                pass
            except Exception as e:
                logger.error(f"Error handling error: {e}")

        # Schedule next poll
        self.root.after(100, self._poll_queues)

    def _on_day_started(self, day_num: int, schedule_text: str):
        """Handle day_started message."""
        logger.debug(f"Day {day_num + 1} started")

        # Track current day for status messages (1-indexed for display)
        self.current_day = day_num + 1

        # Extract today's schedule from worker
        worker = self.controller.get_worker()
        if worker and worker.season:
            # Set the full season schedule on first day
            if day_num == 0:
                self.games_widget.set_season_schedule(worker.season.schedule)

            todays_games = worker.season.schedule[day_num]
            schedule = [(m[0], m[1]) for m in todays_games if 'OFF DAY' not in m]

            # Update games widget
            self.games_widget.on_day_started(day_num, schedule)

            # Update schedule widget
            self.schedule_widget.update_schedule(day_num, worker.season.schedule)

        # Update progress bar
        self.progress_bar['value'] = day_num + 1
        progress_pct = int((day_num + 1) / self.season_length * 100)
        self.progress_label.config(text=f"{progress_pct}%")
        self.day_label.config(text=f"Day: {day_num + 1} / {self.season_length}")

    def _on_game_completed(self, game_data: dict):
        """Handle game_completed message."""
        logger.debug(f"Game completed: {game_data['away_team']} @ {game_data['home_team']}")

        # Update games widget (progressive update)
        self.games_widget.on_game_completed(game_data)

        # If World Series is active, also send to playoff widget
        if hasattr(self, 'playoff_widget') and self.playoff_widget.ws_active:
            self.playoff_widget.add_game_result(game_data)

        # If there's a game_recap, add to games_played widget
        if game_data.get('game_recap') and game_data.get('day_num') is not None:
            self.games_played_widget.add_game_recap(
                game_data['day_num'],
                game_data['away_team'],
                game_data['home_team'],
                game_data['game_recap']
            )

    def _on_day_completed(self, game_results: list, standings_data: dict):
        """Handle day_completed message."""
        logger.debug(f"Day completed with {len(game_results)} non-followed games")

        # Update games widget (batch update for non-followed games)
        self.games_widget.on_day_completed(game_results, standings_data)

        # Update standings widget (but not during World Series to preserve regular season standings)
        if not self.world_series_active:
            worker = self.controller.get_worker()
            followed_team = worker.team_to_follow if worker else ''
            self.standings.set_followed_team(followed_team)
            self.standings.update_standings(standings_data, followed_team)

        # Update roster for followed team
        self._update_roster()

        # Update league stats and leaders
        self._update_league_stats()
        self._update_league_leaders()

        # Update status message based on actual controller pause state
        # This is called after the day completes, so the worker has updated its pause flag
        self._update_status_from_controller()

    def _on_gm_assessment(self, assessment_data: dict):
        """Handle gm_assessment_ready message."""
        team = assessment_data.get('team', 'Unknown')
        games = assessment_data.get('games_played', 0)
        wins = assessment_data.get('wins', 0)
        losses = assessment_data.get('losses', 0)
        games_back = assessment_data.get('games_back', 0.0)
        assessment = assessment_data.get('assessment', {})

        logger.info(f"GM assessment ready for {team} at {games} games")

        # Display in GM assessment widget
        self.gm_assessment_widget.display_assessment(
            team, games, wins, losses, games_back, assessment
        )

    def _on_injury_update(self, injury_list: list):
        """Handle injury_update message."""
        logger.debug(f"Injury update: {len(injury_list)} injured players")

        # Update injuries widget
        self.injuries_widget.update_injuries(injury_list)

    def _on_season_complete(self):
        """Handle season_complete message (regular season ended, prompt for playoffs)."""
        logger.info("Regular season completed, prompting for playoffs")

        # Ask user if they want to run playoffs
        response = messagebox.askyesno(
            "Regular Season Complete",
            "The 162-game regular season is complete!\n\n"
            "Would you like to run the World Series playoffs?",
            icon='question'
        )

        if response:  # Yes
            logger.info("User chose to run World Series")
            self.controller.worker.run_playoffs()
        else:  # No
            logger.info("User chose to skip World Series")
            self.controller.worker.skip_playoffs()

    def _on_simulation_complete(self):
        """Handle simulation_complete message."""
        logger.info("Season simulation completed")
        self.toolbar.update_button_states(simulation_running=False, paused=False)
        self.status_label.config(text=self._format_status_with_day("Season complete!"))
        messagebox.showinfo("Season Complete",
                          "The season simulation has completed successfully.")

    def _on_error(self, error_message: str):
        """Handle error_occurred message."""
        logger.error(f"Simulation error: {error_message}")
        messagebox.showerror("Simulation Error", error_message)
        self.toolbar.update_button_states(simulation_running=False, paused=False)
        self.status_label.config(text=self._format_status_with_day("Error occurred"))

    def _on_play_by_play(self, play_data: dict):
        """Handle play_by_play message."""
        # Forward play-by-play to playoff widget if World Series is active
        if hasattr(self, 'playoff_widget'):
            self.playoff_widget.add_play_by_play(play_data)

    def _on_world_series_started(self, ws_data: dict):
        """Handle world_series_started message."""
        logger.info(f"World Series started: {ws_data.get('al_winner')} vs {ws_data.get('nl_winner')}")

        # Set World Series flag and save current standings
        self.world_series_active = True
        # Standings are already displayed, no need to save/restore

        # Switch to Playoffs tab
        for i in range(self.notebook.index('end')):
            if self.notebook.tab(i, 'text') == 'Playoffs':
                self.notebook.select(i)
                break

        # Update playoff widget
        if hasattr(self, 'playoff_widget'):
            self.playoff_widget.world_series_started(ws_data)

    def _on_world_series_completed(self, ws_data: dict):
        """Handle world_series_completed message."""
        logger.info(f"World Series completed: {ws_data.get('champion')} wins!")

        # Clear World Series flag (regular season standings remain displayed)
        self.world_series_active = False

        # Update playoff widget
        if hasattr(self, 'playoff_widget'):
            self.playoff_widget.world_series_completed(ws_data)

        # Show championship message
        messagebox.showinfo(
            "World Series Complete",
            f"🏆 {ws_data.get('champion')} wins the World Series! 🏆"
        )

    # =================================================================
    # HELPER METHODS
    # =================================================================

    def _format_status_with_day(self, message: str) -> str:
        """
        Format a status message to include current day information.

        Args:
            message: Base status message

        Returns:
            Formatted message with day info (e.g., "Simulating day 11 - Simulation paused")
        """
        if self.current_day > 0:
            return f"Simulating day {self.current_day} - {message}"
        return message

    def _update_status_from_controller(self):
        """
        Update status message based on actual controller pause state.

        This is called after each day starts to reflect whether the simulation
        is actively running or has paused (e.g., after completing a step operation).
        """
        if self.controller.is_paused():
            self.status_label.config(text=self._format_status_with_day("Simulation paused"))
        else:
            self.status_label.config(text=self._format_status_with_day("Simulating..."))

    def _update_roster(self):
        """Update roster widget for followed team."""
        worker = self.controller.get_worker()
        if worker and worker.season:
            self.roster_widget.update_roster(
                self.season_team_to_follow,
                worker.season.baseball_data
            )

    def _update_league_stats(self):
        """Update league stats widget with current season data."""
        worker = self.controller.get_worker()
        if worker and worker.season:
            self.league_stats_widget.update_stats(worker.season.baseball_data)

    def _update_league_leaders(self):
        """Update league leaders widget with current season data."""
        worker = self.controller.get_worker()
        if worker and worker.season:
            # Pass current_day as games_played for PA/IP minimum calculations
            self.league_leaders_widget.update_leaders(
                worker.season.baseball_data,
                games_played=self.current_day
            )

    def _populate_injuries_teams(self):
        """Populate injuries team dropdown with all teams."""
        worker = self.controller.get_worker()
        if worker and worker.season:
            try:
                all_teams = worker.season.baseball_data.get_all_team_names()
                self.injuries_widget.populate_team_filter(all_teams)
                logger.debug(f"Populated injury team filter with {len(all_teams)} teams")
            except Exception as e:
                logger.error(f"Error populating injury teams: {e}")

    def on_close(self):
        """Handle window close event."""
        logger.info("Closing main window")
        self.root.destroy()
