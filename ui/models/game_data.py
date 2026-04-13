"""
--- Copyright Notice ---
Copyright (c) 2024 Jim Maastricht

Shared data structures for baseball simulation.
Used by both the simulation engine and UI widgets.
"""

from dataclasses import dataclass

# Team indices
# Used throughout the codebase to identify away (0) vs home (1) team
AWAY = 0
HOME = 1


@dataclass
class InningRow:
    """
    Represents the score for a single inning.

    Attributes:
        number: The inning number (1-9 for regulation, 10+ for extra innings)
        away_runs: Runs scored by the away team in this inning
        home_runs: Runs scored by the home team in this inning

    Example:
        >>> inning = InningRow(number=1, away_runs=2, home_runs=1)
        >>> inning.away_runs
        2
    """

    number: int
    away_runs: int = 0
    home_runs: int = 0

    def total(self) -> int:
        """Total runs scored in this inning."""
        return self.away_runs + self.home_runs

    def runs_for_team(self, team: int) -> int:
        """
        Get runs for a specific team.

        Args:
            team: AWAY (0) or HOME (1)

        Returns:
            Runs scored by that team
        """
        if team == AWAY:
            return self.away_runs
        elif team == HOME:
            return self.home_runs
        return 0


@dataclass
class InningScore:
    """
    Alias for InningRow for backward compatibility with Pydantic models.

    The UI uses this name in GameRecap.inning_scores.
    The simulation engine uses InningRow internally.
    """

    inning: int = 0
    away_runs: int = 0
    home_runs: int = 0

    @classmethod
    def from_inning_row(cls, row: InningRow) -> "InningScore":
        """Create InningScore from InningRow."""
        return cls(inning=row.number, away_runs=row.away_runs, home_runs=row.home_runs)
