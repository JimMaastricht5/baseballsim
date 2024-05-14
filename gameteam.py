import pandas as pd
import teamgameboxstats
import bbstats


class Team:
    def __init__(self, team_name, baseball_data, game_num=1, rotation_len=5):
        pd.options.mode.chained_assignment = None  # suppresses chained assignment warning for lineup pos setting
        self.team_name = team_name
        self.baseball_data = baseball_data
        self.prior_season_pitchers_df = baseball_data.get_pitching_data(team_name=team_name, prior_season=True)
        self.prior_season_pos_players_df = baseball_data.get_batting_data(team_name=team_name, prior_season=True)
        self.new_season_pos_players_df = baseball_data.get_batting_data(team_name=team_name, prior_season=False)

        self.prior_season_pitchers_df['Condition'] = self.baseball_data.new_season_pitching_data['Condition']
        self.prior_season_pitchers_df['AVG_faced'] = self.prior_season_pitchers_df['AVG_faced'] * \
            self.prior_season_pitchers_df['Condition']
        self.prior_season_pos_players_df['Condition'] = self.baseball_data.new_season_batting_data['Condition']
        if len(self.prior_season_pitchers_df) == 0:
            print(f'Teams available are {self.baseball_data.pitching_data["Team"].unique()}')
            raise ValueError(f'Pitching or batting data was empty for {team_name}')

        self.p_lineup_cols_to_print = ['Player', 'League', 'Team', 'Age', 'G', 'GS', 'CG', 'SHO', 'IP', 'H', '2B', '3B',
                                       'ER', 'K', 'BB', 'HR', 'W', 'L', 'SV', 'BS', 'HLD', 'ERA', 'WHIP',
                                       'Condition']
        self.b_lineup_cols_to_print = ['Player', 'League', 'Team', 'Pos', 'Age', 'G', 'AB', 'R', 'H', '2B', '3B', 'HR',
                                       'RBI', 'SB', 'CS', 'BB', 'SO', 'SH', 'SF', 'HBP', 'AVG', 'OBP', 'SLG', 'OPS',
                                       'Condition']
        if ('Mascot' in self.prior_season_pos_players_df.columns) is True:
            self.mascot = self.prior_season_pos_players_df.loc[self.prior_season_pos_players_df["Team"] == team_name,
                                                               "Mascot"].unique()[0]
            self.city_name = self.prior_season_pos_players_df.loc[self.prior_season_pos_players_df["Team"] == team_name,
                                                                  "City"].unique()[0]
        else:
            self.mascot = ''
            self.city_name = ''
        self.prior_season_lineup_df = None  # uses prior season stats
        self.new_season_lineup_df = None  # new / current season stats for printing starting lineup
        self.prior_season_bench_pos_df = None
        self.new_season_bench_pos_df = None
        self.prior_season_pitching_df = None  # uses prior season stats
        self.new_season_pitching_df = None  # new / current season stats for printing starting lineup
        self.starting_pitchers_df = None
        self.starting_pitchers = []
        self.cur_pitcher_index = None
        self.cur_lineup_index_list = []
        self.relievers_df = None  # df of 2 best closers
        self.middle_relievers_df = None  # remaining pitchers sorted by IP descending
        self.unavailable_pitchers_df = None
        self.box_score = None
        self.game_num = game_num
        self.rotation_len = rotation_len

        self.fatigue_start_perc = 70  # 85% of way to avg max is where fatigue starts, adjust factor to inc outing lgth
        self.fatigue_rate = .001  # at 85% of avg max pitchers have a .014 increase in OBP.  using .001 as proxy
        self.fatigue_pitching_change_limit = 5  # change pitcher at # or below out of 100
        self.fatigue_unavailable = 50  # condition must be 51 or higher for a pitcher or pos player to be available

        return

    def batter_index_in_lineup(self, lineup_pos=1):
        # lineup numbers are from 1 to 9
        # print(f'batter_index_in_lineup {lineup_pos}, {self.cur_lineup_index_list}')
        cur_batter_index = self.cur_lineup_index_list[lineup_pos - 1]
        return cur_batter_index

    def is_pitching_index(self):
        return self.cur_pitcher_index

    def set_initial_lineup(self, show_lineup=False, show_bench=False,
                           current_season_stats=True, force_starting_pitcher=None,
                           force_lineup_dict=None):
        self.set_initial_batting_order(force_lineup_dict=force_lineup_dict)
        self.set_initial_starting_rotation(force_starting_pitcher=force_starting_pitcher)
        self.set_closers()
        self.set_mid_relief()
        if show_lineup:
            self.print_starting_lineups(current_season_stats=current_season_stats)
        if show_bench:
            self.print_pos_not_in_lineup(current_season_stats=current_season_stats)
        self.box_score = teamgameboxstats.TeamBoxScore(self.prior_season_lineup_df, self.prior_season_pitching_df,
                                                       self.team_name)
        return

    def set_prior_and_new_pos_player_batting_bench_dfs(self):
        # print(f'gameteam.py set_prior_and_new....  {self.cur_lineup_index_list}')
        self.prior_season_lineup_df = self.prior_season_pos_players_df.loc[self.cur_lineup_index_list]  # subset team df
        self.new_season_lineup_df = self.new_season_pos_players_df.loc[self.cur_lineup_index_list]

        self.prior_season_bench_pos_df = self.prior_season_pos_players_df.loc[
           ~self.prior_season_pos_players_df.index.isin(self.prior_season_lineup_df.index)]
        self.new_season_bench_pos_df = self.new_season_pos_players_df.loc[
            ~self.new_season_pos_players_df.index.isin(self.new_season_lineup_df.index)]
        return

    def set_initial_batting_order(self, force_lineup_dict):
        # force_lineup is a dictionary in batting order with fielding pos
        if force_lineup_dict is None:
            pos_index_dict = self.dynamic_lineup()  # build cur_lineup_index_list
        else:
            self.cur_lineup_index_list = force_lineup_dict.keys()
            pos_index_dict = force_lineup_dict

        # self.prior_season_lineup_df = self.prior_season_pos_players_df.loc[self.cur_lineup_index_list]  # subset df
        self.set_prior_and_new_pos_player_batting_bench_dfs()
        # self.new_season_bench_pos_df = self.prior_season_pos_players_df.
        # loc[~self.prior_season_pos_players_df.index.isin(self.prior_season_lineup_df.index)]
        # self.new_season_lineup_df = self.baseball_data.new_season_batting_data.loc[self.cur_lineup_index_list]

        # lineup and lineup new season dfs contain all player data and in the correct order
        # loop thru lineup from lead off to last, build lineup list and set player fielding pos in lineup df
        # note cur_lineup_index should be the same as lineup_index_list, but just to be certain we rebuild it.
        for row_num in range(0, len(self.prior_season_lineup_df)):
            #     self.cur_lineup_index_list.append(self.prior_season_lineup_df.index[row_num])
            player_index = self.prior_season_lineup_df.index[row_num]  # grab the index of the player
            self.prior_season_lineup_df.Pos[player_index] = pos_index_dict[player_index]  # set fielding pos in lineup
        return

    def dynamic_lineup(self):
        position_list = ['C', '2B', '3B', 'SS', 'OF', 'OF', 'OF', '1B', 'DH']
        pos_index_list = []
        pos_index_dict = {}
        for position in position_list:  # search for best player at each position, returns a df series and appends list
            pos_index = self.search_for_pos(position=position, lineup_index_list=pos_index_list, stat_criteria='OPS')
            pos_index_list.append(pos_index)  # list of indices into the pos player master df
            pos_index_dict[pos_index] = position  # keep track of the player index and position for this game in a dict

            # select player best at each stat to slot into lead off, cleanup, etc.
            # exclude players prev selected for SLG and ordering remaining players by OPS
        sb_index_list = self.best_at_stat(pos_index_list, 'SB', count=1)  # takes list of index nums and scans master df
        slg_index_list = self.best_at_stat(pos_index_list, 'SLG', count=2, exclude=sb_index_list)  # exclude sb
        self.cur_lineup_index_list = self.best_at_stat(pos_index_list, 'OPS', count=6,
                                                       exclude=sb_index_list + slg_index_list)  # setup initial list

        # insert players into lineup. 1st spot is best SB, 4th and 5th are best SLG
        self.insert_player_in_lineup(player_index=sb_index_list[0], target_pos=1)
        self.insert_player_in_lineup(player_index=slg_index_list[0], target_pos=4)
        self.insert_player_in_lineup(player_index=slg_index_list[1], target_pos=5)
        return pos_index_dict

    def set_initial_starting_rotation(self, force_starting_pitcher=None):
        # pitcher rotates based on selection above or forced number passed in
        if self.starting_pitchers_df is None:  # init starting pitcher list
            self.starting_pitchers_df = self.prior_season_pitchers_df.sort_values(['GS', 'IP'], ascending=False).head(5)
            self.starting_pitchers = self.starting_pitchers_df.index.tolist()

        # set game starter stats
        if force_starting_pitcher is None:  # grab the default nth row of df
            self.prior_season_pitching_df = self.starting_pitchers_df.iloc[[self.game_num % self.rotation_len]]
        else:  # user is forcing a rotation change, swap the starter with the new pither
            self.prior_season_pitching_df = self.prior_season_pitchers_df.loc[[force_starting_pitcher]]

        # load the stats for the current starting pitcher
        self.cur_pitcher_index = self.prior_season_pitching_df.index[0] if force_starting_pitcher is None else \
            force_starting_pitcher
        self.new_season_pitching_df = \
            self.baseball_data.new_season_pitching_data.loc[self.cur_pitcher_index].to_frame().T
        return

    def change_starting_rotation(self, starting_pitcher_num, rotation_order_num):
        # insert the new starting pitcher into the lineup spot
        self.starting_pitchers[rotation_order_num - 1] = starting_pitcher_num
        self.starting_pitchers_df = self.prior_season_pitchers_df.loc[self.starting_pitchers]

        # reset the starters stats in case the switch impacted the days starter
        self.prior_season_pitching_df = self.starting_pitchers_df.iloc[[self.game_num % self.rotation_len]]
        self.cur_pitcher_index = self.prior_season_pitching_df.index[0]  # grab the first starter for the season
        self.new_season_pitching_df = \
            self.baseball_data.new_season_pitching_data.loc[self.cur_pitcher_index].to_frame().T

        # make old pitcher available as a reliever
        self.set_closers()
        self.set_mid_relief()
        return

    def print_available_batters(self, current_season_stats=False, include_starters=False):
        if include_starters:
            self.print_starting_lineups(current_season_stats=current_season_stats, show_pitching_starter=False)
        self.print_pos_not_in_lineup(current_season_stats=current_season_stats)
        return

    def print_available_pitchers(self, include_starters=False):
        if include_starters:
            print('Starting Rotation:')
            print(self.starting_pitchers_df.to_string(justify='right'))
            print('')
        print('Middle Relievers:')
        print(self.middle_relievers_df.to_string(justify='right'))
        print('')
        print('Closers:')
        print(self.relievers_df.to_string(justify='right'))
        print('')
        return

    def cur_pitcher_stats(self):
        if isinstance(self.prior_season_pitching_df, pd.Series) is not pd.Series:  # this should never happen
            self.prior_season_pitching_df = self.prior_season_pitching_df.squeeze()
        return self.prior_season_pitching_df  # should be a series with a single row

    def set_pitching_condition(self, cur_ratio):
        # percent of max includes starting condition of player
        try:
            # condition = 100 - percent_of_max if (100 - percent_of_max) >= 0 else 0
            # condition = 0 if cur_percentage < 0 else 0
            self.prior_season_pitching_df.Condition = 0 if 100 - (cur_ratio * 100) < 0 else 100 - (cur_ratio * 100)
        except Exception as e:
            print(f'error in set_pitching_condition gameteam.py {e}')
            print(self.prior_season_pitching_df)
            raise Exception('set pitching condition error')
        return

    def set_batting_condition(self):
        self.box_score.set_box_batting_condition()
        return

    def batter_stats_in_lineup(self, player_index=0):
        batting_series = self.prior_season_lineup_df.loc[player_index]
        return batting_series

    # def cur_batter_stats(self, loc_in_lineup):
    #     # loc is zero to whatever, this is a row count
    #     batting = self.prior_season_lineup_df.iloc[loc_in_lineup]  # data for batter
    #     return batting  # should be a series with a single row

    def pos_player_prior_year_stats(self, index):
        pos_player_stats = self.prior_season_pos_players_df.loc[index]  # data for pos player
        return pos_player_stats  # should be a series with a single row

    def update_fatigue(self, cur_pitching_index):
        # number of batters faced in game vs. historic avg with fatigue start as a ratio
        # bring in game starting condition by mult
        in_game_fatigue = 0
        cur_game_faced = self.box_score.batters_faced(cur_pitching_index)
        # avg_faced = self.cur_pitcher_stats().AVG_faced  # data for pitcher perf prior year
        avg_faced = self.prior_season_pitching_df.AVG_faced  # avg adjusted for starting condition
        cur_ratio = cur_game_faced / avg_faced * 100
        # print(f'gameteam update fatigue {100 - (cur_ratio * 100)}')
        if cur_ratio >= self.fatigue_start_perc:
            in_game_fatigue = (cur_ratio - self.fatigue_start_perc) * self.fatigue_rate
        self.set_pitching_condition(cur_ratio)
        return in_game_fatigue, cur_ratio  # obp impact to pitcher of fatigue

    def pitching_change(self, inning, score_diff):
        # if the score difference is between zero and 3 (pitching team leading) consider a short term reliever
        # check the number of available relievers against the inning, if the current pitcher is tired and
        # have available short-term relievers grab one.
        if 0 <= score_diff <= 3 and \
           (inning <= 9 and len(self.relievers_df) >= (9 - (inning - 1))) or \
                (inning > 9 and len(self.relievers_df) >= 1):
            if inning <= 9:
                self.cur_pitcher_index = self.relievers_df.index[9 - inning]  # 7th would be rel 2 since row start 0
            else:
                self.cur_pitcher_index = self.relievers_df.index[0]  # just take the next pitcher
            self.prior_season_pitching_df = self.relievers_df.loc[self.cur_pitcher_index]  # should be a series
            self.box_score.add_pitcher_to_box(self.relievers_df.loc[self.cur_pitcher_index])
            self.relievers_df = self.relievers_df.drop(self.cur_pitcher_index, axis=0)  # remove from pen
        elif len(self.middle_relievers_df) >= 1:  # grab the next best middle reliever
            self.cur_pitcher_index = self.middle_relievers_df.index[0]  # make sure to drop the same index below
            self.prior_season_pitching_df = self.middle_relievers_df.loc[self.cur_pitcher_index]  # should be a series
            self.box_score.add_pitcher_to_box(self.middle_relievers_df.loc[self.cur_pitcher_index])
            self.middle_relievers_df = self.middle_relievers_df.drop(self.cur_pitcher_index, axis=0)  # remove from pen
        else:  # no change
            pass
        return self.cur_pitcher_index

    def is_pitcher_fatigued(self, condition):
        return condition <= self.fatigue_pitching_change_limit

    def set_closers(self):
        # grab top closers for setup and final close
        not_selected_criteria = ~self.prior_season_pitchers_df.index.isin(self.starting_pitchers_df.index)
        not_exhausted = ~(self.prior_season_pitchers_df['Condition'] <= self.fatigue_unavailable)
        not_injured = (self.prior_season_pitchers_df['Injured Days'] == 0)
        sv_criteria = self.prior_season_pitchers_df.SV > 0
        df_criteria = not_selected_criteria & sv_criteria & not_exhausted & not_injured
        self.relievers_df = self.prior_season_pitchers_df[df_criteria].\
            sort_values(['SV', 'ERA'], ascending=[False, True]).head(2)
        return

    def set_mid_relief(self):
        not_selected_criteria = ~self.prior_season_pitchers_df.index.isin(self.starting_pitchers_df.index)
        not_reliever_criteria = ~self.prior_season_pitchers_df.index.isin(self.relievers_df.index)
        not_exhausted = ~(self.prior_season_pitchers_df['Condition'] <= self.fatigue_unavailable)
        not_injured = (self.prior_season_pitchers_df['Injured Days'] == 0)
        df_criteria = not_selected_criteria & not_reliever_criteria & not_exhausted & not_injured
        self.middle_relievers_df = self.prior_season_pitchers_df[df_criteria].sort_values(['ERA', 'IP'],
                                                                                          ascending=[True, False])
        return

    def search_for_pos(self, position, lineup_index_list, stat_criteria='OPS'):
        # find players not in lineup at specified position, sort by stat descending to find the best
        # if no players at that position make a recursive call to the func and ask for best remaining player
        # if pos is DH open up search to any position.
        try:
            df_player_num = None
            not_exhausted = ~(self.prior_season_pos_players_df['Condition'] <= self.fatigue_unavailable)
            not_injured = (self.prior_season_pos_players_df['Injured Days'] == 0)
            df_criteria_pos = (~self.prior_season_pos_players_df.index.isin(lineup_index_list) &
                              (self.prior_season_pos_players_df['Pos'] == position)) if (
                               position != 'DH' and position != '1B') else \
                ~self.prior_season_pos_players_df.index.isin(lineup_index_list)
            df_criteria = df_criteria_pos & not_exhausted & not_injured
            df_players = self.prior_season_pos_players_df[df_criteria].sort_values(stat_criteria, ascending=False)
            if len(df_players) == 0:  # missing player at pos, pick best available stat, or best condition
                if position != 'DH':
                    df_player_num = self.search_for_pos('DH', lineup_index_list, stat_criteria)  # dont grab same player
                else:
                    df_players = self.prior_season_pos_players_df[df_criteria_pos].sort_values('Condition',
                                                                                               ascending=False)
        except:
            print(f'***Error in gameteam.py search_for_pos with pos {position}')
            print(f'avaiable players {df_players}')
            print(f'prior season df {self.prior_season_pos_players_df}')
            exit(1)
        return df_players.head(1).index[0] if df_player_num is None else df_player_num  # pick top player at pos

    def best_at_stat(self, lineup_index_list, stat_criteria='OPS', count=9, exclude=None):
        # find players in lineup, sort by stat descending to find the best
        exclude = [] if exclude is None else exclude
        df_criteria = self.prior_season_pos_players_df.index.isin(lineup_index_list) &\
            ~self.prior_season_pos_players_df.index.isin(exclude)
        stat_index = self.prior_season_pos_players_df[df_criteria].sort_values(stat_criteria,
                                                                               ascending=False).head(count).index
        return list(stat_index)

    def print_starting_lineups(self, current_season_stats=True, show_pitching_starter=True):
        print(f'Starting lineup for the {self.city_name} ({self.team_name}) {self.mascot}:')
        if current_season_stats:
            dfb = bbstats.remove_non_print_cols(self.new_season_lineup_df)
            dfp = bbstats.remove_non_print_cols(self.new_season_pitching_df)
        else:
            dfb = bbstats.remove_non_print_cols(self.prior_season_lineup_df)
            dfp = bbstats.remove_non_print_cols(self.prior_season_pitching_df)

        dfb = dfb[self.b_lineup_cols_to_print]
        print(dfb.to_string(index=True, justify='right'))
        print('')
        if show_pitching_starter:
            dfp = dfp[self.p_lineup_cols_to_print]
            print(f'Pitching for {self.team_name}:')
            print(dfp.to_string(index=True, justify='right'))
            print('')
        return

    def print_pos_not_in_lineup(self, current_season_stats=True):
        print('bench players:')
        if current_season_stats:
            print(self.new_season_bench_pos_df.to_string(index=True, justify='right'))
        else:
            print(self.prior_season_bench_pos_df.to_string(index=True, justify='right'))
        print('')
        return

    def change_lineup(self, pos_player_bench_index, target_pos, in_game=False):
        print(f'gameteam.py swap player with bench {target_pos}, {self.cur_lineup_index_list}')
        cur_player_index = self.cur_lineup_index_list[target_pos - 1]
        if pos_player_bench_index in self.prior_season_pos_players_df.index:
            self.insert_player_in_lineup(player_index=pos_player_bench_index, target_pos=target_pos)
            self.cur_lineup_index_list.remove(cur_player_index)
            self.set_prior_and_new_pos_player_batting_bench_dfs()
            self.box_score = teamgameboxstats.TeamBoxScore(self.prior_season_lineup_df, self.prior_season_pitching_df,
                                                           self.team_name)  # update box score
        else:
            print(f'Player Index is {pos_player_bench_index} is not on the team.  No substitution made')
        return

    def insert_player_in_lineup(self, player_index, target_pos):
        # target pos is position in line up not pos in life, works if you insert from front to back
        # so dont insert at pos 3 or pos 4 or it will shift pos 4 to pos 5
        self.cur_lineup_index_list.insert(target_pos - 1, player_index)
        return

    def move_player_in_lineup(self, player_index, target_pos):
        # target pos is position in line up not pos in life
        # note this will shift the lineup back at that pos
        self.cur_lineup_index_list.remove(player_index)
        self.cur_lineup_index_list.insert(target_pos - 1, player_index)
        return

    def line_up_dict(self):
        return dict(self.prior_season_lineup_df.iloc[:, 2])  # get pos col w/o name