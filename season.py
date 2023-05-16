import bbgame
import bbstats
import numpy as np

class BaseballSeason:
    def __init__(self):
        self.home_team = 'MIL'
        self.away_team = 'MIN'
        self.season_length = 1
        self.season_win_loss = [[0, 0], [0, 0]]  # away record pos 0, home pos 1
        self.team0_season_df = None
        self.team0_season_pitching_df = None
        return

    def sim_season(self):
        for game_num in range(1, self.season_length + 1):
            print(game_num)
            game = bbgame.Game(home_team_name=self.home_team, away_team_name=self.away_team)
            score, inning, win_loss = game.sim_game()
            self.season_win_loss[0] = list(np.add(np.array(self.season_win_loss[0]), np.array(win_loss[0])))
            self.season_win_loss[1] = list(np.add(np.array(self.season_win_loss[1]), np.array(win_loss[1])))
            if self.team0_season_df is None:
                self.team0_season_df = game.teams[0].team_box_score.box_batting
                self.team0_season_pitching_df = game.teams[0].team_box_score.box_pitching
            else:
                col_list = ['G', 'AB', 'R', 'H', '2B', '3B', 'HR', 'RBI', 'SB', 'CS', 'BB', 'SO', 'SH', 'SF', 'HBP']
                self.team0_season_df = self.team0_season_df[col_list].add(game.teams[0].team_box_score.box_batting[col_list])
                self.team0_season_df['Player'] = game.teams[0].team_box_score.box_batting['Player']
                self.team0_season_df['Team'] = game.teams[0].team_box_score.box_batting['Team']
                self.team0_season_df['Pos'] = game.teams[0].team_box_score.box_batting['Pos']

                col_list = ['G', 'GS', 'CG', 'SHO', 'IP', 'H', 'ER', 'K', 'BB', 'HR', 'W', 'L', 'SV', 'BS', 'HLD']
                self.team0_season_pitching_df = self.team0_season_pitching_df[col_list].add(
                    game.teams[0].team_box_score.box_pitching[col_list])
                self.team0_season_pitching_df['Player'] = game.teams[0].team_box_score.box_pitching['Player']
                self.team0_season_pitching_df['Team'] = game.teams[0].team_box_score.box_pitching['Team']

            print(f'Score was: {score[0]} to {score[1]}')
            print(f'{self.away_team} season : {self.season_win_loss[0][0]} W and {self.season_win_loss[0][1]} L')
            print(f'{self.home_team} season : {self.season_win_loss[1][0]} W and {self.season_win_loss[1][1]} L')

        team0_season_df = bbstats.team_batting_stats(self.team0_season_df)
        print(team0_season_df.to_string(index=False, justify='center'))
        print('')
        team0_season_pitching_df = bbstats.team_pitching_stats(self.team0_season_pitching_df)
        print(team0_season_pitching_df.to_string(index=False, justify='center'))
        # end season
        return


# test a number of games
if __name__ == '__main__':
   bbseason23 = BaseballSeason()
   bbseason23.sim_season()
