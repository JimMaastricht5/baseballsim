import baseball_stats


class TeamBoxScore:
    def __init__(self, lineup):
        self.hitting = None  # add lineup and box options for each pos or pitcher
        self.pitching = None  # pitcher plus box options for pitching
        self.box = lineup
        return


class Team:

    def __init__(self, team_name, baseball_data):
        self.team_name = team_name
        self.baseball_data = baseball_data
        # IDfg Season Name Team Age W L WAR ERA G GS CG ShO SV BS IP TBF H R ER HR BB IBB HBP WP BK SO GB FB LD
        # IFFB Balls Strikes Pitches RS IFH BU BUH
        self.pitchers = baseball_data.pitching_data[baseball_data.pitching_data["Team"] == team_name]

        # IDfg Season Name Team Age G AB PA H 1B 2B 3B HR R RBI BB IBB SO HBP SF SH GDP SB CS AVG GB FB LD IFFB
        # Pitches Balls Strikes IFH BU BUH BB% K% BB/K OBP SLG OPS ISO BABIP GB/FB
        self.pos_players = baseball_data.batting_data[baseball_data.batting_data["Team"] == team_name]

        self.lineup = None
        self.team_box_score = None
        return

    def set_lineup(self):
        self.lineup = None  # dictionary: order, player_name, position [1..10]
        self.team_box_score = TeamBoxScore(self.lineup)
        return


class Game:
    def __init__(self, home_team_name, away_team_name, seasons=[2022]):
        self.seasons = seasons
        self.teams = [away_team_name, home_team_name]
        self.baseball_data = baseball_stats.BaseballData(seasons=self.seasons)
        print(f'Getting data...')
        self.baseball_data.get_seasons()

        print(f'Setting away team as {self.teams[0]}')
        self.away = Team(self.teams[0], self.baseball_data)
        print(f'Setting home team as {self.teams[1]}')
        self.home = Team(self.teams[1], self.baseball_data)

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
        print(f'The score is {self.teams[0]} {self.score[0]} to {self.teams[1]} {self.score[1]}')
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
    home_team = 'MIL'
    away_team = 'CHI'
    game = Game(home_team_name=home_team, away_team_name=away_team)
    _ = game.sim_game()
