# Signal/Callback Flow Reference

## Architecture Overview

The simulation runs on a background thread (`SeasonWorker`) while the Tkinter UI
runs on the main thread. All communication uses `queue.Queue` objects, which are
thread-safe by design.

```
SeasonWorker (background)              SeasonMainWindow (main thread)
        |                                       |
        | emit_day_started(day, text) ------->  |
        | emit_game_completed(data) --------->  |  (one per followed game)
        | emit_day_completed(results,  ------>  |  (batch: all games + standings)
        |                      standings,       |
        |                      day_num)         |
        | emit_injury_update(list) ---------->  |
        | emit_gm_assessment(data) ---------->  |
        |                                       |
        | <---- emit_day_processed(day) ------- |  (handshake: UI is done)
        |                                       |
        | BLOCKS on day_processed_queue         |
        | until UI confirms processing          |
```

## All Queues (13 total)

| Queue | Direction | Purpose |
|-------|-----------|---------|
| `day_started_queue` | Worker → UI | New simulation day began |
| `day_completed_queue` | Worker → UI | All games for a day finished (batch) |
| `game_completed_queue` | Worker → UI | Single followed-team game finished |
| `gm_assessment_queue` | Worker → UI | AI GM assessment ready |
| `injury_update_queue` | Worker → UI | Updated injured player list |
| `season_complete_queue` | Worker → UI | Regular season ended |
| `simulation_complete_queue` | Worker → UI | Entire simulation finished |
| `error_queue` | Worker → UI | Unhandled exception |
| `play_by_play_queue` | Worker → UI | Real-time play-by-play text |
| `world_series_started_queue` | Worker → UI | World Series begins |
| `world_series_completed_queue` | Worker → UI | World Series ends |
| `pause_state_queue` | Worker → UI | Pause state transition |
| `day_processed_queue` | **UI → Worker** | UI finished processing a day (handshake) |

## Signal Formats

All signals are tuples: `(signal_name, *payload)`

### Day Lifecycle

```
day_started:     ("day_started", day_number: int, schedule_text: str)
game_completed:  ("game_completed", game_data: dict)
day_completed:   ("day_completed", game_results: list[dict], standings_data: dict, day_number: int)
```

`game_data` dict:
```python
{
    "away_team": str, "home_team": str,
    "away_r": int, "home_r": int,     # runs
    "away_h": int, "home_h": int,     # hits
    "away_e": int, "home_e": int,     # errors
    "game_recap": str,
    "day_num": int,
    "structured_game": object | None,
    "is_playoff": bool                 # optional, for playoff games
}
```

### Other Signals

```
gm_assessment:     ("gm_assessment", dict)       # team, games_played, wins, losses, assessment
injury_update:     ("injury_update", list[dict])  # player, team, position, injury, days_remaining
season_complete:   ("season_complete",)            # no payload
simulation_complete: ("simulation_complete",)      # no payload
error:             ("error", error_message: str)
play_by_play:      ("play_by_play", dict)          # away_team, home_team, text, day_num, ws_game_num
world_series_started:    ("world_series_started", dict)    # al_winner, nl_winner, season
world_series_completed:  ("world_series_completed", dict)  # champion, season, series_result
pause_state:       ("pause_state", state: str)     # "running", "pausing", "paused"
day_processed:     ("day_processed", day_number: int)      # UI → Worker handshake
```

## Per-Day Flow

1. Worker calls `season.sim_next_day()`
2. `sim_next_day()` calls `sim_day_threaded()` which:
   - Emits `day_started(day_num, schedule_text)`
   - Simulates all games, emitting `game_completed(data)` for each followed game
   - Emits `day_completed(game_results, standings, day_num)` as a batch
   - Emits `injury_update(injury_list)`
   - Emits `gm_assessment(data)` if assessments are due
3. Worker blocks on `day_processed_queue.get(timeout=30)`
4. Main thread's `_poll_queues()` (every 100ms) drains all queued signals
5. After processing `day_completed`, main thread emits `day_processed(day_num)`
6. Worker receives `day_processed`, unblocks, proceeds to next day

## Queue Polling (Main Thread)

`_poll_queues()` is called every 100ms via `root.after(100, self._poll_queues)`.
Each queue is checked with `get_nowait()` (non-blocking). Only one message is
processed per queue per cycle, providing natural throttling.

```
_poll_queues() polls in this order:
  1. day_started_queue
  2. game_completed_queue
  3. day_completed_queue      ← emits day_processed back to worker
  4. gm_assessment_queue
  5. injury_update_queue
  6. play_by_play_queue
  7. world_series_started_queue
  8. world_series_completed_queue
  9. season_complete_queue
  10. simulation_complete_queue
  11. error_queue
  12. pause_state_queue
```

## Pause/Resume

Uses `threading.Event` for blocking and `threading.Lock` for atomic flag changes:

1. Main thread calls `worker.pause()` → sets `_paused=True`, emits `"pausing"`
2. Worker checks `_handle_pause()` each iteration, clears `_pause_event`, emits `"paused"`
3. Worker blocks on `_pause_event.wait()`
4. Main thread calls `worker.resume()` → clears `_paused`, sets `_pause_event`
5. Worker unblocks, emits `"running"`

Step mode (`step_one_day()`, `step_n_days()`) sets `_step_mode=True` and
`_step_count=N`. After each day, `_step_count` decrements. When it reaches
zero, the worker pauses automatically.

## World Series Transition

When `world_series_started` arrives:
1. Sets `world_series_active=True` and records participating teams
2. **Drains** the `play_by_play_queue` of stale regular-season events
3. Switches to the Playoffs tab
4. While `world_series_active=True`, `day_started` and `day_completed` handlers
   return early to avoid overwriting playoff displays

When `world_series_completed` arrives:
1. Sets `world_series_active=False`
2. **Intentionally keeps** `world_series_teams` set so late-arriving play-by-play
   events (queued before the series ended) can still be processed

## Direct Cross-Thread Access

`signals.main_window` is a direct reference to `SeasonMainWindow`, set at
startup in `main_window_tk.py`. Used **only** in
`UIBaseballSeason._create_signal_output_handler()` to synchronously set
`world_series_active` and `world_series_teams` from the worker thread. This
is the only place where the worker writes directly to the main window object.

## Error Handling

Every queue poll is wrapped in `try/except` blocks. If one malformed signal
fails to process, other queues continue to be checked. The `game_completed`
handler logs full tracebacks for debugging.

The worker's `run()` method catches all exceptions and emits an `error` signal
before the thread exits, ensuring the UI is notified of failures.
