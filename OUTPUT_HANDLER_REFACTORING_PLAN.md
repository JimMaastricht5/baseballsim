# Output Handler Refactoring: Replace Print Statements with Configurable Functions

## Overview

Refactor the baseball simulation to use a configurable output handler function instead of direct `print()` statements. This eliminates the need for UIBaseballSeason to override methods solely for output suppression, making the codebase cleaner and more flexible.

## Current Architecture

### Problems
- **bbseason.py**: 27 direct `print()` calls spread across 7 methods
- **UIBaseballSeason**: Overrides 7 methods just to suppress printing and emit signals instead
- **Code duplication**: Logic duplicated between base class and UI subclass
- **Tight coupling**: Base class assumes console output

### Existing Good Pattern
- **bbgame.py**: Already uses `play_by_play_callback` parameter (14 invocation points)
- Works well for real-time game output
- Will keep this separate from season-level output handler

## Proposed Solution

### Output Handler Function

```python
def output_handler(
    category: str,           # Output type (see categories below)
    text: str,              # Human-readable text
    metadata: Optional[Dict[str, Any]] = None  # Structured data
) -> None:
    """Handle output from season simulation."""
    pass
```

### Output Categories

```python
# Season lifecycle
'season_start'          # Season initialization info
'season_end'            # Final statistics

# Day simulation
'day_schedule'          # Daily game schedule
'day_progress'          # Progress indicators during simulation
'day_standings'         # League standings

# Game results
'game_result_full'      # Full game recap (followed teams)
'game_result_compact'   # Compact summaries (batch of games)

# AI GM
'gm_assessment'         # GM roster assessments

# World Series
'world_series_start'    # WS matchup announcement
'world_series_end'      # Championship result

# Progress
'sim_progress'          # Threading/simulation progress messages
```

### Default Implementations

```python
# Console output (default)
def console_output_handler(category: str, text: str, metadata=None) -> None:
    print(text, end='')

# Null handler (suppress output)
def null_output_handler(category: str, text: str, metadata=None) -> None:
    pass

# UI signal handler (emit to queue)
def create_signal_handler(signals):
    def handler(category: str, text: str, metadata=None):
        if category == 'game_result_full':
            signals.emit_game_completed(metadata)
        elif category == 'day_standings':
            signals.emit_day_completed(metadata['compact_games'], metadata['standings'])
        # ... map other categories
    return handler
```

## Implementation Steps

### Step 1: Add Infrastructure to bbseason.py

**Location**: After imports (~line 46)

```python
from typing import Callable, Optional, Dict, Any

OutputHandlerType = Callable[[str, str, Optional[Dict[str, Any]]], None]

def console_output_handler(category: str, text: str, metadata: Optional[Dict] = None) -> None:
    """Default console output handler."""
    print(text, end='')

def null_output_handler(category: str, text: str, metadata: Optional[Dict] = None) -> None:
    """Null handler that discards output."""
    pass
```

### Step 2: Update BaseballSeason.__init__

**Location**: Line 48-75

Add parameter with default:
```python
def __init__(
    self,
    ...,
    output_handler: Optional[OutputHandlerType] = None,
    ...
) -> None:
    ...
    self.output_handler = output_handler if output_handler is not None else console_output_handler
```

### Step 3: Replace Print Statements (27 locations)

**Pattern**:
```python
# Before:
print(f'Text {variable}')

# After:
self.output_handler(
    'category',
    f'Text {variable}\n',
    metadata={'key': value}
)
```

**Key Methods to Update**:

1. **sim_start()** (lines 572-579): 4 prints → 'season_start' category
2. **sim_end()** (lines 586-596): 4 prints → 'season_end' category
3. **print_standings()** (lines 268-289): 3 prints → 'day_standings' category
4. **_process_and_print_game_results()** (lines 322, 326): 2 prints → 'game_result_full' / 'game_result_compact'
5. **sim_day_threaded()** (lines 697, 702, 717-718): 4 prints → 'day_schedule' / 'sim_progress'
6. **run_world_series()** (lines 778-814): 8 prints → 'world_series_start' / 'world_series_end'
7. **check_gm_assessments()** (indirect via print): → 'gm_assessment'

**Special Case - print_standings()**:
- Refactor to build text string first
- Extract structured standings data
- Pass both to handler

```python
def print_standings(self) -> None:
    standings_text = self._build_standings_text()  # New helper
    standings_data = self._extract_standings_data()  # Reuse existing helper

    self.output_handler(
        'day_standings',
        standings_text,
        metadata={'standings': standings_data}
    )
```

### Step 4: Update MultiBaseballSeason

**Location**: Lines 840-958

Pass handler to child seasons:
```python
self.bbseason_a = BaseballSeason(..., output_handler=output_handler, ...)
self.bbseason_b = BaseballSeason(..., output_handler=output_handler, ...)
```

### Step 5: Simplify UIBaseballSeason

**Location**: `ui/ui_baseball_season.py`

**Add signal handler creator** (~line 50):
```python
def _create_signal_output_handler(self, signals: SeasonSignals):
    """Create output handler that emits signals instead of printing."""
    def handler(category: str, text: str, metadata: Optional[Dict] = None):
        if category == 'game_result_full':
            signals.emit_game_completed(metadata)
        elif category == 'day_standings':
            signals.emit_day_completed(
                metadata.get('compact_games', []),
                metadata['standings']
            )
        elif category == 'gm_assessment':
            signals.emit_gm_assessment_ready(metadata)
        # Other categories can be ignored or logged
    return handler
```

**Update __init__**:
```python
def __init__(self, signals: SeasonSignals, *args, **kwargs):
    output_handler = self._create_signal_output_handler(signals)
    super().__init__(*args, output_handler=output_handler, **kwargs)
    self.signals = signals
```

**Remove/simplify overrides**:
- **DELETE**: `print_standings()` override (line 281-289)
- **DELETE**: `sim_start()` override (line 291-300)
- **DELETE**: `sim_end()` override (line 301-318)
- **SIMPLIFY**: `_process_and_print_game_results()` - Move shared logic to base class
- **KEEP**: `sim_day_threaded()` - Still needed for play-by-play callback injection
- **SIMPLIFY**: `check_gm_assessments()` - Can reduce override
- **SIMPLIFY**: `run_world_series()` - Reduce to signal-specific logic

## Print Statement Locations (27 total)

### bbseason.py detailed locations:

| Method | Line(s) | Count | Category |
|--------|---------|-------|----------|
| `sim_start()` | 572, 576, 578, 579 | 4 | season_start |
| `sim_end()` | 586, 588, 589, 591, 596 | 5 | season_end |
| `print_standings()` | 268, 269, 287, 289 | 4 | day_standings |
| `_process_and_print_game_results()` | 322, 326 | 2 | game_result_* |
| `sim_day_threaded()` | 660, 697, 702, 717, 718 | 5 | day_schedule, sim_progress |
| `run_world_series()` | 778, 779, 780, 781, 782, 802, 811, 814 | 8 | world_series_* |

**Note**: Some methods have multiple print statements that need different categories based on context.

## Critical Files

### Primary Changes
1. **bbseason.py** - Core refactoring (27 print replacements)
   - Lines: 46 (infrastructure), 56 (__init__), 268-289, 322-326, 572-596, 660-718, 778-814
2. **ui/ui_baseball_season.py** - Simplification (remove 3+ overrides)
   - Lines: 50 (new handler), 36 (__init__), 92-145, 281-318 (removals)

### Reference Files
3. **ui/signals.py** - Understand signal types for mapping
4. **bbgame.py** - Keep play_by_play_callback pattern (no changes needed)
5. **ui/main_window_tk.py** - Verify UI integration still works

## Backward Compatibility

**Existing code continues to work**:
```python
# No output_handler specified → defaults to console_output_handler
season = BaseballSeason(...)  # Prints to console as before
season.sim_start()             # Output visible in terminal
```

**Suppress output**:
```python
from bbseason import null_output_handler
season = BaseballSeason(..., output_handler=null_output_handler)
```

**Custom handler**:
```python
def my_handler(category, text, metadata):
    if category == 'game_result_full':
        log_game(metadata)
    # Can selectively handle categories

season = BaseballSeason(..., output_handler=my_handler)
```

## Testing Strategy

### Unit Tests
1. Default behavior (no handler specified) → console output
2. Null handler → no output
3. Custom handler → verify categories captured

### Integration Tests
1. Run full season with console handler → compare output to baseline
2. Run UI simulation → verify all signals still emitted
3. Run with mixed handlers → selective output

### Verification
```bash
# Test console mode still works
cd /mnt/c/Users/jimma/PycharmProjects/baseballsimgit
venv_bb314.2/Scripts/python.exe bbseason.py

# Test UI mode still works
venv_bb314.2/Scripts/python.exe ui/main.py
```

## Benefits

1. **Cleaner architecture**: Base class is output-agnostic
2. **Less code**: Remove 4+ method overrides from UIBaseballSeason
3. **Flexible**: Easy to add file logging, database output, etc.
4. **Testable**: Can capture output for testing without mocking print()
5. **Consistent**: Matches existing play_by_play_callback pattern
6. **Backward compatible**: Existing scripts continue to work

## Trade-offs

**Chosen Design**:
- Single handler with categories (simple API)
- Keep game play_by_play_callback separate (different use case)
- Default to console output (backward compatible)

**Alternative Rejected**:
- Multiple handler parameters (standings_handler, game_handler, etc.)
  - Reason: Too many parameters, harder to extend

## Implementation Effort

- **Step 1-2**: Infrastructure and __init__ (~30 min)
- **Step 3**: Replace 27 print statements (~2 hours)
- **Step 4**: Update MultiBaseballSeason (~15 min)
- **Step 5**: Simplify UIBaseballSeason (~1 hour)
- **Testing**: Verification (~1-2 hours)
- **Total**: ~5-6 hours

## Migration Sequence

### Phase 1: Foundation (Non-Breaking)
1. Add output handler infrastructure to bbseason.py
2. Add parameter to __init__ with default
3. Test: Existing code still works

### Phase 2: Replace Prints (Non-Breaking)
1. Convert print statements method-by-method
2. Test after each method conversion
3. Verify console output matches original

### Phase 3: UI Integration
1. Update UIBaseballSeason
2. Remove unnecessary overrides
3. Test UI signal emission

### Phase 4: Cleanup (Optional)
1. Update documentation
2. Add handler examples
3. Remove redundant parameters if any

## Example: Before and After

### Before (bbseason.py):
```python
def sim_start(self) -> None:
    print(f'{self.new_season} will have {len(self.schedule)} games per team with {len(self.teams)} teams.')
    print(f'{teams_paragraph}\n\n')
```

### After (bbseason.py):
```python
def sim_start(self) -> None:
    self.output_handler(
        'season_start',
        f'{self.new_season} will have {len(self.schedule)} games per team with {len(self.teams)} teams.\n',
        metadata={'season': self.new_season, 'games': len(self.schedule), 'teams': self.teams}
    )
    self.output_handler(
        'season_start',
        f'{teams_paragraph}\n\n',
        metadata={'team_names': self.team_city_dict}
    )
```

### Before (ui_baseball_season.py):
```python
class UIBaseballSeason(bbseason.BaseballSeason):
    def sim_start(self) -> None:
        """Override to suppress printing start info."""
        logger.info(f"Starting {self.new_season} season...")
        # Suppress the print statements from parent
        pass
```

### After (ui_baseball_season.py):
```python
class UIBaseballSeason(bbseason.BaseballSeason):
    def __init__(self, signals: SeasonSignals, *args, **kwargs):
        output_handler = self._create_signal_output_handler(signals)
        super().__init__(*args, output_handler=output_handler, **kwargs)

    # sim_start() override NO LONGER NEEDED - deleted
```
