# AGENTS.md

## Quick Commands

```bash
# Run season simulation (uses uv)
python run.py

# With custom args
python run.py --team NYM --games 81 --seasons 2024,2025 --new-season 2026

# Run individual scripts directly
uv run bbseason_ui.py --team MIL --games 162 --seasons 2023,2024,2025,2026

# Run data preprocessing
uv run bbplayer_projections.py
```

## Environment

- **Python 3.14 (free-threaded)** - Required for multi-threading
- **uv** - Package manager. Use `uv run` or `uv sync`, NOT direct venv paths
- `.venv/` - Local uv virtual environment

## Linting

```bash
uv run ruff check .
uv run ruff format .
```

pyproject.toml: line-length=120, ignores COM812/ISC001

## Architecture Notes

- `run.py` - Entry point for season UI
- `bbseason.py` / `bbgame.py` - Core simulation
- `bbat_bat.py` - At-bat odds-ratio engine (note: file is `bbat_bat.py`, not `at_bat.py`)
- `bbstats.py` - Stats caching (29x speedup), injured/fatigue tracking
- `bbinjuries.py` - Injury durations 5-270 days
- `bbbaserunners.py` - Base advancement logic
- `ui/` - Tkinter UI components

## Data Files

- `player-projected-stats-pp-*.csv` - Age-adjusted projections for simulation
- `historical-*.csv` - Year-by-year data
- `New-Season-stats-pp-*.csv` - Empty placeholder for accumulating season data

## Performance

- DEBUG logging in `odds_ratio()` adds 38% overhead - keep at INFO for production
- Cached RNG in `bbstats.py` provides 29x speedup
- League totals cache provides 2-3x speedup

## Testing

Self-contained with `__main__` blocks. Run individual modules directly.