# AGENTS.md

## Setup

```bash
uv python install 3.14.0  # free-threaded build REQUIRED (regular CPython 3.14 fails)
uv sync
```

## Commands

```bash
# Season UI (Tkinter) - RECOMMENDED
uv run bbseason_ui.py --team MIL --games 162 --seasons 2023,2024,2025,2026 --new-season 2026

# Wrapper: calls uv run bbseason_ui.py with defaults
uv run run.py [--team TEAM --games N --seasons YEAR,YEAR --new-season YEAR]

# Single game (CLI)
uv run bbgame.py

# Full season (CLI)
uv run bbseason.py

# Preprocess data (after download_stats.py)
uv run bbplayer_projections.py

# Download stats from Baseball Reference (uses Selenium)
uv run download_stats.py

# Download schedule from Baseball Reference
uv run download_schedule.py

# Lint/format (120 char line length, ignores COM812/ISC001)
uv run ruff check .
uv run ruff format .
```

## Key Facts

- **Python 3.14 free-threaded required** - threading fails on regular build
- **Always use `uv run`** - never direct `.venv/` paths
- **Entry point**: `run.py` → `bbseason_ui.py` (Tkinter season UI)
- **Core engine**: `bbat_bat.py` - odds-ratio calculations for batter/pitcher matchups
- **Data flow**: `download_stats.py` → `bbplayer_projections.py` → `bbstats.py` → `bbat_bat.py` → `bbgame.py` → `bbseason.py`
- **Supporting modules**: `bbteam.py` (rosters/lineups), `bbgame_box_stats.py` (box scores), `bbschedule_mgr.py` (scheduling), `bb_aigm_manager.py` (AI GM)
- **UI**: `ui/` package with MVC architecture (`main_window_tk.py`, `season_worker.py`, `signals.py`, `controllers/`, `models/`, `widgets/`)
- **Pygame UI** exists in `archive/bbgame_ui.py` but is not active in current codebase
- **Module self-tests**: `uv run <module>.py` (uses `__main__` block, no separate test files)
- **DEBUG logging** in `bbat_bat.py:odds_ratio()` adds ~38% overhead - keep at INFO

## Known Issues

- **Playoff score corruption**: Scores occasionally corrupted (e.g., 987, 292) from memory/threading issues. `run_playoff_series()` validates scores and falls back to `structured_game.final_score`. See `bbseason.py:992-1010`.

## Further Reading

`CLAUDE.md` (architecture), `docs/PROJECTION_FLOW.md` (projections), `docs/ui_claude.md` (UI reference)