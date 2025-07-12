# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a baseball simulation built with Python, using NumPy and Pandas for statistical analysis. The simulator can model individual games or entire seasons using either real MLB stats or randomized data.

## Architecture Overview

### Core Simulation Flow
1. **bbstats.py** loads player statistics from CSV files and manages player conditions
2. **bbteam.py** creates team rosters and optimal lineups based on statistical analysis
3. **bbgame.py** orchestrates game simulation using **at_bat.py** for individual outcomes
4. **bbbaserunners.py** handles base running logic and scoring
5. **bbseason.py** manages full season simulation with scheduling and standings

### Key Components

- **bbstats.py** - Core stats management with thread-safe operations
  - `BaseballStats` class with semaphore locking for concurrent access
  - Handles player conditions, injuries, and fatigue
  - Calculates derived statistics and supports multi-season data blending

- **bbgame.py** - Game simulation engine
  - `Game` class manages innings, at-bats, and game state
  - Supports both interactive and non-interactive modes
  - Integrates with **gameteamboxstats.py** for comprehensive box score tracking

- **bbseason.py** - Season management with multi-threading support
  - Full 162-game season simulation (~30 minutes runtime)
  - Supports AL/NL league configurations and custom game counts
  - Thread-safe operations for performance optimization

- **bbteam.py** - Team management and strategic decisions
  - Manages rosters, lineups, and pitching rotations
  - Handles player substitutions and optimal lineup creation
  - Integrates with injury system for player availability

- **at_bat.py** - Statistical outcome simulation
  - `OutCome` class translates probabilities into game events
  - Maps batter/pitcher matchups to realistic baseball outcomes

- **bbinjuries.py** - Injury simulation system
  - `InjuryType` class manages injury severity and recovery times
  - Affects player availability and roster management

- **bblogger.py** - Centralized logging system
  - Configures loguru for application-wide logging with file rotation
  - Replaces previous debug print statements

## Commands

### Running a Single Game
```bash
python bbgame.py
```
Simulates a single game between two teams (default: MIL vs MIN). Parameters can be modified in the code.

### Running a Full Season
```bash
python bbseason.py
```
Simulates a full 162-game season. Configuration options in the code:
- `only_nl_b = True` - Limit to one league
- `num_games` - Adjust number of games
- `random_data = True` - Use randomized data
- `my_teams_to_follow` - Set team to follow

### GUI Version
```bash
python bbgame_ui.py
```
PyGame-based visual interface for game simulation.

## Data Management

### CSV File Structure
The simulator uses CSV files with specific naming conventions:
- **Real MLB Data**: `stats-pp-Batting.csv`, `stats-pp-Pitching.csv`
- **Randomized Data**: `random-stats-pp-Batting.csv`, `random-stats-pp-Pitching.csv`
- **Multi-season**: Year-prefixed files (e.g., `2024 random-stats-pp-Batting.csv`)

### Data Loading
- **bbstats_preprocess.py** handles data cleaning and randomization
- **city_names.py** and **salary.py** provide supporting data for custom leagues
- Multi-season data blending supported for enhanced statistical depth

## Dependencies
```bash
pip install -r requirements.txt
```

Core dependencies:
- **numpy** - Statistical calculations
- **pandas** - Data manipulation and CSV handling
- **loguru** - Logging system
- **pygame** - GUI interface
- **keyboard** - Interactive input handling

## Development Notes

### Thread Safety
The codebase uses semaphore-based locking for concurrent operations, particularly in `BaseballStats` class.

### Configuration
Most parameters are currently hardcoded in the main files. The enhancement list includes adding command-line argument parsing.

### Interactive Features
- **bbgm_manager.py** provides general manager functionality
- Interactive modes available for managerial decisions during games