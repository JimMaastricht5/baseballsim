# Baseball Simulator

A Python-based baseball season simulation with detailed team and player statistics. Simulates individual games or full 162-game seasons using real MLB stats or randomized data.

## Documentation

### Architecture & Code
- **[CLAUDE.md](CLAUDE.md)** - Comprehensive guide for Claude Code (AI assistant)
- **[PROJECTION_FLOW.md](PROJECTION_FLOW.md)** - Detailed projection algorithm documentation

### UI Documentation
- **[ui_claude.md](ui/ui_claude.md)** - Complete UI reference guide with widget details, signal system, and patterns
- **[ui_flowchart.md](ui_flowchart.md)** - Visual flowcharts of UI architecture including:
  - Application startup flow
  - Main window layout
  - Simulation sequence diagrams
  - Queue communication patterns
  - Widget update flows
  - Thread architecture

## Quick Start

### 1. Preprocess Data
```bash
venv_bb314.2/Scripts/python.exe bbplayer_projections.py
```

### 2. Run a Single Game
```bash
venv_bb314.2/Scripts/python.exe bbgame.py
```

### 3. Run a Full Season (162 games)
```bash
venv_bb314.2/Scripts/python.exe bbseason.py
```

### 4. Run with UI
```bash
venv_bb314.2/Scripts/python.exe ui/main_window_tk.py
```

## Project Structure

### Data Preprocessing
| File | Description |
|------|-------------|
| `bbplayer_projections.py` | Main preprocessing orchestrator |
| `bbplayer_projections_forecast_player.py` | Projection engine with batter/pitcher strategies |
| `bbstats.py` | Runtime stats management |

### Simulation Engine
| File | Description |
|------|-------------|
| `bbgame.py` | Individual game simulation |
| `bbseason.py` | Full season orchestration |
| `at_bat.py` | At-bat simulation with odds-ratio calculations |

### Output Files
| File | Purpose |
|------|---------|
| `player-projected-stats-pp-*.csv` | Age-adjusted projections for simulation |
| `historical-*.csv` | Year-by-year data |
| `New-Season-stats-pp-*.csv` | Empty placeholder for sim data |

## Key Features

- **Season Scheduling**: 162-game schedules with rest days
- **Game Simulation**: Inning-by-inning with detailed box scores
- **Player Statistics**: Full tracking with injury/fatigue systems
- **Threaded Execution**: Parallel game simulation for performance
- **UI Interface**: Tkinter-based graphical interface

## Technical Details

- **Python Environment**: Uses `venv_bb314.2/` (Python 3.14.2)
- **Dependencies**: numpy, pandas, loguru, pygame, selenium
- **Threading**: Free-threaded Python (3.14t) for parallel execution

## Multi-threading Setup

1. Install Microsoft's Visual Studio (for compiling pandas)
2. `uv python install 3.14t`
3. `uv python list`
4. `uv python pin 3.14t`
5. `uv sync`
6. `uv run -- python -X gil=0 bbseason.py`
7. `uv run -- python -X gil=0 ui/main_window_tk.py`