markdown
# Baseball Simulator

The provided code consists of two main parts: a Python script for 
preprocessing baseball statistics and a separate script for 
creating a user interface (UI) using Tkinter.

This project simulates baseball seasons with detailed team and player statistics. 
It includes:
- Season scheduling and game simulation
- Player performance tracking and evaluation
- Team standings and record management
- UI  and threaded game simulation modes

### Baseball Data Preprocessing

The first part of the code is in the file BaseballStatsPreProcess.py. This script handles the preprocessing of baseball statistics, including loading data, processing it, and simulating new seasons based on existing data. Here are some key features:

1. **Loading Data**: The script can load existing season data from CSV files.
2. **Processing Data**: It processes the data to calculate various performance metrics, such as WAR (Wins Above Replacement), age adjustments, and more.
3. **Simulating New Seasons**: It simulates new seasons based on either partial existing season data or completely random data.

#### Key Classes and Methods

- BaseballStatsPreProcess: This is the main class that handles the entire preprocessing pipeline.
  - __init__: Initializes the class with parameters such as load seasons, new season, random data generation, and file paths for loading data.
  - create_hash: Generates a hashcode for each player based on their name.
  - get_pitching_seasons and get_batting_seasons: Load pitching and batting data from CSV files.
  - calc_age_adjustment: Applies an age adjustment to performance metrics based on the player's age.

### User Interface (UI)

The second part of the code is in the file bbseason_ui.py. This script creates a graphical user interface using Tkinter to interact with the baseball season simulation. Here are some key features:

1. **Main Window**: The UI has a main window where users can specify parameters for the simulation.
2. **Event Handling**: It handles events such as closing the window and updating settings based on user input.

#### Key Classes and Methods

- SeasonMainWindow: This is the main class that creates the Tkinter window.
  - __init__: Initializes the window, sets up UI components, and binds event handlers.
  - on_close: Handles the window close event.
  - Other methods handle UI interactions and data processing.

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

The simulator can be run in UI mode or as a batch process. It automatically handles:
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
7. uv run -- python -X gil=0 bbseason_ui.py