import numpy as np

# ??? punch list
# walk with 1b open does not score a run
# fo runners tag?
# fc or dp erases lead runners
# 2 out base hits scores runner from second (2 base advanced instead of one


class Bases:
    def __init__(self):
        self.baserunners = None
        self.baserunners_names = None
        self.player_scored = None
        self.clear_bases()  # initialize bases to no runners
        self.runs_scored = 0
        self.num_runners = 0
        return

    def advance_runners(self, bases_to_advance=1):
        self.player_scored = {}
        self.baserunners = list(np.roll(self.baserunners, bases_to_advance))  # advance runners
        self.runs_scored = np.count_nonzero(self.baserunners[-4:])  # 0 ab 1, 2, 3 are bases. 4-7 run crossed home=len 4
        for player_num in self.baserunners[-4:]:  # get player ids that scored
            if len(self.baserunners_names[player_num]) > 0:  # base runner names is a lookup and does not need reset
                self.player_scored[player_num] = self.baserunners_names[player_num]
        self.baserunners[-4] = 0  # send the runners that score back to the dug out
        self.baserunners = [baserunner if i <= 3 else 0 for i, baserunner in enumerate(self.baserunners)]  # reset bases
        self.num_runners = np.count_nonzero(self.baserunners[1:3])  # add the number of people on base 1st, 2b, and 3rd
        return

    def new_ab(self, batter_num=1, player_name=''):
        self.baserunners[0] = batter_num  # put a player ab
        self.baserunners_names[batter_num] = player_name  # add player name to lookup table
        self.player_scored = {}  # key to not double counting runs
        self.runs_scored = 0
        return

    def clear_bases(self):
        # index 0 is ab, 1st = 1, 2nd =2 , 3rd=3, 4th=home, pos 5-7 scored
        # if a value is non-zero it is the index number of the player
        # 0 indicates an empty base
        self.baserunners = [0, 0, 0, 0, 0, 0, 0, 0]
        self.baserunners_names = {}  # names doesn't need to be cleared, but just to be safe every half inning
        self.baserunners_names[0] = ''
        self.player_scored = {}
        self.num_runners = 0
        return

    def remove_runner(self, base):
        # remove runner from 1st, 2nd, or 3rd for DP or FC
        # index pos 1 is 1b so base # is used as offset
        self.baserunners[base] = 0
        self.baserunners_names[base] = ''
        return

    def is_runner_on_base_num(self, base_num):
        # print(f'is_runner_on_first {self.baserunners}, {self.baserunners[1] == 1}')
        return self.baserunners[base_num] != 0

    def tag_up(self):
        self.runs_scored += 1  # give batter and RBI
        self.move_a_runner(3, 4)  # move runner from 3 to 4
        return

    def move_a_runner(self, basenum_from, basenum_to):
        self.baserunners[basenum_to] = self.baserunners[basenum_from]
        self.baserunners[basenum_from] = 0
        return

    def count_runners(self):
        return np.count_nonzero(self.baserunners[1:])  # don't count the hitter

    def describe_runners(self):
        desc = ''
        base_names = ['AB', '1st', '2nd', '3rd', 'home', 'scored', 'scored', 'scored']  # leave this for sort order
        base_names_zip = set(zip(base_names, self.baserunners))
        base_names_with_runners = list(filter(lambda base_name_zip: base_name_zip[1] > 0 and base_name_zip[0] != 'AB'
                                              and base_name_zip[0] != 'home', base_names_zip))
        base_names_with_runners.sort()
        for base_name in base_names_with_runners:
            desc = base_name[0] if desc == '' else desc + ', ' + base_name[0]
        prefix = 'Runner on ' if self.num_runners == 1 else 'Runners on '
        return prefix + desc
