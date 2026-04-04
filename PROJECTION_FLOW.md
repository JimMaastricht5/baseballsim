# Baseball Statistics Preprocessing: Projection Flow

This document describes the data flow and projection logic for both batters and pitchers in the baseball simulation preprocessing pipeline.

## Output Files

```mermaid
flowchart TB
    subgraph OUTPUT["Output Files"]
        proj_out["{seasons} player-projected-stats-pp-*.csv<br/>Age-adjusted projections for SIMULATION"]
        hist_out["{seasons} historical-*.csv<br/>Year-by-year data"]
        placeholder["{new_season} New-Season-stats-pp-*.csv<br/>EMPTY placeholder for accumulating<br/>simulation data during season"]
    end
```

### File Descriptions

| File | Purpose | Used By |
|------|---------|---------|
| `player-projected-stats-pp-*.csv` | **Age-adjusted projections** for game simulation | Simulation engine |
| `historical-*.csv` | Year-by-year data for analysis | Projections, UI |
| `New-Season-stats-pp-*.csv` | **Empty placeholder** - accumulates sim data | Admin UI save |

**Note:** The `player-projected-stats-pp` files contain the projected stats for simulation. The `New-Season-stats-pp` files are empty placeholders that get populated during the simulation with real-time stats.

## Preprocessing Pipeline

```mermaid
flowchart TB
    subgraph INPUT["Input Data"]
        raw_csv["Raw CSV Files<br/>player-stats-Batters.csv<br/>player-stats-Pitchers.csv"]
    end

    subgraph PREPROCESS["BaseballStatsPreProcess"]
        load["Load & Clean Data"]
        salary["Merge Salary Data"]
        calc["Calculate Derived Stats"]
        hist["Create Historical Files"]
        proj["Create Player Projections<br/>(player-projected-stats-pp)"]
    end

    subgraph OUTPUT["Output Files"]
        aggr["player-projected-stats-pp-*.csv<br/>For Simulation"]
        hist_out["historical-*.csv<br/>Year-by-Year"]
    end

    raw_csv --> load --> salary --> calc --> hist --> proj
    proj --> aggr
    hist --> hist_out
```

## Key Concepts

### 1. Bayesian Shrinkage
Low-sample players are regressed toward a computed league mean using K-values. Higher K = stronger pull toward league average.

```
final_rate = (player_rate * career_vol + K * lg_rate) / (career_vol + K)
```

### 2. Aging Curve
A parabolic multiplier is applied based on projected age:
- **Batters**: Peak ~27, flat prime 25-30, decline after 34
- **Pitchers**: Peak ~28, flat prime 27-30, steeper decline after 34

### 3. K-Values by Stat

| Stat | Batter K | Pitcher K | Purpose |
|------|----------|-----------|---------|
| H | 40 | 2500 | BABIP regression |
| BB | 50 | 300 | Plate discipline |
| SO | 100 | 100 | Strikeout rate |
| HR | 25 | - | Power stability |
| 2B | 80 | - | Doubles respect |
| 3B | 200 | - | High variance |
| ER | - | 300 | ERA anchoring |
| Default | 150 | 250 | Fallback |

---

## Batter Projection Flow

```mermaid
flowchart TD
    START_B{"_project_batter()"}

    VOL["Calculate Volume<br/>Recency-weighted avg PA<br/>Weights: 1:3:6<br/>Clamped [150, 700]"]

    STAT_ORDER["Stat Projection Order:<br/>1. BB, SO (per PA)<br/>2. AB = PA - BB - HBP - SF<br/>3. H = BA_rate × AB<br/>4. 2B, 3B tethered to H<br/>5. HR as HR/AB rate<br/>6. Recalculate AVG, OBP"]

    GET_BB["_get_projection_batter('BB', 'PA')"]
    GET_SO["_get_projection_batter('SO', 'PA')"]
    GET_H["_get_projection_batter('H', 'AB')"]
    GET_2B["_get_projection_batter('2B', 'H')"]
    GET_3B["_get_projection_batter('3B', 'H')"]
    GET_HR["_get_projection_batter('HR', 'AB')"]

    APPLY_AGING["Apply Aging Multiplier<br/>dampened by career volume trust"]
    APPLY_TAX["Apply Unproven Tax<br/>-4% for non-SO stats<br/>+6% for SO"]
    APPLY_REGRESS["Bayesian Regression<br/>toward league mean"]

    OUT["Return projected stat dict"]

    START_B --> VOL --> STAT_ORDER
    STAT_ORDER --> GET_BB
    STAT_ORDER --> GET_SO
    STAT_ORDER --> GET_H
    STAT_ORDER --> GET_2B
    STAT_ORDER --> GET_3B
    STAT_ORDER --> GET_HR

    GET_BB --> APPLY_AGING --> APPLY_TAX --> APPLY_REGRESS --> OUT
    GET_SO --> APPLY_AGING --> APPLY_TAX --> APPLY_REGRESS --> OUT
    GET_H --> APPLY_AGING --> APPLY_TAX --> APPLY_REGRESS --> OUT
    GET_2B --> APPLY_AGING --> APPLY_TAX --> APPLY_REGRESS --> OUT
    GET_3B --> APPLY_AGING --> APPLY_TAX --> APPLY_REGRESS --> OUT
    GET_HR --> APPLY_AGING --> APPLY_TAX --> APPLY_REGRESS --> OUT
```

### Batter Strategy Selection (`_get_projection_batter`)

```mermaid
flowchart TD
    START["_get_projection_batter()"]

    CHECK1{"1 Qualifying Season<br/>PA >= 300?"}
    YES1 --> STARTER["_project_single_year_starter()<br/>80/20 blend with lg_mean<br/>HR: 90/10 blend"]

    CHECK2{"Low Volume?<br/>< 100 PA/yr avg OR<br/>< 2 seasons?"}
    YES2 --> REGRESS["_regress_to_mean()<br/>Bayesian regression to lg_mean"]

    CHECK3{"Consistent Trend?<br/>Monotonic rate history<br/>AND >= 2 seasons?"}

    CHECK4{"Proven Power?<br/>3+ seasons, 1000+ PA<br/>Stat = HR?"}
    CHECK5{"Young?<br/>Age <= 25?"}
    CHECK6{"Prime Age?<br/>27-32?"}

    YES3 --> CHECK4
    NO4_YES5 --> MAX1["max(trend, w_avg)"]
    NO4_YES6 --> MAX1
    NO4_NO5 --> TREND1["trend_rate"]

    TREND["_linear_regression()"]
    W_AVG["_weighted_career_average()"]
    YES3 --> TREND
    YES3 --> W_AVG
    TREND --> CHECK4
    W_AVG --> CHECK4

    CHECK7{"Prime Anchor?<br/>Age 27-33, 600+ PA<br/>Stat = H or BB?"}
    YES7 --> ANCHOR["max(proj, recent * 0.93)"]
    NO7 --> OUT_B["player_rate"]

    REGRESS --> AGING
    STARTER --> AGING
    MAX1 --> OUT_B
    TREND1 --> OUT_B
    ANCHOR --> OUT_B

    NO1 --> CHECK2
    NO2 --> CHECK3
    NO3 --> W_AVG2["_weighted_career_average()"]
    W_AVG2 --> CHECK7
    NO4 --> CHECK5
    NO4 --> CHECK6

    AGING["Apply Aging Multiplier"]
    TAX["Apply Unproven Tax"]
    REG["Bayesian Regression<br/>toward lg_mean"]
    CAP["Apply Sanity Caps<br/>Clip to [0, 0.480]"]

    OUT_B --> AGING --> TAX --> REG --> CAP
```

**Legend:**
- `YES1`, `NO1` = Yes/No branches from CHECK1
- `YES2`, `NO2` = Yes/No branches from CHECK2
- `YES3`, `NO3` = Yes/No branches from CHECK3
- `NO4_YES5` = CHECK4 = No, then CHECK5 = Yes
- `NO4_YES6` = CHECK4 = No, then CHECK6 = Yes
- `NO4_NO5` = CHECK4 = No, then CHECK5 = No
- `YES7`, `NO7` = Yes/No branches from CHECK7

---

## Pitcher Projection Flow

```mermaid
flowchart TD
    START_P{"_project_pitcher()"}

    IP_CONV["IP Conversion<br/>True Decimal = int(IP) + IP% * 3.333<br/>e.g., 200.1 → 200.33"]

    IP_PROJ["Project IP<br/>Workhorse-aware:<br/>- 2+ seasons, 150+ IP: cap 210<br/>- Otherwise: cap 170"]

    STAT_ORDER_P["Stat Projection Order:<br/>1. BB per IP<br/>2. SO per IP<br/>3. HR per IP<br/>4. PA per IP<br/>5. H per PA<br/>6. ER per IP<br/>7. Derive ERA, WHIP, AB"]

    GET_BB_P["_get_projection_pitcher('BB', 'IP')"]
    GET_SO_P["_get_projection_pitcher('SO', 'IP')"]
    GET_HR_P["_get_projection_pitcher('HR', 'IP')"]
    GET_PA_P["_get_projection_pitcher('PA', 'IP')"]
    GET_H_P["_get_projection_pitcher('H', 'PA')"]
    GET_ER_P["_get_projection_pitcher('ER', 'IP')"]

    OUT_P["Return projected stat dict<br/>with ERA, WHIP recalculated"]

    START_P --> IP_CONV --> IP_PROJ --> STAT_ORDER_P

    STAT_ORDER_P --> GET_BB_P
    STAT_ORDER_P --> GET_SO_P
    STAT_ORDER_P --> GET_HR_P
    STAT_ORDER_P --> GET_PA_P
    STAT_ORDER_P --> GET_H_P
    STAT_ORDER_P --> GET_ER_P

    PROC_P["Process Each Stat:<br/>1. Strategy Selection<br/>2. Aging (inverted for H/BB/ER when declining)<br/>3. Unproven Tax<br/>4. OBP Anchor (if applicable)<br/>5. Bayesian Regression<br/>6. Gravity Anchor (ER only)<br/>7. Outlier Brake (ER only)"]
```

### Pitcher Strategy Selection (`_get_projection_pitcher`)

```mermaid
flowchart TD
    START_PP["_get_projection_pitcher()"]

    CHECK1{"< 2 seasons OR<br/>< 150 career vol?"}
    YES1 --> REGRESS["_regress_to_mean()"]

    NO1 --> TREND["_linear_regression()"]
    NO1 --> WAVG["_weighted_career_average()"]
    CHECK2{"Proven SO?<br/>3+ seasons, 1000+ PA?"}
    NO1 --> CHECK2

    TREND --> CHECK2
    WAVG --> CHECK2
    YES2 --> SO_W["w_avg for SO"]
    NO2 --> BLEND["50/50 blend<br/>trend + w_avg"]

    BLEND --> AGING
    SO_W --> AGING
    REGRESS --> AGING

    AGING["Apply Aging<br/>Inverted for H/BB/ER<br/>when declining"]
    TAX["Apply Unproven Tax<br/>+5% for H/BB/ER<br/>-5% for others"]
    ANCHOR["OBP Anchor<br/>If H or BB < 87% of lg:<br/>70/30 blend with lg"]
    REG["Bayesian Regression"]
    GRAVITY["Gravity Anchor (ER only)<br/>Pull elite ERA toward ~2.80"]
    BRAKE["Outlier Brake (ER only)<br/>Floor for fringe pitchers"]
    CAP["Apply Sanity Caps"]

    AGING --> TAX --> ANCHOR --> REG --> GRAVITY --> BRAKE --> CAP
```

---

## Full Pipeline Flow

```mermaid
flowchart LR
    subgraph MAIN["Main Preprocessing Pipeline"]
        direction TB
        1[Load Raw CSV Files]
        2[Merge Salary Data]
        3[Calculate Derived Stats<br/>OBP, SLG, OPS, ERA, WHIP]
        4[Create Historical Files<br/>One row per player per season]
        5[Calculate League Averages]
        6[Create PlayerProjector]
        7[Calculate Projected Stats]
        8[Create Aggregated Files<br/>Career totals per player]
        9[Create New Season Files<br/>Projected stats for new season]
    end

    1 --> 2 --> 3 --> 4 --> 5 --> 6 --> 7 --> 8 --> 9
```

---

## Aging Curve Visualization

```mermaid
graph LR
    subgraph HITTERS["Hitter Aging Curve"]
        A["Age 24: Growth<br/>~1.02 peak"]
        B["Age 25-30: Prime<br/>1.00 flat"]
        C["Age 31-34: Mild decline<br/>0.99"]
        D["Age 35+: Decline<br/>Accelerating"]
    end

    subgraph PITCHERS["Pitcher Aging Curve"]
        E["Age 26: Development<br/>~1.02 peak"]
        F["Age 27-30: Peak<br/>1.00 flat"]
        G["Age 31-33: Mild decline<br/>~0.97"]
        H["Age 34+: Decline<br/>Steeper"]
    end

    A --> B --> C --> D
    E --> F --> G --> H
```

---

## Stat Dependency Order

### Batters (Must be in this order for consistency)

1. **PA** - Base volume (weighted average)
2. **BB, SO** - Anchored per PA
3. **AB** - Derived: PA - BB - HBP - SF
4. **H** - As BA rate × AB (prevents 7-point AVG leak)
5. **2B, 3B** - Tethered to H as ratios (e.g., HR/H)
6. **HR** - Projected as HR/AB (not HR/H)
7. **AVG, OBP** - Recalculated from final counts

### Pitchers (Must be in this order)

1. **IP** - Base volume (workhorse-aware)
2. **BB, SO, HR** - Per IP
3. **PA** - Per IP (for consistency)
4. **H** - Per PA (more stable than per IP)
5. **ER** - Per IP with gravity anchor
6. **ERA, WHIP** - Recalculated from counts

---

## Key Fixes Applied

| Issue | Solution |
|-------|----------|
| 7-point AVG leak | Project H as BA × AB, not independent |
| HR under-projection | Project HR directly as HR/AB, not HR/H |
| Logan Webb IP math | Convert to true decimal before calculations |
| Slap hitter power | ISO identity gate caps HR/H at 4% |
| Elite ERA outliers | Gravity anchor pulls toward ~2.80 ERA |
| Unproven players | Tax adjustment for players < 500 PA |
| V-shaped injury years | Detection + smoothing available |

---

## Files Involved

| File | Purpose |
|------|---------|
| `bbplayer_projections.py` | Main preprocessing orchestrator |
| `bbplayer_projections_forecast_player.py` | Projection engine with strategies |
| `bbstats.py` | Runtime stats management |
| `at_bat.py` | At-bat simulation using projected stats |

## Running Preprocessing

```bash
# Create projected stats files for simulation
venv_bb314.2/Scripts/python.exe bbplayer_projections.py

# With specific seasons
# Edit load_seasons in bbplayer_projections.py

# Files created:
# {seasons} player-projected-stats-pp-Batting.csv    <- Age-adjusted projections for SIMULATION
# {seasons} player-projected-stats-pp-Pitching.csv   <- Age-adjusted projections for SIMULATION
# {seasons} historical-Batting.csv                   <- Year-by-year data
# {seasons} historical-Pitching.csv                 <- Year-by-year data
# {new_season} New-Season-stats-pp-Batting.csv      <- EMPTY placeholder for accumulating sim data
# {new_season} New-Season-stats-pp-Pitching.csv    <- EMPTY placeholder for accumulating sim data
```
