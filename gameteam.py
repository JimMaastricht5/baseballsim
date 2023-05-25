import pandas as pd
import teamgamestats


class Team:
    def __init__(self, team_name, baseball_data, game_num=1, rotation_len=5):
        self.team_name = team_name
        self.baseball_data = baseball_data
        self.pitchers = baseball_data.pitching_data[baseball_data.pitching_data["Team"] == team_name]
        self.pos_players = baseball_data.batting_data[baseball_data.batting_data["Team"] == team_name]

        self.lineup = None
        self.pitching = None
        self.cur_pitcher_index = None
        self.cur_lineup_index = []
        self.box_score = None
        self.game_num = game_num
        self.rotation_len = rotation_len
        return

    def set_lineup(self):
        self.set_batting_order()
        self.set_starting_rotation()

        self.box_score = teamgamestats.TeamBoxScore(self.lineup, self.pitching, self.team_name)
        return

    def set_batting_order(self):
        position_count = {'C': 1, '1B': 1, '2B': 1, '3B': 1, 'SS': 1, 'OF': 3, 'DH': 1}
        for postion in position_count.keys():
            pos_index = self.search_for_pos(postion, position_count[postion])
            # print(pos_index)

        self.lineup = self.pos_players.head(10)  # assumes DH
        for row_num in range(0, len(self.lineup)):  # set up battering order in lineup card by index
            self.cur_lineup_index.append(self.lineup.index[row_num])
        return

    def set_starting_rotation(self):
        self.starting_pitchers = self.pitchers.sort_values('GS', ascending=False).head(5)  # starting 5
        self.pitching = self.starting_pitchers.iloc[[self.game_num % self.rotation_len]]  # grab the nth row dbl []-> df
        self.cur_pitcher_index = self.pitching.index[0]  # pitcher rotates based on selection above
        return

    def search_for_pos(self, position, count, criteria='OPS'):
        if position != 'DH':
            pos_index = self.pos_players[self.pos_players['Pos'] == position].\
                sort_values(criteria, ascending=False).head(1).index
        else:
            pos_index = 0 # ?? need to pick highest something of bench players
        return pos_index