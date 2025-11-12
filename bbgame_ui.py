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

import pygame
import sys
from bbgame import Game
import random

# Initialize Pygame
pygame.init()

# Constants
WINDOW_WIDTH = 1200
WINDOW_HEIGHT = 800
FPS = 60

# Colors
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
GREEN = (0, 100, 0)
DARK_GREEN = (0, 80, 0)
BROWN = (139, 69, 19)
LIGHT_BROWN = (210, 180, 140)
GRAY = (200, 200, 200)
BLUE = (100, 149, 237)
RED = (220, 20, 60)
PURPLE = (128, 0, 128)
ORANGE = (255, 140, 0)
YELLOW = (255, 215, 0)

# Fonts
FONT_SMALLEST = pygame.font.SysFont("Arial", 12)  # Increased from 8
FONT_SMALLER = pygame.font.SysFont("Arial", 14)   # Increased from 10
FONT_SMALL = pygame.font.SysFont("Arial", 16)     # Increased from 12
FONT_MEDIUM = pygame.font.SysFont("Arial", 18)    # Increased from 14
FONT_LARGE = pygame.font.SysFont("Arial", 22)     # Increased from 18
FONT_TITLE = pygame.font.SysFont("Arial", 24, bold=True)  # Increased from 20

class BaseballUI:
    def __init__(self):
        # Setup display
        self.screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
        pygame.display.set_caption("Baseball Simulation")
        self.clock = pygame.time.Clock()
        
        # Game data
        self.game = None
        self.away_team = "NYM"
        self.home_team = "MIL"
        self.current_outcome_text = []
        self.max_outcome_lines = 10
        
        # Track ball-strike count
        self.balls = 0  # Current ball count (0-3)
        self.strikes = 0  # Current strike count (0-2)
        
        # Field coordinates
        self.field_center_x = WINDOW_WIDTH // 2
        self.field_center_y = 400
        self.base_distance = 120
        
        # UI areas - improved layout with clearer sections
        self.scoreboard_rect = pygame.Rect(20, 20, WINDOW_WIDTH - 40, 100)  # Reduced height
        self.field_rect = pygame.Rect(20, 140, WINDOW_WIDTH // 2 - 10, 380)  # Adjusted size and position
        self.lineup_rect = pygame.Rect(WINDOW_WIDTH // 2 + 10, 140, WINDOW_WIDTH // 2 - 30, 380)  # Adjusted size and position
        self.outcome_rect = pygame.Rect(20, 540, WINDOW_WIDTH - 40, 240)  # Increased height for more space
        
        # Load diamond background image 
        try:
            self.diamond_img = pygame.image.load("diamond.png")
            # Scale the image to fit the field_rect
            self.diamond_img = pygame.transform.scale(self.diamond_img, (self.field_rect.width, self.field_rect.height))
        except pygame.error:
            print("Warning: Could not load diamond.png")
            self.diamond_img = None
        
        # Increase max outcome lines to fit in the play-by-play area
        self.max_outcome_lines = 18  # Increased to fit more play-by-play info
        
        # Initialize game
        self.initialize_game()
        
    def initialize_game(self):
        self.game = Game(
            home_team_name=self.home_team, 
            away_team_name=self.away_team,
            chatty=True, 
            print_lineup=True,
            print_box_score_b=True,
            load_seasons=[2024], 
            new_season=2025,
            load_batter_file='aggr-stats-pp-Batting.csv',
            load_pitcher_file='aggr-stats-pp-Pitching.csv',
            interactive=True,
            show_bench=False,
            debug=False
        )
        # Clear outcome text
        self.current_outcome_text = []
        self.add_outcome_text(f"Game initialized: {self.away_team} vs {self.home_team}")
        
        # Make sure we have a proper batter visualization immediately at game start
        batter_num = self.game.batting_num[self.game.team_hitting()]
        batter_index = self.game.teams[self.game.team_hitting()].batter_index_in_lineup(batter_num)
        batter_stats = self.game.teams[self.game.team_hitting()].batter_stats_in_lineup(batter_index)
        
        # Set up the next batter
        self.game.bases.baserunners[0] = batter_index
        self.game.bases.baserunners_names[batter_index] = batter_stats.Player
        
    def add_outcome_text(self, text, color=BLACK):
        """Add text to the outcome window, keeping the last N lines"""
        lines = text.split('\n')
        for line in lines:
            if line.strip():  # Skip empty lines
                # Always use BLACK color for all text
                self.current_outcome_text.append((line, BLACK))
        
        # Keep only the last max_outcome_lines
        if len(self.current_outcome_text) > self.max_outcome_lines:
            self.current_outcome_text = self.current_outcome_text[-self.max_outcome_lines:]
            
    
    def draw_scoreboard(self):
        """Draw the game scoreboard with detailed information"""
        pygame.draw.rect(self.screen, GRAY, self.scoreboard_rect, border_radius=5)
        
        # Title
        title_text = f"{self.away_team} vs {self.home_team}"
        title_surface = FONT_TITLE.render(title_text, True, BLACK)
        self.screen.blit(title_surface, (self.scoreboard_rect.centerx - title_surface.get_width() // 2, 
                                         self.scoreboard_rect.y + 10))
        
        # Draw inning labels (1-9)
        inning_col_width = 30
        inning_start_x = self.scoreboard_rect.x + 150  # Start position for inning columns
        
        # Draw column headers (inning numbers)
        for i in range(1, 10):  # 9 innings
            inning_label = FONT_SMALL.render(str(i), True, BLACK)
            x_pos = inning_start_x + (i-1) * inning_col_width + (inning_col_width - inning_label.get_width()) // 2
            self.screen.blit(inning_label, (x_pos, self.scoreboard_rect.y + 35))
        
        # Draw R, H, E labels
        r_label = FONT_SMALL.render("R", True, BLACK)
        h_label = FONT_SMALL.render("H", True, BLACK)
        e_label = FONT_SMALL.render("E", True, BLACK)
        
        rhe_start_x = inning_start_x + 9 * inning_col_width + 5
        self.screen.blit(r_label, (rhe_start_x + 10, self.scoreboard_rect.y + 35))
        self.screen.blit(h_label, (rhe_start_x + 40, self.scoreboard_rect.y + 35))
        self.screen.blit(e_label, (rhe_start_x + 70, self.scoreboard_rect.y + 35))
        
        # Draw team names and scores by inning
        away_y = self.scoreboard_rect.y + 50
        home_y = self.scoreboard_rect.y + 70
        
        # Team names
        away_label = FONT_MEDIUM.render(self.away_team, True, BLACK)
        home_label = FONT_MEDIUM.render(self.home_team, True, BLACK)
        self.screen.blit(away_label, (self.scoreboard_rect.x + 20, away_y))
        self.screen.blit(home_label, (self.scoreboard_rect.x + 20, home_y))
        
        # Inning scores
        current_inning = self.game.inning[self.game.team_hitting()]
        
        for i in range(1, 10):  # 9 innings
            # Away team inning score - handle both list and dict formats
            if i <= current_inning or (i == current_inning and self.game.top_bottom == 1):
                away_score = "0"
                # Check if inning_score is a list (original format) or dict (our new format)
                if isinstance(self.game.inning_score, list) and i < len(self.game.inning_score):
                    # Original format: list of lists [inning_num, away_score, home_score]
                    try:
                        if self.game.inning_score[i][1] != '':
                            away_score = str(self.game.inning_score[i][1])
                    except (IndexError, TypeError):
                        # Handle any index errors gracefully
                        pass
                
                away_score_label = FONT_SMALL.render(away_score, True, BLACK)
                x_pos = inning_start_x + (i-1) * inning_col_width + (inning_col_width - away_score_label.get_width()) // 2
                self.screen.blit(away_score_label, (x_pos, away_y))
            
            # Home team inning score (only if that inning has been played)
            if i < current_inning or (i == current_inning and self.game.top_bottom == 1):
                home_score = "0"
                # Check if inning_score is a list or dict
                if isinstance(self.game.inning_score, list) and i < len(self.game.inning_score):
                    # Original format
                    try:
                        if self.game.inning_score[i][2] != '':
                            home_score = str(self.game.inning_score[i][2])
                    except (IndexError, TypeError):
                        # Handle any index errors gracefully
                        pass
                
                home_score_label = FONT_SMALL.render(home_score, True, BLACK)
                x_pos = inning_start_x + (i-1) * inning_col_width + (inning_col_width - home_score_label.get_width()) // 2
                self.screen.blit(home_score_label, (x_pos, home_y))
        
        # R H E stats
        # We're estimating hits and errors based on box score data
        away_runs = FONT_SMALL.render(str(self.game.total_score[0]), True, BLACK)
        home_runs = FONT_SMALL.render(str(self.game.total_score[1]), True, BLACK)
        
        # Estimate hits from box score
        away_hits = sum(self.game.teams[0].box_score.box_batting['H'])
        home_hits = sum(self.game.teams[1].box_score.box_batting['H'])
        away_hits_label = FONT_SMALL.render(str(away_hits), True, BLACK)
        home_hits_label = FONT_SMALL.render(str(home_hits), True, BLACK)
        
        # Errors - assume zero since errors aren't explicitly tracked
        away_errors = FONT_SMALL.render("0", True, BLACK)
        home_errors = FONT_SMALL.render("0", True, BLACK)
        
        # Draw R H E values
        self.screen.blit(away_runs, (rhe_start_x + 10, away_y))
        self.screen.blit(away_hits_label, (rhe_start_x + 40, away_y))
        self.screen.blit(away_errors, (rhe_start_x + 70, away_y))
        
        self.screen.blit(home_runs, (rhe_start_x + 10, home_y))
        self.screen.blit(home_hits_label, (rhe_start_x + 40, home_y))
        self.screen.blit(home_errors, (rhe_start_x + 70, home_y))
        
        # Outs with red circles
        outs_text = "Outs: "
        outs_label = FONT_MEDIUM.render(outs_text, True, BLACK)
        
        # Position at the center bottom of scoreboard (original position)
        outs_x = self.scoreboard_rect.centerx
        
        self.screen.blit(outs_label, (outs_x, self.scoreboard_rect.bottom - 25))
        
        # Draw out circles (filled if out occurred)
        circle_radius = 6
        for i in range(3):
            circle_x = outs_x + outs_label.get_width() + 15 + (i * 20)
            circle_y = self.scoreboard_rect.bottom - 25 + outs_label.get_height() // 2
            
            if i < self.game.outs:
                # Filled circle for recorded outs
                pygame.draw.circle(self.screen, RED, (circle_x, circle_y), circle_radius)
            else:
                # Empty circle for remaining outs
                pygame.draw.circle(self.screen, BLACK, (circle_x, circle_y), circle_radius, 1)
    
    def draw_field(self):
        """Draw the baseball field with runners and fielders"""
        # Draw background rectangle
        pygame.draw.rect(self.screen, GRAY, self.field_rect, border_radius=5)
        
        field_center_x = self.field_rect.centerx
        field_center_y = self.field_rect.centery
        
        # Add ball-strike count display in top right corner of field
        balls_strikes_text = f"Count: {self.balls}-{self.strikes}"
        count_surface = FONT_MEDIUM.render(balls_strikes_text, True, BLACK)
        self.screen.blit(count_surface, (self.field_rect.right - count_surface.get_width() - 10, 
                                        self.field_rect.y + 10))
        
        # Draw ball indicators (open/filled circles)
        ball_x = self.field_rect.right - 80
        ball_y = self.field_rect.y + 35
        ball_radius = 5
        ball_spacing = 15
        
        # Draw "Balls:" label
        balls_label = FONT_SMALL.render("Balls:", True, BLACK)
        self.screen.blit(balls_label, (ball_x - balls_label.get_width() - 5, ball_y - 2))
        
        # Draw ball indicators
        for i in range(4):  # 4 balls
            if i < self.balls:
                # Filled circle for balls
                pygame.draw.circle(self.screen, GREEN, (ball_x + (i * ball_spacing), ball_y), ball_radius)
            else:
                # Empty circle for remaining balls
                pygame.draw.circle(self.screen, BLACK, (ball_x + (i * ball_spacing), ball_y), ball_radius, 1)
        
        # Draw strike indicators
        strike_x = self.field_rect.right - 80
        strike_y = self.field_rect.y + 55
        strike_radius = 5
        strike_spacing = 15
        
        # Draw "Strikes:" label
        strikes_label = FONT_SMALL.render("Strikes:", True, BLACK)
        self.screen.blit(strikes_label, (strike_x - strikes_label.get_width() - 5, strike_y - 2))
        
        # Draw strike indicators
        for i in range(3):  # 3 strikes
            if i < self.strikes:
                # Filled circle for strikes
                pygame.draw.circle(self.screen, RED, (strike_x + (i * strike_spacing), strike_y), strike_radius)
            else:
                # Empty circle for remaining strikes
                pygame.draw.circle(self.screen, BLACK, (strike_x + (i * strike_spacing), strike_y), strike_radius, 1)
                
        # Add pitcher fatigue indicator
        team_pitching = self.game.team_pitching()
        pitcher_index = self.game.teams[team_pitching].cur_pitcher_index
        pitcher_game_stats = self.game.teams[team_pitching].box_score.box_pitching.loc[pitcher_index]
        
        # Calculate fatigue based on innings pitched - use a scale of 0-100%
        innings_pitched = pitcher_game_stats['IP']
        pitch_count = innings_pitched * 15  # Rough estimate: 15 pitches per inning
        
        # Fatigue level: 0-30 pitches: fresh, 30-60: moderate, 60-90: tired, 90+: exhausted
        fatigue_percent = min(100, (pitch_count / 120) * 100)  # Cap at 100%
        
        # Draw fatigue meter
        fatigue_text = "Pitcher Fatigue:"
        fatigue_label = FONT_SMALL.render(fatigue_text, True, BLACK)
        self.screen.blit(fatigue_label, (self.field_rect.x + 10, self.field_rect.y + 10))
        
        # Draw fatigue bar
        meter_width = 100
        meter_height = 10
        meter_x = self.field_rect.x + 10
        meter_y = self.field_rect.y + 30
        
        # Background bar
        pygame.draw.rect(self.screen, GRAY, (meter_x, meter_y, meter_width, meter_height), border_radius=3)
        
        # Determine color based on fatigue level
        if fatigue_percent < 33:
            fatigue_color = GREEN
        elif fatigue_percent < 66:
            fatigue_color = YELLOW
        else:
            fatigue_color = RED
        
        # Filled portion representing fatigue
        filled_width = int(meter_width * (fatigue_percent / 100))
        pygame.draw.rect(self.screen, fatigue_color, (meter_x, meter_y, filled_width, meter_height), border_radius=3)
        
        # Define base coordinates for the diamond.png image first
        base_size = 12  # Size of the diamond from center to point (slightly smaller)
        home_plate_size = 12  # Same size as other bases
        
        # First base is at the right corner of the diamond image
        first_base_x = field_center_x + 210  # Adjusted from base_distance (120)
        first_base_y = field_center_y - 17   # Adjusted to match image
        
        # Second base is at the top corner of the diamond image
        second_base_x = field_center_x
        second_base_y = field_center_y - 95  # Adjusted from base_distance
        
        # Third base is at the left corner of the diamond image
        third_base_x = field_center_x - 210  # Adjusted from base_distance
        third_base_y = field_center_y - 17   # Adjusted to match image
        
        # Home plate is at the bottom corner of the diamond image
        home_plate_x = field_center_x
        home_plate_y = field_center_y + 85  # Adjusted for diamond.png
        
        # If we have the diamond image, draw it instead of the polygon field
        if self.diamond_img:
            # Draw the diamond background image
            self.screen.blit(self.diamond_img, self.field_rect)
        else:
            # Fallback to drawn field if image isn't available
            # Draw outfield grass as a diamond (tighter to infield as requested)
            outfield_diamond_size = self.base_distance * 2  # Reduced from 3 to 2
            outfield_points = [
                (field_center_x, field_center_y - outfield_diamond_size),  # Top
                (field_center_x + outfield_diamond_size, field_center_y),  # Right
                (field_center_x, field_center_y + outfield_diamond_size * 0.8),  # Bottom (reduced to not overlap scoreboard)
                (field_center_x - outfield_diamond_size, field_center_y),  # Left
            ]
            pygame.draw.polygon(self.screen, GREEN, outfield_points)
            
            # Draw infield dirt as a diamond
            infield_diamond_size = self.base_distance * 1.5
            infield_points = [
                (field_center_x, field_center_y - infield_diamond_size),  # Top
                (field_center_x + infield_diamond_size, field_center_y),  # Right
                (field_center_x, field_center_y + infield_diamond_size),  # Bottom
                (field_center_x - infield_diamond_size, field_center_y),  # Left
            ]
            pygame.draw.polygon(self.screen, LIGHT_BROWN, infield_points)
            
            # Draw baselines
            pygame.draw.line(self.screen, WHITE, 
                            (field_center_x, field_center_y + self.base_distance), 
                            (field_center_x - self.base_distance, field_center_y), 3)
            pygame.draw.line(self.screen, WHITE, 
                            (field_center_x - self.base_distance, field_center_y), 
                            (field_center_x, field_center_y - self.base_distance), 3)
            pygame.draw.line(self.screen, WHITE, 
                            (field_center_x, field_center_y - self.base_distance), 
                            (field_center_x + self.base_distance, field_center_y), 3)
            pygame.draw.line(self.screen, WHITE, 
                            (field_center_x + self.base_distance, field_center_y), 
                            (field_center_x, field_center_y + self.base_distance), 3)
            
            # Draw pitcher's mound
            pygame.draw.circle(self.screen, BROWN, (field_center_x, field_center_y), 10)
        
        # Draw fielders positioned on the dirt infield
        fielder_positions = {
            # Pitcher on the mound
            'P': (field_center_x, field_center_y - 20),
            
            # Catcher behind home plate
            'C': (field_center_x, home_plate_y + 20),
            
            # First baseman near first base
            '1B': (first_base_x - 20, first_base_y - 55),
            
            # Second baseman on the dirt between first and second
            '2B': (field_center_x + 100, field_center_y - 110),
            
            # Third baseman near third base
            '3B': (third_base_x + 20, third_base_y - 55),
            
            # Shortstop on the dirt between second and third
            'SS': (field_center_x - 100, field_center_y - 110),
            
            # Outfielders in the outfield
            'LF': (field_center_x - self.base_distance - 40, field_center_y - self.base_distance - 40),
            'CF': (field_center_x, field_center_y - self.base_distance - 40),
            'RF': (field_center_x + self.base_distance + 40, field_center_y - self.base_distance - 40)
        }
        
        # Draw the fielders and their names
        team_pitching = self.game.team_pitching()
        fielding_team = self.game.teams[team_pitching]
        
        # Map positions to the actual fielders in the lineup
        position_to_player = {}
        position_to_stats = {}
        
        # First get the pitcher and their in-game stats
        pitcher_stats = fielding_team.cur_pitcher_stats()
        position_to_player['P'] = pitcher_stats.Player
        # Add pitcher's stats (IP, H, ER)
        position_to_stats['P'] = fielding_team.box_score.box_pitching.loc[fielding_team.cur_pitcher_index]
        
        # Then get the position players from the lineup
        for i in range(1, 10):  # 9 batters
            try:
                batting_index = fielding_team.batter_index_in_lineup(i)
                batting_stats = fielding_team.batter_stats_in_lineup(batting_index)
                if batting_stats.Pos in position_to_player:
                    # If duplicate position, just keep first one
                    continue
                position_to_player[batting_stats.Pos] = batting_stats.Player
                # Get in-game stats for the player
                position_to_stats[batting_stats.Pos] = fielding_team.box_score.box_batting.loc[batting_index]
            except:
                # If there's any error, just continue
                continue
        
        # Draw each fielder and their name
        for pos, coords in fielder_positions.items():
            # Draw the fielder as a larger circle
            pygame.draw.circle(self.screen, BLUE, coords, 12)  # Increased from 8
            
            # Show position with larger font and in white for better visibility
            pos_text = FONT_SMALL.render(pos, True, WHITE)
            # Center position text in the fielder circle
            self.screen.blit(pos_text, (coords[0] - pos_text.get_width() // 2, coords[1] - pos_text.get_height() // 2))
            
            # Show player name and in-game stats if we have them
            if pos in position_to_player:
                player_name = position_to_player[pos]
                
                # Format player name (first initial + last name)
                player_parts = player_name.split()
                formatted_player_name = f"{player_parts[0][0]}. {' '.join(player_parts[1:])}" if len(player_parts) > 0 else player_name
                
                # Truncate long names
                if len(formatted_player_name) > 10:
                    formatted_player_name = formatted_player_name[:8] + ".."
                
                # Use larger font for player names
                name_text = FONT_SMALL.render(formatted_player_name, True, BLACK)
                
                # Special positioning for CF - position to the right instead of below
                if pos == 'CF':
                    # Position name to the right of the CF
                    self.screen.blit(name_text, (coords[0] + 20, coords[1] - 5))
                else:
                    # Position name below other fielders with more space
                    self.screen.blit(name_text, (coords[0] - name_text.get_width() // 2, coords[1] + 15))
                
                # No in-game stats displayed next to fielders as requested
        
        # Instead of drawing separate yellow squares, we'll draw the bases with different colors
        # based on whether runners are present. Let's handle this in the base drawing code below.
        
        # Draw runners on bases using blue circles with player initials
        # First get batter info for display
        batter_num = self.game.batting_num[self.game.team_hitting()]
        batter_index = self.game.teams[self.game.team_hitting()].batter_index_in_lineup(batter_num)
        batter_stats = self.game.teams[self.game.team_hitting()].batter_stats_in_lineup(batter_index)
        
        # Show the current batter with a circle and name to the right of home plate
        batter_name = batter_stats.Player
        batter_parts = batter_name.split()
        batter_initial = batter_parts[0][0] if len(batter_parts) > 0 else "B"
        
        # Draw a blue-yellow (split) circle for batter to the right of home plate
        batter_circle_x = home_plate_x + 50
        batter_circle_y = home_plate_y - 5
        
        # Draw half blue, half yellow circle - using same size as fielders (12)
        pygame.draw.circle(self.screen, BLUE, (batter_circle_x, batter_circle_y), 12)
        
        # Draw yellow semi-circle (right half)
        pygame.draw.arc(self.screen, YELLOW, 
                      (batter_circle_x - 12, batter_circle_y - 12, 24, 24),
                      -1.57,  # Start angle in radians (-90 degrees)
                      1.57,   # End angle in radians (90 degrees)
                      12)     # Width of the arc (fills the entire circle)
        
        # Draw batter initial in white
        batter_text = FONT_SMALL.render(batter_initial, True, BLACK)
        self.screen.blit(batter_text, (batter_circle_x - batter_text.get_width()//2, 
                                     batter_circle_y - batter_text.get_height()//2))
        
        # Display the full batter name to the right of the circle
        formatted_batter_name = f"{batter_parts[0][0]}. {' '.join(batter_parts[1:])}" if len(batter_parts) > 0 else batter_name
        name_text = FONT_SMALL.render(formatted_batter_name[:10], True, BLACK)
        self.screen.blit(name_text, (batter_circle_x + 20, batter_circle_y - 10))
        
        # Draw runners on the bases if present
        if self.game.bases.is_runner_on_base_num(1):  # Runner on first
            runner_name = self.game.bases.baserunners_names[self.game.bases.baserunners[1]]
            runner_parts = runner_name.split()
            runner_initial = runner_parts[0][0] if len(runner_parts) > 0 else "R"
            
            # Draw yellow circle at first base (12 matches fielder size)
            pygame.draw.circle(self.screen, YELLOW, (first_base_x, first_base_y), 12)
            
            # Draw runner initial in black
            runner_text = FONT_SMALL.render(runner_initial, True, BLACK)
            self.screen.blit(runner_text, (first_base_x - runner_text.get_width()//2, 
                                       first_base_y - runner_text.get_height()//2))
            
            # Display runner name below the circle
            formatted_name = f"{runner_parts[0][0]}. {' '.join(runner_parts[1:])}" if len(runner_parts) > 0 else runner_name
            name_text = FONT_SMALL.render(formatted_name[:10], True, BLACK)
            self.screen.blit(name_text, (first_base_x - name_text.get_width()//2, first_base_y + 20))
            
        if self.game.bases.is_runner_on_base_num(2):  # Runner on second
            runner_name = self.game.bases.baserunners_names[self.game.bases.baserunners[2]]
            runner_parts = runner_name.split()
            runner_initial = runner_parts[0][0] if len(runner_parts) > 0 else "R"
            
            # Draw yellow circle at second base (12 matches fielder size)
            pygame.draw.circle(self.screen, YELLOW, (second_base_x, second_base_y), 12)
            
            # Draw runner initial in black
            runner_text = FONT_SMALL.render(runner_initial, True, BLACK)
            self.screen.blit(runner_text, (second_base_x - runner_text.get_width()//2, 
                                       second_base_y - runner_text.get_height()//2))
            
            # Display runner name below
            formatted_name = f"{runner_parts[0][0]}. {' '.join(runner_parts[1:])}" if len(runner_parts) > 0 else runner_name
            name_text = FONT_SMALL.render(formatted_name[:10], True, BLACK)
            self.screen.blit(name_text, (second_base_x - name_text.get_width()//2, 
                                      second_base_y + 20))
            
        if self.game.bases.is_runner_on_base_num(3):  # Runner on third
            runner_name = self.game.bases.baserunners_names[self.game.bases.baserunners[3]]
            runner_parts = runner_name.split()
            runner_initial = runner_parts[0][0] if len(runner_parts) > 0 else "R"
            
            # Draw yellow circle at third base (12 matches fielder size)
            pygame.draw.circle(self.screen, YELLOW, (third_base_x, third_base_y), 12)
            
            # Draw runner initial in black
            runner_text = FONT_SMALL.render(runner_initial, True, BLACK)
            self.screen.blit(runner_text, (third_base_x - runner_text.get_width()//2, 
                                       third_base_y - runner_text.get_height()//2))
            
            # Display runner name below the circle
            formatted_name = f"{runner_parts[0][0]}. {' '.join(runner_parts[1:])}" if len(runner_parts) > 0 else runner_name
            name_text = FONT_SMALL.render(formatted_name[:10], True, BLACK)
            self.screen.blit(name_text, (third_base_x - name_text.get_width()//2, third_base_y + 20))
    
    def draw_lineup(self):
        """Draw the batting lineup display"""
        pygame.draw.rect(self.screen, GRAY, self.lineup_rect, border_radius=5)
        
        # Title
        title_text = f"{self.game.team_names[self.game.team_hitting()]} Batting Lineup"
        title_surface = FONT_LARGE.render(title_text, True, BLACK)
        self.screen.blit(title_surface, (self.lineup_rect.centerx - title_surface.get_width() // 2, 
                                         self.lineup_rect.y + 10))
        
        # Current pitcher info with game stats
        pitcher_team = self.game.team_names[self.game.team_pitching()]
        pitcher_stats = self.game.teams[self.game.team_pitching()].cur_pitcher_stats()
        pitcher_name = pitcher_stats.Player
        
        # Get pitcher's game stats
        pitcher_index = self.game.teams[self.game.team_pitching()].cur_pitcher_index
        pitcher_game_stats = self.game.teams[self.game.team_pitching()].box_score.box_pitching.loc[pitcher_index]
        
        # Format pitcher name (first initial + last name)
        pitcher_parts = pitcher_name.split()
        formatted_pitcher_name = f"{pitcher_parts[0][0]}. {' '.join(pitcher_parts[1:])}" if len(pitcher_parts) > 0 else pitcher_name
        
        # Format pitcher with ERA and stats
        pitcher_text = f"Pitcher: {formatted_pitcher_name} ({pitcher_team}) {pitcher_stats.ERA:.2f} ERA, IP: {pitcher_game_stats['IP']:.1f}"
        pitcher_surface = FONT_MEDIUM.render(pitcher_text, True, BLACK)
        self.screen.blit(pitcher_surface, (self.lineup_rect.x + 20, self.lineup_rect.y + 40))
        
        # Current batter
        batter_num = self.game.batting_num[self.game.team_hitting()]
        batter_index = self.game.teams[self.game.team_hitting()].batter_index_in_lineup(batter_num)
        batter_stats = self.game.teams[self.game.team_hitting()].batter_stats_in_lineup(batter_index)
        
        # Format batter name (first initial + last name)
        batter_parts = batter_stats.Player.split()
        formatted_batter_name = f"{batter_parts[0][0]}. {' '.join(batter_parts[1:])}" if len(batter_parts) > 0 else batter_stats.Player
        
        # Get the in-game stats for current batter
        batter_game_stats = self.game.teams[self.game.team_hitting()].box_score.box_batting.loc[batter_index]
        
        # Format current batter with AVG and in-game hits/plate appearances
        plate_appearances = batter_game_stats['AB'] + batter_game_stats['BB'] + batter_game_stats['HBP'] + batter_game_stats['SF']
        batter_text = f"At Bat: {formatted_batter_name} {batter_stats.Pos} (#{batter_num}) {batter_stats.AVG:.3f} AVG, {batter_game_stats['H']}-{plate_appearances}"
        batter_surface = FONT_MEDIUM.render(batter_text, True, BLACK)
        self.screen.blit(batter_surface, (self.lineup_rect.x + 20, self.lineup_rect.y + 70))
        
        # Batting lineup
        lineup_y = self.lineup_rect.y + 110
        for i in range(1, 10):  # 9 batters
            batting_index = self.game.teams[self.game.team_hitting()].batter_index_in_lineup(i)
            batting_stats = self.game.teams[self.game.team_hitting()].batter_stats_in_lineup(batting_index)
            
            # Get the in-game stats for this batter
            game_stats = self.game.teams[self.game.team_hitting()].box_score.box_batting.loc[batting_index]
            
            # Highlight current batter with orange instead of red
            text_color = ORANGE if i == batter_num else BLACK
            
            # Format player name (first initial + last name)
            player_parts = batting_stats.Player.split()
            formatted_player_name = f"{player_parts[0][0]}. {' '.join(player_parts[1:])}" if len(player_parts) > 0 else batting_stats.Player
            
            # Format as requested: Player Name Position AVG, hits-plate appearances
            plate_appearances = game_stats['AB'] + game_stats['BB'] + game_stats['HBP'] + game_stats['SF']
            stats_text = f" {batting_stats.AVG:.3f} AVG, {game_stats['H']}-{plate_appearances}"
            
            lineup_text = f"{i}. {formatted_player_name} {batting_stats.Pos}{stats_text}"
            lineup_surface = FONT_MEDIUM.render(lineup_text, True, text_color)
            self.screen.blit(lineup_surface, (self.lineup_rect.x + 20, lineup_y))
            
            lineup_y += 25  # Reduced spacing since we're using a single line
    
    def draw_outcome_window(self):
        """Draw the text window showing at-bat outcomes"""
        pygame.draw.rect(self.screen, GRAY, self.outcome_rect, border_radius=5)
        
        # Title with inning information included
        inning_text = f"{'Top' if self.game.top_bottom == 0 else 'Bottom'} of Inning {self.game.inning[self.game.team_hitting()]}"
        title_text = f"Game Play-by-Play ({inning_text})"
        title_surface = FONT_LARGE.render(title_text, True, BLACK)
        self.screen.blit(title_surface, (self.outcome_rect.centerx - title_surface.get_width() // 2, 
                                         self.outcome_rect.y + 10))
        
        # Display outcome text with smaller font in a single column
        text_y = self.outcome_rect.y + 40
        
        for line_tuple in self.current_outcome_text:
            if isinstance(line_tuple, tuple) and len(line_tuple) == 2:
                line, _ = line_tuple  # Ignore any stored color
            else:
                # Handle legacy format (string only)
                line = line_tuple
            
            # Left side position
            x_pos = self.outcome_rect.x + 20
            
            # Use slightly larger font for better readability - always BLACK
            line_surface = FONT_SMALL.render(line, True, BLACK)
            self.screen.blit(line_surface, (x_pos, text_y))
            
            # Increment y position after each line
            text_y += 16
            
            # Make sure we don't exceed the outcome rect area
            if text_y > self.outcome_rect.bottom - 20:
                # If we're running out of space, show indicator that there are more lines
                more_text = FONT_SMALL.render("...", True, BLACK)
                self.screen.blit(more_text, (self.outcome_rect.right - 50, self.outcome_rect.bottom - 20))
                break
    
    def sim_next_at_bat(self):
        """Simulate the next at-bat in the game"""
        if self.game.is_game_end():
            self.add_outcome_text("The game has ended.", BLACK)
            return
            
        # Store current state to detect changes
        prior_outs = self.game.outs
        prior_score = self.game.total_score.copy()
        prior_bases_state = [self.game.bases.is_runner_on_base_num(1), 
                             self.game.bases.is_runner_on_base_num(2),
                             self.game.bases.is_runner_on_base_num(3)]
        
        # Reset ball-strike count for each at-bat (still track internally but don't show pitches)
        self.balls = 0
        self.strikes = 0
        
        # Simulate one at-bat
        pitch_switch = False
        pitch_switch = self.game.pitching_sit(self.game.teams[self.game.team_pitching()].cur_pitcher_stats(),
                                           pitch_switch=pitch_switch)
        self.game.stolen_base_sit()
        
        if self.game.outs >= 3:
            self.add_outcome_text("The half inning is over.", BLACK)
            return
            
        self.game.balk_wild_pitch()
        __pitching, __batting = self.game.sim_ab()
        
        # Check for runs scored
        if self.game.bases.runs_scored > 0:
            self.game.update_inning_score(number_of_runs=self.game.bases.runs_scored)
            players = ''
            for player_id in self.game.bases.player_scored.keys():
                players = players + ', ' + self.game.bases.player_scored[player_id] if players != '' else self.game.bases.player_scored[player_id]
            self.add_outcome_text(f"Scored {self.game.bases.runs_scored} run(s)! ({players})", BLACK)
            self.add_outcome_text(f"The score is {self.game.team_names[0]} {self.game.total_score[0]} to {self.game.team_names[1]} {self.game.total_score[1]}", BLACK)
        
        # Get outcome text from the most recent at-bat
        batting_team = self.game.team_names[self.game.team_hitting()]
        batter_name = __batting.Player
        pitcher_name = __pitching.Player
        outcome = self.game.outcomes.score_book_cd
        
        # Just create a simple combined text in black
        self.add_outcome_text(f"Pitcher: {pitcher_name} vs {batter_name} ({batting_team}) - Outcome: {outcome}, Outs: {self.game.outs}", BLACK)
        
        if self.game.bases.count_runners() >= 1 and self.game.outs < 3:
            self.add_outcome_text(self.game.bases.describe_runners(), BLACK)
        
        # Update batting order
        self.game.batting_num[self.game.team_hitting()] = self.game.batting_num[self.game.team_hitting()] + 1 if (self.game.batting_num[self.game.team_hitting()] + 1) <= 9 else 1
        
        # Check if half inning is over
        if prior_outs < 3 and self.game.outs >= 3:
            # Half inning is over
            self.game.update_inning_score(number_of_runs=0)
            self.game.bases.clear_bases()
            top_or_bottom = 'top' if self.game.top_bottom == 0 else 'bottom'
            self.add_outcome_text(f"Completed {top_or_bottom} half of inning {self.game.inning[self.game.team_hitting()]}", BLACK)
            self.add_outcome_text(f"The score is {self.game.team_names[0]} {self.game.total_score[0]} to {self.game.team_names[1]} {self.game.total_score[1]}", BLACK)
            
            self.game.inning[self.game.team_hitting()] += 1
            self.game.top_bottom = 0 if self.game.top_bottom == 1 else 1
            self.game.outs = 0
            
            if self.game.is_game_end():
                self.game.end_game()
                self.add_outcome_text("Game Over!", BLACK)
                self.add_outcome_text(f"Final Score: {self.game.team_names[0]} {self.game.total_score[0]} to {self.game.team_names[1]} {self.game.total_score[1]}", BLACK)
            else:
                top_or_bottom = 'top' if self.game.top_bottom == 0 else 'bottom'
                self.add_outcome_text(f"Starting the {top_or_bottom} of inning {self.game.inning[self.game.team_hitting()]}", BLACK)
    
    def sim_half_inning(self):
        """Simulate a full half-inning"""
        if self.game.is_game_end():
            self.add_outcome_text("The game has ended.", BLACK)
            return
            
        initial_outs = self.game.outs
        initial_team = self.game.team_hitting()
        
        while self.game.outs < 3 and self.game.team_hitting() == initial_team:
            self.sim_next_at_bat()
            
        # After the half inning is over, make sure we're showing the correct next batter
        # by pretending to "set up" the next at-bat without actually simulating it
        if not self.game.is_game_end():
            # Check if we need to set up a new batter (when the inning just changed)
            if self.game.outs >= 3:
                # Clear the visualization of the last out at home plate
                self.game.bases.baserunners[0] = 0
    
    def run(self):
        """Main game loop"""
        running = True
        while running:
            # Handle events
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        running = False
                    elif event.key == pygame.K_SPACE:
                        # Simulate next at-bat
                        self.sim_next_at_bat()
                    elif event.key == pygame.K_RETURN:
                        # Simulate half inning
                        self.sim_half_inning()
                    elif event.key == pygame.K_n:
                        # New game
                        self.initialize_game()
            
            # Draw everything
            self.screen.fill(WHITE)
            self.draw_scoreboard()
            self.draw_field()
            self.draw_lineup()
            self.draw_outcome_window()
            
            # Draw keyboard shortcuts legend at the bottom of the screen
            legend_height = 20
            legend_rect = pygame.Rect(0, WINDOW_HEIGHT - legend_height, WINDOW_WIDTH, legend_height)
            pygame.draw.rect(self.screen, BLACK, legend_rect)
            
            legend_text = "Controls: [SPACE] Next At-Bat  |  [ENTER] Next Half-Inning  |  [N] New Game  |  [ESC] Exit"
            legend_surface = FONT_SMALL.render(legend_text, True, WHITE)
            self.screen.blit(legend_surface, (WINDOW_WIDTH // 2 - legend_surface.get_width() // 2, 
                                            WINDOW_HEIGHT - legend_height + 5))
            
            # Update display
            pygame.display.flip()
            self.clock.tick(FPS)
        
        pygame.quit()
        sys.exit()

# Run the game
if __name__ == "__main__":
    baseball_ui = BaseballUI()
    baseball_ui.run()