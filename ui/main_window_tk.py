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
    GMAssessmentWidget
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

        self.root.title("Baseball Season Simulator")
        self.root.geometry("1500x900")

        # Create simulation controller
        self.controller = SimulationController(
            load_seasons, new_season, rotation_len, series_length,
            season_length, season_chatty, season_print_lineup_b,
            season_print_box_score_b
        )

        # Create widgets
        self._create_toolbar()
        self._create_main_content()
        self._create_status_bar()

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
        self.games_widget = GamesWidget(self.notebook)
        self.notebook.add(self.games_widget.get_frame(), text="Today's Games")

        # Tab 2: Schedule
        self.schedule_widget = ScheduleWidget(self.notebook)
        self.notebook.add(self.schedule_widget.get_frame(), text="Schedule")

        # Tab 3: League IL
        self.injuries_widget = InjuriesWidget(self.notebook)
        self.notebook.add(self.injuries_widget.get_frame(), text="League IL")

        # Tab 4: Team Tab with nested sub-tabs
        team_tab_frame = tk.Frame(self.notebook)
        self.notebook.add(team_tab_frame, text=self.season_team_to_follow)

        # Create inner notebook for team sub-tabs
        team_notebook = ttk.Notebook(team_tab_frame)
        team_notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Sub-tab 1: Roster
        self.roster_widget = RosterWidget(team_notebook)
        team_notebook.add(self.roster_widget.get_frame(), text="Roster")

        # Sub-tab 2: Games Played
        self.games_played_widget = GamesPlayedWidget(team_notebook)
        team_notebook.add(self.games_played_widget.get_frame(), text="Games Played")

        # Sub-tab 3: GM Assessment
        self.gm_assessment_widget = GMAssessmentWidget(team_notebook, self.run_gm_assessments)
        team_notebook.add(self.gm_assessment_widget.get_frame(), text="GM Assessment")

        # Tab 5: Admin (Player Management)
        self.admin_widget = AdminWidget(self.notebook, self.controller.get_worker)
        self.notebook.add(self.admin_widget.get_frame(), text="Admin")

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

    # =================================================================
    # SIMULATION CONTROL METHODS
    # =================================================================

    def start_season(self):
        """Start the season simulation."""
        selected_team = self.toolbar.get_selected_team()

        def on_started():
            """Callback after worker starts."""
            # Reset progress indicators
            self.progress_bar['value'] = 0
            self.progress_label.config(text="0%")
            self.day_label.config(text="Day: 0 / 162")

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
            self.root.after(2000, self.gm_assessment_widget.enable_button)

            # Update UI state
            self.toolbar.update_button_states(simulation_running=True, paused=False)
            self.status_label.config(text="Simulation started...")

        if self.controller.start_season(selected_team, on_started):
            logger.info(f"Season started for team: {selected_team}")

    def pause_season(self):
        """Pause the simulation."""
        if self.controller.pause_season():
            self.toolbar.update_button_states(simulation_running=True, paused=True)
            self.status_label.config(text="Simulation paused")

    def resume_season(self):
        """Resume the simulation from paused state."""
        if self.controller.resume_season():
            self.toolbar.update_button_states(simulation_running=True, paused=False)
            self.status_label.config(text="Simulation resumed")

    def next_day(self):
        """Advance exactly one day, then pause."""
        if self.controller.next_day():
            # Keep paused state - simulation will auto-pause after stepping
            self.toolbar.update_button_states(simulation_running=True, paused=True)
            self.status_label.config(text="Advancing one day...")

    def next_series(self):
        """Advance exactly three days (one series), then pause."""
        if self.controller.next_series():
            # Keep paused state - simulation will auto-pause after stepping
            self.toolbar.update_button_states(simulation_running=True, paused=True)
            self.status_label.config(text="Advancing 3 days (series)...")

    def next_week(self):
        """Advance exactly seven days (one week), then pause."""
        if self.controller.next_week():
            # Keep paused state - simulation will auto-pause after stepping
            self.toolbar.update_button_states(simulation_running=True, paused=True)
            self.status_label.config(text="Advancing 7 days (week)...")

    def run_gm_assessments(self):
        """Force all teams to run GM assessments immediately."""
        self.controller.run_gm_assessments(lambda msg: self.status_label.config(text=msg))

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
                # Not used in current implementation (game_recap in game_completed)
            except queue.Empty:
                pass
            except Exception as e:
                logger.error(f"Error handling play_by_play: {e}")

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

        # Extract today's schedule from worker
        worker = self.controller.get_worker()
        if worker and worker.season:
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

        # Update standings widget
        worker = self.controller.get_worker()
        followed_team = worker.team_to_follow if worker else ''
        self.standings.set_followed_team(followed_team)
        self.standings.update_standings(standings_data, followed_team)

        # Update roster for followed team
        self._update_roster()

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

    def _on_simulation_complete(self):
        """Handle simulation_complete message."""
        logger.info("Season simulation completed")
        self.toolbar.update_button_states(simulation_running=False, paused=False)
        self.status_label.config(text="Season complete!")
        messagebox.showinfo("Season Complete",
                          "The season simulation has completed successfully.")

    def _on_error(self, error_message: str):
        """Handle error_occurred message."""
        logger.error(f"Simulation error: {error_message}")
        messagebox.showerror("Simulation Error", error_message)
        self.toolbar.update_button_states(simulation_running=False, paused=False)
        self.status_label.config(text="Error occurred")

    # =================================================================
    # HELPER METHODS
    # =================================================================

    def _update_roster(self):
        """Update roster widget for followed team."""
        worker = self.controller.get_worker()
        if worker and worker.season:
            self.roster_widget.update_roster(
                self.season_team_to_follow,
                worker.season.baseball_data
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
