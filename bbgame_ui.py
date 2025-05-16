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
import bbgame
from bbgame import Game
import bbbaserunners

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
FONT_SMALLEST = pygame.font.SysFont("Arial", 8)
FONT_SMALLER = pygame.font.SysFont("Arial", 10)
FONT_SMALL = pygame.font.SysFont("Arial", 12)
FONT_MEDIUM = pygame.font.SysFont("Arial", 14)
FONT_LARGE = pygame.font.SysFont("Arial", 18)
FONT_TITLE = pygame.font.SysFont("Arial", 20, bold=True)

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
        
        # Field coordinates
        self.field_center_x = WINDOW_WIDTH // 2
        self.field_center_y = 400
        self.base_distance = 120
        
        # UI areas
        self.scoreboard_rect = pygame.Rect(20, 20, WINDOW_WIDTH - 40, 120)
        self.field_rect = pygame.Rect(20, 160, WINDOW_WIDTH // 2, 400)
        self.lineup_rect = pygame.Rect(WINDOW_WIDTH // 2 + 40, 160, WINDOW_WIDTH // 2 - 60, 400)
        self.outcome_rect = pygame.Rect(20, 580, WINDOW_WIDTH - 40, 200)
        
        # Increase max outcome lines to fit in the play-by-play area
        self.max_outcome_lines = 15
        
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
            load_batter_file='stats-pp-Batting.csv',
            load_pitcher_file='stats-pp-Pitching.csv',
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
        
    def add_outcome_text(self, text):
        """Add text to the outcome window, keeping the last N lines"""
        lines = text.split('\n')
        for line in lines:
            if line.strip():  # Skip empty lines
                self.current_outcome_text.append(line)
        
        # Keep only the last max_outcome_lines
        if len(self.current_outcome_text) > self.max_outcome_lines:
            self.current_outcome_text = self.current_outcome_text[-self.max_outcome_lines:]
    
    def draw_scoreboard(self):
        """Draw the game scoreboard"""
        pygame.draw.rect(self.screen, GRAY, self.scoreboard_rect, border_radius=5)
        
        # Title
        title_text = f"{self.away_team} vs {self.home_team}"
        title_surface = FONT_TITLE.render(title_text, True, BLACK)
        self.screen.blit(title_surface, (self.scoreboard_rect.centerx - title_surface.get_width() // 2, 
                                         self.scoreboard_rect.y + 10))
        
        # Score
        score_text = f"Score: {self.away_team} {self.game.total_score[0]} - {self.home_team} {self.game.total_score[1]}"
        score_surface = FONT_LARGE.render(score_text, True, BLACK)
        self.screen.blit(score_surface, (self.scoreboard_rect.centerx - score_surface.get_width() // 2, 
                                         self.scoreboard_rect.y + 50))
        
        # Inning
        inning_text = f"{'Top' if self.game.top_bottom == 0 else 'Bottom'} of Inning {self.game.inning[self.game.team_hitting()]}"
        inning_surface = FONT_MEDIUM.render(inning_text, True, BLACK)
        self.screen.blit(inning_surface, (self.scoreboard_rect.centerx - inning_surface.get_width() // 2, 
                                          self.scoreboard_rect.y + 80))
        
        # Outs
        outs_text = f"Outs: {self.game.outs}"
        outs_surface = FONT_MEDIUM.render(outs_text, True, BLACK)
        self.screen.blit(outs_surface, (self.scoreboard_rect.right - outs_surface.get_width() - 20, 
                                        self.scoreboard_rect.y + 80))
    
    def draw_field(self):
        """Draw the baseball field with runners and fielders"""
        pygame.draw.rect(self.screen, GRAY, self.field_rect, border_radius=5)
        
        field_center_x = self.field_rect.centerx
        field_center_y = self.field_rect.centery
        
        # Background rectangle with gray
        pygame.draw.rect(self.screen, GRAY, self.field_rect, border_radius=5)
        
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
        
        # Draw bases
        # Home plate
        pygame.draw.rect(self.screen, WHITE, 
                        (field_center_x - 10, field_center_y + self.base_distance - 10, 20, 20))
        
        # First base
        pygame.draw.rect(self.screen, WHITE, 
                        (field_center_x + self.base_distance - 10, field_center_y - 10, 20, 20))
        
        # Second base
        pygame.draw.rect(self.screen, WHITE, 
                        (field_center_x - 10, field_center_y - self.base_distance - 10, 20, 20))
        
        # Third base
        pygame.draw.rect(self.screen, WHITE, 
                        (field_center_x - self.base_distance - 10, field_center_y - 10, 20, 20))
        
        # Draw pitcher's mound
        pygame.draw.circle(self.screen, BROWN, (field_center_x, field_center_y), 10)
        
        # Draw fielders with more spread-out infield positions
        fielder_positions = {
            'P': (field_center_x, field_center_y),
            'C': (field_center_x, field_center_y + self.base_distance + 30),
            '1B': (field_center_x + self.base_distance - 20, field_center_y - 20),
            '2B': (field_center_x + 60, field_center_y - 70),
            '3B': (field_center_x - self.base_distance + 20, field_center_y - 20),
            'SS': (field_center_x - 60, field_center_y - 70),
            'LF': (field_center_x - self.base_distance - 40, field_center_y - self.base_distance - 40),
            'CF': (field_center_x, field_center_y - self.base_distance - 80),
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
            # Draw the fielder as a circle
            pygame.draw.circle(self.screen, BLUE, coords, 8)
            
            # Show position
            pos_text = FONT_SMALLEST.render(pos, True, BLACK)
            self.screen.blit(pos_text, (coords[0] - pos_text.get_width() // 2, coords[1] + 10))
            
            # Show player name and in-game stats if we have them
            if pos in position_to_player:
                player_name = position_to_player[pos]
                
                # Format player name (first initial + last name)
                player_parts = player_name.split()
                formatted_player_name = f"{player_parts[0][0]}. {' '.join(player_parts[1:])}" if len(player_parts) > 0 else player_name
                
                # Truncate long names
                if len(formatted_player_name) > 10:
                    formatted_player_name = formatted_player_name[:8] + ".."
                
                name_text = FONT_SMALLEST.render(formatted_player_name, True, BLACK)
                self.screen.blit(name_text, (coords[0] - name_text.get_width() // 2, coords[1] + 25))
                
                # No in-game stats displayed next to fielders as requested
        
        # Draw runners if present
        if self.game.bases.is_runner_on_base_num(1):  # Runner on first
            # Draw runner as yellow square
            pygame.draw.rect(self.screen, YELLOW, 
                          (field_center_x + self.base_distance - 8, field_center_y - 8, 16, 16))
            runner_name = self.game.bases.baserunners_names[self.game.bases.baserunners[1]]
            
            # Format runner name (first initial + last name)
            runner_parts = runner_name.split()
            formatted_runner_name = f"{runner_parts[0][0]}. {' '.join(runner_parts[1:])}" if len(runner_parts) > 0 else runner_name
            
            name_text = FONT_SMALLEST.render(formatted_runner_name[:10], True, BLACK)
            # Position name to right of base
            self.screen.blit(name_text, (field_center_x + self.base_distance + 15, 
                                      field_center_y - 6))
            
        if self.game.bases.is_runner_on_base_num(2):  # Runner on second
            pygame.draw.rect(self.screen, YELLOW, 
                          (field_center_x - 8, field_center_y - self.base_distance - 8, 16, 16))
            runner_name = self.game.bases.baserunners_names[self.game.bases.baserunners[2]]
            
            # Format runner name (first initial + last name)
            runner_parts = runner_name.split()
            formatted_runner_name = f"{runner_parts[0][0]}. {' '.join(runner_parts[1:])}" if len(runner_parts) > 0 else runner_name
            
            name_text = FONT_SMALLEST.render(formatted_runner_name[:10], True, BLACK)
            # Position name to right of base
            self.screen.blit(name_text, (field_center_x + 15, 
                                      field_center_y - self.base_distance - 6))
            
        if self.game.bases.is_runner_on_base_num(3):  # Runner on third
            pygame.draw.rect(self.screen, YELLOW, 
                          (field_center_x - self.base_distance - 8, field_center_y - 8, 16, 16))
            runner_name = self.game.bases.baserunners_names[self.game.bases.baserunners[3]]
            
            # Format runner name (first initial + last name)
            runner_parts = runner_name.split()
            formatted_runner_name = f"{runner_parts[0][0]}. {' '.join(runner_parts[1:])}" if len(runner_parts) > 0 else runner_name
            
            name_text = FONT_SMALLEST.render(formatted_runner_name[:10], True, BLACK)
            # Position name to right of base
            self.screen.blit(name_text, (field_center_x - self.base_distance + 15, 
                                      field_center_y - 6))
        
        # Draw current batter - always show the current batter in the lineup
        # Get current batter from lineup, not from bases (which might have last out)
        batter_num = self.game.batting_num[self.game.team_hitting()]
        batter_index = self.game.teams[self.game.team_hitting()].batter_index_in_lineup(batter_num)
        batter_stats = self.game.teams[self.game.team_hitting()].batter_stats_in_lineup(batter_index)
        
        # Draw the batter at home plate
        pygame.draw.rect(self.screen, PURPLE, 
                      (field_center_x - 8, field_center_y + self.base_distance - 8, 16, 16))
        
        # Format batter name (first initial + last name)
        batter_name = batter_stats.Player
        batter_parts = batter_name.split()
        formatted_batter_name = f"{batter_parts[0][0]}. {' '.join(batter_parts[1:])}" if len(batter_parts) > 0 else batter_name
        
        # Display the batter name
        name_text = FONT_SMALLEST.render(formatted_batter_name[:10], True, BLACK)
        # Position name to right of base
        self.screen.blit(name_text, (field_center_x + 15, 
                                  field_center_y + self.base_distance - 6))
    
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
        
        # Title
        title_text = "Game Play-by-Play"
        title_surface = FONT_LARGE.render(title_text, True, BLACK)
        self.screen.blit(title_surface, (self.outcome_rect.centerx - title_surface.get_width() // 2, 
                                         self.outcome_rect.y + 10))
        
        # Display outcome text with smaller font and line spacing
        text_y = self.outcome_rect.y + 40
        for line in self.current_outcome_text:
            line_surface = FONT_SMALLER.render(line, True, BLACK)
            self.screen.blit(line_surface, (self.outcome_rect.x + 20, text_y))
            text_y += 16  # Reduced from 20
            
            # Make sure we don't exceed the outcome rect area
            if text_y > self.outcome_rect.bottom - 20:
                # If we're running out of space, show indicator that there are more lines
                more_text = FONT_SMALL.render("...", True, BLACK)
                self.screen.blit(more_text, (self.outcome_rect.right - 50, self.outcome_rect.bottom - 20))
                break
    
    def sim_next_at_bat(self):
        """Simulate the next at-bat in the game"""
        if self.game.is_game_end():
            self.add_outcome_text("The game has ended.")
            return
            
        # Store current state to detect changes
        prior_outs = self.game.outs
        prior_score = self.game.total_score.copy()
        prior_bases_state = [self.game.bases.is_runner_on_base_num(1), 
                             self.game.bases.is_runner_on_base_num(2),
                             self.game.bases.is_runner_on_base_num(3)]
        
        # Simulate one at-bat
        pitch_switch = False
        pitch_switch = self.game.pitching_sit(self.game.teams[self.game.team_pitching()].cur_pitcher_stats(),
                                           pitch_switch=pitch_switch)
        self.game.stolen_base_sit()
        
        if self.game.outs >= 3:
            self.add_outcome_text("The half inning is over.")
            return
            
        self.game.balk_wild_pitch()
        __pitching, __batting = self.game.sim_ab()
        
        # Check for runs scored
        if self.game.bases.runs_scored > 0:
            self.game.update_inning_score(number_of_runs=self.game.bases.runs_scored)
            players = ''
            for player_id in self.game.bases.player_scored.keys():
                players = players + ', ' + self.game.bases.player_scored[player_id] if players != '' else self.game.bases.player_scored[player_id]
            self.add_outcome_text(f"Scored {self.game.bases.runs_scored} run(s)! ({players})")
            self.add_outcome_text(f"The score is {self.game.team_names[0]} {self.game.total_score[0]} to {self.game.team_names[1]} {self.game.total_score[1]}")
        
        # Get outcome text from the most recent at-bat
        batting_team = self.game.team_names[self.game.team_hitting()]
        batter_name = __batting.Player
        pitcher_name = __pitching.Player
        outcome = self.game.outcomes.score_book_cd
        
        self.add_outcome_text(f"Pitcher: {pitcher_name} against {batting_team} batter: {batter_name}")
        self.add_outcome_text(f"Outcome: {outcome}, Outs: {self.game.outs}")
        
        if self.game.bases.count_runners() >= 1 and self.game.outs < 3:
            self.add_outcome_text(self.game.bases.describe_runners())
        
        # Update batting order
        self.game.batting_num[self.game.team_hitting()] = self.game.batting_num[self.game.team_hitting()] + 1 if (self.game.batting_num[self.game.team_hitting()] + 1) <= 9 else 1
        
        # Check if half inning is over
        if prior_outs < 3 and self.game.outs >= 3:
            # Half inning is over
            self.game.update_inning_score(number_of_runs=0)
            self.game.bases.clear_bases()
            top_or_bottom = 'top' if self.game.top_bottom == 0 else 'bottom'
            self.add_outcome_text(f"Completed {top_or_bottom} half of inning {self.game.inning[self.game.team_hitting()]}")
            self.add_outcome_text(f"The score is {self.game.team_names[0]} {self.game.total_score[0]} to {self.game.team_names[1]} {self.game.total_score[1]}")
            
            self.game.inning[self.game.team_hitting()] += 1
            self.game.top_bottom = 0 if self.game.top_bottom == 1 else 1
            self.game.outs = 0
            
            if self.game.is_game_end():
                self.game.end_game()
                self.add_outcome_text("Game Over!")
                self.add_outcome_text(f"Final Score: {self.game.team_names[0]} {self.game.total_score[0]} to {self.game.team_names[1]} {self.game.total_score[1]}")
            else:
                top_or_bottom = 'top' if self.game.top_bottom == 0 else 'bottom'
                self.add_outcome_text(f"Starting the {top_or_bottom} of inning {self.game.inning[self.game.team_hitting()]}")
    
    def sim_half_inning(self):
        """Simulate a full half-inning"""
        if self.game.is_game_end():
            self.add_outcome_text("The game has ended.")
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
            
            # Update display
            pygame.display.flip()
            self.clock.tick(FPS)
        
        pygame.quit()
        sys.exit()

# Run the game
if __name__ == "__main__":
    baseball_ui = BaseballUI()
    baseball_ui.run()