"""
Widget components for the season simulation UI.
"""

from .toolbar import ToolbarWidget
from .standings_widget import StandingsWidget
from .games_widget import GamesWidget
from .schedule_widget import ScheduleWidget
from .injuries_widget import InjuriesWidget
from .roster_widget import RosterWidget
from .admin_widget import AdminWidget
from .games_played_widget import GamesPlayedWidget
from .gm_assessment_widget import GMAssessmentWidget

__all__ = [
    'ToolbarWidget',
    'StandingsWidget',
    'GamesWidget',
    'ScheduleWidget',
    'InjuriesWidget',
    'RosterWidget',
    'AdminWidget',
    'GamesPlayedWidget',
    'GMAssessmentWidget',
]
