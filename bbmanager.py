

class Manager:
    def __init__(self, team):
        self.team = team  # this is the team object from gameteam.py
        return

    def game_setup(self):
        self.options()
        return

    def options(self):
        while True:
            print("\nOptions:")
            print("0. Accept the Lineup and Start the Game")
            print("1. Change One Player in the Lineup")
            print("2. Change Starting Pitcher")
            # print("3. Enter an entirely new Lineup")
            choice = input("\nEnter your choice: ")
            if choice == "1":
                # Perform actions for option 1
                print("Changing lineup....")
                self.interactive_lineup_changes()
            elif choice == "2":
                # Perform actions for option 2
                self.interactive_pitching_changes()
            # elif choice == "3":
            #     # Perform actions for option 2
            #     self.interactive_new_lineup()
            elif choice == "0":
                print("Starting game.")
                break  # Exit the loop
            else:
                print("Invalid choice. Please try again.")
        return

    def interactive_pitching_changes(self):
        print(f'Please enter the number of the pitcher you would like to enter the game')
        self.team.print_available_pitchers(include_starters=True)
        player_index = int(input("Enter the index of the new player: "))
        self.team.set_starting_rotation(force_starting_pitcher=player_index)
        return

    def interactive_lineup_changes(self):
        # with print lineup and print bench set to true in bbgame it is not necessary to reprint them here
       while True:
           batting_order_number = int(input("\nEnter the batting order number to change (1-9), 0 accepts the lineup: "))
           if batting_order_number == 0 or not isinstance(batting_order_number, (int, float, complex)):  # completed
               break

           player_index = int(input("Enter the index of the new player: "))
           if isinstance(player_index, (int, float, complex)) and 1 <= batting_order_number <= 9:
               self.team.change_lineup(target_pos=batting_order_number, pos_player_bench_index=player_index)
               print("\nLineup updated!")
           else:
               print("Invalid input. Please enter valid batting order and player index numbers.")
           print(self.team.print_starting_lineups())  # reprint line up and loop to unused pos players at top
           print(self.team.print_pos_not_in_lineup())  # lineup already printed
       return

    # def interactive_new_lineup(self):
    #     lineup_dict = {}
    #     sample_lineup = {65: 'LF', 71: 'C', 336: '1B', 369: 'DH', 355: 'CF', 62: 'SS', 536: '3B', 154: '2B', 310: 'RF'}
    #     print(f'Enter player Number and Position for All Players one at a time example, e.g., {"65, LF"}: ')
    #     for line_up_num in range(9):
    #         player_index, fielding_pos = str(input(f'New Lineup {str(lineup_dict)} ')).split(',')
    #         lineup_dict[player_index] = fielding_pos
    #
    #     self.team.set_initial_batting_order(lineup_dict)
    #     self.team.set_prior_and_new_pos_player_batting_bench_dfs()  # ?? would prefer not to do this
    #     return
