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
        # baseball_data.print_current_season()

        self.lineup = None  # uses prior season stats
        self.lineup_new_season = None  # new / current season stats for printing starting lineup
        self.pitching = None  # uses prior season stats
        self.pitching_new_season = None  # new / current season stats for printing starting lineup
        self.starting_pitchers = None
        self.cur_pitcher_index = None
        self.cur_lineup_index = []
        self.relievers = None  # df of 2 best closers
        self.middle_relievers = None  # remaining pitchers sorted by IP descending
        self.unavailable_pitchers = None
        self.box_score = None
        self.game_num = game_num
        self.rotation_len = rotation_len

        self.fatigue_start_perc = 70  # 85% of way to avg max is where fatigue starts
        self.fatigue_rate = .001  # at 85% of avg max pitchers have a .014 increase in OBP.  using .001 as proxy
        self.fatigue_pitching_change_limit = 5  # change pitcher at # or below out of 100
        self.fatigue_pitching_unavailable = 50  # condition must be 51 or higher for a pitcher to be available

        return

    def is_pitching_index(self):
        return self.cur_pitcher_index

    def set_lineup(self, show_lineup=False, current_season_stats=True):
        self.set_batting_order()
        self.set_starting_rotation()
        self.set_closers()
        self.set_mid_relief()
        # self.set_unavailable()
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
        # self.pitching_new_season.drop(['Season', 'Total_OB', 'Total_Outs'], axis=1, inplace=True)
        return

    def cur_pitcher_stats(self):
        if isinstance(self.pitching, pd.Series) is not pd.Series:  # this should never happen
            self.pitching = self.pitching.squeeze()
        # print(self.pitching)
        return self.pitching  # should be a series with a single row

    def set_pitching_condition(self, percent_of_max):
        try:
            condition = 100 - percent_of_max if (100 - percent_of_max) >= 0 else 0
            self.pitching.Condition = condition
        except Exception as e:
            print(f'error in set_pitching_condition gameteam.py {e}')
            print(self.pitching)
            raise Exception('set pitching condition error')
        return

    def cur_batter_stats(self, loc_in_lineup):
        batting = self.lineup.iloc[loc_in_lineup]  # data for batter
        return batting  # should be a series with a single row

    def update_fatigue(self, cur_pitching_index):
        # number of batters faced in game vs. historic avg with fatigue start as a ratio
        in_game_fatigue = 0
        cur_game_faced = self.box_score.batters_faced(cur_pitching_index)
        avg_faced = self.cur_pitcher_stats().AVG_faced  # data for pitcher
        cur_percentage = cur_game_faced / avg_faced * 100
        if cur_percentage >= self.fatigue_start_perc:
            in_game_fatigue = (cur_percentage - self.fatigue_start_perc) * self.fatigue_rate
        # print(f'bbgame.update_fatigue current game:{cur_game_faced} avg_batters_faced:{avg_faced}')
        # print(f'current %:{cur_percentage} in game fatigue:{in_game_fatigue}')
        self.set_pitching_condition(cur_percentage)
        return in_game_fatigue, cur_percentage  # obp impact to pitcher of fatigue

    def pitching_change(self, inning):
        # desired 7, 8, 9 short term relief against count, need to check score diff ?????
        if (inning <= 9 and len(self.relievers) >= (9 - (inning - 1))) or (inning > 9 and len(self.relievers) >= 1):
            if inning <= 9:
                self.cur_pitcher_index = self.relievers.index[9 - inning]  # 7th would be rel 2 since row count start 0
            else:
                self.cur_pitcher_index = self.relievers.index[0]  # just take the next pitcher
            self.pitching = self.relievers.loc[self.cur_pitcher_index]  # should be a series
            self.box_score.add_pitcher_to_box(self.relievers.loc[self.cur_pitcher_index])
            self.relievers = self.relievers.drop(self.cur_pitcher_index, axis=0)  # remove from pen
        elif len(self.middle_relievers) >= 1:  # grab next middle reliever
            self.cur_pitcher_index = self.middle_relievers.index[0]  # make sure to drop the same index below
            self.pitching = self.middle_relievers.loc[self.cur_pitcher_index]  # should be a series
            self.box_score.add_pitcher_to_box(self.middle_relievers.loc[self.cur_pitcher_index])
            self.middle_relievers = self.middle_relievers.drop(self.cur_pitcher_index, axis=0)  # remove from pen
        # elif len(self.relievers) == 0 and len(self.relievers) == 0 and len(self.starting_pitchers) > 0:  # grab someone
        #     # print(f'gameteam.py out of pitching in inning {inning}!')
        #     # print(self.starting_pitchers.to_string())
        #     # print(self.relievers.to_string())
        #     # print(self.middle_relievers.to_string())
        #     # print(self.pitchers.to_string())
        #     self.cur_pitcher_index = self.starting_pitchers.index[0]
        #     self.pitching = self.starting_pitchers.loc[0]  # grab any pitcher because we're out!
        #     self.box_score.add_pitcher_to_box(self.starting_pitchers.loc[self.cur_pitcher_index])
        #     self.starting_pitchers = self.starting_pitchers.drop(self.cur_pitcher_index, axis=0)  # remove from pen
        #     # raise Exception('no pitching!')
        else:  # no change
            pass
        return self.cur_pitcher_index

    def is_pitcher_fatigued(self, condition):
        # print(self.cur_pitcher_stats())
        # print(self.cur_pitcher_stats().Condition <= self.fatigue_pitching_change_limit)
        # return self.cur_pitcher_stats().Condition <= self.fatigue_pitching_change_limit
        return condition <= self.fatigue_pitching_change_limit

    def set_closers(self):
        # grab top closers for setup and final close
        not_selected_criteria = ~self.pitchers.index.isin(self.starting_pitchers.index)
        not_exhausted = ~(self.pitchers['Condition'] <= self.fatigue_pitching_unavailable)
        not_injured = (self.pitchers['Injured List'] == 0)
        sv_criteria = self.pitchers.SV > 0
        df_criteria = not_selected_criteria & sv_criteria & not_exhausted & not_injured
        self.relievers = self.pitchers[df_criteria].sort_values('SV', ascending=False).head(2)
        return

    def set_mid_relief(self):
        not_selected_criteria = ~self.pitchers.index.isin(self.starting_pitchers.index)
        not_reliever_criteria = ~self.pitchers.index.isin(self.relievers.index)
        not_exhausted = ~(self.pitchers['Condition'] <= self.fatigue_pitching_unavailable)
        not_injured = (self.pitchers['Injured List'] == 0)
        df_criteria = not_selected_criteria & not_reliever_criteria & not_exhausted & not_injured
        self.middle_relievers = self.pitchers[df_criteria].sort_values('IP', ascending=False)
        return

    def set_unavailable(self):
        exhausted = (self.pitchers['Condition'] > self.fatigue_pitching_unavailable)
        injured = (self.pitchers['Injured List'] > 0)
        df_criteria = exhausted | injured
        self.unavailable_pitchers = self.pitchers[df_criteria].sort_values('IP', ascending=False)
        print('gameteam.py set unavailable due to fatigue or injury....')
        # print(self.unavailable_pitchers.to_string())
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
            dfb = bbstats.remove_non_print_cols(self.lineup_new_season)
            dfp = bbstats.remove_non_print_cols(self.pitching_new_season)
        else:
            dfb = bbstats.remove_non_print_cols(self.lineup)
            dfp = bbstats.remove_non_print_cols(self.pitching)

        print(dfb.to_string(index=True, justify='center'))
        print('')
        print(f'Pitching for {self.team_name}:')
        print(dfp.to_string(index=True, justify='center'))
        print('')
        return
