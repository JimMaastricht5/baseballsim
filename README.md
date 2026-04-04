# Baseball Simulator

A Python-based baseball season simulation with detailed team and player statistics. Simulates individual games or full 162-game seasons using real MLB stats or randomized data.

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
python run.py
```

This launches the graphical season simulator with defaults:
- Team to follow: **MIL**
- Games: **162**
- Stats from: **2023, 2024, 2025**

Override defaults with command-line arguments:
```bash
python run.py --team NYM --games 81 --seasons 2024,2025
```

### Available Arguments
| Argument | Short | Default | Description |
|----------|-------|---------|-------------|
| `--team` | `-t` | MIL | Team to follow |
| `--games` | `-g` | 162 | Number of games to simulate (1-162) |
| `--seasons` | `-s` | 2023,2024,2025 | Years to load stats from |
| `--new-season` | `-n` | 2026 | Season to simulate |
| `--dialog` | `-d` | | Show startup dialog |

## Documentation

### Architecture & Code
- **[CLAUDE.md](CLAUDE.md)** - Comprehensive guide for Claude Code (AI assistant)
- **[PROJECTION_FLOW.md](PROJECTION_FLOW.md)** - Detailed projection algorithm documentation

### UI Documentation
- **[ui_claude.md](ui/ui_claude.md)** - Complete UI reference guide with widget details
- **[ui_flowchart.md](ui_flowchart.md)** - Visual flowcharts of UI architecture

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

- **Python Environment**: uv-managed free-threaded Python 3.14
- **Dependencies**: numpy, pandas, loguru, pygame, selenium, pydantic