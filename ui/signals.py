"""
Queue-based signaling for thread-safe communication between SeasonWorker and UI.

Uses Python's queue.Queue instead of Qt signals for tkinter compatibility.
The worker thread puts messages on queues, and the UI thread polls them.
"""

import queue
from typing import Any, Dict, List, Optional


class SeasonSignals:
    """
    Queue-based signal system for season simulation events.

    Instead of Qt signals, we use separate queues for each event type.
    The worker thread puts tuples on these queues, and the UI thread
    polls them periodically using tkinter's after() method.
    """

    def __init__(self):
        """Initialize all event queues."""
        # Day lifecycle queues
        self.day_started_queue = queue.Queue()
        # Message format: (day_number: int, schedule_text: str)

        self.day_completed_queue = queue.Queue()
        # Message format: (game_results: list, standings_data: dict)

        self.game_completed_queue = queue.Queue()
        # Message format: (game_data: dict)

        # AI GM Assessment queue
        self.gm_assessment_queue = queue.Queue()
        # Message format: (assessment_data: dict)

        # Injury tracking queue
        self.injury_update_queue = queue.Queue()
        # Message format: (injury_list: list)

        # Simulation lifecycle queues
        self.simulation_complete_queue = queue.Queue()
        # Message format: (None,) - just a signal flag

        self.error_queue = queue.Queue()
        # Message format: (error_message: str)

    def emit_day_started(self, day_number: int, schedule_text: str):
        """
        Emit day_started signal.

        Args:
            day_number (int): Current day number (0-indexed)
            schedule_text (str): Formatted schedule text for the day
        """
        self.day_started_queue.put(('day_started', day_number, schedule_text))

    def emit_day_completed(self, game_results: List[Dict], standings_data: Dict):
        """
        Emit day_completed signal.

        Args:
            game_results (list): List of game result dicts for non-followed teams
            standings_data (dict): Current standings
        """
        self.day_completed_queue.put(('day_completed', game_results, standings_data))

    def emit_game_completed(self, game_data: Dict):
        """
        Emit game_completed signal.

        Args:
            game_data (dict): Game data for a followed team
        """
        self.game_completed_queue.put(('game_completed', game_data))

    def emit_gm_assessment_ready(self, assessment_data: Dict):
        """
        Emit gm_assessment_ready signal.

        Args:
            assessment_data (dict): GM assessment data
        """
        self.gm_assessment_queue.put(('gm_assessment', assessment_data))

    def emit_injury_update(self, injury_list: List[Dict]):
        """
        Emit injury_update signal.

        Args:
            injury_list (list): List of injury dicts
        """
        self.injury_update_queue.put(('injury_update', injury_list))

    def emit_simulation_complete(self):
        """Emit simulation_complete signal."""
        self.simulation_complete_queue.put(('simulation_complete',))

    def emit_error(self, error_message: str):
        """
        Emit error_occurred signal.

        Args:
            error_message (str): Human-readable error description
        """
        self.error_queue.put(('error', error_message))
