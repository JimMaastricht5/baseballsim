# ball in play
class InPlay:
    def __init__(self, bases):
        self.bases = bases
        return

    def results_of_ab(self, bases, outcome):
        outs_on_play = 0
        if outcome[0] == 'OUT':
            outs_on_play, outcome = self.at_bat_out(outcome)
        if outcome[1] == 'BB':
            outcome = self.bases.walk(outcome)
        return

    def at_bat_out(self, outcome):
        # there was at least one out on the play, record that right away and deal with SF, DP, FC, adv runners on GB
        # outcome 2 is bases to advance, rbis will be taken care of later
        outs_on_play = 0
        if outcome[1] == 'FO' and self.bases.is_runner_on_base_num(3) and self.outs < 2 and \
                self.rng() <= self.sacfly_odds:  # 3rd out not posted yet so less than 2 outs
            outcome[1] = 'SF'  # will not auto advance if SF
            self.outs += 1
            outs_on_play = 1
            self.bases.remove_runner(0)  # remove batter
            self.bases.tag_up(outs=self.outs)  # only advance runner from 3b to home
            outcome[2] = 0
        elif outcome[1] == 'FO':
            self.outs += 1
            outs_on_play = 1
            self.bases.remove_runner(0)
            outcome[2] = 0
        elif outcome[1] == 'DP' and self.outs <= 1:  # double play
            self.outs += 2
            outs_on_play = 2
            self.bases.remove_runner([0, 1])  # remove runner at bat and first for DP, advancing bases will happen later
            outcome[2] = 1  # advance other runners one base
        elif outcome[1] == 'GB' and self.bases.is_runner_on_base_num(1) and self.rng() <= .5:  # fielders choice
            outcome[1] = 'GB FC'
            self.outs += 1
            outs_on_play = 1
            self.bases.remove_runner(1)  # fc drop runner from 1st going to second, leave batter, advancing bases later
            outcome[2] = 1
        elif outcome[1] == 'GB':
            self.bases.remove_runner(0)  # if it is a gb out runners may advance, but dont adv batter
            self.outs += 1
            outs_on_play = 1
            outcome[2] = 1
        else:
            self.outs += 1
            outs_on_play = 1

        return outs_on_play, outcome