# UI Flow Documentation

This document provides visual flowcharts of the baseball simulator UI architecture.

## Table of Contents
1. [Application Startup](#application-startup)
2. [Main Window Layout](#main-window-layout)
3. [Simulation Flow](#simulation-flow)
4. [Queue Communication](#queue-communication)
5. [Widget Update Flow](#widget-update-flow)
6. [Thread Architecture](#thread-architecture)
7. [Season Progression](#season-progression)

---

## Application Startup

```mermaid
flowchart TB
    subgraph ENTRY["Entry Point: bbseason_ui.py"]
        A[bbseason_ui.py<br/>main function]
    end

    subgraph STARTUP["Startup Dialog"]
        B[StartupDialog<br/>show modal]
        B1[User selects<br/>team to follow]
        B2[User selects<br/>number of games]
        B3[User clicks<br/>Confirm]
        B --> B1 --> B2 --> B3
    end

    subgraph MAIN_WINDOW["Main Window Creation"]
        C[tk.Tk root window<br/>1500 x 900]
        D[SeasonMainWindow<br/>__init__]
        E[SimulationController<br/>__init__]
        F[Create all Widgets]
        G[Start queue polling<br/>100ms interval]
    end

    A --> B
    B3 --> C
    C --> D
    D --> E
    D --> F
    F --> G

    style ENTRY fill:#e1f5fe
    style STARTUP fill:#fff3e0
    style MAIN_WINDOW fill:#e8f5e9
```

---

## Main Window Layout

```mermaid
flowchart TB
    subgraph ROOT["tk.Tk Root Window"]
        TB[ToolbarWidget<br/>Play | Pause | Next Day<br/>Team Dropdown | OBP Adj]
        SB[Status Bar<br/>Day # | Progress | Status]
        PWS[PanedWindow<br/>expand=True]
    end

    subgraph PANES["PanedWindow Panes"]
        LEFT[StandingsWidget<br/>AL | NL<br/>300px min]
        RIGHT[Notebook<br/>Tabs]
    end

    subgraph TABS["Notebook Tabs"]
        T1["Today's Games"<br/>GamesWidget]
        T2["Schedule"<br/>ScheduleWidget]
        T3["League"<br/>Leaders | Stats | IL | Admin]
        T4["{Team}"<br/>Roster | Games | GM Assessment]
        T5["Playoffs"<br/>PlayoffWidget]
    end

    subgraph LEAGUE_SUBS["League Sub-Tabs"]
        L1[LeagueLeadersWidget]
        L2[LeagueStatsWidget]
        L3[InjuriesWidget]
        L4[AdminWidget]
    end

    subgraph TEAM_SUBS["Team Sub-Tabs"]
        TE1[RosterWidget]
        TE2[GamesPlayedWidget]
        TE3[GMAssessmentWidget]
    end

    ROOT --> TB
    ROOT --> SB
    ROOT --> PWS
    PWS --> LEFT
    PWS --> RIGHT
    RIGHT --> T1
    RIGHT --> T2
    RIGHT --> T3
    RIGHT --> T4
    RIGHT --> T5
    T3 -.-> LEAGUE_SUBS
    T4 -.-> TEAM_SUBS
    LEAGUE_SUBS -.-> L1
    LEAGUE_SUBS -.-> L2
    LEAGUE_SUBS -.-> L3
    LEAGUE_SUBS -.-> L4
    TEAM_SUBS -.-> TE1
    TEAM_SUBS -.-> TE2
    TEAM_SUBS -.-> TE3

    style ROOT fill:#fce4ec
    style TABS fill:#e8eaf6
    style PANES fill:#f3e5f5
```

---

## Simulation Flow

```mermaid
sequenceDiagram
    participant User
    participant Toolbar as ToolbarWidget
    participant Controller as SimulationController
    participant Worker as SeasonWorker
    participant Season as UIBaseballSeason
    participant Signals as SeasonSignals
    participant MainWindow as SeasonMainWindow

    User->>Toolbar: Click "Start Season"
    Toolbar->>MainWindow: start_season()
    MainWindow->>Controller: start_season(team, games)
    Controller->>Worker: create SeasonWorker
    Controller->>Worker: start()
    
    Worker->>Season: create UIBaseballSeason
    Worker->>Season: sim_start()
    
    loop Each Day
        Worker->>Season: sim_next_day()
        Season->>Signals: emit_day_started()
        Season->>Season: run games in parallel
        
        loop Each Game
            Season->>Signals: emit_game_completed()
            Signals-->>MainWindow: queue signal
        end
        
        Season->>Signals: emit_day_completed()
        Season->>Signals: emit_injury_update()
        
        alt world_series_active
            Season->>Season: run_world_series()
            Season->>Signals: emit_world_series_started()
            Season->>Signals: emit_play_by_play()
        end
        
        Season->>Signals: emit_season_complete()
    end
    
    Worker->>Signals: emit_simulation_complete()
    Signals-->>MainWindow: simulation_complete
    
    MainWindow->>User: Show completion dialog
```

---

## Queue Communication

```mermaid
flowchart TB
    subgraph WORKER["Worker Thread"]
        W1[UIBaseballSeason<br/>sim_next_day]
        W2[emit_day_started]
        W3[emit_game_completed]
        W4[emit_day_completed]
        W5[emit_injury_update]
        W6[emit_gm_assessment]
        W7[emit_world_series_*]
        W8[emit_simulation_complete]
    end

    subgraph QUEUES["Thread-Safe Queues"]
        Q1[day_started_queue]
        Q2[game_completed_queue]
        Q3[day_completed_queue]
        Q4[injury_update_queue]
        Q5[gm_assessment_queue]
        Q6[world_series_queue]
        Q7[simulation_complete_queue]
    end

    subgraph HANDLERS["Main Window Handlers"]
        H1[_on_day_started]
        H2[_on_game_completed]
        H3[_on_day_completed]
        H4[_on_injury_update]
        H5[_on_gm_assessment]
        H6[_on_world_series_*]
        H7[_on_simulation_complete]
    end

    W1 --> W2
    W1 --> W3
    W1 --> W4
    W1 --> W5
    W1 --> W6
    W1 --> W7
    W1 --> W8

    W2 --> Q1
    W3 --> Q2
    W4 --> Q3
    W5 --> Q4
    W6 --> Q5
    W7 --> Q6
    W8 --> Q7

    Q1 --> H1
    Q2 --> H2
    Q3 --> H3
    Q4 --> H4
    Q5 --> H5
    Q6 --> H6
    Q7 --> H7

    style WORKER fill:#e3f2fd
    style QUEUES fill:#fff8e1
    style HANDLERS fill:#e8f5e9
```

---

## Widget Update Flow

```mermaid
flowchart TB
    subgraph POLL["_poll_queues() every 100ms"]
        P[Check all queues<br/>process messages]
    end

    subgraph DAY_EVENTS["Day Events"]
        D1[_on_day_started]
        D2[_on_day_completed]
    end

    subgraph GAME_EVENTS["Game Events"]
        G1[_on_game_completed]
    end

    subgraph UPDATES["Widget Updates"]
        U1[GamesWidget<br/>update today's games]
        U2[ScheduleWidget<br/>update schedule]
        U3[StandingsWidget<br/>update standings]
        U4[RosterWidget<br/>update roster]
        U5[LeagueStatsWidget<br/>update stats]
        U6[LeagueLeadersWidget<br/>update leaders]
        U7[GamesPlayedWidget<br/>add game recap]
    end

    P --> D1
    P --> D2
    P --> G1

    D1 --> U1
    D1 --> U2

    D2 --> U3
    D2 --> U4
    D2 --> U5
    D2 --> U6

    G1 --> U7

    style POLL fill:#e1f5fe
    style UPDATES fill:#e8f5e9
```

---

## Thread Architecture

```mermaid
flowchart TB
    subgraph MAIN_THREAD["Main Thread (UI)"]
        TK[tkinter mainloop<br/>100ms poll]
        MW[SeasonMainWindow<br/>queue handlers]
        W[Widgets<br/>display updates]
    end

    subgraph WORKER_THREAD["Worker Thread (Simulation)"]
        SW[SeasonWorker<br/>run loop]
        S[UIBaseballSeason<br/>simulation]
        SI[Signals<br/>emit events]
    end

    subgraph SHARED["Shared Objects"]
        Q[Queues<br/>thread-safe]
        C[Controller<br/>lifecycle control]
    end

    TK --> MW
    MW --> W
    MW --> Q
    Q -.-> MW

    SW --> S
    S --> SI
    SI --> Q
    SW --> C
    C -.-> SW

    style MAIN_THREAD fill:#e8f5e9
    style WORKER_THREAD fill:#e3f2fd
    style SHARED fill:#fff8e1
```

---

## Season Progression

```mermaid
flowchart TB
    START[Start Season]
    
    subgraph PRE_GAME["Pre-Game Setup"]
        S1[Create UIBaseballSeason]
        S2[Load teams & players]
        S3[Generate schedule]
        S4[sim_start]
    end

    START --> PRE_GAME

    loop For Each Day
        D1[emit_day_started]
        D2[Simulate all games<br/>parallel threads]
        D3[emit_game_completed<br/>for each game]
        D4[emit_day_completed<br/>all games done]
        D5[emit_injury_update]
        D6[Check GM assessments]
        D7[Update standings]
        
        D1 --> D2 --> D3 --> D4 --> D5 --> D6 --> D7
        
        alt world_series_active
            WS1[Run World Series]
            WS2[emit_world_series_started]
            WS3[emit_play_by_play]
            WS4[emit_world_series_completed]
            D7 --> WS1 --> WS2 --> WS3 --> WS4
        end
    end

    D7 --> CHECK{Days =<br/>Total Games?}
    CHECK -->|Yes| END[emit_simulation_complete]
    CHECK -->|No| loop

    style START fill:#e8f5e9
    style PRE_GAME fill:#e3f2fd
    style END fill:#c8e6c9
```

---

## World Series Gating

```mermaid
flowchart TB
    subgraph STATE["World Series State"]
        WS_ACTIVE{world_series_active<br/>flag}
        WS_TEAMS["world_series_teams<br/>set of 2 teams"]
    end

    WS_ACTIVE -->|False| NORMAL[Normal day processing<br/>All widgets update]

    WS_ACTIVE -->|True| GATED[World Series Active<br/>Widgets gated]

    GATED --> G1[_on_day_started]
    GATED --> G2[_on_day_completed]

    G1 --> G1A[Return early<br/>No widget updates]
    G2 --> G2A[Return early<br/>No widget updates]

    GATED --> G3[_on_game_completed]

    subgraph WS_ROUTING["World Series Routing"]
        G3 --> IS_WS{Game teams in<br/>world_series_teams?}
        IS_WS -->|Yes| PW[PlayoffWidget<br/>add_game_result]
        IS_WS -->|No| SKIP[Skip<br/>Postseason game]
    end

    GATED --> G4[_on_play_by_play]

    subgraph PBP_ROUTING["Play-by-Play Routing"]
        G4 --> IS_PBP{Teams in<br/>world_series_teams?}
        IS_PBP -->|Yes| PBP[Forward to<br/>PlayoffWidget]
        IS_PBP -->|No| IGNORE[Ignore]
    end

    style WS_ACTIVE fill:#fff8e1
    style NORMAL fill:#c8e6c9
    style GATED fill:#ffcdd2
```

---

## Key Files Reference

| File | Purpose |
|------|---------|
| `bbseason_ui.py` | Entry point, StartupDialog |
| `ui/main_window_tk.py` | SeasonMainWindow, layout, queue polling |
| `ui/season_worker.py` | Background thread, pause/resume control |
| `ui/signals.py` | Thread-safe queue communication |
| `ui/controllers/simulation_controller.py` | Worker lifecycle management |
| `ui/ui_baseball_season.py` | UIBaseballSeason, signal emission |
| `ui/widgets/*.py` | Individual UI components |

## Running the UI

```bash
# Full UI with tkinter
venv_bb314.2/Scripts/python.exe ui/main_window_tk.py

# With free-threaded Python for parallel games
uv run -- python -X gil=0 ui/main_window_tk.py
```
