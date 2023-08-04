import pandas as pd
import teamgameboxstats
import bbstats


class Team:
    def __init__(self, team_name, baseball_data, game_num=1, rotation_len=5):
        pd.options.mode.chained_assignment = None  # suppresses chained assignment warning for lineup pos setting
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
        self.relievers = None  # df of 2 best closers
        self.middle_relievers = None  # remaining pitchers sorted by IP descending
        self.box_score = None
        self.game_num = game_num
        self.rotation_len = rotation_len

        self.fatigue_start_perc = 15  # % of avg max is where fatigue starts
        self.fatigue_rate = .001  # at 85% of avg max pitchers have a .014 increase in OBP.  using .001 as proxy
        return

    def set_lineup(self, show_lineup=False, current_season_stats=True):
        self.set_batting_order()
        self.set_starting_rotation()
        self.set_closers()
        self.set_mid_relief()
        if show_lineup:
            self.print_starting_lineups(current_season_stats=current_season_stats)
        self.box_score = teamgameboxstats.TeamBoxScore(self.lineup, self.pitching, self.team_name)
        return

    def set_batting_order(self):
        position_list = ['C', '2B', '3B', 'SS', 'OF', 'OF', 'OF', '1B', 'DH']  # ?? need to handle subs at 1b and dh ??
        pos_index_list = []
        pos_index_dict = {}
        for position in position_list:
            pos_index = self.search_for_pos(position=position, lineup_index_list=pos_index_list, stat_criteria='OPS')
            pos_index_list.append(pos_index)
            pos_index_dict[pos_index] = position  # keep track of the player index and position for this game

        sb_index = self.best_at_stat(pos_index_list, 'SB', count=1)
        slg_index = self.best_at_stat(pos_index_list, 'SLG', count=2, exclude=sb_index)  # exclude sb since 1st spot
        ops_index = self.best_at_stat(pos_index_list, 'OPS', count=6, exclude=sb_index + slg_index)

        ops_index = self.insert_player_in_lineup(lineup_list=ops_index, player_index=sb_index[0], target_pos=1)  # 1spot
        ops_index = self.insert_player_in_lineup(lineup_list=ops_index, player_index=slg_index[0], target_pos=4)  # 4th
        ops_index = self.insert_player_in_lineup(lineup_list=ops_index, player_index=slg_index[1], target_pos=5)  # 5th
        self.lineup = self.pos_players.loc[ops_index]
        self.lineup_new_season = self.baseball_data.new_season_batting_data.loc[ops_index]  # get the new season stats
        # self.lineup_new_season = bbstats.remove_non_print_cols(self.lineup_new_season, False)
        # self.lineup_new_season.drop(['Season', 'Total_OB', 'Total_Outs'], axis=1, inplace=True)
        for row_num in range(0, len(self.lineup)):  # set up battering order in lineup card by index
            self.cur_lineup_index.append(self.lineup.index[row_num])
            player_index = self.lineup.index[row_num]  # grab the index of the player and set pos for game
            self.lineup.Pos[player_index] = pos_index_dict[player_index]  # set lineup pos
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

    def cur_pitcher_stats(self):
        pitching = self.pitching.iloc[0]  # data for pitcher
        if isinstance(pitching, pd.DataFrame):  # ?? this should never happen
            pitching = pitching.to_series()
        return pitching  # should be a series with a single row

    def cur_batter_stats(self, loc_in_lineup):
        batting = self.lineup.iloc[loc_in_lineup]  # data for batter
        return batting  # should be a series with a single row

    def update_fatigue(self, cur_pitching_index):
        # number of batters faced in game vs. historic avg with fatigue start as a ratio
        in_game_fatigue = 0
        cur_game_faced = self.box_score.batters_faced(cur_pitching_index)
        # print(f'current game faced {cur_game_faced}')
        avg_faced = self.cur_pitcher_stats().AVG_faced  # data for pitcher
        cur_percentage = cur_game_faced / avg_faced * 100
        # print(f'bb game update fatigue {cur_game_faced}, {avg_faced}, {cur_percentage}')
        # print(self.cur_pitcher_stats())
        # + kicker * self.fatigue_rate  # fatigue quickly after reaching 100%
        if cur_percentage >= self.fatigue_start_perc:
            in_game_fatigue = (cur_percentage - self.fatigue_start_perc) * self.fatigue_rate
        # print(f'bbgame.update_fatigue current game:{cur_game_faced} avg_batters_faced:{avg_faced}')
        # print(f'current %:{cur_percentage} in game fatigue:{in_game_fatigue}')
        return in_game_fatigue, cur_percentage  # obp impact to pitcher of fatigue

    def pitching_change(self):  # ?? need to understand game situation for close or mid
        reliever_pitcher_index = self.middle_relievers.index[0]  # make sure to drop the same index below
        self.cur_pitcher_index = reliever_pitcher_index
        self.pitching = pd.DataFrame(self.middle_relievers.loc[reliever_pitcher_index].to_frame().T)
        self.box_score.add_pitcher_to_box(self.middle_relievers.loc[reliever_pitcher_index])
        self.middle_relievers = self.middle_relievers.drop(reliever_pitcher_index, axis=0)  # remove reliever from  pen
        return self.cur_pitcher_index

    def set_closers(self):
        # grab top two closers for setup and final close
        not_selected_criteria = ~self.pitchers.index.isin(self.starting_pitchers.index)
        sv_criteria = self.pitchers.SV > 0
        df_criteria = not_selected_criteria & sv_criteria
        self.relievers = self.pitchers[df_criteria].sort_values('SV', ascending=False).head(2)
        return

    def set_mid_relief(self):
        not_selected_criteria = ~self.pitchers.index.isin(self.starting_pitchers.index)
        not_reliever_criteria = ~self.pitchers.index.isin(self.relievers.index)
        df_criteria = not_selected_criteria & not_reliever_criteria
        self.middle_relievers = self.pitchers[df_criteria].sort_values('IP', ascending=False)
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
            dfb = bbstats.remove_non_print_cols(self.lineup_new_season, False)
            dfp = bbstats.remove_non_print_cols(self.pitching_new_season, True)
        else:
            dfb = bbstats.remove_non_print_cols(self.lineup, False)
            dfp = bbstats.remove_non_print_cols(self.pitching, True)

        print(dfb.to_string(index=True, justify='center'))
        print('')
        print(f'Pitching for {self.team_name}:')
        print(dfp.to_string(index=True, justify='center'))
        print('')
        return
