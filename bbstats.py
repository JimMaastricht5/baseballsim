import pandas as pd
import random
import city_names as city
from itertools import combinations
import numpy as np


class BaseballStats:
    def __init__(self, load_seasons, new_season, random_data=False):
        self.numeric_bcols = ['G', 'AB', 'R', 'H', '2B', '3B', 'HR', 'RBI', 'SB', 'CS', 'BB', 'SO', 'SH', 'SF', 'HBP',
                              'AVG', 'OBP', 'SLG', 'OPS']
        self.numeric_pcols = ['G', 'GS', 'CG', 'SHO', 'IP', 'H', 'ER', 'K', 'BB', 'HR', 'W', 'L',
                              'SV', 'BS', 'HLD', 'ERA', 'WHIP']

        self.load_seasons = load_seasons  # list of seasons to load from csv files
        self.new_season = new_season
        self.pitching_data = None
        self.batting_data = None
        self.new_season_pitching_data = None
        self.new_season_batting_data = None
        self.get_seasons()
        if random_data:
            self.randomize_data()
        self.create_new_season_from_existing()
        return

    def get_seasons(self):
        if self.pitching_data is None or self.batting_data is None:  # need to read data... else skip as cached
            for season in self.load_seasons:
                pitching_data = pd.read_csv(str(season) + " player-stats-Pitching.csv")
                pitching_data['Season'] = str(season)
                pitching_data['OBP'] = pitching_data['WHIP'] / (3 + pitching_data['WHIP'])  # bat reached / number faced
                pitching_data['Total_OB'] = pitching_data['H'] + pitching_data['BB']  # + pitching_data['HBP']
                pitching_data['Total_Outs'] = pitching_data['IP'] * 3  # 3 outs per inning
                pitching_data = pitching_data[pitching_data['IP'] >= 10]  # drop pitchers without enough innings
                pitching_data['AVG_faced'] = (pitching_data['Total_OB'] + pitching_data['Total_Outs']) / pitching_data.G
                pitching_data['Game_Fatigue_Factor'] = 0
                pitching_data['Condition'] = 100

                batting_data = pd.read_csv(str(season) + " player-stats-Batters.csv")
                batting_data['Season'] = str(season)
                batting_data['Total_OB'] = batting_data['H'] + batting_data['BB'] + batting_data['HBP']
                batting_data['Total_Outs'] = batting_data['AB'] - batting_data['H'] + batting_data['HBP']
                batting_data = batting_data[batting_data['AB'] >= 25]  # drop players without enough AB
                batting_data['Game_Fatigue_Factor'] = 0
                batting_data['Condition'] = 100

                if self.pitching_data is None:
                    self.pitching_data = pitching_data
                    self.batting_data = batting_data
                else:
                    self.pitching_data = pd.concat([self.pitching_data, pitching_data])
                    self.batting_data = pd.concat([self.batting_data, batting_data])
        return

    def randomize_data(self):
        self.randomize_player_names()
        self.randomize_city_names()
        self.create_leagues(league_num=2, team_num=6, minors=False)
        return

    def randomize_mascots(self, length):
        with open('animals.txt', 'r') as f:
            animals = f.readlines()
        animals = [animal.strip() for animal in animals]
        mascots = random.sample(animals, length)
        return mascots

    def randomize_city_names(self):
        current_team_names = self.batting_data.Team.unique()  # get list of current team names
        city.abbrev = [str(name[:3]).upper() for name in city.names]
        df_city_names = pd.DataFrame({'Team': city.abbrev, 'City': city.names}).drop_duplicates(subset='Team')
        df_city_names['Mascot'] = self.randomize_mascots(df_city_names.shape[0])
        if not df_city_names['Team'].is_unique:
            raise ValueError('Team abbrev must be unique for city join to work properly')

        new_team = list(df_city_names['Team'].sample(len(current_team_names)))
        for ii, team in enumerate(current_team_names):
            self.pitching_data.replace([team], [new_team[ii]], inplace=True)
            self.batting_data.replace([team], [new_team[ii]], inplace=True)
        self.pitching_data = pd.merge(self.pitching_data, df_city_names, on='Team')
        self.batting_data = pd.merge(self.batting_data, df_city_names, on='Team')
        return

    def randomize_player_names(self):
        # change pitching_data and batting data names, team name, etc
        df = pd.concat([self.batting_data.Player.str.split(pat=' ', n=1, expand=True),
                        self.pitching_data.Player.str.split(pat=' ', n=1, expand=True)])
        first_names = df[0].values.tolist()
        last_names = df[1].values.tolist()
        random_names = []
        for ii in range(1, df.shape[0] * 2):  # generate twice as many random names as needed
            random_names.append(random.choice(first_names) + ' ' + random.choice(last_names))
        random_names = list(set(random_names))  # drop non-unique names
        random_names = random.sample(random_names, self.batting_data.shape[0] + self.pitching_data.shape[0])
        df['Player'] = pd.DataFrame(random_names)
        df.reset_index(inplace=True, drop=True)  # clear duplicate index error, should not happen but leave this alone!
        self.batting_data.Player = df['Player'][0:self.batting_data.shape[0]]
        self.pitching_data['Player'] = df['Player'][0:self.pitching_data.shape[0]]
        return

    def create_new_season_from_existing(self):
        # print('creating new season of data....')
        if self.pitching_data is None or self.batting_data is None:
            raise Exception('load at least one season of pitching and batting')

        self.new_season_pitching_data = self.pitching_data.copy()
        self.new_season_pitching_data[self.numeric_pcols] = 0
        self.new_season_pitching_data[['OBP', 'Total_OB', 'Total_Outs']] = 0  # zero out calculated fields
        self.new_season_pitching_data.drop(['Total_OB', 'Total_Outs'], axis=1)
        self.new_season_pitching_data['Season'] = str(self.new_season)
        self.new_season_pitching_data.fillna(0)

        self.new_season_batting_data = self.batting_data.copy()
        self.new_season_batting_data[self.numeric_bcols] = 0
        self.new_season_batting_data[['Total_OB', 'Total_Outs']] = 0  # zero out calculated fields
        self.new_season_batting_data.drop(['Total_OB', 'Total_Outs'], axis=1)
        self.new_season_batting_data['Season'] = str(self.new_season)
        self.new_season_batting_data = self.new_season_batting_data.fillna(0)
        # print(self.new_season_batting_data.to_string())
        return

    def create_leagues(self, league_num=2, team_num=8, minors=True):
        league_names = ['ABC', 'NBL', 'SOL', 'NNL']  # Armchair Baseball and Nerd Baseball, Some Other League, No Name
        team_names = list(self.batting_data['Team'].unique())  # get list of 3 character team names
        if len(team_names) < league_num * team_num:
            raise ValueError(f'Available # of teams {len(team_names)} must be <= then {league_num * team_num}')
        league_teams = random.sample(team_names, (league_num * team_num))
        for i in combinations(league_teams, league_num):
            print(i)
        return

    def game_results_to_season(self, box_score_class):
        batting_box_score = box_score_class.get_batter_game_stats()
        pitching_box_score = box_score_class.get_pitcher_game_stats()
        numeric_cols = self.numeric_bcols
        for index, row in batting_box_score.iterrows():
            # print(index, row)
            new_row = batting_box_score.loc[index][numeric_cols] + self.new_season_batting_data.loc[index][numeric_cols]
            self.new_season_batting_data.loc[index, numeric_cols] = new_row
            # print(self.new_season_batting_data.to_string())
        numeric_cols = self.numeric_pcols
        for index, row in pitching_box_score.iterrows():
            new_row = pitching_box_score.loc[index][numeric_cols] + \
                      self.new_season_pitching_data.loc[index][numeric_cols]
            self.new_season_pitching_data.loc[index, numeric_cols] = new_row
        return

    def update_season_stats(self):
        self.new_season_pitching_data = \
            team_pitching_stats(self.new_season_pitching_data[self.new_season_pitching_data['IP'] > 0].fillna(0))
        self.new_season_batting_data = \
            team_batting_stats(self.new_season_batting_data[self.new_season_batting_data['AB'] > 0].fillna(0))

    def print_current_season(self, teams=['MIL']):
        df = team_batting_totals(self.new_season_batting_data, team_name='', concat=True)
        df = remove_non_print_cols(df, False).sort_values(by='OPS', ascending=False)
        print(df[df['Team'].isin(teams)].to_string(justify='center'))

        print('')
        df = team_pitching_totals(self.new_season_pitching_data, team_name='', concat=True)
        df = remove_non_print_cols(df, True).sort_values(by='ERA', ascending=True)
        print(df[df['Team'].isin(teams)].to_string(justify='center'))
        return

    def print_prior_season(self, teams=['MIN']):
        df = remove_non_print_cols(self.batting_data, False)
        # df = self.batting_data.drop(['Total_OB', 'Total_Outs'], axis=1)
        print(df[df['Team'].isin(teams)].to_string(justify='center'))
        print('')
        df = remove_non_print_cols(self.pitching_data, True)
        # df = self.pitching_data.drop(['Total_OB', 'Total_Outs'], axis=1)
        print(df[df['Team'].isin(teams)].to_string(justify='center'))
        return


# static function start
def remove_non_print_cols(df_input, bpitchers=False):
    df = df_input.drop(['Season', 'Total_OB', 'Total_Outs', 'Game_Fatigue_Factor', 'Condition'], axis=1)  # pitch&hitter
    if bpitchers:
        df = df.drop(['AVG_faced'], axis=1)
    return df


def trunc_col(df_n, d=3):
    return (df_n * 10 ** d).astype(int) / 10 ** d


def team_batting_stats(df):
    df = df[df['AB'] > 0]
    try:
        df['AVG'] = trunc_col(df['H'] / df['AB'], 3)
        df['OBP'] = trunc_col((df['H'] + df['BB'] + df['HBP']) / (df['AB'] + df['BB'] + df['HBP']), 3)
        df['SLG'] = trunc_col(
            ((df['H'] - df['2B'] - df['3B'] - df['HR']) + df['2B'] * 2 + df['3B'] * 3 + df['HR'] * 4) / df['AB'], 3)
        df['OPS'] = trunc_col(df['OBP'] + df['SLG'] + df['SLG'], 3)
    except ZeroDivisionError:
        pass  # skip calculation for zero div error
    return df


def team_pitching_stats(df):
    # missing data
    # hbp is 0, 2b are 0, 3b are 0
    df = df[df['IP'] > 0]
    try:
        df['IP'] = trunc_col(df['IP'] + .0001, 3)
        df_ab = df['IP'] * 3 + df['H']
        df['AVG'] = trunc_col(df['H'] / df_ab, 3)
        df['OBP'] = trunc_col((df['H'] + df['BB'] + 0) / (df_ab + df['BB'] + 0), 3)
        df['SLG'] = trunc_col(((df['H'] - 0 - 0 - df['HR']) + 0 * 2 + 0 * 3 + df['HR'] * 4) / df_ab, 3)
        df['OPS'] = trunc_col(df['OBP'] + df['SLG'] + df['SLG'], 3)
        df['WHIP'] = trunc_col((df['BB'] + df['H']) / df['IP'], 3)
        df['ERA'] = trunc_col((df['ER'] / df['IP']) * 9)
    except ZeroDivisionError:
        pass  # trap zero division error
    return df


def team_batting_totals(batting_df, team_name='', concat=True):
    df = batting_df.copy()
    df = df[['AB', 'R', 'H', '2B', '3B', 'HR', 'RBI', 'SB', 'CS', 'BB', 'SO', 'SH', 'SF', 'HBP']].sum().astype(int)
    df['Player'] = 'Team Totals'
    df['Team'] = team_name
    df['Age'] = ''
    df['Pos'] = ''
    df['G'] = np.max(batting_df['G'])
    df = df.to_frame().T
    if concat:
        df = pd.concat([batting_df, df], ignore_index=True)
    df = team_batting_stats(df)
    return df


def team_pitching_totals(pitching_df, team_name='', concat=True):
    df = pitching_df.copy()
    df = df[['GS', 'CG', 'SHO', 'IP', 'H', 'ER', 'K', 'BB', 'HR', 'W', 'L', 'SV', 'BS',
             'HLD', 'ERA', 'WHIP']].sum().astype(int)
    cols_to_trunc = ['GS', 'CG', 'SHO', 'H', 'ER', 'K', 'BB', 'HR', 'W', 'L', 'SV', 'BS', 'HLD']
    df['Player'] = 'Team Totals'
    df['Team'] = team_name
    df['Age'] = ''
    df['G'] = np.max(pitching_df['G'])

    df = df.to_frame().T
    if concat:
        df = pd.concat([pitching_df, df], ignore_index=True)
    df = team_pitching_stats(df)
    for col in cols_to_trunc:  # remove trailing zeros after decimal
        df[col] = np.floor(df[col])
    return df


if __name__ == '__main__':
    baseball_data = BaseballStats(load_seasons=[2022], new_season=2023, random_data=False)

    print(*baseball_data.pitching_data.columns)
    print(*baseball_data.batting_data.columns)
    print(baseball_data.batting_data[baseball_data.batting_data.Team == baseball_data.batting_data.Team.unique()[0]].
          to_string(justify='center'))
    print(baseball_data.pitching_data[baseball_data.pitching_data.Team == baseball_data.batting_data.Team.unique()[0]].
          sort_values('GS', ascending=False).head(5).to_string(justify='center'))
    print(baseball_data.batting_data.Team.unique())
    baseball_data.print_prior_season()
