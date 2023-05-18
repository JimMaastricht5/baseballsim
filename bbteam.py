import pandas as pd
import bbboxscore

class Team:
    def __init__(self, team_name, baseball_data):
        self.team_name = team_name
        self.baseball_data = baseball_data
        self.pitchers = baseball_data.pitching_data[baseball_data.pitching_data["Team"] == team_name]
        self.pos_players = baseball_data.batting_data[baseball_data.batting_data["Team"] == team_name]

        self.lineup = None
        self.pitching = None
        self.cur_pitcher_index = None
        self.team_box_score = None
        return

    def set_lineup(self):
        self.lineup = self.pos_players.head(10)  # assumes DH
        print(self.lineup)
        self.pitching = self.pitchers.head(1)
        self.cur_pitcher_index.append(self.pitching.index[0])

        self.team_box_score = bbboxscore.TeamBoxScore(self.lineup, self.pitching, self.team_name)
        return
