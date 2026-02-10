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
from .league_stats_widget import LeagueStatsWidget
from .league_leaders_widget import LeagueLeadersWidget
from .playoff_widget import PlayoffWidget

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
    'LeagueStatsWidget',
    'LeagueLeadersWidget',
    'PlayoffWidget',
]
