# Plan: Enhanced League and Team Stats with Historical Comparisons

## User Requirements

1. **Add Totals Row**: Show totals at bottom of position players and pitchers for league/team stats
2. **Prorated 2025 Stats**: Display last year's totals prorated for current number of games played
3. **Difference Column**: Show difference between sim totals and prorated 2025 version
4. **Toggle View**: Allow toggling between current stats and +/- difference from 2025 by player
5. **Dual Display Modes**:
   - Mode 1: Current simulation stats
   - Mode 2: Difference from 2025 performance

---

## Architecture Overview

### Current State

**Console Output** (`bbstats.py`):
- `print_season()` (lines 978-1035) - Master display function
- `team_batting_totals()` (lines 1179-1193) - Already aggregates batting stats
- `team_pitching_totals()` (lines 1196-1210) - Already aggregates pitching stats

**UI Widgets**:
- `league_stats_widget.py` - All league players with filtering
- `roster_widget.py` - Team-specific roster display

**Historical Data Access**:
- `get_player_historical_data(player_name, is_batter)` (bbstats.py:199-237)
- Loads from `{seasons} historical-Batting.csv` and `historical-Pitching.csv`
- Indexed by `Player_Season_Key` (format: `Hashcode_Year`)

**Games Tracking**:
- `team_games_played` dict in `bbseason.py` (lines 231-235, 474-489)
- Player level: `G` column in DataFrames

---

## Design Decisions

| Decision Point | Chosen Approach | Rationale |
|---------------|-----------------|-----------|
| **Data Loading** | Lazy load + cache per-team | Balance memory vs performance; don't load all until needed |
| **Prorating** | Linear by games played | Simple, intuitive; matches typical usage (162-game season) |
| **Console Format** | Three-row side-by-side | Readable, fits existing console width patterns |
| **UI Toggle** | Global StringVar with per-widget refresh | Consistent across UI; easy to extend |
| **Difference Calc** | Absolute difference | Simple to understand; can add z-score later |
| **Missing Data** | Show "N/A", no comparison | Clear communication; don't guess at baseline |
| **Performance** | Pre-calculate at season start + cache invalidation | Leverages existing vectorized patterns |

---

## Implementation Plan

### Phase 1: Core Data Layer (bbstats.py)

**1.1 Add Historical 2025 Data Loading**

Add to `BaseballStats.__init__()`:
```python
# Add caches for 2025 historical data
self.historical_2025_batting = None  # Lazy-loaded cache
self.historical_2025_pitching = None  # Lazy-loaded cache
self.prorated_2025_cache = {}  # {team_name_games: (batting_df, pitching_df)}
```

**1.2 Create Lazy Loading Method**

```python
def _ensure_2025_historical_loaded(self):
    """Lazy load 2025 historical data if not already cached."""
    if self.historical_2025_batting is None:
        seasons_str = " ".join(str(s) for s in self.load_seasons)
        hist_batting_file = f"{seasons_str} historical-Batting.csv"
        hist_pitching_file = f"{seasons_str} historical-Pitching.csv"

        full_hist_b = pd.read_csv(hist_batting_file, index_col='Player_Season_Key')
        full_hist_p = pd.read_csv(hist_pitching_file, index_col='Player_Season_Key')

        # Filter to 2025 season only
        self.historical_2025_batting = full_hist_b[full_hist_b['Season'] == 2025]
        self.historical_2025_pitching = full_hist_p[full_hist_p['Season'] == 2025]
```

**1.3 Create Prorating Method**

```python
def calculate_prorated_2025_stats(self, team_name: str, current_games_played: int) -> tuple:
    """
    Calculate prorated 2025 stats based on current team games played.

    Returns:
        (batting_df, pitching_df): DataFrames with prorated stats for team players
    """
    # Check cache first
    cache_key = f"{team_name}_{current_games_played}"
    if cache_key in self.prorated_2025_cache:
        return self.prorated_2025_cache[cache_key]

    # Ensure 2025 data loaded
    self._ensure_2025_historical_loaded()

    # Filter to team's current roster by Hashcode
    current_roster_hashcodes_b = self.new_season_batting_data[
        self.new_season_batting_data['Team'] == team_name
    ].index

    current_roster_hashcodes_p = self.new_season_pitching_data[
        self.new_season_pitching_data['Team'] == team_name
    ].index

    # Get 2025 data for current roster players
    team_batting_2025 = self.historical_2025_batting[
        self.historical_2025_batting['Hashcode'].isin(current_roster_hashcodes_b)
    ].copy()

    team_pitching_2025 = self.historical_2025_pitching[
        self.historical_2025_pitching['Hashcode'].isin(current_roster_hashcodes_p)
    ].copy()

    # Proration factor (current games / 162)
    prorate_factor = current_games_played / 162.0

    # Prorate batting counting stats
    batting_count_cols = ['AB', 'R', 'H', '2B', '3B', 'HR', 'RBI', 'SB', 'CS',
                          'BB', 'SO', 'SF', 'SH', 'HBP']
    for col in batting_count_cols:
        if col in team_batting_2025.columns:
            team_batting_2025[col] = (team_batting_2025[col] * prorate_factor).round()

    # Recalculate batting rate stats from prorated counting stats
    team_batting_2025 = team_batting_stats(team_batting_2025, filter_stats=False)

    # Prorate pitching counting stats
    pitching_count_cols = ['IP', 'H', 'R', 'ER', 'HR', 'BB', 'SO', 'W', 'L',
                           'SV', 'BS', 'HLD', 'GS', 'CG', 'SHO']
    for col in pitching_count_cols:
        if col in team_pitching_2025.columns:
            if col == 'IP':
                # Keep decimal precision for innings pitched
                team_pitching_2025[col] = (team_pitching_2025[col] * prorate_factor).round(1)
            else:
                team_pitching_2025[col] = (team_pitching_2025[col] * prorate_factor).round()

    # Recalculate pitching rate stats
    team_pitching_2025 = team_pitching_stats(team_pitching_2025, filter_stats=False)

    # Cache result
    self.prorated_2025_cache[cache_key] = (team_batting_2025, team_pitching_2025)

    return team_batting_2025, team_pitching_2025
```

**1.4 Cache Invalidation**

Add to `game_results_to_season()` method (after line 399):
```python
def game_results_to_season(self, box_score_class) -> None:
    """Adds game results to season df - VECTORIZED for 50-200x speedup"""
    with self.semaphore:
        # ... existing update logic ...

        # Invalidate cache for teams that played
        teams_in_game = [box_score_class.away_team, box_score_class.home_team]
        for team in teams_in_game:
            # Clear cached prorated stats
            keys_to_remove = [k for k in self.prorated_2025_cache.keys()
                             if k.startswith(f"{team}_")]
            for key in keys_to_remove:
                del self.prorated_2025_cache[key]
```

---

### Phase 2: Console Display Enhancement (bbstats.py)

**2.1 Modify `print_season()` Method**

Update method signature and add comparison logic (lines 978-1035):

```python
def print_season(self, df_b: DataFrame, df_p: DataFrame, teams: list,
                summary_only_b: bool = False, show_2025_comparison: bool = True) -> None:
    """
    Print season stats with optional 2025 comparison.

    Args:
        show_2025_comparison: If True, show three-row format with 2025 prorated and difference
    """
    for team in teams:
        # ... existing filtering logic ...

        if show_2025_comparison and hasattr(self, 'team_games_played'):
            games_played = self.team_games_played.get(team, 0)

            if games_played > 0:
                # Get prorated 2025 stats
                batting_2025, pitching_2025 = self.calculate_prorated_2025_stats(
                    team, games_played
                )

                # Calculate totals for all three rows
                current_b_totals = team_batting_totals(df_b_display)
                current_p_totals = team_pitching_totals(df_p_display)

                prorated_b_totals = team_batting_totals(batting_2025)
                prorated_p_totals = team_pitching_totals(pitching_2025)

                diff_b_totals = self._calculate_difference_row(
                    current_b_totals, prorated_b_totals, is_batting=True
                )
                diff_p_totals = self._calculate_difference_row(
                    current_p_totals, prorated_p_totals, is_batting=False
                )

                # Display three-row format
                print(f'\n{team} Pitching Totals (Games: {games_played}):')
                print('Current:        ', current_p_totals[self.numeric_pcols_to_print].to_string(index=False))
                print('2025 (Prorated):', prorated_p_totals[self.numeric_pcols_to_print].to_string(index=False))
                print('Difference:     ', diff_p_totals[self.numeric_pcols_to_print].to_string(index=False))

                print(f'\n{team} Batting Totals (Games: {games_played}):')
                print('Current:        ', current_b_totals[self.numeric_bcols_to_print].to_string(index=False))
                print('2025 (Prorated):', prorated_b_totals[self.numeric_bcols_to_print].to_string(index=False))
                print('Difference:     ', diff_b_totals[self.numeric_bcols_to_print].to_string(index=False))
            else:
                # No games played yet, show standard display
                print(f'\n{team} Pitching Totals:')
                print(team_pitching_totals(df_p_display)[self.numeric_pcols_to_print].to_string())

                print(f'\n{team} Batting Totals:')
                print(team_batting_totals(df_b_display)[self.numeric_bcols_to_print].to_string())
        else:
            # Standard display (existing behavior)
            print(f'\n{team} Pitching Totals:')
            print(team_pitching_totals(df_p_display)[self.numeric_pcols_to_print].to_string())

            print(f'\n{team} Batting Totals:')
            print(team_batting_totals(df_b_display)[self.numeric_bcols_to_print].to_string())
```

**2.2 Add Helper Method for Difference Calculation**

```python
def _calculate_difference_row(self, current_df: DataFrame, historical_df: DataFrame,
                              is_batting: bool = True) -> DataFrame:
    """Calculate difference between current and historical stats."""
    diff_df = current_df.copy()

    if is_batting:
        cols_to_diff = self.numeric_bcols_to_print
    else:
        cols_to_diff = self.numeric_pcols_to_print

    for col in cols_to_diff:
        if col in current_df.columns and col in historical_df.columns:
            diff_df[col] = current_df[col] - historical_df[col]

    return diff_df
```

---

### Phase 3: UI Toggle Infrastructure (main_window_tk.py or ui/main_window_tk.py)

**3.1 Add Comparison Mode State**

Add to `MainWindow.__init__()`:
```python
# Comparison mode toggle
self.comparison_mode = tk.StringVar(value="current")  # "current" or "difference"
```

**3.2 Add View Menu**

Add to menu bar creation (or create new method):
```python
def create_view_menu(self, menubar):
    """Add View menu with comparison toggle."""
    view_menu = tk.Menu(menubar, tearoff=0)

    view_menu.add_radiobutton(
        label="Show Current Stats",
        variable=self.comparison_mode,
        value="current",
        command=self._on_comparison_mode_change
    )
    view_menu.add_radiobutton(
        label="Show Difference from 2025",
        variable=self.comparison_mode,
        value="difference",
        command=self._on_comparison_mode_change
    )

    menubar.add_cascade(label="View", menu=view_menu)
    return menubar
```

**3.3 Add Callback for Mode Change**

```python
def _on_comparison_mode_change(self):
    """Refresh all visible widgets when comparison mode changes."""
    # Trigger refresh of visible stats widgets
    if hasattr(self, 'roster_widget') and self.roster_widget.winfo_ismapped():
        self.roster_widget.refresh_display()

    if hasattr(self, 'league_stats_widget') and self.league_stats_widget.winfo_ismapped():
        self.league_stats_widget.refresh_display()
```

---

### Phase 4: League Stats Widget Enhancement (ui/widgets/league_stats_widget.py)

**4.1 Update Constructor**

Add comparison_mode_var parameter:
```python
def __init__(self, parent, baseball_data, comparison_mode_var):
    # ... existing init code ...
    self.comparison_mode_var = comparison_mode_var
    self.batters_df_2025 = None  # Cached prorated 2025 data
    self.pitchers_df_2025 = None
```

**4.2 Add Refresh Method**

```python
def refresh_display(self):
    """Refresh display when comparison mode changes."""
    # Re-run the update logic
    self._filter_and_display_stats()
```

**4.3 Modify `_update_stats_tree()` Method**

Add difference calculation logic (around lines 343-412):
```python
def _update_stats_tree(self, tree, data_df, is_batter=True):
    """Update tree with current or difference view."""
    tree.delete(*tree.get_children())  # Clear existing

    mode = self.comparison_mode_var.get()

    if mode == "difference":
        # Load 2025 data if not cached
        if is_batter and self.batters_df_2025 is None:
            self._load_2025_data()
        elif not is_batter and self.pitchers_df_2025 is None:
            self._load_2025_data()

        # Calculate differences
        display_df = self._calculate_difference_df(data_df, is_batter)
    else:
        display_df = data_df

    # Insert rows (format values with +/- prefix in difference mode)
    for idx, row in display_df.iterrows():
        if is_batter:
            values = self._format_batter_row(row, mode)
        else:
            values = self._format_pitcher_row(row, mode)

        tree.insert("", tk.END, values=values)
```

**4.4 Add Helper Methods**

```python
def _load_2025_data(self):
    """Load and cache 2025 historical data."""
    self.baseball_data._ensure_2025_historical_loaded()

    # Get current games played for prorating
    if hasattr(self.baseball_data, 'team_games_played'):
        # Average games across all teams for league-wide view
        avg_games = sum(self.baseball_data.team_games_played.values()) // len(self.baseball_data.team_games_played)
    else:
        avg_games = 0

    # Prorate 2025 data
    self.batters_df_2025 = self._prorate_league_2025_data(is_batter=True, games=avg_games)
    self.pitchers_df_2025 = self._prorate_league_2025_data(is_batter=False, games=avg_games)

def _calculate_difference_df(self, current_df, is_batter):
    """Calculate current - prorated 2025 for each player."""
    hist_df = self.batters_df_2025 if is_batter else self.pitchers_df_2025

    diff_df = current_df.copy()

    # Join on Hashcode (index)
    for idx in diff_df.index:
        if idx in hist_df.index:
            hist_row = hist_df.loc[idx]

            # Counting stats: absolute difference
            count_cols = ['AB', 'R', 'H', '2B', '3B', 'HR', 'RBI', 'BB', 'SO'] if is_batter else \
                         ['IP', 'H', 'ER', 'SO', 'BB', 'W', 'L', 'SV']

            for col in count_cols:
                if col in diff_df.columns and col in hist_row.index:
                    diff_df.at[idx, col] = diff_df.at[idx, col] - hist_row[col]

            # Rate stats: difference (small decimals)
            rate_cols = ['AVG', 'OBP', 'SLG', 'OPS'] if is_batter else ['ERA', 'WHIP']
            for col in rate_cols:
                if col in diff_df.columns and col in hist_row.index:
                    diff_df.at[idx, col] = diff_df.at[idx, col] - hist_row[col]
        else:
            # No 2025 data for this player (rookie)
            # Leave values as-is or mark as N/A
            pass

    return diff_df

def _format_batter_row(self, row, mode):
    """Format batter row values with +/- prefix in difference mode."""
    if mode == "difference":
        return (
            row['Player'],
            row['Team'],
            row['Pos'],
            self._format_diff(row['AB']),
            self._format_diff(row['R']),
            self._format_diff(row['H']),
            self._format_diff(row['2B']),
            self._format_diff(row['3B']),
            self._format_diff(row['HR']),
            self._format_diff(row['RBI']),
            self._format_diff(row['BB']),
            self._format_diff(row['SO']),
            self._format_diff(row['AVG'], decimals=3),
            self._format_diff(row['OBP'], decimals=3),
            self._format_diff(row['SLG'], decimals=3),
            self._format_diff(row['OPS'], decimals=3)
        )
    else:
        # Existing format (current stats)
        return (
            row['Player'],
            row['Team'],
            row['Pos'],
            f"{int(row['AB'])}",
            f"{int(row['R'])}",
            # ... etc
        )

def _format_diff(self, value, decimals=0):
    """Format difference value with +/- prefix."""
    if pd.isna(value):
        return "N/A"

    if decimals == 0:
        formatted = f"{int(value)}"
    else:
        formatted = f"{value:.{decimals}f}"

    if value > 0:
        return f"+{formatted}"
    else:
        return formatted  # Already has negative sign
```

---

### Phase 5: Roster Widget Enhancement (ui/widgets/roster_widget.py)

**5.1 Update Constructor**

Same pattern as league stats widget:
```python
def __init__(self, parent, baseball_data, comparison_mode_var):
    # ... existing init code ...
    self.comparison_mode_var = comparison_mode_var
    self.team_batting_2025 = None
    self.team_pitching_2025 = None
    self.current_team = None
```

**5.2 Add Refresh and Difference Calculation**

Similar methods to league_stats_widget but filtered by team:
```python
def refresh_display(self):
    """Refresh display when comparison mode changes."""
    if self.current_team:
        self.show_roster(self.current_team)

def _load_team_2025_data(self, team_name, games_played):
    """Load and cache 2025 data for specific team."""
    batting_2025, pitching_2025 = self.baseball_data.calculate_prorated_2025_stats(
        team_name, games_played
    )

    self.team_batting_2025 = batting_2025
    self.team_pitching_2025 = pitching_2025
```

Apply same pattern as league_stats_widget for `_update_roster_tree()` and formatting methods.

---

### Phase 6: Edge Cases and Polish

**6.1 Handle Missing 2025 Data**

In difference calculation methods, check for missing data:
```python
if idx not in hist_df.index:
    # Player didn't play in 2025 (rookie, call-up, etc.)
    # Option 1: Show "N/A" for all difference columns
    for col in diff_cols:
        diff_df.at[idx, col] = np.nan

    # Option 2: Show current stats as-is (no comparison)
    # (Keep existing values)
```

**6.2 Add Low Sample Size Warning**

```python
def _is_reliable_2025_data(self, games_2025):
    """Check if 2025 sample size is reliable for comparison."""
    MINIMUM_GAMES = 10
    return games_2025 >= MINIMUM_GAMES

# In display formatting:
if not self._is_reliable_2025_data(row['G_2025']):
    # Add asterisk to player name
    player_name = f"{row['Player']}*"
```

**6.3 Add Tooltips/Help Text**

In UI widgets, add tooltip explaining the difference view:
```python
# Add label or tooltip near toggle
info_label = tk.Label(
    parent,
    text="* = Less than 10 games in 2025 (unreliable comparison)",
    font=('Arial', 8),
    fg='gray'
)
```

---

## Critical Files to Modify

1. **`/mnt/c/Users/jimma/PycharmProjects/baseballsimgit/bbstats.py`**
   - Lines 199-237: Historical data loading
   - Lines 360-399: Cache invalidation in `game_results_to_season()`
   - Lines 978-1035: Console display in `print_season()`
   - Lines 1179-1210: Totals calculation methods

2. **`/mnt/c/Users/jimma/PycharmProjects/baseballsimgit/bbseason.py`**
   - Line 233: `team_games_played` dict (already exists)
   - Pass to `baseball_data` for prorating calculations

3. **`/mnt/c/Users/jimma/PycharmProjects/baseballsimgit/ui/widgets/league_stats_widget.py`**
   - Lines 217-259: Constructor and initialization
   - Lines 343-412: Tree update logic

4. **`/mnt/c/Users/jimma/PycharmProjects/baseballsimgit/ui/widgets/roster_widget.py`**
   - Lines 166-250: Constructor and initialization
   - Lines 274-360: Roster display logic

5. **`/mnt/c/Users/jimma/PycharmProjects/baseballsimgit/ui/main_window_tk.py`** (or equivalent)
   - Add menu bar with View menu
   - Add comparison_mode StringVar
   - Add callback for mode changes

---

## Verification Plan

### Unit Tests
1. Test prorating algorithm with known inputs
2. Test difference calculation with edge cases
3. Test cache invalidation logic

### Integration Tests
1. Run season simulation with console output enabled
2. Verify three-row totals display format
3. Verify prorated stats match manual calculations
4. Test UI toggle switches between modes correctly

### Edge Case Tests
1. Rookie players (no 2025 data) - show "N/A"
2. Low sample size players (< 10 games) - add asterisk
3. Mid-season trades - use 2025 data from original team
4. Empty league (no games played) - skip comparison

### Performance Tests
1. Load time for historical data (should be < 1 second)
2. Cache hit rate (should be > 90% after first load)
3. UI refresh speed (should be < 100ms)

---

## Example Console Output

```
MIL Pitching Totals (Games: 81):
                        G    GS   IP     H    ER   BB   SO   W    L    ERA   WHIP
Current:                81   81   725.0  680  315  245  720  45   36   3.91  1.28
2025 (Prorated):        81   81   712.0  695  330  258  698  42   39   4.17  1.34
Difference:             0    0    +13.0  -15  -15  -13  +22  +3   -3   -0.26 -0.06

MIL Batting Totals (Games: 81):
                        G    AB    R    H    2B   3B   HR   RBI  BB   SO   AVG   OBP   OPS
Current:                81   2790  385  715  142  18   98   368  285  645  .256  .325  .765
2025 (Prorated):        81   2815  398  720  148  15   92   385  272  658  .256  .322  .758
Difference:             0    -25   -13  -5   -6   +3   +6   -17  +13  -13  .000  +.003 +.007
```

---

## Open Questions (Resolved)

1. **Toggle scope**: Global across all UI (via StringVar)
2. **Missing 2025 data**: Show "N/A", no comparison
3. **Difference display**: Absolute difference with +/- prefix
4. **Color coding**: Optional future enhancement (green/red tags)

---

*Status: Final design ready for implementation*
