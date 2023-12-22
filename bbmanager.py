

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
            print("1. Change Lineup")
            print("2. Change Starting Pitcher")
            print("3. Done")
            choice = input("\nEnter your choice (1-3): ")
            if choice == "1":
                # Perform actions for option 1
                print("Changing lineup....")
                self.lineup_changes()
            elif choice == "2":
                # Perform actions for option 2
                print("You chose Option 2.")
            elif choice == "3":
                print("Starting game.")
                break  # Exit the loop
            else:
                print("Invalid choice. Please try again.")
        return

    def lineup_changes(self):
        # with print lineup and print bench set to true in bbgame it is not necessary to reprint them here
       while True:
           batting_order_number = int(input("\nEnter the batting order number to change (1-9), 0 is done: "))
           if batting_order_number == 0 or not isinstance(batting_order_number, (int, float, complex)):  # completed
               break

           player_index = int(input("Enter the index of the new player: "))
           if isinstance(player_index, (int, float, complex)) and 1 <= batting_order_number <= 9 and \
                   player_index in self.team.pos_players.index:  # check pos number and player exists
               self.team.swap_player_in_lineup_w_bench(target_pos=batting_order_number,
                                                       pos_player_bench_index=player_index)
               print("\nLineup updated!")
           else:
               print("Invalid input. Please enter valid batting order and player index numbers.")
           print(self.team.print_starting_lineups())  # reprint line up and loop to unused pos players at top
           print(self.team.print_pos_not_in_lineup())  # lineup already printed
       return