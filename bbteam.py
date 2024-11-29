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
import pandas as pd
import gameteamboxstats
import bbstats
from numpy import bool_, float64, int32, int64
from pandas.core.series import Series
from typing import Any, Dict, List, Optional, Tuple, Union


class Team:
    def __init__(self, team_name: str, baseball_data: bbstats.BaseballStats, game_num: int = 1,
                 rotation_len: int = 5, interactive: bool=False, debug: bool = False) -> None:
        """
        class handles a single team within a game including all prev year and current year stats, rosters,
        available players, in game fatigue for pitchers, provides stats to in game requests.  sets, maintains, and
        changes the lineup for a team in game
        :param team_name: 3 character abbrev for team
        :param baseball_data: baseball data class
        :param game_num: number of game in season
        :param rotation_len: length of stating rotations, typically 5
        :param interactive: should the program print to screen for interaction with GM and keyboard?
        :param debug: are we debugging?
        :return: None
        """
        pd.options.mode.chained_assignment = None  # suppresses chained assignment warning for lineup pos setting
        self.debug = debug
        self.interactive = interactive
        self.team_name = team_name
        self.baseball_data = baseball_data
        self.prior_season_pitchers_df = baseball_data.get_pitching_data(team_name=team_name, prior_season=True)
        self.prior_season_pos_players_df = baseball_data.get_batting_data(team_name=team_name, prior_season=True)
        self.new_season_pos_players_df = baseball_data.get_batting_data(team_name=team_name, prior_season=False)
        if self.debug:
            print(f'bbteam.py init prior season data')
            print(self.prior_season_pos_players_df.to_string())
            print(self.new_season_pos_players_df.to_string())
        if self.prior_season_pitchers_df.shape[0] == 0:
            print(f'bbteam.py init: team {team_name} does not exist.')
            print(f'Try one of these teams {self.baseball_data.get_all_team_names()}')
            exit(1)

        self.prior_season_pitchers_df['Condition'] = self.baseball_data.new_season_pitching_data['Condition']
        self.prior_season_pitchers_df['AVG_faced'] = self.prior_season_pitchers_df['AVG_faced'] * \
            self.prior_season_pitchers_df['Condition']
        self.prior_season_pos_players_df['Condition'] = self.baseball_data.new_season_batting_data['Condition']
        # test for empty or insufficient number of players generally need 5 starting pitchers and 9 players
        if (len(self.prior_season_pitchers_df) == 0 or len(self.prior_season_pitchers_df) < 5 or
                len(self.prior_season_pos_players_df) == 0 or len(self.prior_season_pos_players_df) < 9):
            print(f'Teams available are {self.baseball_data.pitching_data["Team"].unique()}')

            raise ValueError(f'Pitching did not contain enough pitchers for {team_name} with length'
                             f' {len(self.prior_season_pitchers_df)}')

        self.p_lineup_cols_to_print = ['Player', 'League', 'Team', 'Age', 'G', 'GS', 'CG', 'SHO', 'IP', 'H', '2B', '3B',
                                       'ER', 'SO', 'BB', 'HR', 'W', 'L', 'SV', 'BS', 'HLD', 'ERA', 'WHIP']
        self.b_lineup_cols_to_print = ['Player', 'League', 'Team', 'Pos', 'Age', 'G', 'AB', 'R', 'H', '2B', '3B', 'HR',
                                       'RBI', 'SB', 'CS', 'BB', 'SO', 'SH', 'SF', 'HBP', 'AVG', 'OBP', 'SLG', 'OPS']
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

        # condition and fatigue constants are in bbstats, baseball data object
        self.fatigue_start_perc = self.baseball_data.fatigue_start_perc
        self.fatigue_rate = self.baseball_data.fatigue_rate
        self.fatigue_pitching_change_limit = self.baseball_data.fatigue_pitching_change_limit
        self.fatigue_unavailable = self.baseball_data.fatigue_unavailable
        self.lineup_card = ''
        return

    def batter_index_in_lineup(self, lineup_pos: int = 1) -> int:
        """
        returns the batters hashcode key for a pos in the lineup.
        :param lineup_pos: order in lineup numbers are from 1 to 9
        :return: hashcode of the current batter in the lineup
        """
        if self.debug:
            print(f'batter_index_in_lineup {lineup_pos}, {self.cur_lineup_index_list}')
        cur_batter_hash_code = self.cur_lineup_index_list[lineup_pos - 1]
        return cur_batter_hash_code

    def is_pitching_index(self) -> int64:
        """
        returns hashcode of the current pitcher
        :return:
        """
        return self.cur_pitcher_index

    def set_initial_lineup(self, show_lineup: bool = False, show_bench: bool = False,
                           current_season_stats: bool = True, force_starting_pitcher: None = None,
                           force_lineup_dict: None = None) -> str:
        """
        sets the initial lineup pre-game for pitchers and hitters
        :param show_lineup: print the lineup upon completion?
        :param show_bench:  print the bench post lineup construction?
        :param current_season_stats: use current seasons stats for printing when no games are played in new season
        :param force_starting_pitcher: optional int hashcode to force the starting pitcher
        :param force_lineup_dict: optional dictionary of players to use for lineup for example
            {647549: 'LF', 239398: 'C', 224423: '1B', 138309: 'DH', 868055: 'CF', 520723: 'SS',
                  299454: '3B', 46074: '2B', 752787: 'RF'}
        :return: printed lineup card if any
        """
        self.set_initial_batting_order(force_lineup_dict=force_lineup_dict)
        self.set_initial_starting_rotation(force_starting_pitcher=force_starting_pitcher)
        self.set_closers()
        self.set_mid_relief()
        if show_lineup:
            self.print_starting_lineups(current_season_stats=current_season_stats)
        if show_bench:
            self.print_pos_not_in_lineup(current_season_stats=current_season_stats)
            self.print_available_pitchers(include_starters=False, current_season_stats=current_season_stats)
        self.box_score = gameteamboxstats.TeamBoxScore(self.prior_season_lineup_df, self.prior_season_pitching_df,
                                                       self.team_name)
        return self.lineup_card

    def set_prior_and_new_pos_player_batting_bench_dfs(self) -> None:
        """
        set the dfs used for prior season team data as well as new season team data.
        :return: None
        """
        if self.debug:
            print(f'bbteam.py set_prior_and_new....  {self.cur_lineup_index_list}')
            print(self.prior_season_pos_players_df.head(5).to_string())
            print(self.new_season_pos_players_df.head(5).to_string())
        self.prior_season_lineup_df = self.prior_season_pos_players_df.loc[self.cur_lineup_index_list]  # subset team df
        self.new_season_lineup_df = self.new_season_pos_players_df.loc[self.cur_lineup_index_list]

        self.prior_season_bench_pos_df = self.prior_season_pos_players_df.loc[
           ~self.prior_season_pos_players_df.index.isin(self.prior_season_lineup_df.index)]
        self.new_season_bench_pos_df = self.new_season_pos_players_df.loc[
            ~self.new_season_pos_players_df.index.isin(self.new_season_lineup_df.index)]
        return

    def set_initial_batting_order(self, force_lineup_dict: Optional[dict] = None) -> None:
        """
        sets the initial batting order and lineup for pos players
        :param force_lineup_dict: optional dictionary of player pos and hashcode.  like this...
        {647549: 'LF', 239398: 'C', 224423: '1B', 138309: 'DH', 868055: 'CF', 520723: 'SS',
                  299454: '3B', 46074: '2B', 752787: 'RF'}
        :return: None
        """
        # force_lineup is a dictionary in batting order with fielding pos
        if force_lineup_dict is None:
            pos_index_dict = self.dynamic_lineup()  # build cur_lineup_index_list
        else:
            self.cur_lineup_index_list = list(force_lineup_dict.keys())
            pos_index_dict = force_lineup_dict

        self.set_prior_and_new_pos_player_batting_bench_dfs()
        # lineup and lineup new season dfs contain all player data and in the correct order
        # loop over lineup from lead off to last, build lineup list and set player fielding pos in lineup df
        # note cur_lineup_index should be the same as lineup_index_list, but just to be certain we rebuild it.
        for row_num in range(0, len(self.prior_season_lineup_df)):
            player_index = int64(self.prior_season_lineup_df.index[row_num])  # grab the index of the player
            self.prior_season_lineup_df.loc[player_index, 'Pos'] = pos_index_dict[player_index]  # field pos in lineup
            self.new_season_lineup_df.loc[player_index, 'Pos'] = pos_index_dict[player_index]
        return

    def dynamic_lineup(self) -> Dict[int64, str]:
        """
        if no batting order is provided create one
        :return: dictionary containing lineup with pos and hashcode for player
        """
        position_list = ['C', '2B', '3B', 'SS', 'LF', 'CF', 'RF', '1B', 'DH']
        pos_index_list = []
        pos_index_dict = {}
        for position in position_list:  # search for best player at each position, returns a df series and appends list
            pos_index = self.search_for_pos(position=position, lineup_index_list=pos_index_list, stat_criteria='OPS')
            pos_index_list.append(pos_index)  # list of indices into the pos player master df
            pos_index_dict[pos_index] = position  # keep track of the player index and position for this game in a dict

        # select player best at each stat to slot into lead off, cleanup, etc.
        # exclude players prev selected for SLG and ordering remaining players by OPS
        sb_index_list = self.best_at_stat(pos_index_list, 'SB', count=1)  # list of index#,scans master df
        slg_index_list = self.best_at_stat(pos_index_list, 'SLG', count=2, exclude=sb_index_list)  # excl sb
        self.cur_lineup_index_list = self.best_at_stat(pos_index_list, 'OPS', count=6,
                                                       exclude=sb_index_list + slg_index_list)  # setup initial list

        # insert players into lineup. 1st spot is the best SB, 4th and 5th are best SLG
        self.insert_player_in_lineup(player_hashcode=sb_index_list[0], target_batting_order_pos=1)
        self.insert_player_in_lineup(player_hashcode=slg_index_list[0], target_batting_order_pos=4)
        self.insert_player_in_lineup(player_hashcode=slg_index_list[1], target_batting_order_pos=5)
        return pos_index_dict

    def set_initial_starting_rotation(self, force_starting_pitcher: None = None) -> None:
        """
        set the initial starting rotation or use the pitcher provided
        :param force_starting_pitcher: optional hashcode of pitcher to pitch this game
        :return: None
        """
        # pitcher rotates based on selection above or forced number passed in
        try:
            if self.starting_pitchers_df is None:  # init starting pitcher list
                self.starting_pitchers_df = (
                    self.prior_season_pitchers_df.sort_values(['GS', 'IP'], ascending=False).head(5))
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
        except IndexError:
            print('****bbteam.py set_initial_starting_rotation error')
            print(self.starting_pitchers)
            print(self.prior_season_pitchers_df)
        return

    def change_starting_rotation(self, starting_pitcher_num: int, rotation_order_num: int) -> None:
        """
        change the default starting pitching rotation
        :param starting_pitcher_num: hashcode of new pitcher to insert into rotation
        :param rotation_order_num: pos in rotation usually 1 to 5
        :return: None
        """
        # insert the new starting pitcher into the lineup spot
        self.starting_pitchers[rotation_order_num - 1] = starting_pitcher_num
        self.starting_pitchers_df = self.prior_season_pitchers_df.loc[self.starting_pitchers]

        # reset the starters stats in case the switch impacted the days starter
        self.prior_season_pitching_df = self.starting_pitchers_df.iloc[[self.game_num % self.rotation_len]]
        self.cur_pitcher_index = self.prior_season_pitching_df.index[0]  # grab the first starter for the season
        self.new_season_pitching_df = \
            self.baseball_data.new_season_pitching_data.loc[self.cur_pitcher_index].to_frame().T

        # reset relievers available
        self.set_closers()
        self.set_mid_relief()
        return

    def print_available_batters(self, include_starters: bool = False, current_season_stats: bool = False) -> None:
        """
        prints the available position players on the bench
        :param current_season_stats: use the prior (current) or new seasons stats for printing
        :param include_starters: include the starters not just the bench players
        :return: None
        """
        if include_starters:
            self.print_starting_lineups(current_season_stats=current_season_stats, show_pitching_starter=False)
        self.print_pos_not_in_lineup(current_season_stats=current_season_stats)
        return

    def print_available_pitchers(self, include_starters: bool = False, current_season_stats: bool=False) -> None:
        """
        prints the available pitchers in the bullpen
        :param include_starters: include the starters not just the bench players
        :param current_season_stats: use current season stats, not the new season
        :return: None
        """
        if include_starters:
            self.lineup_card += f'Starting Rotation:\n {self.starting_pitchers_df.to_string(justify="right")} \n'
        self.lineup_card += f'Middle Relievers:\n {self.middle_relievers_df.to_string(justify="right")} \n'
        self.lineup_card += f'Closers:\n{self.relievers_df.to_string(justify="right")} \n'
        if self.interactive:
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

    def cur_pitcher_stats(self) -> Series:
        """
        :return: returns a pandas series containing the current pitchers stats
        """
        if isinstance(self.prior_season_pitching_df, pd.Series) is not pd.Series:  # this should never happen
            self.prior_season_pitching_df = self.prior_season_pitching_df.squeeze()
        return self.prior_season_pitching_df  # should be a series with a single row

    def set_pitching_condition(self, cur_ratio: float64) -> None:
        """
        set the condition of the pitcher in the team df, used for fatigue management in game
        :param cur_ratio: is the value of cur_game_faced / avg_faced * 100
        :return: None
        """
        # percent of max includes starting condition of player
        try:
            # condition = 100 - percent_of_max if (100 - percent_of_max) >= 0 else 0
            # condition = 0 if cur_percentage < 0 else 0
            self.prior_season_pitching_df.Condition = 0 if 100 - (cur_ratio * 100) < 0 else 100 - (cur_ratio * 100)
        except Exception as e:
            print(f'error in set_pitching_condition bbteam.py {e}')
            print(self.prior_season_pitching_df)
            raise Exception('set pitching condition error')
        return

    def set_batting_condition(self) -> None:
        """
        set the condition of the batter in the box score for transfer to season stats, happens post game
        :return: None
        """
        self.box_score.set_box_batting_condition()
        return

    def batter_stats_in_lineup(self, lineup_order_num: int = 0) -> Series:
        """
        return a pandas series containing the stats for the batter with the position in the lineup provided
        :param lineup_order_num:  lineup pos to request stats for 0 to 8 for positions 1 to 9
        :return: pandas series with data
        """
        batting_series = self.prior_season_lineup_df.loc[lineup_order_num]
        return batting_series

    def pos_player_prior_year_stats(self, index: int32) -> Series:
        """
        prior year stats for batter given the hashcode key for the player
        :param index: hashcode index for the player in the df
        :return: pandas series with player data
        """
        pos_player_stats = self.prior_season_pos_players_df.loc[index]  # data for pos player
        return pos_player_stats  # should be a series with a single row

    def update_fatigue(self, cur_pitching_index: int64) -> Tuple[int, float64]:
        """
        calcs the ratio of batters the pitcher has faced in game against historic avg
        so if a pitcher faces 10 batters per game, and they have faced 8 the pitcher is 80% of the way to their
        max outing.
        :param cur_pitching_index: hashcode of current pitcher
        :return: returns the impact to obp for pitcher fatigue, if tired they give up more hits
                also returns the new cur_ratio
        """
        in_game_fatigue = 0
        cur_game_faced = self.box_score.batters_faced(cur_pitching_index)
        avg_faced = self.prior_season_pitching_df.AVG_faced  # avg adjusted for starting condition
        cur_ratio = cur_game_faced / avg_faced * 100
        if self.debug:
            print(f'gameteam update fatigue {100 - (cur_ratio * 100)}')
        if cur_ratio >= self.fatigue_start_perc:
            in_game_fatigue = (cur_ratio - self.fatigue_start_perc) * self.fatigue_rate
        self.set_pitching_condition(cur_ratio)
        return in_game_fatigue, cur_ratio  # obp impact to pitcher of fatigue

    def pitching_change(self, inning: int, score_diff: int) -> int64:
        """
        should we make a pitching change?  if so make one
        if the score difference is between zero and 3 (pitching team leading) consider a short term reliever
        check the number of available relievers against the inning, if the current pitcher is tired and
        have available short-term relievers grab one.
        :param inning: what inning is it?
        :param score_diff: what is the score difference? positive number means the team pitching is winning
        :return: hashcode for new pitcher or hashcode for current pitcher
        """
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

    def is_pitcher_fatigued(self, condition: Union[int, int64, float64]) -> Union[bool, bool_]:
        """
        :param condition: current condition of the pitcher expressed from 0 to 100.
        :return: boolean true if the pitcher is below the set limit.  limits is set in bbstats.py
        """
        return condition <= self.fatigue_pitching_change_limit

    def set_closers(self) -> None:
        """
        set relievers_df with top closers for setup and final close
        :return: None
        """
        not_selected_criteria = ~self.prior_season_pitchers_df.index.isin(self.starting_pitchers_df.index)
        not_exhausted = ~(self.prior_season_pitchers_df['Condition'] <= self.fatigue_unavailable)
        not_injured = (self.prior_season_pitchers_df['Injured Days'] == 0)
        sv_criteria = self.prior_season_pitchers_df.SV > 0
        df_criteria = not_selected_criteria & sv_criteria & not_exhausted & not_injured
        self.relievers_df = self.prior_season_pitchers_df[df_criteria].\
            sort_values(['SV', 'ERA'], ascending=[False, True]).head(2)
        return

    def set_mid_relief(self) -> None:
        """
        if you're not a start or a closer you must be a .... df_middle_relievers_df
        :return: None
        """
        not_selected_criteria = ~self.prior_season_pitchers_df.index.isin(self.starting_pitchers_df.index)
        not_reliever_criteria = ~self.prior_season_pitchers_df.index.isin(self.relievers_df.index)
        not_exhausted = ~(self.prior_season_pitchers_df['Condition'] <= self.fatigue_unavailable)
        not_injured = (self.prior_season_pitchers_df['Injured Days'] == 0)
        df_criteria = not_selected_criteria & not_reliever_criteria & not_exhausted & not_injured
        self.middle_relievers_df = self.prior_season_pitchers_df[df_criteria].sort_values(['ERA', 'IP'],
                                                                                          ascending=[True, False])
        return

    def search_for_pos(self, position: str, lineup_index_list: List[Union[Any, int64]],
                       stat_criteria: str = 'OPS', debug: bool = False) -> int64:
        """
        find players not in lineup at specified position, sort by stat descending to find the best
        if no players at that position make a recursive call to the func and ask for best remaining player
        if pos is DH open up search to any position.
        :param position: position to search for C, 1B, 2B, SS, 3B, OF, DH
        :param lineup_index_list: place in the lineup, clean up hitters should have high SLG
        :param stat_criteria: criteria to select player with, could be AVG, OBP, OBS, SB, etc.
        :param debug: are we debugging?
        :return: hashcode with player number select at the request position
        """
        df_players, df_criteria = None, None
        if debug:
            print(f'bbteam.py search_for_pos with pos {position}')
            print(f'prior season df {self.prior_season_pos_players_df}')
        try:
            df_player_num = None
            not_exhausted = ~(self.prior_season_pos_players_df['Condition'] <= self.fatigue_unavailable)
            not_injured = (self.prior_season_pos_players_df['Injured Days'] == 0)
            df_criteria_pos = (~self.prior_season_pos_players_df.index.isin(lineup_index_list) &
                               # (self.prior_season_pos_players_df['Pos'] == position)) if (
                               (self.prior_season_pos_players_df['Pos'].apply(lambda df_positions: position in df_positions))) if (
                               position != 'DH' and position != '1B') else \
                ~self.prior_season_pos_players_df.index.isin(lineup_index_list)
            df_criteria = df_criteria_pos & not_exhausted & not_injured
            df_players = self.prior_season_pos_players_df[df_criteria].sort_values(stat_criteria, ascending=False)
            if len(df_players) == 0:  # missing player at pos, pick the best available stat, or best condition
                if position != 'DH':  # if we are not looking for a DH use the DH criteria to just grab one
                    df_player_num = self.search_for_pos('DH', lineup_index_list, stat_criteria)
                else:  # try if the DH criteria fails try grabbing tired players
                    df_players = self.prior_season_pos_players_df[df_criteria_pos].sort_values('Condition',
                                                                                               ascending=False)
            if debug:
                print(f'top player at pos {df_players.head(1).index[0] if df_player_num is None else df_player_num}')
        except IndexError:
            print(f'***Error in bbteam.py search_for_pos with pos {position}')
            print(f'with criteria {df_criteria}')
            print(f'available players {df_players}')
            print(f'prior season df {self.prior_season_pos_players_df}')
            exit(1)
        return df_players.head(1).index[0] if df_player_num is None else df_player_num  # pick top player at pos

    def best_at_stat(self, lineup_index_list: List[int64], stat_criteria: str = 'OPS',
                     count: int = 9, exclude: Optional[List[int]] = None) -> List[int]:
        """
        find the best available player using a given stat as the selection criteria
        :param lineup_index_list: current lineup, we need to exclude these players since they are already in the lineup
        :param stat_criteria: criteria to sort by
        :param count: how many players to add to list?  default is 9
        :param exclude: optional list of players (hashcode) to exclude, useful for DL players
        :return: list of players that are best at the given stat in descending order
        """
        exclude = [] if exclude is None else exclude
        df_criteria = self.prior_season_pos_players_df.index.isin(lineup_index_list) &\
            ~self.prior_season_pos_players_df.index.isin(exclude)
        stat_index = self.prior_season_pos_players_df[df_criteria].sort_values(stat_criteria,
                                                                               ascending=False).head(count).index
        return list(stat_index)

    def print_starting_lineups(self, current_season_stats: bool = True, show_pitching_starter: bool = True) -> None:
        """
        print the teams starting lineup
        :param current_season_stats: use the current seasons stats
        :param show_pitching_starter: true prints the starting pitcher
        :return: None
        """
        if self.debug:
            print('bbteam.py in print_starting_lineups')
            print(self.prior_season_lineup_df.head(5).to_string())
            print(self.new_season_lineup_df.head(5).to_string())
        self.lineup_card += f'Starting lineup for the {self.city_name} ({self.team_name}) {self.mascot}:\n'
        if current_season_stats:
            dfb = bbstats.remove_non_print_cols(self.new_season_lineup_df)
            dfp = bbstats.remove_non_print_cols(self.new_season_pitching_df)
        else:
            dfb = bbstats.remove_non_print_cols(self.prior_season_lineup_df)
            dfp = bbstats.remove_non_print_cols(self.prior_season_pitching_df)

        dfb = dfb[self.b_lineup_cols_to_print]
        self.lineup_card += dfb.to_string(index=True, justify='right') + '\n'

        if show_pitching_starter:
            dfp = dfp[self.p_lineup_cols_to_print]
            self.lineup_card += f'Pitching for {self.team_name}:\n'
            self.lineup_card += (dfp.to_string(index=True, justify='right')) + '\n'

        if self.interactive:
            print(f'Starting lineup for the {self.city_name} ({self.team_name}) {self.mascot}:')
            print(dfb.to_string(index=True, justify='right'))
            print('')
            if show_pitching_starter:
                print(f'Pitching for {self.team_name}:')
                print(dfp.to_string(index=True, justify='right'))
                print('')
        return

    def print_pos_not_in_lineup(self, current_season_stats: bool = True) -> None:
        """
        prints the players not in the lineup, bench warmers
        :param current_season_stats: use the prior seasons stats, not the current season
        :return: None
        """
        self.lineup_card += 'bench players:\n'
        if current_season_stats:
            self.lineup_card += (self.new_season_bench_pos_df.to_string(index=True, justify='right'))
            if self.interactive:
                print('bench players:')
                print(self.new_season_bench_pos_df.to_string(index=True, justify='right'))
        else:
            self.lineup_card += (self.prior_season_bench_pos_df.to_string(index=True, justify='right'))
            if self.interactive:
                print('bench players:')
                print(self.prior_season_bench_pos_df.to_string(index=True, justify='right'))
        self.lineup_card += '\n'
        return

    def change_lineup(self, pos_player_bench_hashcode: int, target_batting_order_pos: int) -> None:
        """
        sub a bench player into the lineup, remove player from bench, add to box score
        :param pos_player_bench_hashcode: the hashcode of the player that is subbing into the lineup
        :param target_batting_order_pos: batting order number to sub, 1 would be the first pos in the lineup
        :return: None
        """
        print(f'bbteam.py swap player with bench {target_batting_order_pos}, {self.cur_lineup_index_list}')
        cur_player_index = self.cur_lineup_index_list[target_batting_order_pos - 1]
        if pos_player_bench_hashcode in self.prior_season_pos_players_df.index:
            self.insert_player_in_lineup(player_hashcode=pos_player_bench_hashcode,
                                         target_batting_order_pos=target_batting_order_pos)  # insert new player
            self.cur_lineup_index_list.remove(cur_player_index)  # remove old player
            self.set_prior_and_new_pos_player_batting_bench_dfs()
            self.box_score = gameteamboxstats.TeamBoxScore(self.prior_season_lineup_df, self.prior_season_pitching_df,
                                                           self.team_name)  # update box score
        else:
            print(f'Player Index is {pos_player_bench_hashcode} is not on the team.  No substitution made')
        return

    def insert_player_in_lineup(self, player_hashcode: int, target_batting_order_pos: int) -> None:
        """
        insert a player into a spot in the lineup, in front of the old player
        :param player_hashcode: hashcode of player to insert
        :param target_batting_order_pos: batting order pos to insert into
        :return: None
        """
        self.cur_lineup_index_list.insert(target_batting_order_pos - 1, player_hashcode)
        return

    def move_player_in_lineup(self, player_hashcode, new_target_batter_order_num) -> None:
        """
        :param player_hashcode: hashcode of player to move
        :param new_target_batter_order_num: new spot in the lineup, 9 would be the last spot
        :return: None
        """
        self.cur_lineup_index_list.remove(player_hashcode)  # remove the player and collapse the list
        self.cur_lineup_index_list.insert(new_target_batter_order_num - 1, player_hashcode)  # insert at the target spot
        return

    def line_up_dict(self) -> dict:
        """
        :return: the dictionary of pos and hashcode in lineup order
        """
        return dict(self.prior_season_lineup_df.iloc[:, 2])  # get pos col w/o name
