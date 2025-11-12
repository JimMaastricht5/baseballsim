# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a baseball simulation built with Python, using NumPy and Pandas for statistical analysis. The simulator can model individual games or entire seasons using either real MLB stats or randomized data.

## Key Components

- **bbstats.py** - Core stats management module
  - Loads player statistics from CSV files
  - Handles player condition, injuries, and fatigue
  - Calculates derived statistics (AVG, OBP, SLG, ERA, etc.)

- **bbgame.py** - Game simulation engine
  - Simulates individual games between two teams
  - Manages innings, at-bats, runners, and scoring
  - Tracks game state and box scores

- **bbseason.py** - Season management
  - Handles full season simulations (162 games by default)
  - Creates schedules and tracks standings
  - Supports multi-league simulations (MLB/minors)

- **bbteam.py** - Team management
  - Manages team rosters, lineups, and pitching rotations
  - Handles player substitutions and pitching changes
  - Creates optimal lineups based on player statistics

- **at_bat.py** - At-bat simulation
  - Simulates individual at-bat outcomes based on batter/pitcher matchups
  - Uses statistical models to determine hits, walks, and outs

## Commands

### Running a Single Game
```bash
python bbgame.py
```
This simulates a single game between two teams (default: NYM vs MIL). You can modify the teams and other parameters by editing the code at the bottom of bbgame.py.

### Running a Full Season
```bash
python bbseason.py
```
This simulates a full 162-game season for all teams. Options at the bottom of the file can be edited to:
- Limit to one league with `only_nl_b = True`
- Adjust number of games with `num_games`
- Use randomized data with `random_data = True`
- Set a team to follow with `my_teams_to_follow`

### Input Data
The simulator uses CSV files for player statistics:
- Real MLB data: files like "stats-pp-Batting.csv" and "stats-pp-Pitching.csv"
- Randomized data: files like "random-stats-pp-Batting.csv" and "random-stats-pp-Pitching.csv"

To use specific data, modify the `load_batter_file` and `load_pitcher_file` parameters when creating game/season objects.

**Note:** The preprocessor creates two types of files:
- Aggregated files (`aggr-stats-pp-*.csv`) - Career totals used for game simulation
- Historical files (`historical-*.csv`) - Year-by-year data for analysis

## Dependencies
To install required dependencies:
```bash
pip install -r requirements.txt
```

The core dependencies are:
- numpy
- pandas
- keyboard