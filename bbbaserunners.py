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
Baseball base runner tracking and advancement system.

This module handles the movement of base runners during game simulation, including
walks, hits, double plays, stolen bases, and scoring. Runners are tracked using
player hashcodes, with special positions for at-bat, bases 1-3, and scoring positions.
"""
import numpy as np
from numpy import bool_, int32
from typing import Union


class Bases:
    """
    Manages base runners and their advancement during baseball game simulation.

    The class tracks runners using an 8-position array:
    - Index 0: At-bat (current batter)
    - Index 1-3: Bases 1st, 2nd, 3rd
    - Index 4-7: Temporary scoring positions (cleared after each at-bat)

    Each position contains either 0 (empty) or a player's hashcode (occupied).
    Player names are tracked separately in baserunners_names dictionary.

    Attributes:
        baserunners: 8-element list tracking player positions
        baserunners_names: Dictionary mapping player hashcodes to names
        player_scored: Dictionary of players who scored this at-bat
        runs_scored: Number of runs scored in current at-bat
    """
    def __init__(self) -> None:
        """Initialize empty bases with no runners."""
        self.baserunners = None
        self.baserunners_names = {}
        self.player_scored = None
        self.clear_bases()  # initialize bases to no runners
        self.runs_scored = 0
        return

    def handle_runners(self, score_book_cd: str, bases_to_advance: int, on_base_b: bool, outs: int) -> None:
        """
        Process runner advancement based on at-bat outcome.

        Handles special cases like walks, HBP, sacrifice flies, and ground outs,
        then advances all runners by the calculated number of bases. Tracks which
        players score and updates runs_scored.

        Args:
            score_book_cd: Scorebook code (H, 2B, 3B, HR, BB, HBP, SF, DP, GB FC, GB, SO, etc.)
            bases_to_advance: Number of bases to advance runners (typically 1-4)
            on_base_b: Whether batter reached base safely
            outs: Current number of outs in the inning

        Returns:
            None. Updates self.runs_scored and self.player_scored.
        """
        if outs >= 3:
            return
        if score_book_cd in ['BB', 'HBP']:
            bases_to_advance = self.walk_or_hbp(bases_to_advance)  # set to 1 if bases loaded, else move runners indivly
        elif score_book_cd in ['SF']:
            bases_to_advance = self.tag_up(outs)  # move runner from third and set other runners to hold w/ 0
        elif score_book_cd in ['DP', 'GB FC', 'GB']:
            bases_to_advance = self.ground_out(score_book_cd)
        elif on_base_b and score_book_cd not in ['BB', 'HR', '3B'] and outs == 2:  # 2 out base hit or 2b gets xta base
            self.push_a_runner(1, 2)  # push all runners one base before the std 1 base adv.  adds rbi and runs

        self.player_scored = {}
        self.baserunners = list(np.roll(self.baserunners, bases_to_advance))  # advance runners
        self.runs_scored = np.count_nonzero(self.baserunners[-4:])  # 0 ab 1, 2, 3 are bases. 4-7 run crossed home=len 4
        for player_num in self.baserunners[-4:]:  # get player ids that scored
            if len(self.baserunners_names[player_num]) > 0:  # base runner names is a lookup and does not need reset
                self.player_scored[player_num] = self.baserunners_names[player_num]
        self.baserunners[-4] = 0  # send the runners that score back to the dug out
        # self.baserunners = [baserunner if i <= 3 else 0 for i, baserunner in enumerate(self.baserunners)]  #resetbases
        self.baserunners[4:] = [0] * 4  # reset based without list comprehension
        return

    def ground_out(self, score_book_cd: str) -> int:
        """
        Handle ground ball outs, including double plays and fielder's choice.

        Args:
            score_book_cd: 'GB' (ground out), 'DP' (double play), or 'GB FC' (fielder's choice)

        Returns:
            int: Number of bases to advance remaining runners (always 1)
        """
        if score_book_cd in ['GB']:  # batter is out
            self.remove_runner(0)
        elif score_book_cd in ['DP']:  # runner at first is out and batter are out
            self.remove_runner(0)
            self.remove_runner(1)
        elif score_book_cd in ['GB FC']:  # runner at first is out
            self.remove_runner(1)
        return 1  # advance remaining runners and batter on an GB FC one base

    def new_ab(self, batter_num: int = 1, player_name: str = '') -> None:
        """
        Start a new at-bat by placing the batter at position 0.

        Args:
            batter_num: Player hashcode (must be non-zero)
            player_name: Player's name for tracking

        Raises:
            ValueError: If batter_num is 0 (reserved for empty positions)
        """
        self.add_runner_to_base(0, batter_num, player_name)
        # self.baserunners[0] = batter_num  # put a player ab
        # self.baserunners_names[batter_num] = player_name  # add player name to lookup table
        if batter_num == 0:
            print(self.baserunners_names)
            raise ValueError('bbbaserunners.py, new_ab, zero value baserunner index.  must be non-zero')
        self.player_scored = {}  # key to not double counting runs
        self.runs_scored = 0
        return

    def add_runner_to_base(self, base_num: int, batter_num: int, player_name: str = '') -> None:
        """
        Place a runner at a specific base position.

        Args:
            base_num: Base position (0=at-bat, 1=1st, 2=2nd, 3=3rd)
            batter_num: Player hashcode
            player_name: Optional player name for tracking
        """
        self.baserunners[base_num] = batter_num
        if player_name != '':
            self.baserunners_names[batter_num] = player_name  # add name to look up table
        return

    def clear_bases(self) -> None:
        """
        Clear all bases and reset tracking for a new half-inning.

        Resets baserunners array to all zeros, clears player name lookup,
        and resets scoring trackers.
        """
        # index 0 is ab, 1st = 1, 2nd =2 , 3rd=3, 4th=home, pos 5-7 scored
        # if a value is non-zero it is the index number of the player
        # 0 indicates an empty base
        self.baserunners = [0, 0, 0, 0, 0, 0, 0, 0]
        self.baserunners_names.clear()  # ={} doesn't need to be cleared, but just to be safe every half inning
        self.baserunners_names[0] = ''
        self.player_scored = {}
        return

    def remove_runner(self, bases: int) -> None:
        """
        Remove runner(s) from base(s) for outs (double play, fielder's choice).

        Args:
            bases: Base position(s) to clear (int or list of ints)
        """
        # remove runner from 1st, 2nd, or 3rd for DP or FC
        # index pos 1 is 1b so base # is used as offset
        if isinstance(bases, list):
            for base in bases:
                self.baserunners[base] = 0
                self.baserunners_names[base] = ''
        else:
            self.baserunners[bases] = 0
            self.baserunners_names[bases] = ''
        return

    def is_runner_on_base_num(self, base_num: int) -> Union[bool, bool_]:
        """
        Check if a runner is on a specific base.

        Args:
            base_num: Base position to check (0=at-bat, 1=1st, 2=2nd, 3=3rd)

        Returns:
            bool: True if runner is on that base, False otherwise
        """
        return self.baserunners[base_num] != 0

    def is_eligible_for_stolen_base(self) -> Union[bool, bool_]:
        """
        Check if stolen base attempt is possible.

        Returns:
            bool: True if runner on 1st with 2nd and 3rd empty
        """
        return self.is_runner_on_base_num(1) and \
                not self.is_runner_on_base_num(2) and not self.is_runner_on_base_num(3)

    def get_runner_key(self, base_num: int) -> int32:
        """
        Get the player hashcode for a runner on a specific base.

        Args:
            base_num: Base position (0=at-bat, 1=1st, 2=2nd, 3=3rd)

        Returns:
            int32: Player hashcode (0 if base is empty)
        """
        return self.baserunners[base_num]  # non zero if there is a runner

    def tag_up(self, outs):
        """
        Handle sacrifice fly - runner on 3rd tags up and scores.

        Moves runner from 3rd to home, advances runner on 2nd to 3rd,
        and removes batter (who is out).

        Args:
            outs: Current number of outs

        Returns:
            int: 0 (no base advancement for remaining runners)
        """
        if outs >= 3:
            return
        self.runs_scored += 1  # give batter an RBI
        self.move_a_runner(3, 4)  # move runner from 3 to 4
        self.move_a_runner(2, 3)  # move runner from 2 to 3rd if there is a runner on second
        self.remove_runner(0)  # batter is out
        return 0  # bases to advance

    def move_a_runner(self, basenum_from: int, basenum_to: int) -> None:
        """
        Move a single runner from one base to another.

        Args:
            basenum_from: Source base position
            basenum_to: Destination base position
        """
        self.baserunners[basenum_to] = self.baserunners[basenum_from]
        self.baserunners[basenum_from] = 0
        if basenum_from == 3 and basenum_to == 4:
            self.runs_scored += 1
        return

    def push_a_runner(self, basenum_from: int, basenum_to: int) -> None:
        """
        Recursively push runners forward when forced.

        If destination base is occupied, recursively pushes that runner forward
        before moving the current runner. Used for walks/HBP with runners on.

        Args:
            basenum_from: Source base position
            basenum_to: Destination base position
        """
        if self.is_runner_on_base_num(basenum_to):
            self.push_a_runner(basenum_from + 1, basenum_to + 1)
        self.move_a_runner(basenum_from, basenum_to)
        return

    def walk_or_hbp(self, bases_to_move_all_runners: int) -> int:
        """
        Handle walk or hit-by-pitch runner advancement.

        If bases are loaded, advances all runners. Otherwise, only advances
        forced runners (uses push_a_runner for cascading movement).

        Args:
            bases_to_move_all_runners: Default bases to advance (typically 1)

        Returns:
            int: Actual bases to advance (0 if bases not loaded, original value if loaded)
        """
        # default is move all runners on base, that works unless there is a hole
        if self.count_runners() < 3 and self.count_runners() != 0:  # not loaded or empty
            # bases are not loaded so move runners up a base when forced
            self.push_a_runner(0, 1)  # move the ab player to 1st base
            bases_to_move_all_runners = 0
        return bases_to_move_all_runners

    def count_runners(self) -> int:
        """
        Count the number of runners currently on base.

        Returns:
            int: Number of runners on 1st, 2nd, and 3rd bases
        """
        return np.count_nonzero(self.baserunners[1:3+1])  # add the number of people on base 1st, 2b, and 3rd

    def describe_runners(self) -> str:
        """
        Generate a human-readable description of base runners.

        Returns:
            str: Description like "Runner on 1st" or "Runners on 1st, 3rd" or empty string if bases empty
        """
        desc = ''
        base_names = ['AB', '1st', '2nd', '3rd', 'home', 'scored', 'scored', 'scored']  # leave this for sort order
        base_names_zip = set(zip(base_names, self.baserunners))
        base_names_with_runners = list(filter(lambda base_name_zip: base_name_zip[1] > 0 and base_name_zip[0] != 'AB'
                                              and base_name_zip[0] != 'home', base_names_zip))
        base_names_with_runners.sort()
        for base_name in base_names_with_runners:
            desc = base_name[0] if desc == '' else desc + ', ' + base_name[0]
        prefix = 'Runner on ' if self.count_runners() == 1 else 'Runners on '
        return desc if self.count_runners() == 0 else prefix + desc
