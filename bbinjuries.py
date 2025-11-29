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
import random
from typing import Dict, List, Tuple


class InjuryType:
    """
    Class to manage injury types, descriptions, and their severity levels
    """
    def __init__(self):
        """
        Initialize injury types with their duration ranges
        """
        # Pitcher-specific injuries (arm/shoulder focused)
        self.pitcher_injuries = {
            # Long-term (30+ days)
            'UCL Tear (Tommy John Surgery)': (120, 210),  # 4-7 months
            'Rotator Cuff Tear': (60, 120),
            'Labrum Tear': (90, 180),
            'Stress Fracture (Arm)': (40, 80),
            'Shoulder Impingement': (30, 60),
            
            # Medium-term (15-30 days)
            'Forearm Strain': (15, 30),
            'Shoulder Inflammation': (15, 30),
            'Elbow Inflammation': (15, 30),
            'Biceps Tendinitis': (15, 25),
            'Lat Strain': (20, 30),
            
            # Short-term (5-15 days)
            'Blister': (5, 12),
            'Finger Strain': (7, 15),
            'Back Spasms': (7, 14),
            'Minor Shoulder Fatigue': (7, 14),
            'Neck Stiffness': (5, 10)
        }
        
        # Batter-specific injuries (more varied)
        self.batter_injuries = {
            # Long-term (30+ days)
            'ACL Tear': (180, 270),
            'Broken Ankle': (40, 60),
            'Broken Wrist': (30, 50),
            'Hamstring Tear': (30, 60),
            'Oblique Strain (Severe)': (30, 45),
            
            # Medium-term (15-30 days)
            'Oblique Strain (Moderate)': (15, 30),
            'Hamstring Strain': (15, 25),
            'Quad Strain': (15, 25),
            'Wrist Inflammation': (15, 25),
            'Ankle Sprain': (15, 30),
            
            # Short-term (5-15 days)
            'Back Spasms': (7, 14),
            'Minor Knee Inflammation': (5, 15),
            'Finger Sprain': (7, 14),
            'Hip Soreness': (5, 12),
            'Foot Contusion': (5, 10)
        }

        # Both pitchers and batters can get these general injuries
        self.general_injuries = {
            # Special cases with specific IL designations
            'Concussion': (7, 14),  # 7-day IL specific for concussions
         #   'COVID-19 Protocol': (10, 21),
            
            # Short-term
            'Illness': (3, 7),
            'Food Poisoning': (2, 5),
            'Paternity Leave': (1, 3)
        }
        
        # Track injury types that have special IL rules
        self.concussion_injuries = {'Concussion'}

    def get_pitcher_injury(self, days: int) -> str:
        """
        Get an appropriate pitcher injury description based on the number of days
        :param days: Number of days the player will be injured
        :return: Injury description that matches the duration
        """
        # Special case: small chance for concussion (1% chance)
        if random.random() < 0.01:
            return "Concussion"
            
        # Categorize injuries based on the number of days
        if days >= 30:
            category = {k: v for k, v in self.pitcher_injuries.items() if v[0] >= 30}
            general = {k: v for k, v in self.general_injuries.items() if v[0] >= 30 and k != "Concussion"}
        elif days >= 15:
            category = {k: v for k, v in self.pitcher_injuries.items() if 15 <= v[0] < 30}
            general = {k: v for k, v in self.general_injuries.items() if 15 <= v[0] < 30 and k != "Concussion"}
        else:
            category = {k: v for k, v in self.pitcher_injuries.items() if v[0] < 15}
            general = {k: v for k, v in self.general_injuries.items() if v[0] < 15 and k != "Concussion"}
        
        # Combine pitcher-specific and general injuries
        combined = {**category, **general}
        if not combined:  # Fallback if no matching injuries found
            return "Undisclosed Injury"
        
        # Return a random injury description from the appropriate category
        return random.choice(list(combined.keys()))

    def get_batter_injury(self, days: int) -> str:
        """
        Get an appropriate batter injury description based on the number of days
        :param days: Number of days the player will be injured
        :return: Injury description that matches the duration
        """
        # Special case: small chance for concussion (2% chance - batters more likely to get concussions)
        if random.random() < 0.02:
            return "Concussion"
            
        # Categorize injuries based on the number of days
        if days >= 30:
            category = {k: v for k, v in self.batter_injuries.items() if v[0] >= 30}
            general = {k: v for k, v in self.general_injuries.items() if v[0] >= 30 and k != "Concussion"}
        elif days >= 15:
            category = {k: v for k, v in self.batter_injuries.items() if 15 <= v[0] < 30}
            general = {k: v for k, v in self.general_injuries.items() if 15 <= v[0] < 30 and k != "Concussion"}
        else:
            category = {k: v for k, v in self.batter_injuries.items() if v[0] < 15}
            general = {k: v for k, v in self.general_injuries.items() if v[0] < 15 and k != "Concussion"}
        
        # Combine batter-specific and general injuries
        combined = {**category, **general}
        if not combined:  # Fallback if no matching injuries found
            return "Undisclosed Injury"
        
        # Return a random injury description from the appropriate category
        return random.choice(list(combined.keys()))

    def get_injury_days_from_description(self, description: str, is_pitcher: bool = True) -> int:
        """
        Get a random number of days for the given injury description
        :param description: The injury description
        :param is_pitcher: Whether the player is a pitcher (True) or batter (False)
        :return: Random number of days within the injury's typical range
        """
        # Check pitcher injuries
        if description in self.pitcher_injuries:
            min_days, max_days = self.pitcher_injuries[description]
            return random.randint(min_days, max_days)
        
        # Check batter injuries
        if description in self.batter_injuries:
            min_days, max_days = self.batter_injuries[description]
            return random.randint(min_days, max_days)
        
        # Check general injuries
        if description in self.general_injuries:
            min_days, max_days = self.general_injuries[description]
            return random.randint(min_days, max_days)
        
        # If injury description not found, return a default range based on player type
        if is_pitcher:
            return random.randint(15, 30)  # Default for pitchers
        else:
            return random.randint(10, 20)  # Default for batters
    
    def is_concussion(self, injury_description: str) -> bool:
        """
        Check if the injury is a concussion, requiring 7-day IL
        :param injury_description: The injury description
        :return: True if it's a concussion, False otherwise
        """
        return injury_description in self.concussion_injuries


# Test the class if run directly
if __name__ == "__main__":
    injury_system = InjuryType()
    
    # Test pitcher injuries
    for days in [10, 20, 45]:
        injury = injury_system.get_pitcher_injury(days)
        print(f"Pitcher injured for {days} days: {injury}")
        
    # Test batter injuries
    for days in [10, 20, 45]:
        injury = injury_system.get_batter_injury(days)
        print(f"Batter injured for {days} days: {injury}")