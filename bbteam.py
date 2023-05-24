import pandas as pd
import bbboxscore

class Team:
    def __init__(self, team_name, baseball_data, game_num=1, rotation_len=5):
        self.team_name = team_name
        self.baseball_data = baseball_data
        self.pitchers = baseball_data.pitching_data[baseball_data.pitching_data["Team"] == team_name]
        self.pos_players = baseball_data.batting_data[baseball_data.batting_data["Team"] == team_name]

        self.lineup = None
        self.pitching = None
        self.cur_pitcher_index = None
        self.cur_lineup_index = []
        self.box_score = None
        self.game_num = game_num
        self.rotation_len = rotation_len
        return

    def set_lineup(self):
        self.lineup = self.pos_players.head(10)  # assumes DH
        for row_num in range(0, len(self.lineup)):
            self.cur_lineup_index.append(self.lineup.index[row_num])

        self.starting_pitchers = self.pitchers.sort_values('GS', ascending=False).head(5)  # starting 5
        self.pitching = self.starting_pitchers.iloc[[self.game_num % self.rotation_len]]  # grab the nth row dbl []-> df
        self.cur_pitcher_index = self.pitching.index[0]

        self.box_score = bbboxscore.TeamBoxScore(self.lineup, self.pitching, self.team_name)
        return
