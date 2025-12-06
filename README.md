markdown
# Baseball Simulator

A comprehensive baseball simulation system that models real-world baseball scenarios including team performance, player statistics, and game outcomes.

## Project Overview

This project simulates baseball seasons with detailed team and player statistics. It includes:
- Season scheduling and game simulation
- Player performance tracking and evaluation
- Team standings and record management
- Interactive and threaded game simulation modes

## Key Features

### Core Simulation Components
- **Season Management**: Handles complete season scheduling and progression
- **Game Simulation**: Real-time game simulation with detailed box scores
- **Player Statistics**: Comprehensive tracking of individual player performance
- **Team Records**: Dynamic team standings and win-loss tracking

### Technical Implementation
- **Threaded Execution**: Parallel game simulation for performance optimization
- **Data Persistence**: Automatic saving of game results and season statistics
- **Flexible Scheduling**: Support for various league structures and schedules

### Key Classes and Methods

#### Main Simulation Class
- sim_full_season(): simulates a full season of games as defined in the bbseason.py setup
- sim_day(): Simulates a single day of games across the league
- sim_day_threaded(): Threaded version for parallel game simulation
- sim_next_day(): Advances the simulation to the next day

#### Game Management
- update_win_loss(): Maintains team win-loss records
- new_game_day(): Prepares team data for new game day
- print_day_schedule(): Displays daily game schedule

## Usage

The simulator can be run in interactive mode or as a batch process. It automatically handles:
- Team roster management
- Player injury tracking
- Rest scheduling
- Season progression

## Data Flow

1. Season initialization with team and player data
2. Daily game simulation with thread management
3. Results aggregation and statistics updating
4. Season standings calculation and display

## Requirements

- Python 3.14t
- Standard Python libraries (threading, queue, etc.)
- Baseball data structures for teams, players, and games

## Contributing

This project simulates baseball scenarios and provides a framework for:
- Analyzing player performance
- Testing team strategies
- Understanding baseball statistics
- Building predictive models
- The data can be randomized using bbstats.py to create a custom stats file as input.
- Running bbgame.py will run a single game with two teams.  bbgame also accepts the number of simulations to run for a signle
game.  
- Running bbseason.py will run an entire season of baseball of 162 games with every team.  This takes about 15 minutes if run multi-threaded.

## Multi-threading notes
1. Install Microsoft's Visual Studio.  You'll need this to compile a python 3.14t version of pandas.
2.uv python install 3.14t
3. uv python list
4. uv python pin 3.14t
5. uv sync
6. uv run -- python -X gil=0 bbseason.py