# UI Reference Guide for Claude

## Overview

The baseball sim UI is a **tkinter** application launched via `bbseason_ui.py` (project root).
The UI layer lives entirely under `ui/` and is decoupled from the simulation engine via a
queue-based signal system. The simulation runs on a **background thread**; the UI polls for
messages every 100 ms using `root.after()`.

---

## Entry Point: `bbseason_ui.py`

Two classes:

### `StartupDialog`
- Simple modal dialog shown at startup.
- User selects **team to follow** (30 MLB teams) and **number of games** (1–162).
- Returns `(confirmed, selected_team, num_games)` from `show()`.

### `main()`
- Creates `StartupDialog`, gets user selections.
- Creates `tk.Tk()` root window.
- Instantiates `SeasonMainWindow` from `ui/main_window_tk.py`.
- Binds `window.on_close` to the WM_DELETE_WINDOW protocol.
- Calls `root.mainloop()`.

---

## Main Window: `ui/main_window_tk.py` → `SeasonMainWindow`

Window size: 1500×900. Theme: baseball green inactive tabs, Dodger blue active tab.

### Layout (pack order matters)

```
root (tk.Tk)
├── ToolbarWidget          ← pack side=TOP
├── status_bar (Frame)     ← pack side=BOTTOM  [day label | progress bar | % label | status msg]
└── PanedWindow (BOTH+expand)
    ├── StandingsWidget    ← left panel (minsize=300, initial sash at 360px)
    └── notebook_frame
        └── ttk.Notebook
            ├── Tab: "Today's Games"  → GamesWidget
            ├── Tab: "Schedule"       → ScheduleWidget
            ├── Tab: "League"         → inner ttk.Notebook
            │   ├── Sub: "Leaders"    → LeagueLeadersWidget
            │   ├── Sub: "Stats"      → LeagueStatsWidget
            │   ├── Sub: "IL"         → InjuriesWidget
            │   └── Sub: "Admin"      → AdminWidget
            ├── Tab: "{team}"         → inner ttk.Notebook
            │   ├── Sub: "Roster"     → RosterWidget
            │   ├── Sub: "Games Played" → GamesPlayedWidget
            │   └── Sub: "GM Assessment" → GMAssessmentWidget
            └── Tab: "Playoffs"       → PlayoffWidget
```

### Key instance variables

| Variable | Purpose |
|---|---|
| `self.controller` | `SimulationController` — manages worker lifecycle |
| `self.toolbar` | `ToolbarWidget` — buttons + team dropdown |
| `self.standings` | `StandingsWidget` |
| `self.games_widget` | `GamesWidget` |
| `self.schedule_widget` | `ScheduleWidget` |
| `self.league_leaders_widget` | `LeagueLeadersWidget` |
| `self.league_stats_widget` | `LeagueStatsWidget` |
| `self.injuries_widget` | `InjuriesWidget` |
| `self.admin_widget` | `AdminWidget` |
| `self.roster_widget` | `RosterWidget` |
| `self.games_played_widget` | `GamesPlayedWidget` |
| `self.gm_assessment_widget` | `GMAssessmentWidget` |
| `self.playoff_widget` | `PlayoffWidget` |
| `self.comparison_mode` | `tk.StringVar("current"/"difference")` — shared by RosterWidget & LeagueStatsWidget |
| `self.current_day` | 1-indexed day counter for status bar formatting |
| `self.world_series_active` | Flag gating which widgets receive updates during playoffs |
| `self.world_series_teams` | `set` of two team abbreviations playing in WS |

### Simulation control methods (delegate to controller)

- `start_season()` — creates and starts `SeasonWorker`; sets up 1–2 second delayed initializations
- `pause_season()` / `resume_season()` — pass through to worker
- `next_day()` / `next_series()` / `next_week()` — step 1/3/7 days then auto-pause
- `run_gm_assessments()` — force immediate GM assessment for all teams

### Queue polling: `_poll_queues()` (called every 100 ms via `root.after`)

Polls 10 queues from `worker.signals` and dispatches to handler methods:

| Queue | Handler | Triggers |
|---|---|---|
| `day_started_queue` | `_on_day_started(day_num, schedule_text)` | GamesWidget, ScheduleWidget, progress bar |
| `game_completed_queue` | `_on_game_completed(game_data)` | GamesWidget (followed game), GamesPlayedWidget |
| `day_completed_queue` | `_on_day_completed(game_results, standings_data)` | GamesWidget (batch), StandingsWidget, RosterWidget, LeagueStatsWidget, LeagueLeadersWidget |
| `gm_assessment_queue` | `_on_gm_assessment(assessment_data)` | GMAssessmentWidget |
| `injury_update_queue` | `_on_injury_update(injury_list)` | InjuriesWidget |
| `play_by_play_queue` | `_on_play_by_play(play_data)` | PlayoffWidget (WS only) |
| `world_series_started_queue` | `_on_world_series_started(ws_data)` | Sets `world_series_active=True`, switches to Playoffs tab, PlayoffWidget |
| `world_series_completed_queue` | `_on_world_series_completed(ws_data)` | PlayoffWidget, messagebox |
| `season_complete_queue` | `_on_season_complete()` | (logs only; playoffs auto-run) |
| `simulation_complete_queue` | `_on_simulation_complete()` | Shows elapsed time, messagebox |

**World Series gating**: When `world_series_active=True`, `_on_day_started` and `_on_day_completed`
return early (no widget updates). `_on_game_completed` routes to `playoff_widget.add_game_result()`.
`_on_play_by_play` only forwards if both teams are in `world_series_teams`.

---

## Threading Architecture

### `ui/season_worker.py` → `SeasonWorker(threading.Thread)`

Runs simulation on a daemon background thread.

**Control flags:**
- `_paused` (bool) + `_pause_event` (threading.Event) — pause/resume
- `_step_mode` (bool) + `_step_count` (int) — step N days then auto-pause
- `_stopped` (bool) — terminate loop

**Public control methods:** `pause()`, `resume()`, `step_one_day()`, `step_n_days(n)`, `stop()`

**Run loop:**
1. Creates `UIBaseballSeason` instance.
2. Calls `season.sim_start()`.
3. Loops `season.sim_next_day()` until all days complete.
4. After regular season, auto-runs `season.run_world_series()` if eligible.
5. Emits `simulation_complete` signal.

### `ui/signals.py` → `SeasonSignals`

Thread-safe queue-based pub/sub. Each event type has its own `queue.Queue`.

**Emit methods** (called from worker thread):

| Method | Queue | Message format |
|---|---|---|
| `emit_day_started(day_num, text)` | `day_started_queue` | `('day_started', day_num, text)` |
| `emit_game_completed(game_data)` | `game_completed_queue` | `('game_completed', game_data_dict)` |
| `emit_day_completed(results, standings)` | `day_completed_queue` | `('day_completed', list, dict)` |
| `emit_gm_assessment_ready(data)` | `gm_assessment_queue` | `('gm_assessment', data_dict)` |
| `emit_injury_update(injury_list)` | `injury_update_queue` | `('injury_update', list)` |
| `emit_play_by_play(play_data)` | `play_by_play_queue` | `('play_by_play', data_dict)` |
| `emit_world_series_started(ws_data)` | `world_series_started_queue` | `('world_series_started', dict)` |
| `emit_world_series_completed(ws_data)` | `world_series_completed_queue` | `('world_series_completed', dict)` |
| `emit_season_complete()` | `season_complete_queue` | `('season_complete',)` |
| `emit_simulation_complete()` | `simulation_complete_queue` | `('simulation_complete',)` |
| `emit_error(msg)` | `error_queue` | `('error', msg)` |

**Special:** `signals.main_window` — direct reference set synchronously by main window
so `UIBaseballSeason.run_world_series()` can set `world_series_active=True` before
emitting the signal (avoids race condition).

### `ui/controllers/simulation_controller.py` → `SimulationController`

Owns the `SeasonWorker` instance. Methods:

- `start_season(team, callback)` → creates + starts worker, calls callback
- `pause_season()`, `resume_season()`, `next_day()`, `next_series()`, `next_week()` → delegate to worker
- `run_gm_assessments(callback)` → calls `season.check_gm_assessments(force=True)`
- `get_worker()` → returns worker instance
- `is_running()`, `is_paused()` → worker state queries

---

## UI-Aware Season: `ui/ui_baseball_season.py` → `UIBaseballSeason`

Subclass of `bbseason.BaseballSeason`. Minimal overrides:

| Overridden method | Purpose |
|---|---|
| `__init__` | Injects `output_handler` and `play_by_play_callback_factory` into parent |
| `sim_day_threaded(day_num)` | Emits `day_started`, calls super, emits `injury_update` |
| `_process_and_print_game_results(results)` | Emits `game_completed` (followed) or batches for `day_completed` |
| `check_gm_assessments(force)` | Emits `gm_assessment_ready` for followed teams |
| `run_world_series()` | Sets WS tracking state, emits WS signals, runs WS loop |

**Data extraction helpers:**
- `extract_standings()` → dict `{al: {teams, wins, losses, pct, gb}, nl: {...}}`
- `extract_injuries()` → list of `{player, team, position, injury, days_remaining, status}`
- `print_day_schedule(day)` → returns formatted string (does NOT print)

**Play-by-play factory:** `_create_play_by_play_callback(away, home, day_num)` returns a
closure that emits `play_by_play` signals only for followed teams. During WS, also computes
`ws_game_num` from the win totals delta.

---

## Widgets (`ui/widgets/`)

All widgets expose a `get_frame()` method returning their root `tk.Frame`.
All widgets use `ttk.Treeview` for tabular data and `scrolledtext.ScrolledText` for text.

### `toolbar.py` → `ToolbarWidget`

Packs `side=TOP` directly on root.

**Buttons:** Start Season (green), Pause, Resume, Next Day, Next Series (3d), Next Week (7d)
**Dropdown:** 30-team combobox (locked during simulation)
**Key methods:**
- `get_selected_team()` → str
- `update_button_states(running, paused)` → enables/disables buttons appropriately

---

### `standings_widget.py` → `StandingsWidget`

Left panel of PanedWindow. Two separate Treeviews: AL and NL.
Columns: Team | W-L | Pct | GB. Followed team highlighted with `"followed"` tag (blue background, bold).
Sortable by any column (click heading). GB sorts numerically (`"-"` = leader = first).

**Key methods:**
- `update_standings(standings_data, followed_team)` → full redraw
- `set_followed_team(team)` → caches team for sort re-renders

---

### `games_widget.py` → `GamesWidget`

Tab: "Today's Games". Two `ScrolledText` areas: **RESULTS** (top) and **SCHEDULE** (bottom).
Games displayed in a grid: 5 per row, showing R H E columns. Followed team name **bold**.

**State:**
- `current_day_schedule` — list of (away, home) tuples for today
- `current_day_results` — dict keyed by (away, home) with game_data
- `previous_day_results` — carried over from prior day
- `season_schedule` — full schedule set on day 0 for lookahead

**Key methods:**
- `set_season_schedule(schedule)` — called once on day 0
- `on_day_started(day_num, schedule)` — clears state, shows prev results + today's grid
- `on_game_completed(game_data)` — progressive update as followed games finish
- `on_day_completed(game_results, standings_data)` — batch adds non-followed games
- `_rebuild_games_display()` — internal; switches RESULTS/SCHEDULE panes based on completion state

---

### `schedule_widget.py` → `ScheduleWidget`

Tab: "Schedule". Shows next 14 days of matchups in a `ScrolledText`.
Current day highlighted with yellow background + "◄ CURRENT" suffix.
4 matchups per line. Followed team name **bold**.

**Key method:** `update_schedule(current_day, schedule)` — called each day from `_on_day_started`.

---

### `roster_widget.py` → `RosterWidget`

Team sub-tab: "Roster". Inner notebook: **Pos Players** | **Pitchers**.

**Columns:**
- Batters: Player, Pos, AB, R, H, 2B, 3B, HR, RBI, BB, K, AVG, OBP, SLG, OPS, Condition, Status
- Pitchers: Player, G, GS, W, L, IP, H, R, ER, HR, BB, SO, ERA, WHIP, SV, Condition, Status

**Features:**
- Player name search (live filter via `StringVar.trace`)
- Clear Filters button
- Sortable columns (click heading; ↑/↓ indicator)
- Injury color coding: yellow = Day-to-Day (<10 days), red = IL (≥10 days)
- **Comparison mode toggle** ("Show Difference from 2025" / "Show Current Stats") — shared `comparison_mode_var`
- Click a player row → opens a **popup `Toplevel` window** with year-by-year historical stats (680×280, resizable)
- **Team totals** section below each tab (treeview with 3 rows: Current / 2025 Prorated / Difference)

**Key method:** `update_roster(team, baseball_data)` — called after each day

---

### `injuries_widget.py` → `InjuriesWidget`

League sub-tab: "IL". Single Treeview: Player, Team, Pos, Injury, Status.
Color coded: red = 10-Day IL or 60-Day IL; yellow = Day-to-Day.
Team filter dropdown (All Teams or specific team). Sortable columns.

**Key methods:**
- `update_injuries(injury_list)` — called after each day
- `populate_team_filter(team_names)` — called once at simulation start

---

### `league_stats_widget.py` → `LeagueStatsWidget`

League sub-tab: "Stats". Inner notebook: **Position Players** | **Pitchers**.

**Columns:**
- Batters: Player, Team, Pos, AB, R, H, 2B, 3B, HR, RBI, BB, K, AVG, OBP, SLG, OPS
- Pitchers: Player, Team, G, GS, W, L, IP, H, R, ER, HR, BB, SO, ERA, WHIP, SV

**Features:**
- Team filter dropdown + player name search per tab
- Sortable columns (default: OPS desc for batters, ERA asc for pitchers)
- Comparison mode toggle (same button pattern as RosterWidget)
- League totals treeview (3 rows: Current / 2025 Prorated / Difference)
- Click player → opens **popup `Toplevel` window** with year-by-year historical stats

**Key method:** `update_stats(baseball_data)` — called after each day

---

### `league_leaders_widget.py` → `LeagueLeadersWidget`

League sub-tab: "Leaders". Inner notebook: **Position Players** | **Pitchers**.

**Batting leader boards** (top 10 each): AVG, OBP, OPS, HR (2×2 grid)
**Pitching leader boards** (top 10 each): Wins, ERA, WHIP, K, Saves (3×2 grid with 5 boards)

Applies MLB qualification minimums: 3.1 PA per team game played (batters), 1.0 IP per game (pitchers).
HR and counting stats (W, K, SV) use no minimum.

**Key method:** `update_leaders(baseball_data, games_played)` — called after each day

---

### `admin_widget.py` → `AdminWidget`

League sub-tab: "Admin". Player management tool.

**Features:**
- Lists all players (batters + pitchers) in a Treeview
- Search by name, filter by team
- Select player + destination team → "Move Player" button
- Calls `baseball_data.move_a_player_between_teams(hashcode, dest_team)` live
- "Save Changes to CSV" → calls `baseball_data.save_new_season_stats()`
- **Requires simulation to be paused** before moving players

**Key method:** `load_players()` — called 1 second after simulation starts

---

### `games_played_widget.py` → `GamesPlayedWidget`

Team sub-tab: "Games Played". Day dropdown + `ScrolledText` play-by-play.

Stores full game recap text for each followed-team game by day.
User selects a day from dropdown to see that day's game(s).
Score lines ("Scored", "score is") highlighted green.

**Key method:** `add_game_recap(day_num, away, home, game_recap)` — called from `_on_game_completed`

---

### `gm_assessment_widget.py` → `GMAssessmentWidget`

Team sub-tab: "GM Assessment". Header label + "Update Assessment" button + `ScrolledText`.

Displays structured GM assessment with tagged sections:
- TEAM STRATEGY (stage, alpha, win pct, GB)
- TOP 5 MOST VALUABLE PLAYERS
- TRADE CANDIDATES
- TRADE TARGETS
- SPECIFIC PLAYERS TO TARGET
- RELEASE CANDIDATES

Button starts disabled, enabled 2 seconds after simulation starts.
Assessment replaces (not appends to) previous content.

**Key methods:**
- `display_assessment(team, games, wins, losses, games_back, assessment)`
- `enable_button()`

---

### `playoff_widget.py` → `PlayoffWidget`

Tab: "Playoffs". Horizontal PanedWindow: **BOX SCORES** (left 1/3) | **PLAY-BY-PLAY** (right 2/3).

**Game selector dropdown** in play-by-play header (auto-advances to latest game).

**State:**
- `game_pbp_data` — dict `{game_num: [(text, tag), ...]}` — stored per game
- `completed_games` — set of finished game numbers
- `series_score` — dict `{team: wins}` updated as games complete

**Key methods:**
- `world_series_started(ws_data)` — initializes display, shows matchup
- `add_play_by_play(play_data)` — tracks game number, auto-selects new games in dropdown
- `add_game_result(game_data)` — adds box score entry + calls `_add_final_box_score_to_pbp()`
- `world_series_completed(ws_data)` — adds champion banner to box scores

**Note:** Play-by-play is shown **all at once** when a game completes (not incrementally).
`_parse_game_recap()` splits the raw game recap into lineups + play-by-play + box score sections.

---

## Comparison Mode

Shared `comparison_mode` (`tk.StringVar`) lives on `SeasonMainWindow` and is passed to
`RosterWidget` and `LeagueStatsWidget`. Toggle buttons in both widgets update the same var.

**Modes:**
- `"current"` — show actual sim season stats
- `"difference"` — show `current - prorated_2025` per player; formatted with `+/-` prefix

2025 prorated stats come from `baseball_data.calculate_prorated_2025_stats(team, games_played)`.

---

## Data Flow Summary

```
bbseason_ui.py::main()
  └─ StartupDialog → team, num_games
  └─ SeasonMainWindow.__init__()
       ├─ SimulationController.__init__()
       ├─ _create_toolbar()    → ToolbarWidget
       ├─ _create_status_bar()
       └─ _create_main_content() → all widgets
            └─ _poll_queues() [every 100ms]

User clicks "Start Season"
  └─ SeasonMainWindow.start_season()
       └─ SimulationController.start_season(team, callback)
            └─ SeasonWorker.start()  [daemon thread]
                 └─ UIBaseballSeason.__init__()
                 └─ season.sim_start()
                 └─ loop: season.sim_next_day()
                      └─ sim_day_threaded(day)
                           ├─ signals.emit_day_started(...)
                           ├─ super().sim_day_threaded()   [runs games, emits game_completed]
                           │    └─ _process_and_print_game_results()
                           │         ├─ signals.emit_game_completed(...)  [followed games]
                           │         └─ signals.emit_day_completed(...)   [all + standings]
                           └─ signals.emit_injury_update(...)
                 └─ season.run_world_series()  [if eligible]
                 └─ signals.emit_simulation_complete()

_poll_queues() → dispatches signal → updates widget(s)
```

---

## Key File Quick Reference

| File | Class | Role |
|---|---|---|
| `bbseason_ui.py` | `StartupDialog`, `main()` | Entry point |
| `ui/main_window_tk.py` | `SeasonMainWindow` | Layout, event dispatch |
| `ui/controllers/simulation_controller.py` | `SimulationController` | Worker lifecycle |
| `ui/season_worker.py` | `SeasonWorker` | Background thread |
| `ui/signals.py` | `SeasonSignals` | Thread-safe queues |
| `ui/ui_baseball_season.py` | `UIBaseballSeason` | Sim subclass with signal emission |
| `ui/widgets/toolbar.py` | `ToolbarWidget` | Control buttons |
| `ui/widgets/standings_widget.py` | `StandingsWidget` | AL/NL standings |
| `ui/widgets/games_widget.py` | `GamesWidget` | Today's games R/H/E grid |
| `ui/widgets/schedule_widget.py` | `ScheduleWidget` | 14-day schedule |
| `ui/widgets/roster_widget.py` | `RosterWidget` | Team roster + history |
| `ui/widgets/injuries_widget.py` | `InjuriesWidget` | League IL report |
| `ui/widgets/league_stats_widget.py` | `LeagueStatsWidget` | All-player stats table |
| `ui/widgets/league_leaders_widget.py` | `LeagueLeadersWidget` | Top-10 leader boards |
| `ui/widgets/admin_widget.py` | `AdminWidget` | Player team moves |
| `ui/widgets/games_played_widget.py` | `GamesPlayedWidget` | Game-by-game play-by-play |
| `ui/widgets/gm_assessment_widget.py` | `GMAssessmentWidget` | AI GM roster report |
| `ui/widgets/playoff_widget.py` | `PlayoffWidget` | World Series display |

---

## Common Patterns When Modifying the UI

### Adding a new tab
1. Create a new widget class in `ui/widgets/` with `__init__(parent, ...)` and `get_frame()`.
2. Export it from `ui/widgets/__init__.py`.
3. Import in `ui/main_window_tk.py`.
4. In `_create_main_content()`, instantiate it and call `self.notebook.add(widget.get_frame(), text="Tab Name")`.

### Adding a new signal
1. Add a `queue.Queue` to `SeasonSignals.__init__()` with a comment showing message format.
2. Add an `emit_*()` method to `SeasonSignals`.
3. Call it from `UIBaseballSeason` at the right point.
4. Add a queue poll + handler in `SeasonMainWindow._poll_queues()`.
5. Add the handler method `_on_*(...)` on `SeasonMainWindow`.

### Updating a widget each day
The `_on_day_completed()` handler is the main hook called once per simulation day.
It already calls `_update_roster()`, `_update_league_stats()`, `_update_league_leaders()`.
Add a similar call for any new widget that needs daily updates.

### Accessing simulation data from a widget
All widgets that need live data receive it via their update methods. The pattern is:
```python
worker = self.controller.get_worker()
if worker and worker.season:
    data = worker.season.baseball_data.get_batting_data(team, prior_season=False)
```
`baseball_data` is a `bbstats.BaseballStats` instance. Key methods:
- `get_batting_data(team_name, prior_season)` → DataFrame (team_name=None for all teams)
- `get_pitching_data(team_name, prior_season)` → DataFrame
- `get_player_historical_data(player_name, is_batter)` → DataFrame
- `calculate_prorated_2025_stats(team_name, games_played)` → (batting_df, pitching_df)
- `get_all_team_names()` → list of abbreviations
