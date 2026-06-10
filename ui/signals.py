"""
Copyright (c) 2024 Jim Maastricht

Queue-based signaling for thread-safe communication between SeasonWorker and UI.

ARCHITECTURE OVERVIEW
=====================

The simulation runs on a background thread (SeasonWorker) while the Tkinter UI
runs on the main thread. All communication uses queue.Queue objects, which are
thread-safe by design.

    SeasonWorker (background)          SeasonMainWindow (main thread)
            |                                   |
            |  emit_day_started(day, text) ---> |
            |  emit_game_completed(data) -----> |   (one per followed game)
            |  emit_day_completed(results,  --> |   (batch: all games + standings)
            |                       standings,  |
            |                       day_num)    |
            |  emit_injury_update(list) ------> |
            |  emit_gm_assessment(data) ------> |
            |                                   |
            |  <--- emit_day_processed(day) --- |   (handshake: UI is done)
            |                                   |
            |  BLOCKS on day_processed_queue    |
            |  until UI confirms processing     |

SIGNAL FLOW PER DAY
====================

1. Worker calls season.sim_next_day()
2. sim_next_day() calls sim_day_threaded() which:
   a. Emits day_started(day_num, schedule_text)
   b. Simulates all games, emitting game_completed(data) for each followed game
   c. Emits day_completed(game_results, standings, day_num) as a batch
   d. Emits injury_update(injury_list)
   e. Emits gm_assessment(data) if assessments are due
3. Worker blocks on day_processed_queue.get(timeout=30)
4. Main thread's _poll_queues() (called every 100ms) drains all queued signals
5. After processing day_completed, main thread emits day_processed(day_num)
6. Worker receives day_processed, unblocks, proceeds to next day

LIFECYCLE SIGNALS
=================

- season_complete: Regular season ended, playoffs will start (emitted by worker)
- simulation_complete: Entire sim finished including playoffs (emitted by worker)
- world_series_started: World Series begins (emitted by UIBaseballSeason output_handler)
- world_series_completed: World Series ends (emitted by UIBaseballSeason output_handler)
- error: Unhandled exception in worker thread (emitted by worker)
- pause_state: "running", "pausing", or "paused" (emitted by worker)

PAUSE/RESUME
============

Uses threading.Event for blocking and threading.Lock for atomic flag changes:

- Main thread calls worker.pause() -> sets _paused=True, emits "pausing"
- Worker checks _handle_pause() each iteration, clears _pause_event, emits "paused"
- Worker blocks on _pause_event.wait()
- Main thread calls worker.resume() -> clears _paused, sets _pause_event
- Worker unblocks, emits "running"

DIRECT ACCESS (CROSS-THREAD)
=============================

signals.main_window is a direct reference to SeasonMainWindow, set at startup.
Used ONLY in UIBaseballSeason._create_signal_output_handler() to synchronously
set world_series_active and world_series_teams from the worker thread. This is
the only place where the worker writes directly to the main window object.
"""

import queue
from typing import Dict, List


class SeasonSignals:
    """Queue-based signal system for season simulation events."""

    def __init__(self):
        """Initialize all event queues."""
        self.main_window = None  # Will be set by main window for direct synchronous access

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
        self.season_complete_queue = queue.Queue()
        # Message format: (None,) - signals regular season ended, asking about playoffs

        self.simulation_complete_queue = queue.Queue()
        # Message format: (None,) - just a signal flag

        self.error_queue = queue.Queue()
        # Message format: (error_message: str)

        self.play_by_play_queue = queue.Queue()
        # Message format: (play_data: dict)

        # World Series queues
        self.world_series_started_queue = queue.Queue()
        # Message format: (ws_data: dict) with keys: al_winner, nl_winner, season, al_record, nl_record

        self.world_series_completed_queue = queue.Queue()
        # Message format: (ws_data: dict) with keys: champion, season, series_result

        # Pause state queue
        self.pause_state_queue = queue.Queue()
        # Message format: (pause_state: str) - "running", "pausing", "paused"

        # Day processed queue - UI signals back to worker after draining all signals for a day
        self.day_processed_queue = queue.Queue()
        # Message format: (day_number: int) - signals worker that UI has processed all signals for this day

    def emit_day_started(self, day_number: int, schedule_text: str):
        """Emit day_started signal."""
        self.day_started_queue.put(("day_started", day_number, schedule_text))

    def emit_day_completed(self, game_results: List[Dict], standings_data: Dict, day_number: int):
        """Emit day_completed signal."""
        self.day_completed_queue.put(("day_completed", game_results, standings_data, day_number))

    def emit_game_completed(self, game_data: Dict):
        """Emit game_completed signal."""
        self.game_completed_queue.put(("game_completed", game_data))

    def emit_gm_assessment_ready(self, assessment_data: Dict):
        """Emit gm_assessment_ready signal."""
        self.gm_assessment_queue.put(("gm_assessment", assessment_data))

    def emit_injury_update(self, injury_list: List[Dict]):
        """Emit injury_update signal."""
        self.injury_update_queue.put(("injury_update", injury_list))

    def emit_season_complete(self):
        """Emit season_complete signal (regular season ended, before playoffs)."""
        self.season_complete_queue.put(("season_complete",))

    def emit_simulation_complete(self):
        """Emit simulation_complete signal."""
        self.simulation_complete_queue.put(("simulation_complete",))

    def emit_error(self, error_message: str):
        """Emit error_occurred signal."""
        self.error_queue.put(("error", error_message))

    def emit_play_by_play(self, play_data: Dict):
        """Emit play_by_play signal."""
        self.play_by_play_queue.put(("play_by_play", play_data))

    def emit_world_series_started(self, ws_data: Dict):
        """Emit world_series_started signal."""
        self.world_series_started_queue.put(("world_series_started", ws_data))

    def emit_world_series_completed(self, ws_data: Dict):
        """Emit world_series_completed signal."""
        self.world_series_completed_queue.put(("world_series_completed", ws_data))

    def emit_pause_state(self, state: str):
        """Emit pause_state signal."""
        self.pause_state_queue.put(("pause_state", state))

    def emit_day_processed(self, day_number: int):
        """Emit day_processed signal - UI signals back after draining all signals for a day."""
        self.day_processed_queue.put(("day_processed", day_number))
