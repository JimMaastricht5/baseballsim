"""
--- Copyright Notice ---
Copyright (c) 2024 Jim Maastricht

Simulation controller for baseball season simulation UI.

Manages SeasonWorker lifecycle and simulation state.
"""

import tkinter as tk
from tkinter import messagebox
from typing import Callable, Optional
from ui.season_worker import SeasonWorker
from bblogger import logger


class SimulationController:
    """
    Controller for managing season simulation lifecycle.

    Responsibilities:
    - Create and start SeasonWorker
    - Control simulation (pause, resume, step)
    - Manage simulation state
    - Coordinate initialization callbacks
    """

    def __init__(self, load_seasons: list, new_season: int, rotation_len: int,
                 series_length: int, season_length: int, season_chatty: bool,
                 season_print_lineup_b: bool, season_print_box_score_b: bool):
        """
        Initialize simulation controller.

        Args:
            load_seasons: Years to load stats from
            new_season: Season year to simulate
            rotation_len: Pitcher rotation length
            series_length: Games per series
            season_length: Games per team
            season_chatty: Verbose output flag
            season_print_lineup_b: Print lineup flag
            season_print_box_score_b: Print box score flag
        """
        self.load_seasons = load_seasons
        self.new_season = new_season
        self.rotation_len = rotation_len
        self.series_length = series_length
        self.season_length = season_length
        self.season_chatty = season_chatty
        self.season_print_lineup_b = season_print_lineup_b
        self.season_print_box_score_b = season_print_box_score_b

        self.worker: Optional[SeasonWorker] = None

    def start_season(self, selected_team: str,
                    on_started_callback: Optional[Callable] = None) -> bool:
        """
        Start the season simulation.

        Args:
            selected_team: Team abbreviation to follow
            on_started_callback: Optional callback after worker starts

        Returns:
            bool: True if started successfully, False otherwise
        """
        if self.worker and self.worker.is_alive():
            messagebox.showwarning("Already Running",
                                   "A season simulation is already running.")
            return False

        if not selected_team:
            messagebox.showwarning("No Team Selected",
                                   "Please select a team to follow before starting.")
            return False

        logger.info(f"Starting season simulation, following team: {selected_team}")

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
            selected_team
        )

        # Start worker thread
        self.worker.daemon = True  # Thread will exit when main program exits
        self.worker.start()

        # Call callback if provided
        if on_started_callback:
            on_started_callback()

        return True

    def pause_season(self) -> bool:
        """
        Pause the simulation.

        Returns:
            bool: True if paused successfully, False otherwise
        """
        if self.worker and self.worker.is_alive():
            logger.info("Pausing simulation")
            self.worker.pause()
            return True
        return False

    def resume_season(self) -> bool:
        """
        Resume the simulation from paused state.

        Returns:
            bool: True if resumed successfully, False otherwise
        """
        if self.worker and self.worker.is_alive():
            logger.info("Resuming simulation")
            self.worker.resume()
            return True
        return False

    def next_day(self) -> bool:
        """
        Advance exactly one day, then pause.

        Returns:
            bool: True if stepped successfully, False otherwise
        """
        if self.worker and self.worker.is_alive():
            logger.info("Advancing one day")
            self.worker.step_one_day()
            return True
        return False

    def next_series(self) -> bool:
        """
        Advance exactly three days (one series), then pause.

        Returns:
            bool: True if stepped successfully, False otherwise
        """
        if self.worker and self.worker.is_alive():
            logger.info("Advancing three days (series)")
            self.worker.step_n_days(3)
            return True
        return False

    def next_week(self) -> bool:
        """
        Advance exactly seven days (one week), then pause.

        Returns:
            bool: True if stepped successfully, False otherwise
        """
        if self.worker and self.worker.is_alive():
            logger.info("Advancing seven days (week)")
            self.worker.step_n_days(7)
            return True
        return False

    def run_gm_assessments(self, status_callback: Optional[Callable[[str], None]] = None) -> bool:
        """
        Force all teams to run GM assessments immediately.

        Args:
            status_callback: Optional callback to update status message

        Returns:
            bool: True if assessments ran successfully, False otherwise
        """
        if self.worker and self.worker.season:
            logger.info("Running forced GM assessments for all teams")
            try:
                # Call check_gm_assessments with force=True
                self.worker.season.check_gm_assessments(force=True)
                if status_callback:
                    status_callback("GM assessments completed")
                return True
            except Exception as e:
                logger.error(f"Error running GM assessments: {e}")
                messagebox.showerror("Error", f"Failed to run GM assessments: {e}")
                return False
        else:
            messagebox.showwarning("Warning", "Simulation must be started before running GM assessments.")
            return False

    def get_worker(self) -> Optional[SeasonWorker]:
        """
        Get the current worker instance.

        Returns:
            Optional[SeasonWorker]: Worker instance or None
        """
        return self.worker

    def is_running(self) -> bool:
        """
        Check if simulation is running.

        Returns:
            bool: True if worker is alive
        """
        return self.worker is not None and self.worker.is_alive()

    def is_paused(self) -> bool:
        """
        Check if simulation is paused.

        Returns:
            bool: True if worker is paused
        """
        return self.worker is not None and self.worker._paused
