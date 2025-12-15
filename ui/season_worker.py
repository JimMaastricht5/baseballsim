"""
--- Copyright Notice ---
Copyright (c) 2024 Jim Maastricht

Worker thread for running baseball season simulation.

This threading.Thread wraps the BaseballSeason simulation, running it in a
background thread and putting messages on queues to update the UI.
"""

import threading

from ui.signals import SeasonSignals
from ui.ui_baseball_season import UIBaseballSeason
from bblogger import logger


class SeasonWorker(threading.Thread):
    """
    Background worker thread for season simulation.

    Runs the baseball season simulation in a separate thread from the UI,
    putting messages on queues for all state changes. Supports pause/resume and
    day-by-day stepping controls.

    Attributes:
        signals (SeasonSignals): Queue-based signal emitter for UI updates
        season: BaseballSeason instance (None until run())
        _paused (bool): Pause flag
        _step_mode (bool): Single-step mode flag
        _stopped (bool): Stop flag for termination
        _pause_lock (threading.Lock): Lock for pause state synchronization
        _pause_event (threading.Event): Event for waiting when paused
    """

    def __init__(self, load_seasons=None, new_season=2026,
                rotation_len=5, series_length=3, season_length=162, season_chatty=False,
                season_print_lineup_b=False, season_print_box_score_b=False,
                team_to_follow=None):
        """
        Initialize season worker with simulation parameters.

        Args:
            load_seasons (list): Years to load stats from (e.g., [2023, 2024, 2025])
            new_season (int): Season year to simulate
            team_to_follow (list): Teams to follow in detail (e.g., ['NYM', 'LAD'])
            rotation_len (int): Pitcher rotation length (default 5)
            season_length (int): Number of games per team (default 162)
        """
        super().__init__()

        # Store simulation parameters
        self.load_seasons = load_seasons or [2023, 2024, 2025]
        self.new_season = new_season
        self.team_to_follow = team_to_follow or []
        self.random_data = False
        self.rotation_len = rotation_len
        self.series_length = series_length
        self.num_games = season_length
        self.season_chatty = season_chatty
        self.season_print_lineup_b = season_print_lineup_b
        self.season_print_box_score_b = season_print_box_score_b
        self.only_nl_b = False

        # Create signal emitter
        self.signals = SeasonSignals()

        # Season instance (created in run())
        self.season = None

        # Control flags
        self._paused = False
        self._step_mode = False
        self._stopped = False

        # Synchronization primitives for pause/resume
        self._pause_lock = threading.Lock()
        self._pause_event = threading.Event()
        self._pause_event.set()  # Initially not paused

    def run(self):
        """
        Main thread execution method.

        Runs the season simulation loop, checking pause/step flags and
        emitting signals for UI updates. This method runs in the worker
        thread, not the main UI thread.
        """
        try:
            logger.info(f"Starting season simulation: {self.new_season}")

            # Create UIBaseballSeason instance
            # This will handle all signal emission through overridden methods
            self.season = UIBaseballSeason(
                signals=self.signals,
                load_seasons=self.load_seasons,
                new_season=self.new_season,
                team_list=None,  # Use all teams
                season_length=self.num_games,
                series_length=self.series_length,  # Standard 3-game series
                rotation_len=self.rotation_len,
                include_leagues=None if not self.only_nl_b else ['NL'],
                season_print_lineup_b=self.season_print_lineup_b,  # Suppress console output
                season_print_box_score_b=self.season_print_box_score_b,  # Suppress console output
                season_chatty=self.season_chatty,  # Suppress verbose output
                season_team_to_follow=self.team_to_follow,
                load_batter_file='aggr-stats-pp-Batting.csv',
                load_pitcher_file='aggr-stats-pp-Pitching.csv',
                schedule=None  # Let it generate schedule
            )

            # Call sim_start for initialization
            self.season.sim_start()

            # Simulation loop
            total_days = len(self.season.schedule)
            logger.info(f"Season has {total_days} days scheduled")

            while self.season.season_day_num < total_days:
                # Check if stopped
                if self._stopped:
                    logger.info("Season simulation stopped by user")
                    break

                # Handle pause
                self._handle_pause()

                # sim_next_day() will:
                # 1. Call sim_day_threaded() which emits day_started, runs games, emits game_completed/day_completed, emits injury_update
                # 2. Call print_standings() (suppressed)
                # 3. Call check_gm_assessments() which emits gm_assessment_ready
                # 4. Increment season_day_num
                self.season.sim_next_day()
                logger.debug(f"Completed day {self.season.season_day_num}")

                # If in step mode, pause after this day
                if self._step_mode:
                    self._step_mode = False
                    self._paused = True

            # Season complete
            if not self._stopped:
                self.season.sim_end()
                logger.info("Season simulation complete")
                self.signals.emit_simulation_complete()

        except Exception as e:
            error_msg = f"Error in season simulation: {str(e)}"
            logger.error(error_msg)
            import traceback
            logger.error(traceback.format_exc())
            self.signals.emit_error(error_msg)

    def _handle_pause(self):
        """
        Handle pause state by waiting on event.

        This method blocks the worker thread when paused until resume()
        or step_one_day() is called.
        """
        with self._pause_lock:
            if self._paused and not self._stopped:
                logger.debug("Worker thread paused, waiting...")
                self._pause_event.clear()

        # Wait outside the lock
        if self._paused and not self._stopped:
            self._pause_event.wait()
            logger.debug("Worker thread resumed")

    def pause(self):
        """
        Pause the simulation.

        Sets the pause flag. The worker will pause after completing the
        current day's simulation.
        """
        with self._pause_lock:
            self._paused = True
        logger.info("Pause requested")

    def resume(self):
        """
        Resume the simulation from paused state.

        Clears the pause flag and wakes the worker thread.
        """
        with self._pause_lock:
            self._paused = False
            self._pause_event.set()
        logger.info("Resume requested")

    def step_one_day(self):
        """
        Advance exactly one day, then pause.

        Useful for day-by-day stepping through the season.
        """
        with self._pause_lock:
            self._step_mode = True
            self._paused = False
            self._pause_event.set()
        logger.info("Step one day requested")

    def stop(self):
        """
        Stop the simulation entirely.

        Sets the stopped flag and resumes if paused. The worker thread
        will exit the simulation loop.
        """
        with self._pause_lock:
            self._stopped = True
            self._paused = False
            self._pause_event.set()
        logger.info("Stop requested")
