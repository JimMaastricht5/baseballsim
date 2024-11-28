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
                 load_seasons=2024, new_season=2025, baseball_data=None):
        self.team_name = team_name
        self.baseball_data = baseball_data
        if self.baseball_data is None:
            self.baseball_data = bbstats.BaseballStats(load_seasons=load_seasons, new_season=new_season,
                                                       load_batter_file=load_batter_file,
                                                       load_pitcher_file=load_pitcher_file)
        self.team = bbteam.Team(team_name=self.team_name, baseball_data=self.baseball_data)
        self.print_team()
        self.team.set_initial_lineup(show_lineup=True, show_bench=True)  # accept all defaults batting and pitching
        # self.team.set_initial_batting_order()
        # self.team.set_starting_rotation()
        # self.team.set_closers()
        # self.team.set_mid_relief()
        return

    def game_setup(self):
        self.options()
        return

    def options(self):
        while True:
            print("\nOptions:")
            print("0. Accept the Team and Start the Game")
            print("1. Change a Player in the Preferred Lineup")
            print("2. Change the Preferred Starting Rotation")
            print("3. Load a Saved Team")
            print("4. Reset")
            choice = input("\nEnter your choice: ")
            if choice == "1":
                print("Changing lineup....2")
                self.lineup_changes()
            elif choice == "2":
                self.pitching_rotation_changes()
            elif choice == "3":
                self.load_lineup()
            elif choice == "4":
                self.team.set_initial_lineup(show_lineup=True, show_bench=True)  # defaults batting and pitching

            elif choice == "0":
                print("Starting game.")
                break  # Exit the loop
            else:
                print("Invalid choice. Please try again.")
        return

    def pitching_rotation_changes(self):
        while True:
            self.team.print_available_pitchers(include_starters=True)
            starting_rotation_order_num = int(input("\nEnter the spot in the starting rotation to change (1-5),"
                                                    " 0 accepts the lineup: "))
            if starting_rotation_order_num == 0:
                break
            start_rotation_pitcher_num = int(input(f'Please enter the number of the pitcher you would like to be '
                                                   f'in the starting rotation: '))
            self.team.change_starting_rotation(starting_pitcher_num=start_rotation_pitcher_num,
                                               rotation_order_num=starting_rotation_order_num)

        return

    def lineup_changes(self):
        # with print lineup and print bench set to true in bbgame it is not necessary to reprint them here
        while True:
            self.team.print_starting_lineups()
            self.team.print_pos_not_in_lineup()
            batting_order_number = int(input("\nEnter the batting order number to change (1-9),"
                                             " 0 accepts the lineup: "))
            if batting_order_number == 0 or not isinstance(batting_order_number, (int, float, complex)):  # completed
                break

            player_index = int(input("Enter the index of the new player: "))
            if isinstance(player_index, (int, float, complex)) and 1 <= batting_order_number <= 9:
                self.team.change_lineup(target_pos=batting_order_number, pos_player_bench_index=player_index)
                print("\nLineup updated!")
            else:
                print("Invalid input. Please enter valid batting order and player index numbers.")
            # print(self.team.print_starting_lineups())  # reprint already printed
        return

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
        print(lineup_dict)
        self.team.set_initial_batting_order(lineup_dict)
        # self.team.set_prior_and_new_pos_player_batting_bench_dfs()  # ?? would prefer not to do this
        return

    def print_team(self):
        self.baseball_data.print_prior_season([self.team_name])
        self.baseball_data.print_current_season([self.team_name])
        self.team.print_available_batters(include_starters=True)
        self.team.print_available_pitchers(include_starters=True)
        return


# test code Main
if __name__ == '__main__':
    bbgm = Manager(team_name='MIL', load_seasons=2024, new_season=2025,
                   load_batter_file='stats-pp-Batting.csv',
                   load_pitcher_file='stats-pp-Pitching.csv')
    # bbgm.print_team()
    bbgm.game_setup()
    bbgm.team.print_starting_lineups()  # reprint line up and loop to unused pos players at top
    bbgm.team.print_pos_not_in_lineup()  # lineup already printed
