# AI General Manager Implementation

## Overview

The `bbgm_manager.py` module implements intelligent general managers that make strategic roster decisions based on team performance. Each GM has a unique **alpha coefficient (α)** that determines whether they prioritize winning now or building for the future.

## Files Created

1. **bbgm_manager.py** - Core AI GM implementation
2. **test_ai_gm.py** - Integration test and example usage
3. **AI_GM_IMPLEMENTATION.md** - This documentation

## New Features in bbstats.py

### calculate_sim_war() Method

Added dynamic Sim WAR calculation to `bbstats.py`:

```python
baseball_data.calculate_sim_war()  # Calculates in-season player value
```

**For Batters:**
- Uses wOBA (weighted On-Base Average) vs league average
- Based purely on observable stats: H, 2B, 3B, HR, BB, HBP, PA

**For Pitchers:**
- Uses FIP (Fielding Independent Pitching) vs league average
- Based purely on observable stats: HR, BB, SO, IP

**Design Philosophy:**
- Sim_WAR is calculated ONLY from observable performance statistics
- Internal adjustment factors (Age_Adjustment, Injury_Rate_Adj, Injury_Perf_Adj, Streak_Adjustment) affect IN-GAME outcomes but are NOT applied to WAR
- This prevents double-counting: adjustments influence the stats that are produced, and WAR measures those stats
- Like real-world WAR, this metric is purely results-based

**Auto-calculated:** Called in `update_season_stats()` after each game

## Alpha Strategy Coefficient (α)

The alpha coefficient determines how GMs weight immediate vs future value:

| Alpha Range | Strategy Stage | Team Approach |
|-------------|----------------|---------------|
| 0.8-1.0 | Aggressive Contender | Win now at all costs |
| 0.6-0.8 | Contending | Prioritize current season |
| 0.4-0.6 | Balanced/Retooling | Compete while building |
| 0.2-0.4 | Rebuilding | Sell vets, acquire prospects |
| 0.0-0.2 | Full Rebuild | Future assets only |

### Alpha Calculation Formula

Alpha is calculated based on:

1. **Win Percentage (40% weight)** - Overall team quality
2. **Games Back (40% weight)** - Playoff positioning
3. **Season Timing (20% weight)** - Urgency increases late season

```
alpha = 0.50 + (combined_signal * 0.45)
where combined_signal ranges from -1.0 (rebuild) to +1.0 (contender)
```

## Player Value Formula

Total player value combines immediate and future components:

```
V_player = α * V_immediate + (1-α) * V_future
```

### Components:

**V_immediate (Current Season Value):**
- Base: Sim_WAR from observable stats (H, 2B, HR, BB, SO, IP, etc.)
- Adjusted for playing time (games/IP played relative to expectations)
- Note: Sim_WAR is calculated purely from observable statistics, just like real-world WAR
- Internal factors (Age_Adjustment, Injury_Rate_Adj, etc.) affect in-game performance but are NOT applied to WAR to avoid double-counting

**V_future (Age-Adjusted Projections):**
- Projects career trajectory from current age
- Uses MLB aging curves (peak age 29)
- Younger players have more future value
- Discounts future value by 10% per year

**Additional Metrics:**
- `value_per_dollar`: Value / (Salary / $1M) - for budget decisions
- `years_remaining`: Estimated contract years

## Classes

### GMStrategy
Calculates team strategy (alpha) based on performance and standings.

```python
strategy_calc = GMStrategy()
strategy = strategy_calc.calculate_alpha(
    team_record=(wins, losses),
    games_back=games_back,  # Negative = leading
    games_played=games_played
)
# Returns: TeamStrategy(alpha, games_back, win_pct, stage)
```

### PlayerValuation
Calculates comprehensive player value with strategy weighting.

```python
valuator = PlayerValuation()
value = valuator.calculate_player_value(
    player_row=batter_stats_row,
    alpha=strategy.alpha,
    is_pitcher=False
)
# Returns: PlayerValue dataclass with all components
```

### AIGeneralManager
Makes strategic roster decisions and recommendations.

```python
gm = AIGeneralManager(
    team_name='NYM',
    assessment_frequency=30  # Assess every 30 games
)

# Check if assessment is due
if gm.should_assess(games_played):
    assessment = gm.assess_roster(
        baseball_stats=baseball_data,
        team_record=(wins, losses),
        games_back=games_back,
        games_played=games_played
    )
```

## GM Recommendations

Based on strategy, GMs generate four types of recommendations:

### 1. Trade Away
Players to consider trading:
- **Contenders (α ≥ 0.60)**: Young prospects not helping now
- **Rebuilders (α ≤ 0.40)**: Veterans on expiring contracts
- **All teams**: Negative value overpaid players

### 2. Trade Targets
Player profiles to acquire:
- **Contenders**: Proven veterans with immediate value
- **Rebuilders**: Young players with high upside
- **Balanced**: Value inefficiencies

### 3. Promote
Prospects to call up from minors (not yet implemented - requires minor league system)

### 4. Release
Cut unproductive players:
- Total value < -0.5 WAR
- Salary ≤ $1M (low financial risk)

## Integration with bbseason.py

Add to `BaseballSeason.__init__()`:

```python
# Initialize AI GMs for all teams
self.gm_managers = {}
for team in self.team_names:
    self.gm_managers[team] = AIGeneralManager(
        team_name=team,
        assessment_frequency=30
    )
```

Add to game loop in `play_season()`:

```python
# After each game, check if GM assessment is due
for team in [home_team, away_team]:
    gm = self.gm_managers[team]

    if gm.should_assess(self.current_game_number):
        # Get team standings
        wins, losses = self.get_team_record(team)
        games_back = self.calculate_games_back(team)

        # Run GM assessment
        assessment = gm.assess_roster(
            baseball_stats=self.baseball_stats,
            team_record=(wins, losses),
            games_back=games_back,
            games_played=self.current_game_number
        )

        # Store assessment for later reference
        self.gm_assessments[team].append(assessment)
```

## Example Scenarios

### Scenario 1: Division Leader (Early Season)
- **Record**: 20-10 (0.667), GB: -1.5, Games: 30
- **Alpha**: 0.604 (Contending)
- **Strategy**: Look to acquire win-now veterans
- **Avoid**: Trading away young prospects

### Scenario 2: Wild Card Race (Mid-Season)
- **Record**: 35-25 (0.583), GB: 2.0, Games: 60
- **Alpha**: 0.556 (Balanced/Retooling)
- **Strategy**: Make strategic moves, avoid overpaying
- **Look for**: Value inefficiencies

### Scenario 3: Falling Out (Late Season)
- **Record**: 48-42 (0.533), GB: 8.5, Games: 90
- **Alpha**: 0.506 (Balanced/Retooling)
- **Strategy**: Starting to pivot toward future
- **Consider**: Moving vets on expiring deals

### Scenario 4: Out of Contention (Late Season)
- **Record**: 58-62 (0.483), GB: 12.0, Games: 120
- **Alpha**: 0.309 (Rebuilding)
- **Strategy**: Full sell mode - trade all vets for prospects
- **Focus**: Accumulate young talent and future value

## Future Enhancements

### Phase 1 (Current):
- [x] Dynamic strategy calculation (alpha)
- [x] Player valuation (immediate + future)
- [x] Trade recommendations (buy/sell)
- [x] Release recommendations

### Phase 2 (Next Steps):
- [ ] Minor league system (promote/demote)
- [ ] Actual trade execution between teams
- [ ] Contract negotiations (extend/let walk)
- [ ] Free agent signings

### Phase 3 (Advanced):
- [ ] Multi-team trade logic
- [ ] Draft pick valuation
- [ ] Salary cap management
- [ ] Machine learning for optimal trades

## Testing

Run the test suite:

```bash
venv_bb314.2/Scripts/python.exe test_ai_gm.py
```

Test the module standalone:

```bash
venv_bb314.2/Scripts/python.exe bb_aigm_manager.py
```

## Key Insights

1. **Dynamic Strategy**: Alpha adjusts based on performance, not fixed at season start
2. **Context Matters**: Same player has different value to different teams
3. **Trade Deadline**: Urgency increases as season progresses (affects alpha)
4. **Age Curves**: Young players valued more by rebuilders, vets by contenders
5. **Salary Relief**: Overpaid veterans are trade candidates regardless of strategy

## Performance Notes

- Valuation calculations are vectorized for speed
- Runs in O(n) time where n = roster size (~40 players)
- Assessment takes ~0.1 seconds per team
- Minimal impact on season simulation performance

## Data Dependencies

Requires the following columns in player data:

**Observable Stats (used by Sim_WAR and GMs):**
- `Sim_WAR` - Current season value (auto-calculated from stats)
- `Age` - Player age (visible)
- `Salary` - Annual salary (visible)
- `Team` - Current team (visible)
- `G` / `GS` / `IP` - Games/starts/innings played (visible)
- `Injured Days` - Days on IL (visible)
- Performance stats: `H`, `2B`, `3B`, `HR`, `BB`, `SO`, `HBP`, `AB`, `SF` (batters)
- Performance stats: `HR`, `BB`, `SO`, `IP` (pitchers)

**Internal Simulation Factors (used in at_bat.py, NOT in WAR/GM evaluations):**
- `Age_Adjustment` - Age performance curve (internal)
- `Injury_Rate_Adj` - Injury proneness (internal)
- `Injury_Perf_Adj` - Performance impact from injury history (internal)
- `Streak_Adjustment` - Hot/cold streak factor (internal)

All of these are already present in the current `bbstats.py` data structure!

## Notes

- Alpha values are suggestions and can be tuned via constants in `GMStrategy`
- Player valuations use simplified WAR formulas (not full fWAR/bWAR)
- Trade recommendations are advisory only - no automatic trades executed
- Future versions will add trade negotiation logic between teams
