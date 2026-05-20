# Baseball Simulator

A Python-based baseball season simulation with detailed team and player statistics. Simulates individual games or full
162-game seasons using real MLB stats (2020–2026) or randomized data. Supports partial-season starts — the sim picks up
from wherever the real season left off.

## Prerequisites

- **uv** - Package manager (install from [astral.sh](https://astral.sh/uv))
- **Free-threaded Python 3.14** - Required for multi-threaded simulation performance

### Setup

```bash
uv python install 3.14.0
uv sync
```

## Quick Start

### Run with UI (Recommended)

```bash
uv run run.py
```

This launches the graphical season simulator with defaults:

- Team to follow: **MIL**
- Games: **162**
- Stats from: **2020, 2021, 2022, 2023, 2024, 2025, 2026**

Override defaults with command-line arguments:

```bash
uv run run.py --team NYM --games 81 --seasons 2020,2021,2022,2023,2024,2025,2026
```

### Alternative Entry Points

| Command                          | Description                         |
|----------------------------------|-------------------------------------|
| `uv run run.py`                  | Season UI (recommended)             |
| `uv run bbgame.py`               | Single game simulation (CLI)        |
| `uv run bbseason.py`             | Simulate a full season (CLI)        |
| `uv run bbplayer_projections.py` | Preprocess downloaded stats         |

### Preprocessing

After running `uv run download_stats.py` to fetch fresh data from Baseball Reference, run the projection step:

```bash
uv run bbplayer_projections.py
```

### Available Arguments

| Argument       | Short | Default   | Description                                                    |
|----------------|-------|-----------|----------------------------------------------------------------|
| `--team`       | `-t`  | MIL       | Team to follow                                                 |
| `--games`      | `-g`  | 162       | Total games in season (includes partial season already played) |
| `--seasons`    | `-s`  | 2020–2026 | Years to load historical stats from                            |
| `--new-season` | `-n`  | 2026      | Season year to simulate                                        |
| `--dialog`     | `-d`  |           | Show startup dialog                                            |

## Documentation

### Architecture & Code

- **[CLAUDE.md](CLAUDE.md)** - Comprehensive guide for Claude Code (AI assistant)
- **[PROJECTION_FLOW.md](PROJECTION_FLOW.md)** - Detailed projection algorithm documentation

### UI Documentation

- **[ui_claude.md](ui/ui_claude.md)** - Complete UI reference guide with widget details
- **[ui_flowchart.md](ui_flowchart.md)** - Visual flowcharts of UI architecture
- **[AGENTS.md](AGENTS.md)** - Compact instruction file for AI coding assistants

## Project Structure

### Data Preprocessing

| File                                      | Description                                                           |
|-------------------------------------------|-----------------------------------------------------------------------|
| `bbplayer_projections.py`                 | Main preprocessing orchestrator                                       |
| `bbplayer_projections_forecast_player.py` | Projection engine with batter/pitcher strategies                      |
| `bbstats.py`                              | Data load, Save, runtime stats management, fatigue, injuries, streaks |

### Simulation Engine

| File                  | Description                                                           |
|-----------------------|-----------------------------------------------------------------------|
| `bbgame.py`           | Individual game simulation (inning-by-inning)                         |
| `bbseason.py`         | Full season orchestration, standings, playoffs                        |
| `bbschedule_mgr.py`   | Schedule loading (CSV or random), partial-season start detection      |
| `bbat_bat.py`         | At-bat simulation with odds-ratio calculations                        |
| `bbteam.py`           | Roster management, lineups, pitching rotation and changes             |
| `bbgame_box_stats.py` | In-game box score tracking, fatigue updates                           |
| `bbbaserunners.py`    | Base running logic                                                    |
| `bbinjuries.py`       | Injury system with realistic durations and performance impact         |
| `bb_aigm_manager.py`  | AI General Manager assessments                                        |
| `bbstats.py`          | Data load, Save, runtime stats management, fatigue, injuries, streaks |

### UI Package

| File / Directory               | Description                                           |
|-------------------------------|-------------------------------------------------------|
| `ui/main_window_tk.py`        | Tkinter main window with notebook tabs                |
| `ui/controllers/`             | Controller layer (season, lineup, depth chart)        |
| `ui/models/`                  | Data models for UI consumption                        |
| `ui/widgets/`                 | Widgets: standings, schedule, rosters, box scores     |
| `ui/season_worker.py`         | Background thread for season simulation               |
| `ui/ress.py`                  | Resource constants (colors, fonts, styles)            |

### Output Files

| File                                        | Purpose                                      |
|---------------------------------------------|----------------------------------------------|
| `{seasons} player-projected-stats-pp-*.csv` | Age-adjusted projections used for simulation |
| `{seasons} historical-*.csv`                | Year-by-year data for analysis               |
| `{new_season} New-Season-stats-pp-*.csv`    | Accumulates sim results during the season    |
| `{new_season} MLB Schedule.csv`             | Real MLB schedule with completed game scores |

## Key Features

- **Partial Season Support**: Loads real game results through today; sim continues from the first unplayed game
- **Real MLB Schedule**: Reads downloaded schedule CSV; marks completed games automatically
- **Season Scheduling**: 162-game schedules with authentic rest days and division structure
- **Game Simulation**: Inning-by-inning with detailed box scores (including team totals), play-by-play, and defensive substitutions
- **Player Statistics**: Full tracking across seasons (2020–2026) with age-adjusted projections
- **Injury & Fatigue Systems**: Realistic pitcher fatigue (post-game condition cost by innings pitched), injury
  durations, and recovery
- **Hot/Cold Streaks**: Player performance streaks tracked and displayed with ▲/▼ indicators
- **Standings**: Division-based Games Behind, updated after every game day
- **AI General Managers**: Automated roster assessments at configurable intervals
- **Threaded Execution**: Parallel game simulation for performance
- **UI Interface**: Tkinter-based graphical interface with live standings, roster, and schedule views

## Technical Details

- **Python Environment**: uv-managed free-threaded Python 3.14
- **Dependencies**: numpy, pandas, loguru, pygame, selenium, pydantic
