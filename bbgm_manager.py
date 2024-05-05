import json
import bbstats
import gameteam


class Manager:
    def __init__(self, team_name, load_batter_file, load_pitcher_file,
                 load_seasons=2023, new_season=2024, baseball_data=None):
        self.team_name = team_name
        self.baseball_data = baseball_data
        if self.baseball_data is None:
            self.baseball_data = bbstats.BaseballStats(load_seasons=load_seasons, new_season=new_season,
                                                       load_batter_file=load_batter_file,
                                                       load_pitcher_file=load_pitcher_file)
        self.team = gameteam.Team(team_name=self.team_name, baseball_data=self.baseball_data)
        self.team.set_initial_lineup(show_lineup=True, show_bench=True)  # accept all defaults
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
            print("0. Accept the Lineup and Start the Game")
            print("1. Change a Player in the Lineup")
            print("2. Change the Starting Rotation")
            print("3. Load Lineup Previous Lineup")
            choice = input("\nEnter your choice: ")
            if choice == "1":
                print("Changing lineup....2")
                self.lineup_changes()
            elif choice == "2":
                self.pitching_rotation_changes()
            elif choice == "3":
                self.load_lineup()
            elif choice == "0":
                print("Starting game.")
                break  # Exit the loop
            else:
                print("Invalid choice. Please try again.")
        return

    # def pitching_changes(self):
    #     print(f'Please enter the number of the pitcher you would like to enter the game')
    #     self.team.print_available_pitchers(include_starters=True)
    #     player_index = int(input("Enter the index of the new player: "))
    #     self.team.set_starting_rotation(force_starting_pitcher=player_index)
    #     return

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
        # lineup_dict = {}
        try:
            with open('lineup.json', 'r') as f:
                lineup_dict = json.load(f)
        except FileNotFoundError:
            lineup_dict = {65: 'LF', 71: 'C', 336: '1B', 369: 'DH', 355: 'CF', 62: 'SS',
                           536: '3B', 154: '2B', 310: 'RF'}
            with open('lineup.json', 'w') as f:
                json.dump(lineup_dict, f)
        print(lineup_dict)
        self.team.set_initial_batting_order(lineup_dict)
        self.team.set_prior_and_new_pos_player_batting_bench_dfs()  # ?? would prefer not to do this
        return

    def print_team(self):
        self.baseball_data.print_prior_season([self.team_name])
        self.baseball_data.print_current_season([self.team_name])
        return


# test code Main
if __name__ == '__main__':
    bbgm = Manager(team_name='MIL', load_seasons=2023, new_season=2024,
                   load_batter_file='player-stats-Batters.csv',
                   load_pitcher_file='player-stats-Pitching.csv')
    # bbgm.print_team()
    bbgm.game_setup()
    bbgm.team.print_starting_lineups()  # reprint line up and loop to unused pos players at top
    bbgm.team.print_pos_not_in_lineup()  # lineup already printed
