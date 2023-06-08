import pandas as pd
import teamgamestats


class Team:
    def __init__(self, team_name, baseball_data, game_num=1, rotation_len=5):
        self.team_name = team_name
        self.baseball_data = baseball_data
        self.pitchers = baseball_data.pitching_data[baseball_data.pitching_data["Team"] == team_name]
        self.pos_players = baseball_data.batting_data[baseball_data.batting_data["Team"] == team_name]

        self.lineup = None  # uses prior season stats
        self.lineup_new_season = None  # new / current season stats for printing starting lineup
        self.pitching = None  # uses prior season stats
        self.pitching_new_season = None  # new / current season stats for printing starting lineup
        self.starting_pitchers = None
        self.cur_pitcher_index = None
        self.cur_lineup_index = []
        self.box_score = None
        self.game_num = game_num
        self.rotation_len = rotation_len
        return

    def set_lineup(self, show_lineup=False, current_season_stats=True):
        self.set_batting_order()
        self.set_starting_rotation()
        if show_lineup:
            self.print_starting_lineups(current_season_stats=current_season_stats)
        self.box_score = teamgamestats.TeamGameStatsBoxScore(self.lineup, self.pitching, self.team_name)
        return

    def set_batting_order(self):
        position_list = ['C', '2B', '3B', 'SS', 'OF', 'OF', 'OF', '1B', 'DH']  # ?? need to handle subs at 1b and dh ??
        pos_index_list = []
        for postion in position_list:
            pos_index = self.search_for_pos(position=postion, lineup_index_list=pos_index_list, stat_criteria='OPS')
            pos_index_list.append(pos_index)

        sb_index = self.best_at_stat(pos_index_list, 'SB', count=1)
        slg_index = self.best_at_stat(pos_index_list, 'SLG', count=2, exclude=sb_index)  # exclude sb since 1st spot
        ops_index = self.best_at_stat(pos_index_list, 'OPS', count=6, exclude=sb_index + slg_index)

        ops_index = self.insert_player_in_lineup(lineup_list=ops_index, player_index=sb_index[0], target_pos=1)  # 1spot
        ops_index = self.insert_player_in_lineup(lineup_list=ops_index, player_index=slg_index[0], target_pos=4)  # 4th
        ops_index = self.insert_player_in_lineup(lineup_list=ops_index, player_index=slg_index[1], target_pos=5)  # 5th
        self.lineup = self.pos_players.loc[ops_index]
        self.lineup_new_season = self.baseball_data.new_season_batting_data.loc[ops_index]  # get the new season stats
        self.lineup_new_season.drop(['Season', 'Total_OB', 'Total_Outs'], axis=1, inplace=True)
        for row_num in range(0, len(self.lineup)):  # set up battering order in lineup card by index
            self.cur_lineup_index.append(self.lineup.index[row_num])
        return

    def insert_player_in_lineup(self, lineup_list, player_index, target_pos):
        # target pos is position in line up not pos in life, works if you insert from front to back
        # so dont insert at pos 3 or pos 4 or it will shift pos 4 to pos 5
        # print(f'Insert player: {player_index} into {target_pos - 1} with current lineup {lineup_list}')
        lineup_list.insert(target_pos - 1, player_index)
        # print(f'Inserted player: {player_index} into {target_pos - 1} with current lineup {lineup_list}')
        return lineup_list

    def move_player_in_lineup(self, lineup_list, player_index, target_pos):
        # target pos is position in line up not pos in life
        # note this will shift the lineup back at that pos
        # print(f'Move player: {player_index} into {target_pos - 1} with current lineup {lineup_list}')
        lineup_list.remove(player_index)
        lineup_list.insert(target_pos - 1, player_index)
        # print(f'Moved player: {player_index} into {target_pos - 1} with current lineup {lineup_list}')
        return lineup_list

    def set_starting_rotation(self):
        self.starting_pitchers = self.pitchers.sort_values('GS', ascending=False).head(5)  # starting 5
        self.pitching = self.starting_pitchers.iloc[[self.game_num % self.rotation_len]]  # grab the nth row dbl []-> df
        self.cur_pitcher_index = self.pitching.index[0]  # pitcher rotates based on selection above
        self.pitching_new_season = self.baseball_data.new_season_pitching_data.loc[self.cur_pitcher_index].to_frame().T
        self.pitching_new_season.drop(['Season', 'Total_OB', 'Total_Outs'], axis=1, inplace=True)
        return

    def search_for_pos(self, position, lineup_index_list, stat_criteria='OPS'):
        # find players not in lineup at specified position, sort by stat descending to find the best
        # if pos is DH open up search to any position.
        not_selected_criteria = ~self.pos_players.index.isin(lineup_index_list)
        pos_criteria = self.pos_players['Pos'] == position
        df_criteria = not_selected_criteria & pos_criteria if (position != 'DH' and position != '1B')\
            else not_selected_criteria
        pos_index = self.pos_players[df_criteria].sort_values(stat_criteria, ascending=False).head(1).index
        return pos_index[0]  # tuple of index and dtype, just want index

    def best_at_stat(self, lineup_index_list, stat_criteria='OPS', count=9, exclude=[]):
        # find players in lineup, sort by stat descending to find the best
        df_criteria = self.pos_players.index.isin(lineup_index_list) & ~self.pos_players.index.isin(exclude)
        stat_index = self.pos_players[df_criteria].sort_values(stat_criteria, ascending=False).head(count).index
        # print(f'best at stat: {stat_criteria}, {stat_index}')
        return list(stat_index)

    def print_starting_lineups(self, current_season_stats=True):
        print(f'Starting lineup for {self.team_name}:')
        if current_season_stats:
            print(self.lineup_new_season.to_string(index=True, justify='center'))
            print('')
            print(f'Pitching for {self.team_name}:')
            print(self.pitching_new_season.to_string(index=True, justify='center'))
            print('')
        else:
            print(self.lineup.to_string(index=True, justify='center'))
            print('')
            print(f'Pitching for {self.team_name}:')
            print(self.pitching.to_string(index=True, justify='center'))
            print('')
        return
