# MIT License
#
# 2024 Jim Maastricht
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
#
# JimMaastricht5@gmail.com
"""
AI General Manager for baseball simulation.

This module implements intelligent general managers that make roster decisions based on
team performance, player value, and organizational strategy. Each GM has a unique strategy
coefficient (alpha) that determines whether they prioritize winning now or building for
the future.

Key Features:
- Dynamic strategy adjustment based on team performance (contending vs rebuilding)
- Player valuation combining immediate and future value
- Trade recommendations (buy/sell decisions)
- Roster management (promote/demote/release decisions)
- Contract and salary considerations
- Age-adjusted player projections

Alpha Strategy Coefficient (α):
- α = 0.8-1.0: Aggressive contender (win now at all costs)
- α = 0.6-0.8: Contending team (prioritize current season)
- α = 0.4-0.6: Balanced approach (compete while building)
- α = 0.2-0.4: Retooling team (sell vets, acquire prospects)
- α = 0.0-0.2: Full rebuild (future assets only)

Player Value Formula:
    V_player = α * V_immediate + (1-α) * V_future

    Where:
    - V_immediate: Current season Sim_WAR, adjusted for health/streaks
    - V_future: Age-adjusted potential value over remaining career
    - α: Team strategy coefficient (win now vs win later)
"""
import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from bblogger import logger


@dataclass
class TeamStrategy:
    """
    Represents a team's strategic approach to roster management.

    Attributes:
        alpha: Strategy coefficient (0.0-1.0) where high=win now, low=rebuild
        games_back: Games behind division/wildcard leader
        win_pct: Current winning percentage
        stage: Description of team strategy stage
        games_played: Number of games played this season
    """
    alpha: float
    games_back: float
    win_pct: float
    stage: str
    games_played: int = 0


@dataclass
class PlayerValue:
    """
    Comprehensive player valuation for trade/roster decisions.

    Attributes:
        player_name: Player name
        hashcode: Player unique identifier
        total_value: Combined weighted value (immediate + future)
        immediate_value: Current season value (Sim_WAR based)
        future_value: Age-adjusted projected value
        salary: Annual salary
        value_per_dollar: Total value divided by salary
        age: Player age
        years_remaining: Contract years remaining (estimated)
        team: Current team
        position: Position(s) played
    """
    player_name: str
    hashcode: int
    total_value: float
    immediate_value: float
    future_value: float
    salary: float
    value_per_dollar: float
    age: int
    years_remaining: int
    team: str
    position: str


class GMStrategy:
    """
    Determines team strategy (alpha coefficient) based on performance and standings.

    The alpha coefficient determines how a GM weights immediate vs future value:
    - High alpha (0.8+): Contending team prioritizes current season (buyers)
    - Low alpha (0.2-): Rebuilding team prioritizes future assets (sellers)
    """

    def __init__(self):
        """Initialize strategy calculator with league context parameters."""
        # Alpha calculation parameters
        self.alpha_max = 0.95  # Maximum alpha for elite contenders
        self.alpha_min = 0.05  # Minimum alpha for full rebuild
        self.alpha_balanced = 0.50  # Neutral strategy

        # Performance thresholds
        self.contender_win_pct = 0.550  # 89+ win pace (contending)
        self.rebuild_win_pct = 0.450  # 73- win pace (rebuilding)
        self.games_back_contender = 3.0  # Within 3 games = contending
        self.games_back_rebuild = 10.0  # 10+ games back = rebuild

    def calculate_alpha(self, team_record: Tuple[int, int], games_back: float,
                       games_played: int, is_playoff_race: bool = True) -> TeamStrategy:
        """
        Calculate team's strategy coefficient based on current performance.

        Formula combines:
        1. Win percentage (40% weight) - overall team quality
        2. Games back (40% weight) - playoff positioning
        3. Season timing (20% weight) - urgency increases late season

        Args:
            team_record: Tuple of (wins, losses)
            games_back: Games behind division/wildcard leader (negative if leading)
            games_played: Games into the season (1-162)
            is_playoff_race: Whether team is in realistic playoff contention

        Returns:
            TeamStrategy object with alpha, context, and description
        """
        wins, losses = team_record
        win_pct = wins / (wins + losses) if (wins + losses) > 0 else 0.500

        # Component 1: Win percentage signal (-1.0 to 1.0)
        # Positive = above average, negative = below average
        if win_pct >= self.contender_win_pct:
            win_pct_signal = (win_pct - self.contender_win_pct) / (1.0 - self.contender_win_pct)
        elif win_pct <= self.rebuild_win_pct:
            win_pct_signal = (win_pct - self.rebuild_win_pct) / self.rebuild_win_pct
        else:
            # Between rebuild and contender thresholds - linear interpolation
            win_pct_signal = (win_pct - self.rebuild_win_pct) / (self.contender_win_pct - self.rebuild_win_pct) * 2 - 1

        # Component 2: Games back signal (-1.0 to 1.0)
        # Negative games_back means team is leading
        if games_back <= 0:  # Leading division
            games_back_signal = min(1.0, abs(games_back) / 5.0)  # Cap at +1.0
        elif games_back <= self.games_back_contender:  # Close to lead
            games_back_signal = 0.5 * (1 - games_back / self.games_back_contender)
        elif games_back >= self.games_back_rebuild:  # Far from playoffs
            games_back_signal = -1.0
        else:  # Between contender and rebuild
            games_back_signal = -((games_back - self.games_back_contender) /
                                  (self.games_back_rebuild - self.games_back_contender))

        # Component 3: Season timing urgency (0.0 to 1.0)
        # Early season: less urgent, Late season: more urgent
        season_progress = games_played / 162.0
        urgency = season_progress ** 2  # Quadratic urgency curve

        # Combine signals with weights
        base_signal = (0.40 * win_pct_signal +
                      0.40 * games_back_signal +
                      0.20 * urgency)

        # If not in realistic playoff race, push toward rebuild regardless of record
        if not is_playoff_race and games_back > self.games_back_rebuild:
            base_signal = min(base_signal, -0.3)

        # Convert signal to alpha (0.0 to 1.0)
        # base_signal ranges from -1.0 (full rebuild) to +1.0 (max contender)
        alpha = self.alpha_balanced + (base_signal * (self.alpha_balanced - self.alpha_min))
        alpha = np.clip(alpha, self.alpha_min, self.alpha_max)

        # Determine strategic stage
        stage = self._determine_stage(alpha, win_pct, games_back)

        logger.info(f"Strategy calculation: W-L={wins}-{losses} ({win_pct:.3f}), "
                   f"GB={games_back:.1f}, G={games_played}, alpha={alpha:.3f}, Stage={stage}")

        return TeamStrategy(
            alpha=alpha,
            games_back=games_back,
            win_pct=win_pct,
            stage=stage,
            games_played=games_played
        )

    def _determine_stage(self, alpha: float, win_pct: float, games_back: float) -> str:
        """Classify team's strategic stage based on alpha and performance."""
        if alpha >= 0.80:
            return "Aggressive Contender"
        elif alpha >= 0.60:
            return "Contending"
        elif alpha >= 0.40:
            return "Balanced/Retooling"
        elif alpha >= 0.20:
            return "Rebuilding"
        else:
            return "Full Rebuild"


class PlayerValuation:
    """
    Calculate player value considering immediate and future contributions.

    Combines current performance (Sim_WAR) with age-adjusted future projections
    to produce a strategy-weighted total value for roster decisions.
    """

    def __init__(self):
        """Initialize valuation model with aging curves and projections."""
        # Age curve parameters (based on MLB aging research)
        self.peak_age = 29  # Peak performance age
        self.career_start_age = 20  # Typical career start
        self.career_end_age = 40  # Typical career end

        # Value projection parameters
        self.replacement_war = 0.0  # Replacement level (0 WAR)
        self.discount_rate = 0.10  # 10% annual discount for future value

        # Contract estimation (if not available)
        self.min_years_remaining = 0  # Free agent
        self.max_years_remaining = 6  # Long-term contract

    def calculate_player_value(self, player_row: pd.Series, alpha: float,
                               team_games_played: int, is_pitcher: bool = False) -> PlayerValue:
        """
        Calculate comprehensive player value with strategy weighting.

        Args:
            player_row: Player stats row from batting_data or pitching_data
            alpha: Team strategy coefficient (0.0-1.0)
            team_games_played: Number of games the team has played this season
            is_pitcher: Whether player is a pitcher

        Returns:
            PlayerValue dataclass with all valuation components
        """
        # Extract player attributes
        player_name = player_row.get('Player', 'Unknown')
        hashcode = player_row.name  # Index is Hashcode
        age = player_row.get('Age', 30)
        team = player_row.get('Team', '')
        salary = player_row.get('Salary', 740000)  # League minimum default

        # Get position (handle both string and list formats)
        pos = player_row.get('Pos', 'P' if is_pitcher else 'Unknown')
        if isinstance(pos, list):
            position = ','.join(pos)
        else:
            position = str(pos) if pos else ('P' if is_pitcher else 'Unknown')

        # Calculate immediate value (current season)
        immediate_value = self._calculate_immediate_value(player_row, team_games_played, is_pitcher)

        # Calculate future value (age-adjusted projections)
        future_value = self._calculate_future_value(player_row, age, is_pitcher)

        # Estimate contract years remaining
        years_remaining = self._estimate_years_remaining(age, salary, is_pitcher)

        # Weighted total value based on alpha
        total_value = alpha * immediate_value + (1 - alpha) * future_value

        # Value per dollar (for budget-conscious decisions)
        value_per_dollar = total_value / (salary / 1_000_000) if salary > 0 else 0.0

        return PlayerValue(
            player_name=player_name,
            hashcode=int(hashcode),
            total_value=total_value,
            immediate_value=immediate_value,
            future_value=future_value,
            salary=salary,
            value_per_dollar=value_per_dollar,
            age=age,
            years_remaining=years_remaining,
            team=team,
            position=position
        )

    def _calculate_immediate_value(self, player_row: pd.Series, team_games_played: int,
                                   is_pitcher: bool) -> float:
        """
        Calculate immediate value based on current season performance.

        Components:
        - Base: Sim_WAR (current season performance)
        - Adjustments: Playing time ratio (normalized by team games), injury status, streak

        Args:
            player_row: Player stats row
            team_games_played: Total games the team has played this season
            is_pitcher: Whether this is a pitcher
        """
        sim_war = player_row.get('Sim_WAR', 0.0)

        # Adjustment 1: Normalize playing time by team's season progress
        # The key insight: a player's value should be consistent regardless of when we assess
        # If team has played 81 games and player has played 40 (49%), they're on pace for ~79 games (49% of 162)
        player_games = player_row.get('G', 0)

        if team_games_played > 0:
            # Calculate what % of team games the player has participated in
            participation_rate = player_games / team_games_played
            # Most regulars play ~90% of games, bench players ~40%
            # We don't project forward; instead we assess their current contribution rate
            playing_time_factor = min(participation_rate / 0.85, 1.2)  # Normalize to "regular" (85% participation)
        else:
            playing_time_factor = 1.0

        if is_pitcher:
            # For pitchers, also consider IP as additional context
            ip = player_row.get('IP', 0)
            # Typical starter: ~180 IP/season, reliever: ~70 IP/season
            # Adjust based on role expectation
            if ip > 0:
                ip_per_game = ip / max(player_games, 1)
                # Starters avg ~6 IP/appearance, relievers ~1 IP/appearance
                # Use IP rate to modulate the playing time factor
                if ip_per_game >= 3.0:  # Likely a starter
                    ip_factor = min(ip / 100, 1.5)  # Expect ~100+ IP for assessment
                else:  # Likely a reliever
                    ip_factor = min(ip / 40, 1.5)  # Expect ~40+ IP for assessment
                playing_time_factor = (playing_time_factor + ip_factor) / 2

        # Apply playing time adjustment to base WAR
        projected_war = sim_war * playing_time_factor

        # Adjustment 2: Health/availability (injured players have reduced immediate value)
        injured_days = player_row.get('Injured Days', 0)
        health_factor = max(0.0, 1.0 - (injured_days / 162.0))  # Reduce by days lost

        # Adjustment 3: Current streak (hot/cold affects short-term value)
        streak_adj = player_row.get('Streak_Adjustment', 0.0)
        streak_factor = 1.0 + (streak_adj * 0.5)  # Streak worth ±5% at extremes

        immediate_value = projected_war * health_factor * streak_factor

        return max(immediate_value, self.replacement_war)

    def _calculate_future_value(self, player_row: pd.Series, age: int, is_pitcher: bool) -> float:
        """
        Calculate future value based on age-adjusted career projections.

        Uses aging curves to project remaining career value, discounted by years.
        Younger players have more future value, older players have less.
        """
        sim_war = player_row.get('Sim_WAR', 0.0)

        # Estimate peak WAR based on current performance and age
        # Players improve until peak age, then decline
        if age < self.peak_age:
            # Young player: project improvement to peak
            years_to_peak = self.peak_age - age
            improvement_rate = 0.15  # 15% improvement per year (aggressive for prospects)
            peak_war = sim_war * (1 + improvement_rate) ** years_to_peak
        else:
            # Peak or declining: current performance is close to peak
            peak_war = sim_war * 1.05  # Slight upside

        # Project career trajectory from current age
        years_remaining = max(0, self.career_end_age - age)
        future_value_total = 0.0

        for year_offset in range(1, min(years_remaining + 1, 10)):  # Look ahead max 10 years
            future_age = age + year_offset

            # Age curve: decline after peak
            if future_age <= self.peak_age:
                age_factor = min(1.0, future_age / self.peak_age)
            else:
                # Decline curve: -2% per year after 29 (position players)
                #                -3% per year after 29 (pitchers)
                decline_rate = 0.03 if is_pitcher else 0.02
                years_past_peak = future_age - self.peak_age
                age_factor = max(0.0, 1.0 - (decline_rate * years_past_peak))

            # Project WAR for this future year
            projected_war_year = peak_war * age_factor

            # Discount future value (10% per year)
            discount_factor = (1 - self.discount_rate) ** year_offset

            # Add to cumulative future value
            future_value_total += projected_war_year * discount_factor

        return max(future_value_total, 0.0)

    def _estimate_years_remaining(self, age: int, salary: float, is_pitcher: bool) -> int:
        """
        Estimate contract years remaining based on age and salary.

        Heuristic approach:
        - Young players (< 27): Likely on team control (2-5 years)
        - Prime players (27-32) with high salary: Long contracts (3-6 years)
        - Older players (33+): Short contracts (1-2 years)
        - League minimum: Likely 1 year or arbitration
        """
        league_min = 740000

        if salary <= league_min * 1.2:  # Near minimum
            return 1 if age >= 30 else 2  # Short deal or arbitration
        elif age < 27:
            return 4  # Pre-arbitration or early arbitration
        elif age >= 33:
            return max(1, int(42 - age) // 3)  # Short deals late career
        else:
            # Prime age with salary: estimate based on salary
            if salary >= 20_000_000:
                return 5  # Star player, long deal
            elif salary >= 10_000_000:
                return 3  # Above-average, medium term
            else:
                return 2  # Average player, shorter term


class AIGeneralManager:
    """
    AI General Manager that makes strategic roster decisions.

    Evaluates roster every N games and makes recommendations for:
    - Trades (which players to acquire/trade away)
    - Promotions (call-ups from minors)
    - Releases (cut unproductive veterans)
    - Contract priorities (who to extend/let walk)
    """

    def __init__(self, team_name: str, assessment_frequency: int = 30):
        """
        Initialize AI GM for a specific team.

        Args:
            team_name: Team abbreviation (e.g., 'NYY', 'LAD')
            assessment_frequency: How often (games) to reassess roster
        """
        self.team_name = team_name
        self.assessment_frequency = assessment_frequency
        self.last_assessment_game = 0

        # Initialize strategy calculator and valuation model
        self.strategy_calculator = GMStrategy()
        self.valuator = PlayerValuation()

        # GM decision thresholds
        self.min_value_to_keep = -0.5  # Release if below this WAR value
        self.trade_value_threshold = 2.0  # Consider trading if value exceeds this
        self.promotion_threshold = 1.0  # Promote prospects if projected above this

        logger.info(f"Initialized AI GM for {team_name}, assessing every {assessment_frequency} games")

    def should_assess(self, games_played: int) -> bool:
        """
        Determine if it's time for a roster assessment.

        Args:
            games_played: Total games played by team this season

        Returns:
            True if assessment is due
        """
        if games_played >= self.last_assessment_game + self.assessment_frequency:
            return True
        return False

    def assess_roster(self, baseball_stats, team_record: Tuple[int, int],
                     games_back: float, games_played: int) -> Dict:
        """
        Perform comprehensive roster assessment and generate recommendations.

        Args:
            baseball_stats: BaseballStats instance with current season data
            team_record: Tuple of (wins, losses)
            games_back: Games behind division/wildcard leader
            games_played: Games into season

        Returns:
            Dictionary with assessment results and recommendations
        """
        logger.info(f"\n{'='*60}")
        logger.info(f"AI GM Assessment: {self.team_name} after {games_played} games")
        logger.info(f"Record: {team_record[0]}-{team_record[1]}, GB: {games_back:.1f}")
        logger.info(f"{'='*60}")

        # Update last assessment
        self.last_assessment_game = games_played

        # Step 1: Calculate team strategy (alpha)
        strategy = self.strategy_calculator.calculate_alpha(
            team_record, games_back, games_played
        )

        logger.info(f"Strategy: {strategy.stage} (alpha={strategy.alpha:.3f})")
        logger.info(f"Win Pct: {strategy.win_pct:.3f}, Games Back: {strategy.games_back:.1f}")

        # Step 2: Value all players on roster
        roster_values = self._value_roster(baseball_stats, strategy.alpha, games_played)

        # Step 3: Generate recommendations based on strategy
        recommendations = self._generate_recommendations(
            roster_values, strategy, baseball_stats
        )

        # Step 4: Print summary
        self._print_assessment_summary(strategy, roster_values, recommendations)

        return {
            'strategy': strategy,
            'roster_values': roster_values,
            'recommendations': recommendations,
            'games_played': games_played
        }

    def _value_roster(self, baseball_stats, alpha: float, team_games_played: int) -> Dict[str, List[PlayerValue]]:
        """
        Value all batters and pitchers on the roster.

        Args:
            baseball_stats: BaseballStats instance
            alpha: Strategy coefficient
            team_games_played: Number of games the team has played this season

        Returns:
            Dictionary with 'batters' and 'pitchers' lists of PlayerValue objects
        """
        roster_values = {'batters': [], 'pitchers': []}

        # Value batters
        team_batters = baseball_stats.new_season_batting_data[
            baseball_stats.new_season_batting_data['Team'] == self.team_name
        ]

        for idx, batter_row in team_batters.iterrows():
            value = self.valuator.calculate_player_value(batter_row, alpha, team_games_played, is_pitcher=False)
            roster_values['batters'].append(value)

        # Value pitchers
        team_pitchers = baseball_stats.new_season_pitching_data[
            baseball_stats.new_season_pitching_data['Team'] == self.team_name
        ]

        for idx, pitcher_row in team_pitchers.iterrows():
            value = self.valuator.calculate_player_value(pitcher_row, alpha, team_games_played, is_pitcher=True)
            roster_values['pitchers'].append(value)

        # Sort by total value
        roster_values['batters'].sort(key=lambda x: x.total_value, reverse=True)
        roster_values['pitchers'].sort(key=lambda x: x.total_value, reverse=True)

        return roster_values

    def _generate_recommendations(self, roster_values: Dict, strategy: TeamStrategy,
                                 baseball_stats) -> Dict[str, List]:
        """
        Generate trade and roster move recommendations based on strategy.

        Args:
            roster_values: Dictionary with team's batters and pitchers
            strategy: TeamStrategy with alpha and context
            baseball_stats: BaseballStats instance with league-wide data

        Returns:
            Dictionary with 'trade_away', 'trade_targets', 'promote', 'release' lists
        """
        recommendations = {
            'trade_away': [],  # Players to trade away
            'trade_targets': [],  # Player types to target (generic)
            'specific_targets': [],  # Specific players to target from other teams
            'promote': [],  # Prospects to call up
            'release': []  # Players to release
        }

        all_players = roster_values['batters'] + roster_values['pitchers']

        # CONTENDING TEAM (High Alpha) - Buy mode
        if strategy.alpha >= 0.60:
            # Look to trade away:
            # 1. Young prospects not contributing now (package for upgrades)
            # 2. Underperforming veterans who are blocking prospects
            for player in all_players:
                # Young prospects: future > immediate and not helping now
                if (player.age < 25 and
                    player.future_value > player.immediate_value * 1.5 and
                    player.immediate_value < 1.5):
                    recommendations['trade_away'].append({
                        'player': player.player_name,
                        'reason': f"Prospect (age {player.age}) - future ({player.future_value:.1f}) > now ({player.immediate_value:.1f}), trade chip for upgrade",
                        'value': player.total_value
                    })
                # Underperforming veterans with bad contracts
                elif (player.age >= 30 and
                      player.total_value < 0.5 and
                      player.salary > 3_000_000):
                    recommendations['trade_away'].append({
                        'player': player.player_name,
                        'reason': f"Underperforming vet (age {player.age}, ${player.salary/1e6:.1f}M) - low value ({player.total_value:.1f})",
                        'value': player.total_value
                    })

            # Look to acquire: High immediate value, low future value
            # (Win-now veterans)
            recommendations['trade_targets'].append({
                'profile': 'Veteran bat (age 30+)',
                'target_value': 'Immediate WAR > 2.0',
                'reason': 'Add playoff-caliber production'
            })
            recommendations['trade_targets'].append({
                'profile': 'Proven starter (age 30-35)',
                'target_value': 'Immediate WAR > 2.5',
                'reason': 'Strengthen rotation for stretch run'
            })

            # Find specific players matching contender needs
            specific_targets = self._find_specific_trade_targets(
                baseball_stats, strategy, is_contender=True
            )
            recommendations['specific_targets'].extend(specific_targets)

        # REBUILDING TEAM (Low Alpha) - Sell mode
        elif strategy.alpha <= 0.40:
            # Look to trade away: High immediate value but low future value
            # (Veterans on expiring contracts)
            for player in all_players:
                if (player.immediate_value > 2.0 and
                    player.future_value < 1.0 and
                    player.age >= 30 and
                    player.years_remaining <= 2):
                    recommendations['trade_away'].append({
                        'player': player.player_name,
                        'reason': f"Veteran (age {player.age}) on short deal - peak trade value",
                        'value': player.total_value
                    })

            # Look to acquire: Young players with upside
            recommendations['trade_targets'].append({
                'profile': 'Young position player (age 20-24)',
                'target_value': 'Future WAR > 3.0',
                'reason': 'Build core for future contention'
            })
            recommendations['trade_targets'].append({
                'profile': 'High-ceiling pitching prospect',
                'target_value': 'Future WAR > 4.0',
                'reason': 'Develop rotation for future'
            })

            # Find specific young players with high upside
            specific_targets = self._find_specific_trade_targets(
                baseball_stats, strategy, is_contender=False
            )
            recommendations['specific_targets'].extend(specific_targets)

        # BALANCED TEAM - Strategic moves only
        else:
            # Look for value inefficiencies
            for player in all_players:
                if player.value_per_dollar < 0.0 and player.salary > 5_000_000:
                    recommendations['trade_away'].append({
                        'player': player.player_name,
                        'reason': f"Negative value (${player.salary/1e6:.1f}M) - salary relief",
                        'value': player.total_value
                    })

        # RELEASES: Any strategy - cut unproductive players
        for player in all_players:
            # Release replacement-level or worse players on cheap contracts
            if player.total_value < 0.2 and player.salary <= 1_500_000:
                recommendations['release'].append({
                    'player': player.player_name,
                    'reason': f"Below replacement level (value={player.total_value:.2f})",
                    'savings': player.salary
                })
            # Also release highly negative value players even with higher salaries (salary dumps)
            elif player.total_value < -0.5 and player.salary <= 5_000_000:
                recommendations['release'].append({
                    'player': player.player_name,
                    'reason': f"Negative value ({player.total_value:.2f}) hurting team, salary dump at ${player.salary/1e6:.1f}M",
                    'savings': player.salary
                })

        return recommendations

    def _find_specific_trade_targets(self, baseball_stats, strategy: TeamStrategy,
                                     is_contender: bool) -> List[Dict]:
        """
        Scan league for specific players matching team's trade needs.

        Args:
            baseball_stats: BaseballStats with league-wide data
            strategy: TeamStrategy with alpha
            is_contender: True for win-now targets, False for rebuild targets

        Returns:
            List of player dictionaries with name, team, value, reason
        """
        targets = []

        # Get team's games played for consistent valuation
        team_games_played = strategy.games_played if hasattr(strategy, 'games_played') else 150

        if is_contender:
            # CONTENDERS: Look for veteran impact players
            # Scan batters for veteran bats
            for idx, batter_row in baseball_stats.new_season_batting_data.iterrows():
                team = batter_row.get('Team', '')
                if team == self.team_name:  # Skip own team
                    continue

                age = batter_row.get('Age', 30)
                # Filter: Veterans (30+) with high immediate value
                if age >= 28:
                    player_value = self.valuator.calculate_player_value(
                        batter_row, strategy.alpha, team_games_played, is_pitcher=False
                    )
                    if player_value.immediate_value >= 1.5:  # Solid contributors
                        targets.append({
                            'player': player_value.player_name,
                            'team': team,
                            'position': player_value.position,
                            'age': age,
                            'value': player_value.immediate_value,
                            'type': 'BAT',
                            'reason': f"Veteran bat - {player_value.immediate_value:.1f} WAR now"
                        })

            # Scan pitchers for impact arms
            for idx, pitcher_row in baseball_stats.new_season_pitching_data.iterrows():
                team = pitcher_row.get('Team', '')
                if team == self.team_name:
                    continue

                age = pitcher_row.get('Age', 30)
                if age >= 27 and age <= 35:  # Prime-age pitchers
                    player_value = self.valuator.calculate_player_value(
                        pitcher_row, strategy.alpha, team_games_played, is_pitcher=True
                    )
                    if player_value.immediate_value >= 1.8:  # Impact starters
                        targets.append({
                            'player': player_value.player_name,
                            'team': team,
                            'position': 'P',
                            'age': age,
                            'value': player_value.immediate_value,
                            'type': 'PITCH',
                            'reason': f"Impact arm - {player_value.immediate_value:.1f} WAR now"
                        })

        else:
            # REBUILDERS: Look for young players with upside
            # Scan for young position players
            for idx, batter_row in baseball_stats.new_season_batting_data.iterrows():
                team = batter_row.get('Team', '')
                if team == self.team_name:
                    continue

                age = batter_row.get('Age', 30)
                if age <= 25:  # Young players
                    player_value = self.valuator.calculate_player_value(
                        batter_row, strategy.alpha, team_games_played, is_pitcher=False
                    )
                    if player_value.future_value >= 2.5:  # High ceiling
                        targets.append({
                            'player': player_value.player_name,
                            'team': team,
                            'position': player_value.position,
                            'age': age,
                            'value': player_value.future_value,
                            'type': 'BAT',
                            'reason': f"Young prospect - {player_value.future_value:.1f} future WAR"
                        })

            # Scan for young pitchers
            for idx, pitcher_row in baseball_stats.new_season_pitching_data.iterrows():
                team = pitcher_row.get('Team', '')
                if team == self.team_name:
                    continue

                age = pitcher_row.get('Age', 30)
                if age <= 26:
                    player_value = self.valuator.calculate_player_value(
                        pitcher_row, strategy.alpha, team_games_played, is_pitcher=True
                    )
                    if player_value.future_value >= 3.0:
                        targets.append({
                            'player': player_value.player_name,
                            'team': team,
                            'position': 'P',
                            'age': age,
                            'value': player_value.future_value,
                            'type': 'PITCH',
                            'reason': f"Young arm - {player_value.future_value:.1f} future WAR"
                        })

        # Sort by value and return top 5
        targets.sort(key=lambda x: x['value'], reverse=True)
        return targets[:5]

    def _print_assessment_summary(self, strategy: TeamStrategy, roster_values: Dict,
                                 recommendations: Dict) -> None:
        """Print formatted assessment summary for GM review."""
        print(f"\n{'='*60}")
        print(f"AI GM ASSESSMENT: {self.team_name}")
        print(f"{'='*60}")
        print(f"Strategy: {strategy.stage} (alpha={strategy.alpha:.3f})")
        print(f"Record: W-L {strategy.win_pct:.3f}, GB {strategy.games_back:.1f}")
        print()

        # Top valued players
        print("TOP 5 MOST VALUABLE PLAYERS:")
        all_players = roster_values['batters'] + roster_values['pitchers']
        all_players.sort(key=lambda x: x.total_value, reverse=True)

        for i, player in enumerate(all_players[:5], 1):
            print(f"{i}. {player.player_name:20s} ({player.position:5s}, Age {player.age:2d}): "
                  f"Value={player.total_value:5.2f} (Now={player.immediate_value:4.2f}, "
                  f"Future={player.future_value:4.2f}) ${player.salary/1e6:6.2f}M")
        print()

        # Trade recommendations
        if recommendations['trade_away']:
            print("TRADE CANDIDATES (Consider Dealing):")
            for i, trade in enumerate(recommendations['trade_away'][:5], 1):
                print(f"{i}. {trade['player']:20s} - {trade['reason']}")
            print()

        if recommendations['trade_targets']:
            print("TRADE TARGETS (Acquire Players Matching):")
            for i, target in enumerate(recommendations['trade_targets'], 1):
                print(f"{i}. {target['profile']:30s} - {target['reason']}")
            print()

        if recommendations.get('specific_targets'):
            print("SPECIFIC PLAYERS TO TARGET:")
            for i, target in enumerate(recommendations['specific_targets'][:5], 1):
                print(f"{i}. {target['player']:20s} ({target['team']}, {target['position']:6s}, Age {target['age']:2d}) - "
                      f"{target['reason']}")
            print()

        if recommendations['release']:
            print("RELEASE CANDIDATES:")
            for i, release in enumerate(recommendations['release'][:3], 1):
                print(f"{i}. {release['player']:20s} - {release['reason']}")
            print()

        print(f"{'='*60}\n")


if __name__ == '__main__':
    """Test AI GM with sample data."""
    from bblogger import configure_logger
    configure_logger("INFO")

    # Test strategy calculation
    print("Testing GMStrategy calculations:")
    print("-" * 60)

    strategy_calc = GMStrategy()

    # Test scenarios
    scenarios = [
        ((95, 50), -2.0, 145, "Division leader late season"),
        ((88, 74), 3.5, 162, "Wild card race final game"),
        ((72, 90), 15.0, 162, "Out of contention"),
        ((45, 35), 5.0, 80, "Mediocre mid-season"),
        ((30, 50), 12.0, 80, "Rebuild mode mid-season"),
    ]

    for record, gb, games, desc in scenarios:
        strategy = strategy_calc.calculate_alpha(record, gb, games)
        print(f"{desc}")
        print(f"  Record: {record[0]}-{record[1]} ({strategy.win_pct:.3f}), GB: {gb:.1f}")
        print(f"  Alpha: {strategy.alpha:.3f} - {strategy.stage}")
        print()

    print("\nAI GM module ready for integration with bbseason.py")
