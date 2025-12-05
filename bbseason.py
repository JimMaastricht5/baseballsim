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
# notes on multi-threading
# 1.uv python install 3.14t
# 2. uv python list
# 3. uv python pin 3.14t
# 4. uv sync
# 5. uv run -- python -X gil=0 bbseason.py
# JimMaastricht5@gmail.com
import datetime
import queue
import random
import pandas as pd
import bbgame
import bbstats
import bbgm_manager
import numpy as np
from typing import List, Optional
import threading
from bblogger import logger

AWAY = 0
HOME = 1


class BaseballSeason:
    def __init__(self, load_seasons: List[int], new_season: int, team_list: Optional[list] = None,
                 season_length: int = 6, series_length: int = 3,
                 rotation_len: int = 5, include_leagues: list = None, season_interactive: bool = False,
                 season_print_lineup_b: bool = False, season_print_box_score_b: bool = False,
                 season_chatty: bool = False, season_team_to_follow: str = None,
                 load_batter_file: str = 'aggr-stats-pp-Batting.csv',
                 load_pitcher_file: str = 'aggr-stats-pp-Pitching.csv',
                 schedule: list = None) -> None:
        """
        :param load_seasons: list of seasons to load for stats, can blend multiple seasons
        :param new_season: int value representing the year of the new season can be the same as one of the loads
        :param team_list: list of teams to use in the simulations, optional param
        :param season_length: number of games to be played for the season
        :param series_length: series is usually 3, the default is one for testing
        :param rotation_len: number of starters to rotate, default is 5
        :param include_leagues: list of leagues to include in the season
        :param season_interactive: if true the sim pauses after each day
        :param season_print_lineup_b: if true print lineups
        :param season_print_box_score_b: if true print box scores
        :param season_chatty: if true provide more detail
        :param season_team_to_follow: if none skip otherwise follow this team in gory detail
        :param load_batter_file: name of the file with batter data, year will be added to the front of the text
        :param load_pitcher_file: name of the file for the pitcher data, year will be added to the front of the text
        :return: None
        """
        self.season_day_num = 0  # set to first day of the season
        self.season_length = season_length
        self.series_length = series_length
        self.rotation_len = rotation_len
        self.team_season_df = None
        self.team_season_pitching_df = None
        self.load_seasons = load_seasons  # pull base data across for what seasons
        self.new_season = new_season
        self.leagues_str = ' '.join(include_leagues) if include_leagues is not None else 'MLB'
        self.interactive = season_interactive
        self.print_lineup_b = season_print_lineup_b
        self.print_box_score_b = season_print_box_score_b
        self.season_chatty = season_chatty
        self.team_to_follow = season_team_to_follow
        logger.debug("Initializing BaseballSeason with seasons: {}, new season: {}", load_seasons, new_season)
        self.baseball_data = bbstats.BaseballStats(load_seasons=self.load_seasons, new_season=new_season,
                                                   include_leagues=include_leagues, load_batter_file=load_batter_file,
                                                   load_pitcher_file=load_pitcher_file)
        self.teams = list(self.baseball_data.batting_data.Team.unique()) if team_list == [] or team_list is None \
            else team_list
        if len(self.teams) % 2 == 1:  # odd number of teams
            self.teams.append('OFF DAY')

        self.schedule = [] if schedule is None else schedule
        if schedule is None:
            self.create_schedule()  # set schedule if not passed
        self.team_win_loss = {}
        self.team_games_played = {}  # Track games played per team
        for team in self.teams:
            self.team_win_loss.update({team: [0, 0]})  # set team win loss to 0, 0
            self.team_games_played[team] = 0  # Initialize games played
        self.team_city_dict = self.baseball_data.get_all_team_city_names()

        # Initialize AI General Managers for each team
        self.gm_managers = {}
        self.gm_assessment_intervals = [30, 60, 90, 120, 150]  # Assess at these game milestones
        for team in self.teams:
            if team != 'OFF DAY':
                self.gm_managers[team] = bbgm_manager.AIGeneralManager(
                    team_name=team,
                    assessment_frequency=30  # Will assess every 30 games
                )
        logger.info(f"Initialized {len(self.gm_managers)} AI General Managers")

        return

    def get_team_names(self) -> list:
        return self.teams

    def create_schedule(self) -> None:
        """
        set the schedule for the seasons using the teams, series length, min games in season, and limit of games
        conflicts sometimes occur between the params, so it is possible for a team to play an extra game
        day schedule in format  ([['MIL', 'COL'], ['PIT', 'CIN'], ['CHC', 'STL']])  # test schedule
        if there are an odd number of teams there may be an "OFF" day in the schedule
        :return: None
        """
        for game_day in range(0, len(self.teams)-1):  # setup each team play all other teams one time
            random.shuffle(self.teams)  # randomize team match ups. may repeat, deal with it
            day_schedule = []
            for ii in range(0, len(self.teams), 2):  # select home and away without repeating a team, inc by 2 away/home
                day_schedule.append([self.teams[ii], self.teams[ii+1]])  # build schedule for one day

            for series_game in range(0, self.series_length):  # repeat day schedule to build series
                self.schedule.append(day_schedule)  # add day schedule to full schedule
        # schedule is built, check against minimums and repeat if needed, recursive call to build out further
        if len(self.schedule) < self.season_length:
            self.create_schedule()  # recursive call to add more games to get over minimum
        elif len(self.schedule) > self.season_length:
            self.schedule = self.schedule[0:self.season_length]
        return

    def print_day_schedule(self, day: int) -> str:
        """
        prints the schedule for the day in compact 2-column format
        :param day: integer of the day in season, e.g., 161
        :return: str with printed schedule text
        """
        schedule_str = ''
        game_day_off = ''
        day_schedule = self.schedule[day]
        games = []

        # Collect games and off days
        for game in day_schedule:
            if 'OFF DAY' not in game:
                games.append(f'{game[0]:>3} @ {game[1]:<3}')
            else:
                game_day_off = game[0] if game[0] != 'OFF DAY' else game[1]

        # Print header
        schedule_str += f'Day {day + 1} Games:\n'

        # Print games in 2 columns
        if games:
            mid_point = (len(games) + 1) // 2
            for i in range(mid_point):
                left_game = games[i]
                if i + mid_point < len(games):
                    right_game = games[i + mid_point]
                    schedule_str += f'{left_game}   {right_game}\n'
                else:
                    schedule_str += f'{left_game}\n'

        # Print off day at the end
        if game_day_off != '':
            schedule_str += f'({game_day_off} - Off Day)\n'

        schedule_str += '\n'
        return schedule_str

    def print_standings(self) -> None:
        """
        print the current standings with GB and Win% in compact 2-column format
        :return: None
        """
        teaml, winl, lossl = [], [], []
        for team in self.team_win_loss:
            if team != 'OFF DAY':
                win_loss = self.team_win_loss[team]
                teaml.append(team)  # Use abbreviation only for compact display
                winl.append(win_loss[0])
                lossl.append(win_loss[1])

        # Create DataFrame and calculate stats
        df = pd.DataFrame({'Team': teaml, 'W': winl, 'L': lossl})
        df['Pct'] = df['W'] / (df['W'] + df['L'])
        df = df.sort_values('W', ascending=False).reset_index(drop=True)

        # Calculate Games Back from leader
        max_wins = df['W'].iloc[0]
        leader_losses = df['L'].iloc[0]
        df['GB'] = ((max_wins - df['W']) + (df['L'] - leader_losses)) / 2.0
        df['GB'] = df['GB'].apply(lambda x: '-' if x == 0 else f'{x:.1f}')

        # Format for display
        df['W-L'] = df['W'].astype(str) + '-' + df['L'].astype(str)
        df['Pct'] = df['Pct'].apply(lambda x: f'{x:.3f}')
        display_df = df[['Team', 'W-L', 'Pct', 'GB']]

        # Split into 2 columns for compact display
        n_teams = len(display_df)
        mid_point = (n_teams + 1) // 2

        left_half = display_df.iloc[:mid_point].reset_index(drop=True)
        right_half = display_df.iloc[mid_point:].reset_index(drop=True)

        # Print header
        print(f"{'Team':<5} {'W-L':<8} {'Pct':<6} {'GB':<5}   {'Team':<5} {'W-L':<8} {'Pct':<6} {'GB':<5}")
        print('-' * 60)

        # Print rows side by side
        for i in range(mid_point):
            left_row = left_half.iloc[i]
            left_line = f"{left_row['Team']:<5} {left_row['W-L']:<8} {left_row['Pct']:<6} {left_row['GB']:<5}"

            if i < len(right_half):
                right_row = right_half.iloc[i]
                right_line = f"{right_row['Team']:<5} {right_row['W-L']:<8} {right_row['Pct']:<6} {right_row['GB']:<5}"
                print(f"{left_line}   {right_line}")
            else:
                print(left_line)

        print('')
        return

    def update_win_loss(self, away_team_name: str, home_team_name: str, win_loss: List[List[int]]) -> None:
        """
        :param away_team_name: name of away team for the game
        :param home_team_name: name of home team for the game
        :param win_loss: list of lists with team name and integer win and loss ['MAD', [1, 0]] is a w for Mad
        :return: None
        """
        self.team_win_loss[away_team_name] = list(
            np.add(np.array(self.team_win_loss[away_team_name]), np.array(win_loss[0])))
        self.team_win_loss[home_team_name] = list(
            np.add(np.array(self.team_win_loss[home_team_name]), np.array(win_loss[1])))

        # Increment games played for both teams
        self.team_games_played[away_team_name] += 1
        self.team_games_played[home_team_name] += 1
        return

    def calculate_games_back(self, team_name: str) -> float:
        """
        Calculate how many games back a team is from the division/league leader.

        Args:
            team_name: Team to calculate games back for

        Returns:
            Games back (negative if team is leading, 0.0 if tied for lead)
        """
        if team_name == 'OFF DAY':
            return 0.0

        # Get team's record
        team_record = self.team_win_loss[team_name]
        team_wins = team_record[0]
        team_losses = team_record[1]

        # Find leader (most wins)
        max_wins = 0
        leader_losses = 0

        for other_team, record in self.team_win_loss.items():
            if other_team != 'OFF DAY':
                other_wins = record[0]
                other_losses = record[1]

                # Update leader if this team has more wins
                # If tied in wins, use fewer losses as tiebreaker
                if other_wins > max_wins or (other_wins == max_wins and other_losses < leader_losses):
                    max_wins = other_wins
                    leader_losses = other_losses

        # Games back formula: ((Leader W - Team W) + (Team L - Leader L)) / 2
        games_back = ((max_wins - team_wins) + (team_losses - leader_losses)) / 2.0

        return games_back

    def _get_teams_to_print(self) -> Optional[List[str]]:
        """
        Get list of teams to print AI GM output for.
        Returns None to print all teams, or a list of team names to print.
        """
        if self.team_to_follow is None or self.team_to_follow == '':
            return None  # Print all teams
        elif isinstance(self.team_to_follow, list):
            return self.team_to_follow  # Already a list
        else:
            return [self.team_to_follow]  # Convert string to list

    def check_gm_assessments(self) -> None:
        """
        Check if any teams have reached GM assessment milestones (30, 60, 90, 120, 150 games).
        Run assessments for teams that are due.
        """
        # Skip GM assessments after game 150 milestone (last assessment)
        # This avoids expensive calculations late in the season
        # Check max games played by any team to handle uneven schedules
        if self.team_games_played:
            max_games = max(self.team_games_played.values())
            if max_games > 150:  # Last milestone is 150 games
                return

        # Calculate current Sim WAR values before assessments
        # NOTE: calculate_sim_war() requires semaphore protection
        with self.baseball_data.semaphore:
            self.baseball_data.calculate_sim_war()

        # Determine which teams to print
        teams_to_print = self._get_teams_to_print()

        for team_name, gm in self.gm_managers.items():
            games_played = self.team_games_played[team_name]

            # Check if assessment is due
            if gm.should_assess(games_played):
                # Get team record
                record = self.team_win_loss[team_name]
                wins, losses = record[0], record[1]

                # Calculate games back
                games_back = self.calculate_games_back(team_name)

                # Determine if this team should print
                should_print = teams_to_print is None or team_name in teams_to_print

                # Run GM assessment
                logger.info(f"Running GM assessment for {team_name} after {games_played} games")
                assessment = gm.assess_roster(
                    baseball_stats=self.baseball_data,
                    team_record=(wins, losses),
                    games_back=games_back,
                    games_played=games_played,
                    should_print=should_print
                )

                # Could store assessment for later analysis
                # self.gm_assessments[team_name].append(assessment)

        return

    def sim_start(self) -> None:
        """
        Print start of season info
        :return: None
        """
        teams_paragraph = ''
        print(f'{self.new_season} will have {len(self.schedule)} games per team with {len(self.teams)} teams.')
        for team in self.team_city_dict.keys():
            teams_paragraph = teams_paragraph + ', ' if len(teams_paragraph) > 0 else ''
            teams_paragraph = teams_paragraph + f'{self.team_city_dict[team]} ({team})'
        print(f'{teams_paragraph} \n')
        if self.season_chatty:
            print(f'Full schedule of games: {self.schedule}')
        return

    def sim_end(self) -> None:
        """
        print end of season info and update end of season stats
        :return: None
        """
        print('\nCalculating final season statistics...')
        self.baseball_data.update_season_stats()
        print(f'\n\n****** End of {self.new_season} season ******')
        print(f'{self.new_season} Season Standings:')
        self.print_standings()
        print(f'\n{self.new_season} Season Stats')
        if self.team_to_follow != '' and self.team_to_follow in self.baseball_data.get_all_team_names():
            self.baseball_data.print_current_season(teams=[self.team_to_follow], summary_only_b=False)
        self.baseball_data.print_current_season(teams=self.teams, summary_only_b=not self.season_chatty)

        # Save final season statistics to CSV files
        self.baseball_data.save_season_stats()

        # Perform AI GM end-of-season evaluations
        print(f'\n\n****** AI GM End-of-Season Evaluations ******\n')
        self._perform_gm_evaluations()

        return

    def _perform_gm_evaluations(self) -> None:
        """
        Perform end-of-season evaluations for all AI GMs.
        Calculates final standings and calls each GM's evaluation method.
        """
        # Calculate final standings (sorted by wins)
        standings = []
        for team in self.teams:
            # Skip invalid team entries
            if team and team != 'OFF DAY' and team in self.team_win_loss:
                wins, losses = self.team_win_loss[team]
                win_pct = wins / (wins + losses) if (wins + losses) > 0 else 0.0
                standings.append({
                    'team': team,
                    'wins': wins,
                    'losses': losses,
                    'win_pct': win_pct
                })

        # Sort by wins (descending), then by losses (ascending)
        standings.sort(key=lambda x: (x['wins'], -x['losses']), reverse=True)

        # Assign standings positions
        team_standings = {s['team']: idx + 1 for idx, s in enumerate(standings)}
        total_teams = len(standings)

        # Determine which teams to print
        teams_to_print = self._get_teams_to_print()

        # Perform evaluation for each GM (only for teams with valid standings)
        for team_name, gm in self.gm_managers.items():
            if team_name in team_standings and team_name in self.team_win_loss:
                standing = team_standings[team_name]
                record = self.team_win_loss[team_name]
                games_back = self.calculate_games_back(team_name)

                # Determine if this team should print
                should_print = teams_to_print is None or team_name in teams_to_print

                gm.perform_end_of_season_evaluation(
                    baseball_stats=self.baseball_data,
                    team_record=(record[0], record[1]),
                    final_standing=standing,
                    total_teams=total_teams,
                    games_back=games_back,
                    should_print=should_print
                )

        # Print all player stats after GM evaluations
        print(f'\n\n****** Complete Player Statistics ******\n')
        self.baseball_data.print_current_season(teams=None, summary_only_b=False)

        return

    def sim_day(self, season_day_num: int) -> None:
        """
        sim one day of games across the league
        :return: None
        """
        print(self.print_day_schedule(season_day_num))
        todays_games = self.schedule[season_day_num]
        # Pass team_to_follow as a list (if not None) to show hot/cold players
        teams_list = [self.team_to_follow] if self.team_to_follow else None
        self.baseball_data.new_game_day(teams_to_follow=teams_list)  # update rest, injury, and print lists
        for match_up in todays_games:  # run all games for a day, day starts at zero
            if 'OFF DAY' not in match_up:  # not an off day
                print(f'Playing day #{season_day_num + 1}: {match_up[0]} away against {match_up[1]}')
                game = bbgame.Game(away_team_name=match_up[0], home_team_name=match_up[1],
                                   baseball_data=self.baseball_data, game_num=season_day_num,
                                   rotation_len=self.rotation_len, print_lineup=self.print_lineup_b,
                                   chatty=self.season_chatty, print_box_score_b=self.print_box_score_b,
                                   interactive=self.interactive)
                score, inning, win_loss_list, game_recap = game.sim_game(team_to_follow=self.team_to_follow)
                self.update_win_loss(away_team_name=match_up[0], home_team_name=match_up[1], win_loss=win_loss_list)
                print(game_recap)
                print(f'Final: {match_up[0]} {score[0]} {match_up[1]} {score[1]}')
                self.baseball_data.game_results_to_season(box_score_class=game.teams[AWAY].box_score)
                self.baseball_data.game_results_to_season(box_score_class=game.teams[HOME].box_score)
                print('')
                # end of game
            # end of all games for one day
        return

    def sim_day_threaded(self, season_day_num: int) -> None:
        """
        sim one day of games across the league
        :return: None
        """
        threads = []
        queues = []
        match_ups = []
        print(self.print_day_schedule(season_day_num) + '\n')
        todays_games = self.schedule[season_day_num]
        # Pass team_to_follow as a list (if not None) to show hot/cold players
        teams_list = [self.team_to_follow] if self.team_to_follow else None
        self.baseball_data.new_game_day(teams_to_follow=teams_list)  # update rest, injury, and print lists
        print(f'Simulating day #{season_day_num + 1} for league(s): {self.leagues_str}', end='')  # start sim wait line
        for match_up in todays_games:  # run all games for a day, day starts at zero
            if 'OFF DAY' not in match_up:  # not an off day
                # print(f'in sim day threaded: Playing day #{season_day_num + 1}: {match_up[0]} away against {match_up[1]}')
                game = bbgame.Game(away_team_name=match_up[0], home_team_name=match_up[1],
                                   baseball_data=self.baseball_data, game_num=season_day_num,
                                   rotation_len=self.rotation_len, print_lineup=self.print_lineup_b,
                                   chatty=self.season_chatty, print_box_score_b=self.print_box_score_b,
                                   interactive=self.interactive)
                q = queue.Queue()
                q.put(self.team_to_follow)
                thread = threading.Thread(target=game.sim_game_threaded, args=(q,))
                threads.append(thread)
                queues.append(q)
                match_ups.append(match_up)
                thread.start()
                print('.', end='')
        print('')
        for ii, thread in enumerate(threads):  # wait for all results, loop over games played, no off days
            thread.join()
            (score, inning, win_loss_list, away_box_score, home_box_score, game_recap) = queues[ii].get()
            match_up = match_ups[ii]
            self.update_win_loss(away_team_name=match_up[0], home_team_name=match_up[1], win_loss=win_loss_list)
            print(game_recap)
            # print(f'Final: {match_up[0]} {score[0]} {match_up[1]} {score[1]}')
            self.baseball_data.game_results_to_season(box_score_class=away_box_score)
            self.baseball_data.game_results_to_season(box_score_class=home_box_score)
        # end of all games for one day
        return

    def sim_next_day(self) -> None:
        """
        sims the next day for a season
        :return: None
        """
        # self.sim_day(season_day_num=self.season_day_num)
        self.sim_day_threaded(season_day_num=self.season_day_num)
        print(f'Standings for Day {self.season_day_num + 1}:')
        self.print_standings()

        # Check if any teams are due for GM assessment (every 30 games)
        self.check_gm_assessments()

        self.season_day_num = self.season_day_num + 1
        return

    def sim_full_season(self) -> None:
        """
        function drives overall sim for entire season
        :return: None
        """
        self.sim_start()
        while self.season_day_num <= len(self.schedule) - 1:  # loop over every day and every game scheduled that day
            self.sim_next_day()

        self.sim_end()
        return


class MultiBaseballSeason:
    def __init__(self, load_seasons: List[int], new_season: int, team_lists: Optional[list] = None,
                 season_length: int = 6, series_length: int = 3,
                 rotation_len: int = 5, majors_minors: list = None, season_interactive: bool = False,
                 season_print_lineup_b: bool = False, season_print_box_score_b: bool = False,
                 season_chatty: bool = False, season_team_to_follow: str = None,
                 load_batter_file: str = 'stats-pp-Batting.csv',
                 load_pitcher_file: str = 'stats-pp-Pitching.csv') -> None:
        """
                :param load_seasons: list of seasons to load for stats, can blend multiple seasons
                :param new_season: int value representing the year of the new season can be the same as one of the loads
                :param team_lists: list of list for [[majors], [minors]] to use in the simulations, optional param
                :param season_length: number of games to be played for the season
                :param series_length: series is usually 3, the default is one for testing
                :param rotation_len: number of starters to rotate, default is 5
                :param majors_minors: majors and minors leagues to include in season, each league gets its own season
                :param season_interactive: if true the sim pauses after each day
                :param season_print_lineup_b: if true print lineups
                :param season_print_box_score_b: if true print box scores
                :param season_chatty: if true provide more detail
                :param season_team_to_follow: if none skip otherwise follow this team in gory detail
                :param load_batter_file: name of the file with batter data, year will be added to the front of the text
                :param load_pitcher_file: name of the file for the pitcher data, year will be added to the front of name
                :return: None
                """
        self.season_day_num = 0  # set to first day of the season
        self.load_seasons = load_seasons  # pull base data across for what seasons
        self.new_season = new_season
        self.team_lists = team_lists if team_lists is not None else [None, None]  # create list for input to season
        self.season_length = season_length
        self.series_length = series_length
        self.rotation_len = rotation_len
        if majors_minors is not None:
            self.majors = [majors_minors[0]]  # convert to a list, expected input for single season class
            self.minors = [majors_minors[1]]
        else:
            self.majors = None
            self.minors = None
        self.interactive = season_interactive
        self.print_lineup_b = season_print_lineup_b
        self.print_box_score_b = season_print_box_score_b
        self.season_chatty = season_chatty
        self.team_to_follow = season_team_to_follow
        self.load_batter_file = load_batter_file
        self.load_pitcher_file = load_pitcher_file
        logger.debug("Initializing MultiBaseballSeason with seasons: {}, new season: {}", load_seasons, new_season)
        # if no major and minor league settings is passed bbseason_a will run all teams in all leagues
        self.bbseason_a = BaseballSeason(load_seasons=self.load_seasons, new_season=self.new_season,
                                         team_list= self.team_lists[0],  # majors team list
                                         season_length=self.season_length, series_length=self.season_length,
                                         rotation_len=self.rotation_len,
                                         include_leagues=self.majors,
                                         season_interactive=self.interactive,
                                         season_chatty=self.season_chatty, season_print_lineup_b=self.print_lineup_b,
                                         season_print_box_score_b=self.print_box_score_b,
                                         season_team_to_follow=self.team_to_follow,
                                         load_batter_file=self.load_batter_file,
                                         load_pitcher_file=self.load_pitcher_file)

        if self.minors is not None:
            self.bbseason_b = BaseballSeason(load_seasons=self.load_seasons, new_season=self.new_season,
                                             team_list = self.team_lists[1],  # minors team list
                                             season_length=self.season_length, series_length=self.season_length,
                                             rotation_len=self.rotation_len,
                                             include_leagues=self.minors,
                                             season_interactive=self.interactive,
                                             season_chatty=self.season_chatty,
                                             season_print_lineup_b=self.print_lineup_b,
                                             season_print_box_score_b=self.print_box_score_b,
                                             season_team_to_follow=self.team_to_follow,
                                             load_batter_file=self.load_batter_file,
                                             load_pitcher_file=self.load_pitcher_file)
            self.affliations = dict(zip(self.bbseason_a.get_team_names(), self.bbseason_b.get_team_names()))
            print(self.affliations)
        else:
            self.bbseason_b = None
            self.affliations = None
        return

    def sim_start(self) -> None:
        """
        starts simulations for both seasons
        :return: None
        """
        self.bbseason_a.sim_start()
        if self.bbseason_b is not None:
            self.bbseason_b.sim_start()
        return

    def sim_end(self) -> None:
        """
        ends simulations for both seasons
        :return: None
        """
        self.bbseason_a.sim_end()
        if self.bbseason_b is not None:
            self.bbseason_b.sim_end()
        return

    def sim_next_day(self) -> None:
        """
        runs one day of the sim for both seasons
        :return:
        """
        self.bbseason_a.sim_next_day()
        if self.bbseason_b is not None:
            self.bbseason_b.sim_next_day()
        return

    def sim_all_days_for_seasons(self) -> None:
        """
        run all days across both seasons
        :return: None
        """
        for day in range(self.season_length):
            self.sim_next_day()
        return


# test a number of games
if __name__ == '__main__':
    # Configure logger level - change to "DEBUG" for more detailed logs
    from bblogger import configure_logger
    configure_logger("INFO")
    
    start_time = datetime.datetime.now()

    # full season 162 games
    num_games = 162
    interactive = True
    fantasy = False

    # multiple seasons for majors and minors of random league
    if fantasy:
        my_team_to_follow = 'AUG'
        bbseasonMS = MultiBaseballSeason(load_seasons=[2023, 2024, 2025], new_season=2026,
                                         season_length=num_games, series_length=3, rotation_len=5,
                                         majors_minors=['ACB', 'NBL'],
                                         season_interactive=interactive,
                                         season_chatty=False, season_print_lineup_b=False,
                                         season_print_box_score_b=False, season_team_to_follow=my_team_to_follow,
                                         load_batter_file='aggr-stats-pp-Batting.csv',
                                         load_pitcher_file='aggr-stats-pp-Pitching.csv')
        bbseasonMS.sim_start()
        bbseasonMS.sim_all_days_for_seasons()
        bbseasonMS.sim_end()

    # handle a single full season of MLB
    if not fantasy:
        my_team_to_follow ='MIL'  # or None
        # my_team_to_follow = None

        # set a series schedule if you just want to simulate a playoff series or use the team_list param
        # series_schedule = [[['LAD', 'TOR']], [['LAD', 'TOR']],
        #                    [['TOR', 'LAD']], [['TOR', 'LAD']],
        #                    [['TOR', 'LAD']], [['LAD', 'TOR']],[['LAD', 'TOR']]]
        bbseasonSS = BaseballSeason(load_seasons=[2023, 2024, 2025], new_season=2026,
                                    season_length=num_games, series_length=7, rotation_len=5,
                                    season_interactive=interactive,
                                    season_chatty=False, season_print_lineup_b=False,
                                    season_print_box_score_b=False, season_team_to_follow=my_team_to_follow,
                                    load_batter_file='aggr-stats-pp-Batting.csv',  # 'random-aggr-stats-pp-Batting.csv',
                                    load_pitcher_file='aggr-stats-pp-Pitching.csv')
                                    # schedule=series_schedule)
        bbseasonSS.sim_full_season()

    # how long did that take?
    end_time = datetime.datetime.now()
    run_time = end_time - start_time
    total_seconds = run_time.total_seconds()  # Get the total run time in seconds
    minutes = int(total_seconds // 60)
    seconds = int(total_seconds % 60)

    print(f"Run time: {minutes} minutes and {seconds} seconds")
    print(f"Run time (timedelta format): {run_time}")
