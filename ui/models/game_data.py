"""
Copyright (c) 2024 Jim Maastricht

Shared data structures for baseball simulation.
"""

from dataclasses import dataclass

# Team indices: AWAY (0) vs HOME (1)
AWAY = 0
HOME = 1


@dataclass
class InningRow:
    """Score for a single inning."""

    number: int
    away_runs: int = 0
    home_runs: int = 0

    def total(self) -> int:
        """Total runs scored in this inning."""
        return self.away_runs + self.home_runs

    def runs_for_team(self, team: int) -> int:
        """Get runs for a specific team (AWAY or HOME)."""
        if team == AWAY:
            return self.away_runs
        elif team == HOME:
            return self.home_runs
        return 0


@dataclass
class InningScore:
    """Alias for InningRow for backward compatibility with Pydantic models."""

    inning: int = 0
    away_runs: int = 0
    home_runs: int = 0

    @classmethod
    def from_inning_row(cls, row: InningRow) -> "InningScore":
        """Create InningScore from InningRow."""
        return cls(inning=row.number, away_runs=row.away_runs, home_runs=row.home_runs)
