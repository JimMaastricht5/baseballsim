# AGENTS.md

## Critical Setup

```bash
# First-time setup (MUST DO)
uv python install 3.14.0  # Freethreaded REQUIRED - regular build fails
uv sync
```

## Essential Commands

```bash
# Season simulation with UI (Tkinter) - RECOMMENDED
uv run bbseason_ui.py --team MIL --games 162 --seasons 2023,2024,2025,2026 --new-season 2026

# Convenience wrapper (same as above)
python run.py [--team TEAM --games N --seasons YEAR,YEAR --new-season YEAR]

# Visual game simulation (Pygame)
uv run bbgame_ui.py

# Single game (CLI)
uv run bbgame.py

# Full season (CLI)
uv run bbseason.py

# Data preprocessing (after downloading stats)
uv run bbplayer_projections.py

# Download fresh stats from RotoWire
uv run download_stats.py

# Linting
uv run ruff check .
uv run ruff format .
```

## Critical Notes

- **Python 3.14 freethreaded REQUIRED** - Regular build causes threading failures
- **ONLY use `uv run`** - Never direct `.venv/` paths
- **Entry point**: `run.py` (wrapper for `bbseason_ui.py`)
- **Core engine**: `bbat_bat.py` - odds-ratio calculations
- **Performance**: DEBUG logging adds 38% overhead in `odds_ratio()` - keep at INFO
- **Data flow**: download → preprocess → stats → at-bat → game → season
- **Testing**: `uv run <module>.py` for self-tests via `__main__` blocks