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
        self.starting_pitchers = None
        self.cur_pitcher_index = None
        self.cur_lineup_index = []
        self.box_score = None
        self.game_num = game_num
        self.rotation_len = rotation_len
        return

    def set_lineup(self, show_lineup=False):
        self.set_batting_order()
        self.set_starting_rotation()
        if show_lineup:
            self.print_starting_lineups()
        self.box_score = teamgamestats.TeamBoxScore(self.lineup, self.pitching, self.team_name)
        return

    def set_batting_order(self):
        position_list = ['C', '1B', '2B', '3B', 'SS', 'OF', 'OF', 'OF', 'DH']
        pos_index_list = []
        for postion in position_list:
            pos_index = self.search_for_pos(position=postion, lineup_index_list=pos_index_list, stat_criteria='OPS')
            pos_index_list.append(pos_index)

        self.lineup = self.pos_players.loc[pos_index_list].sort_values('OPS', ascending=False)
        for row_num in range(0, len(self.lineup)):  # set up battering order in lineup card by index
            self.cur_lineup_index.append(self.lineup.index[row_num])
        return

    def set_starting_rotation(self):
        self.starting_pitchers = self.pitchers.sort_values('GS', ascending=False).head(5)  # starting 5
        self.pitching = self.starting_pitchers.iloc[[self.game_num % self.rotation_len]]  # grab the nth row dbl []-> df
        self.cur_pitcher_index = self.pitching.index[0]  # pitcher rotates based on selection above
        return

    def search_for_pos(self, position, lineup_index_list, stat_criteria='OPS'):
        # find players not in lineup at specified position, sort by stat descending to find the best
        # if pos is DH open up search to any position.
        not_selected_criteria = ~self.pos_players.index.isin(lineup_index_list)
        pos_criteria = self.pos_players['Pos'] == position
        df_criteria = not_selected_criteria & pos_criteria if position != 'DH' else not_selected_criteria
        pos_index = self.pos_players[df_criteria].sort_values(stat_criteria, ascending=False).head(1).index
        return pos_index[0]  # tuple of index and dtype, just want index

    def best_at_stat(self, lineup_index_list, stat_criteria='OPS', count=9):
        # find players in lineup, sort by stat descending to find the best
        df_criteria = self.pos_players.index.isin(lineup_index_list)
        stat_index = self.pos_players[df_criteria].sort_values(stat_criteria, ascending=False).head(count).index
        return list(stat_index)

    def print_starting_lineups(self):
        print(f'Starting lineup for {self.team_name}:')
        print(self.lineup.to_string(index=False, justify='center'))
        print('')
        print(f'Pitching for {self.team_name}:')
        print(self.pitching.to_string(index=False, justify='center'))
        print('')
        return
