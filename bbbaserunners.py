import numpy as np
class Bases:
    def __init__(self):
        self.baserunners = None
        self.clear_bases()  # initialize bases to no runners
        self.runs_scored = 0
        self.num_runners = 0
        return

    def advance_runners(self, bases_to_advance=1):
        self.baserunners = list(np.roll(self.baserunners, bases_to_advance))  # advance runners
        self.runs_scored = np.sum(self.baserunners[-4:])  # 0 ab 1, 2, 3 are bases. 4-7 run crossed home hence length 4
        self.baserunners[-4] = 0  # send the runners that score back to the dug out
        self.baserunners = [baserunner if i <= 3 else 0 for i, baserunner in enumerate(self.baserunners)]
        self.num_runners = np.sum(self.baserunners[1:3])  # add the number of people on base 1st, 2b, and 3rd
        return

    def new_ab(self):
        self.baserunners[0] = 1  # put a player ab
        self.runs_scored = 0
        return

    def clear_bases(self):
        # index 0 is ab, 1st = 1, 2nd =2 , 3rd=3, 4th=home, pos 5-7 scored
        self.baserunners = [0, 0, 0, 0, 0, 0, 0, 0]
        self.num_runners = 0
        return

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
