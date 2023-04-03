import baseball_stats


class TeamBoxScore:
    def __init__(self, lineup):
        self.hitting = None  # add lineup and box options for each pos or pitcher
        self.pitching = None  # pitcher plus box options for pitching
        self.box = lineup
        return


class Team:
    def __init__(self, teamname, baseball_data):
        self.teamname = teamname
        self.baseball_data = baseball_data
        self.pitchers = baseball_data.pitching_data[baseball_data.pitching_data["Team"] == teamname]
        self.pos_players = baseball_data.batting_data[baseball_data.batting_data["Team"] == teamname]

        self.lineup = None
        self.team_box_score = None
        return

    def set_lineup(self):
        self.lineup = None  # dictionary: order, playername, position [1..10]
        self.team_box_score = TeamBoxScore(self.lineup)
        return


class Game:
    def __init__(self, hometeamname, awayteamname, seasons=[2022]):
        self.seasons = seasons
        self.hometeamname = hometeamname
        self.awayteamname = awayteamname
        self.teams = [self.awayteamname, self.hometeamname]
        self.baseball_data = baseball_stats.BaseballData(seasons=self.seasons)
        print(f'Getting data...')
        self.baseball_data.get_seasons()

        print(f'Setting home team as {hometeamname}')
        self.home = Team(hometeamname, self.baseball_data)
        print(f'Setting away team as {awayteamname}')
        self.away = Team(awayteamname, self.baseball_data)
        self.score = [0, 0]
        self.inning = [1, 1]
        self.batting_num = [1, 1]
        self.outs = 0
        self.top_bottom = 0  # zero is top offset, 1 is bottom offset
        return

    def sim_ab(self):
        outcome = ['out', 'K']  # ob, out sub types ob: 1b, 2b, 3b, hr, hbp, e, w; out: k, ...
        if outcome[0] == 'out':
            self.outs += 1
        return outcome

    def sim_half_inning(self):
        while self.outs < 3:
            outcome = self.sim_ab()  # assuming an out for now...
            print(f'{self.teams[self.top_bottom]} batter number '
                  f'{self.batting_num[self.top_bottom]}: {outcome[1]}, {self.outs} Outs')
            self.batting_num[self.top_bottom] = self.batting_num[self.top_bottom] + 1 \
                if self.batting_num[self.top_bottom] <= 9 else 1

        # half inning over
        top_or_bottom = 'top' if self.top_bottom == 0 else 'bottom'
        print(f'Completed {top_or_bottom} half inning: {self.inning[self.top_bottom]}')
        print(f'The score is {self.awayteamname} {self.score[0]} to {self.hometeamname} {self.score[1]}')
        self.inning[self.top_bottom] += 1
        self.top_bottom = 0 if self.top_bottom == 1 else 1
        self.outs = 0
        return

    def sim_game(self):
        game_end = False
        while game_end is False:
            if self.inning[1] < 9:  # home team has played less than nine innings
                self.sim_half_inning()
            elif self.inning[1] == 9 and self.score[0] >= self.score[1]:  # home team is tied or losing, play bot 9
                self.sim_half_inning()
            else:
                game_end = True  # end game
                # report final score for standings
        return game_end


if __name__ == '__main__':
    hometeam = 'MIL'
    awayteam = 'CHI'
    game = Game(hometeamname=hometeam, awayteamname=awayteam)
    _ = game.sim_game()
