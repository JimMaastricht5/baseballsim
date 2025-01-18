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
import json
import bbstats
import bbteam


class Manager:
    def __init__(self, team_name, load_batter_file, load_pitcher_file,
                 load_seasons=2024, new_season=2025, baseball_data=None, debug=False):
        self.debug = debug
        self.team_name = team_name
        self.baseball_data = baseball_data
        if self.baseball_data is None:
            self.baseball_data = bbstats.BaseballStats(load_seasons=load_seasons, new_season=new_season,
                                                       load_batter_file=load_batter_file,
                                                       load_pitcher_file=load_pitcher_file, debug=self.debug)
        self.team = None
        self.setup_team()
        # self.print_team()
        # self.team.set_initial_lineup(show_lineup=True, show_bench=True)  # accept all defaults batting and pitching
        # self.team.set_initial_batting_order()
        # self.team.set_starting_rotation()
        # self.team.set_closers()
        # self.team.set_mid_relief()
        return

    def setup_team(self):
        self.team = bbteam.Team(team_name=self.team_name, baseball_data=self.baseball_data,
                                interactive=True, debug=self.debug)
        self.team.set_initial_lineup(show_lineup=False, show_bench=False)
        return

    def game_setup(self):
        self.options()
        return

    def options(self):
        while True:
            print("\nOptions:")
            print("0. Accept the Team and Start the Game")
            print("P. Print the Entire Team")
            print("\t P1 Print the Pos Players")
            print("\t P2 Print the Pitchers")
            print("M. Move a Player to a new team.  Note: This resets lineups and rotations")
            print("T. Trade Players between two teams.  Note: This resets lineups and rotations")
            print("L. Change a Player in the Preferred Lineup")
            print("R. Change the Preferred Starting Rotation")
            print("Load. Load a Saved Team")
            print("Reset. Reset Lineup to Default")

            choice = input("\nEnter your choice: ").lower()
            if choice == "p":
                self.print_team()
            elif choice == "p1":
                self.team.print_available_batters(include_starters=True, current_season_stats=True)
            elif choice == "p2":
                self.team.print_available_pitchers(include_starters=True, current_season_stats=True)
            elif choice == "l":
                print("Changing lineup....2")
                self.lineup_changes()
            elif choice == "r":
                self.pitching_rotation_changes()
            elif choice == "load":
                self.load_lineup()
            elif choice == "reset":
                self.team.set_initial_lineup(show_lineup=True, show_bench=True)  # defaults batting and pitching
            elif choice == 'm':
                self.move_a_player()  # move players between teams
            elif choice == 't':
                self.trade_players()  # move players between teams
            elif choice == "0":
                print("Starting game.")
                break  # Exit the loop
            else:
                print("Invalid choice. Please try again.")
        return

    def pitching_rotation_changes(self):
        while True:
            try:
                # self.team.print_available_pitchers(include_starters=True)
                starting_rotation_order_num = float(input("\nEnter the spot in the starting rotation to change (1-5),"
                                                        " 0 accepts the lineup: "))
                if starting_rotation_order_num == 0:
                    break
                elif (not 1 <= starting_rotation_order_num <= 5) or not (
                    abs(starting_rotation_order_num - round(starting_rotation_order_num) == 0)):
                    print('Enter the spot in the starting rotation to change (1-5)')
                    print(self.team.print_available_pitchers(include_starters=True, current_season_stats=True))
                else:
                    starting_rotation_order_num = int(starting_rotation_order_num)
                    start_rotation_pitcher_num = int(
                        input(f'Please enter the number of the pitcher you would like to be '
                              f'in the starting rotation: '))
            except ValueError:
                break

            if (1 <= starting_rotation_order_num <= 5) and (abs(starting_rotation_order_num - round(starting_rotation_order_num) == 0)):
                self.team.change_starting_rotation(starting_pitcher_num=start_rotation_pitcher_num,
                                                   rotation_order_num=starting_rotation_order_num)
        return

    def lineup_changes(self):
        # with print lineup and print bench set to true in bbgame it is not necessary to reprint them here
        while True:
            try:
                batting_order_number = input("\nEnter the batting order number to change (1-9),  0 accepts the lineup: ")
                if batting_order_number.lower == 'p1':
                    print(self.team.print_available_batters(include_starters=True, current_season_stats=True))
                else:
                    batting_order_number = int(batting_order_number)
                    if batting_order_number == 0:  # completed
                        break
                    elif (not 1 <= batting_order_number <= 9) or not (abs(batting_order_number - round(batting_order_number) == 0)):
                        print('Enter a batting order position betweeen 1 and 9')
                    else:
                        player_index = int(input("Enter the index of the new player: "))
                        batting_order_number = int(batting_order_number)
            except ValueError:
                break

            if 1 <= batting_order_number <= 9 and abs(batting_order_number - round(batting_order_number) == 0):
                self.team.change_lineup(target_batting_order_pos=batting_order_number, pos_player_bench_hashcode=player_index)
                print("\nLineup updated!")
            else:
                print("Invalid input. Please enter valid batting order and player index numbers.")
        return

    def move_a_player(self):
        player_index = int(input("Enter the index of the player to move: "))
        print(self.baseball_data.get_all_team_names())
        new_team = str(input("Enter the name of the team the player is moving to: "))
        self.move_multiple_players(new_team=new_team, players=[player_index])
        self.team.reset_team_data()
        self.team.set_initial_lineup()
        return

    def trade_players(self):
        team_a = str(input("Enter the name of the first team involved in the trade: "))
        print(self.baseball_data.get_all_team_names())
        self.baseball_data.print_current_season(teams=[team_a])
        team_a_players = self.multiplayer_selection(team=team_a)

        team_b = str(input("Enter the name of the second team involved in the trade: "))
        print(self.baseball_data.get_all_team_names())
        self.baseball_data.print_current_season(teams=[team_b])
        team_b_players = self.multiplayer_selection(team=team_b)

        self.move_multiple_players(new_team=team_b, players=team_a_players)
        self.move_multiple_players(new_team=team_a, players=team_b_players)
        self.team.reset_team_data()
        self.team.set_initial_lineup()
        return

    def move_multiple_players(self, new_team: str, players: list):
        for player in players:
            print(new_team, player)
            self.baseball_data.move_a_player_between_teams(player_index=player, new_team=new_team)
        return

    @staticmethod
    def multiplayer_selection(team: str = ''):
        players = []
        player_num = ''
        while player_num != "x":
            player_num = str(input("Enter the player number (enter x when done): "))
            try:
                players.append(int(player_num))
            except ValueError:
                break
        return players

    def load_lineup(self):
        lineup_dict = {}
        try:
            with open(self.team_name + '_team.json', 'r') as f:
                lineup_dict_str = json.load(f)
                lineup_dict = {int(key): value for key, value in lineup_dict_str.items()}
        except FileNotFoundError:  # create a default file
            lineup_dict = {647549: 'LF', 239398: 'C', 224423: '1B', 302715: 'DH', 660657: 'CF', 520723: 'SS',
                           299454: '3B', 46074: '2B', 752787: 'RF'}
            # lineup_dict = self.team.line_up_dict()
            with open(self.team_name + '_team.json', 'w') as f:
                json.dump(lineup_dict, f)
        self.team.set_initial_batting_order(lineup_dict)
        return

    def print_team(self):
        self.team.print_available_batters(include_starters=True, current_season_stats=True)
        self.team.print_available_pitchers(include_starters=True)
        return


# test code Main
if __name__ == '__main__':
    bbgm = Manager(team_name='MIL', load_seasons=2024, new_season=2025,
                   load_batter_file='stats-pp-Batting.csv',
                   load_pitcher_file='stats-pp-Pitching.csv',
                   debug=False)
    bbgm.game_setup()
    # bbgm.team.print_starting_lineups()  # reprint line up and loop to unused pos players at top
    # bbgm.team.print_pos_not_in_lineup()  # lineup already printed
