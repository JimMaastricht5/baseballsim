# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a baseball simulation built with Python, using NumPy and Pandas for statistical analysis. The simulator can model individual games or entire seasons using either real MLB stats or randomized data. It features a statistical odds-ratio engine for realistic at-bat outcomes, injury systems, fatigue modeling, hot/cold streaks, and age-adjusted performance.

## Architecture

### Data Flow
1. **Data Acquisition** (`download_stats.py`) - Downloads stats from RotoWire using Selenium
2. **Preprocessing** (`bbstats_preprocess.py`) - Cleans data, calculates stats, creates aggregated/historical files
3. **Stats Management** (`bbstats.py`) - Loads preprocessed data, manages league statistics, tracks injuries/fatigue
4. **Simulation Engine** - Three layers:
   - **Season** (`bbseason.py`) - Schedule, standings, multi-threaded game execution
   - **Game** (`bbgame.py`) - Inning-by-inning simulation, lineups, substitutions
   - **At-Bat** (`at_bat.py`) - Odds-ratio calculations for individual outcomes

### Key Components

- **at_bat.py** - At-bat simulation core
  - `SimAB` class: Odds-ratio calculations for batter/pitcher matchups
  - `OutCome` class: Translates scorebook codes to base running
  - Uses cached RNG and league totals for performance (29x and 2-3x speedups respectively)
  - Adjusts for age, injuries, fatigue, and hot/cold streaks

- **bbstats.py** - Statistics and state management
  - Loads aggregated CSV files for game simulation
  - Caches league-wide statistics for performance
  - Manages player condition, injuries (via `bbinjuries.py`), and fatigue
  - Thread-safe game stats updates (uses semaphore)
  - Calculates derived stats (AVG, OBP, SLG, ERA, WHIP, etc.)

- **bbstats_preprocess.py** - Data preparation
  - Creates two file types:
    - **Aggregated** (`aggr-stats-pp-*.csv`) - Career totals for game simulation
    - **Historical** (`historical-*.csv`) - Year-by-year data with `Player_Season_Key`
  - Handles age-adjusted performance projection for new seasons
  - Supports random data generation for testing
  - See HISTORICAL_DATA_IMPLEMENTATION.md for details

- **bbgame.py** - Game simulation
  - `Game` class manages full game flow
  - Tracks inning, outs, score, base runners (`bbbaserunners.py`)
  - Handles pitcher fatigue and changes
  - Updates player/team statistics in real-time
  - Optional interactive mode with keyboard controls

- **bbseason.py** - Season orchestration
  - `BaseballSeason` class creates schedules and manages standings
  - Supports multi-threaded game execution for performance
  - Tracks win/loss records and can follow specific teams
  - Handles rest days and injury recovery between games

- **bbteam.py** - Team/roster management
  - `Team` class manages active lineup and bench
  - Handles pitching rotations (5-man default)
  - Creates optimal lineups based on player stats
  - Manages substitutions and pitching changes
  - Tracks current season stats vs historical stats

- **bbinjuries.py** - Injury system
  - `InjuryType` class with pitcher/batter-specific injuries
  - Realistic injury durations (5-270 days)
  - Performance adjustments during recovery
  - Special cases: concussions, COVID-19 protocol

- **bbbaserunners.py** - Base running logic
  - `Bases` class manages runner advancement
  - Handles walks, HBP, tag-ups, double plays
  - Tracks runs scored and player movement

- **bblogger.py** - Logging configuration
  - Uses loguru for structured logging
  - File rotation (1 MB) in `logs/` directory
  - Configurable log levels (DEBUG/INFO/WARNING/ERROR)
  - **Performance note:** DEBUG logging in hot paths (e.g., `odds_ratio`) adds ~38% overhead

- **bbgame_ui.py** - Visual interface (Pygame)
  - Graphical display of game state, diamond, scoreboard
  - Real-time animation of at-bats and base running

## Commands

### Running a Single Game
```bash
venv_bb314.2/Scripts/python.exe bbgame.py
```
Simulates one game between two teams (default: NYM vs MIL). Edit parameters at the bottom of `bbgame.py` to customize teams, starting pitchers, or lineups.

### Running a Full Season
```bash
venv_bb314.2/Scripts/python.exe bbseason.py
```
Simulates a 162-game season. Edit parameters at bottom of `bbseason.py`:
- `only_nl_b = True` - Single league
- `num_games` - Games per team
- `random_data = True` - Use randomized data
- `my_teams_to_follow` - Detailed output for specific team

### Running with UI
```bash
venv_bb314.2/Scripts/python.exe bbgame_ui.py
```
Launches Pygame window with visual game simulation.

### Data Preprocessing
```bash
venv_bb314.2/Scripts/python.exe bbstats_preprocess.py
```
Run after downloading stats or to regenerate aggregated/historical files. Creates:
- `{seasons} aggr-stats-pp-Batting.csv` - For simulation
- `{seasons} aggr-stats-pp-Pitching.csv` - For simulation
- `{seasons} historical-Batting.csv` - Year-by-year analysis
- `{seasons} historical-Pitching.csv` - Year-by-year analysis
- `{new_season} New-Season-stats-pp-*.csv` - Age-projected stats

### Downloading Stats
```bash
venv_bb314.2/Scripts/python.exe download_stats.py
```
Downloads latest stats from RotoWire using Selenium/ChromeDriver.

### Profiling
```bash
venv_bb314.2/Scripts/python.exe -m cProfile -o profile.stats <script.py>
venv_bb314.2/Scripts/python.exe -c "import pstats; p = pstats.Stats('profile.stats'); p.sort_stats('cumulative').print_stats(30)"
```

## Data Files

### Input Files (Raw Stats)
- `{year} player-stats-Batters.csv` - Downloaded from RotoWire
- `{year} player-stats-Pitching.csv` - Downloaded from RotoWire

### Preprocessed Files (Used by Simulator)
- `{seasons} aggr-stats-pp-Batting.csv` - Career totals, indexed by Hashcode
- `{seasons} aggr-stats-pp-Pitching.csv` - Career totals, indexed by Hashcode
- `{seasons} historical-Batting.csv` - Year-by-year, indexed by Player_Season_Key
- `{seasons} historical-Pitching.csv` - Year-by-year, indexed by Player_Season_Key
- `{new_season} New-Season-stats-pp-*.csv` - Age-adjusted projections

### Configuration
All simulations use `load_batter_file` and `load_pitcher_file` parameters:
- Default: `'aggr-stats-pp-Batting.csv'` and `'aggr-stats-pp-Pitching.csv'`
- For random data: prefix with `'random-'`
- Year prefixes added automatically (e.g., `'2023 2024 2025 aggr-stats-pp-Batting.csv'`)

## Environment

### Python Environment
Uses Windows Python with multiple venv directories:
- `venv_bb314.2/` - Current primary environment (Python 3.14.2)
- Execute via: `venv_bb314.2/Scripts/python.exe`

### Dependencies
```bash
pip install -r requirements.txt
```
Core dependencies:
- numpy, pandas - Data manipulation and statistics
- loguru - Structured logging
- keyboard - Interactive game controls
- pygame - Visual UI
- selenium, webdriver-manager - Stats downloading

## Performance Optimizations

### Existing Optimizations (Do Not Remove)
1. **Cached RNG** (`at_bat.py:96-98`, `bbstats.py:52-54`) - Single numpy RNG instance, 29x speedup
2. **Cached League Totals** (`bbstats.py:132-143`) - Pre-calculated league stats, 2-3x speedup
3. **Pre-compiled Regex** (`bbstats.py:37`) - Pattern compilation for parsing, 2-5x speedup
4. **Return Scalar** (`bbstats.py:118-127`) - Direct values vs size=1 arrays with indexing

### Known Performance Issues
1. **DEBUG Logging** - Adds 38% overhead in `at_bat.py:odds_ratio()` (7,395 calls/test)
   - Use INFO level for production
   - Only enable DEBUG for troubleshooting
2. **Warning Filters** - Context manager overhead in `odds_ratio()` (3% overhead)
   - Could be moved to initialization

## Testing

Files include `__main__` blocks with self-tests:
```bash
venv_bb314.2/Scripts/python.exe at_bat.py      # Tests SimAB and OutCome classes
venv_bb314.2/Scripts/python.exe test_historical.py  # Tests data file structure
venv_bb314.2/Scripts/python.exe test_injuries.py    # Tests injury system
```

## Logging

Logs written to `logs/baseball_sim.log` with 1 MB rotation.

Configure log level:
```python
from bblogger import configure_logger
configure_logger("DEBUG")  # or "INFO", "WARNING", "ERROR"
```

Default is INFO level to minimize performance impact.