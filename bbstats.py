import pandas as pd
import random
import city_names as city
from itertools import combinations
import numpy as np


class BaseballStats:
    def __init__(self, load_seasons, new_season, random_data=False, only_nl_b=False):
        self.rnd = lambda: np.random.default_rng().uniform(low=0.0, high=1.001)  # random generator between 0 and 1
        self.numeric_bcols = ['G', 'AB', 'R', 'H', '2B', '3B', 'HR', 'RBI', 'SB', 'CS', 'BB', 'SO', 'SH', 'SF', 'HBP',
                              'AVG', 'OBP', 'SLG', 'OPS']
        self.numeric_pcols = ['G', 'GS', 'CG', 'SHO', 'IP', 'AB', 'H', '2B', '3B', 'ER', 'K', 'BB', 'HR', 'W', 'L',
                              'SV', 'BS', 'HLD', 'ERA', 'WHIP', 'Total_Outs']
        self.nl= ['CHC', 'CIN', 'MIL', 'PIT', 'STL', 'ATL', 'MIA', 'NYM', 'PHI', 'WAS', 'AZ', 'COL', 'LA', 'SD', 'SF']
        self.only_nl_b=only_nl_b
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

        # ***************** game to game stats and settings for injury and rest
        # condition and injury odds
        # 64% of injuries are to pitchers (188 of 684); 26% position players (87 of 634)
        # 27.5% of pitchers w > 5 in will spend time on IL per season (188 out of 684)
        # 26.3% of pitching injuries affect the throwing elbow results in avg of 74 days lost
        # position player (non-pitcher) longevitiy: https://www.nytimes.com/2007/07/15/sports/baseball/15careers.html
        self.condition_change_per_day = 20  # improve with rest
        self.pitching_injury_odds_for_season = .275 / 162  # per game
        self.pitching_injury_avg_len = 74
        self.batting_injury_odds_for_season = 87 / 634 / 162  # 2022 pos player count of 634
        self.batting_injury_avg_len = 30  # made this up
        self.odds_of_survival_age_20 = .90  # 90 chance for a 20 year-old to play the following year
        self.odd_of_survival_additional_years = -.0328  # 3.28% decrease in survival, use to increase injury chance
        # self.injured_lists = [7, 14, 60, 162]  # mlb is 10 for pos min, 15 for pitcher min, and 60 day
        # self.injuries_Severity = {'Healthy': 0, 'Minor Injury': 7, 'Injury': 14, 'Major Injury': 75,
        #                           'Season Ending': 162, 'Career Ending': 9999}
        return

    def get_seasons(self):
        if self.pitching_data is None or self.batting_data is None:  # need to read data... else skip as cached
            for season in self.load_seasons:
                pitching_data = pd.read_csv(str(season) + " player-stats-Pitching.csv")
                pitching_data['AB'] = pitching_data['IP'] * 3 + pitching_data['H']
                pitching_data['2B'] = 0
                pitching_data['3B'] = 0
                pitching_data['Season'] = str(season)
                pitching_data['OBP'] = pitching_data['WHIP'] / (3 + pitching_data['WHIP'])  # bat reached / number faced
                pitching_data['Total_OB'] = pitching_data['H'] + pitching_data['BB']  # + pitching_data['HBP']
                pitching_data['Total_Outs'] = pitching_data['IP'] * 3  # 3 outs per inning
                pitching_data = pitching_data[pitching_data['IP'] >= 10]  # drop pitchers without enough innings
                pitching_data['AVG_faced'] = (pitching_data['Total_OB'] + pitching_data['Total_Outs']) / pitching_data.G
                pitching_data['Game_Fatigue_Factor'] = 0
                pitching_data['Condition'] = 100
                pitching_data['Injured'] = 'Healthy'  # status
                pitching_data['Injured List'] = 0  # days to spend in IL
                pitching_data.index += 1

                batting_data = pd.read_csv(str(season) + " player-stats-Batters.csv")
                batting_data['Season'] = str(season)
                batting_data['Total_OB'] = batting_data['H'] + batting_data['BB'] + batting_data['HBP']
                batting_data['Total_Outs'] = batting_data['AB'] - batting_data['H'] + batting_data['HBP']
                batting_data = batting_data[batting_data['AB'] >= 25]  # drop players without enough AB
                batting_data['Game_Fatigue_Factor'] = 0
                batting_data['Condition'] = 100
                batting_data['Injured'] = 'Healthy'
                batting_data['Injured List'] = 0
                batting_data.index += 1

                if self.pitching_data is None:
                    self.pitching_data = pitching_data
                    self.batting_data = batting_data
                else:
                    self.pitching_data = pd.concat([self.pitching_data, pitching_data])
                    self.batting_data = pd.concat([self.batting_data, batting_data])
                if self.only_nl_b:
                    self.pitching_data = self.pitching_data[self.pitching_data['Team'].isin(self.nl)]
                    self.batting_data = self.batting_data[self.batting_data['Team'].isin(self.nl)]
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
        self.new_season_pitching_data[['OBP', 'Total_OB', 'Total_Outs', 'AB']] = 0  # zero out calculated fields
        self.new_season_pitching_data.drop(['Total_OB', 'Total_Outs'], axis=1)
        self.new_season_pitching_data['Season'] = str(self.new_season)
        self.new_season_pitching_data['Age'] = self.new_season_pitching_data['Age'] + 1  # everyone is a year older
        self.new_season_pitching_data.fillna(0)

        self.new_season_batting_data = self.batting_data.copy()
        self.new_season_batting_data[self.numeric_bcols] = 0
        self.new_season_batting_data[['Total_OB', 'Total_Outs']] = 0  # zero out calculated fields
        self.new_season_batting_data.drop(['Total_OB', 'Total_Outs'], axis=1)
        self.new_season_batting_data['Season'] = str(self.new_season)
        self.new_season_batting_data['Age'] = self.new_season_batting_data['Age'] + 1  # everyone is a year older
        self.new_season_batting_data = self.new_season_batting_data.fillna(0)
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
            self.new_season_batting_data.loc[index, 'Condition'] = batting_box_score.loc[index, 'Condition']
        numeric_cols = self.numeric_pcols
        for index, row in pitching_box_score.iterrows():
            new_row = pitching_box_score.loc[index][numeric_cols] + \
                      self.new_season_pitching_data.loc[index][numeric_cols]
            self.new_season_pitching_data.loc[index, numeric_cols] = new_row
            self.new_season_pitching_data.loc[index, 'Condition'] = pitching_box_score.loc[index, 'Condition']
        return

    def is_injured(self):
        self.new_season_pitching_data['Injured List'] = self.new_season_pitching_data.\
            apply(lambda x: 0 if self.rnd() > self.pitching_injury_odds_for_season else
                  self.rnd() * self.pitching_injury_avg_len + self.pitching_injury_avg_len / 2)
        self.new_season_batting_data['Injured List'] = self.new_season_batting_data.\
            apply(lambda x: 0 if self.rnd() > self.batting_injury_odds_for_season else
                  self.rnd() * self.batting_injury_avg_len + self.batting_injury_avg_len / 2)
        return

    def new_game_day(self):
        # self.is_injured()
        self.new_season_pitching_data['Condition'] = self.new_season_pitching_data['Condition'] \
                                                     + self.condition_change_per_day
        self.new_season_pitching_data['Condition'] = self.new_season_pitching_data['Condition'].clip(lower=0, upper=100)
        self.new_season_pitching_data['Injured List'] = self.new_season_pitching_data['Injured List'] - 1
        self.new_season_pitching_data['Injured List'] = self.new_season_pitching_data['Injured List'].clip(lower=0)
        self.new_season_pitching_data['Injured'] = \
            self.new_season_pitching_data['Injured List'].apply(lambda x: 'Injured' if x != 0 else 'Healthy')
        self.new_season_batting_data['Condition'] = self.new_season_batting_data['Condition'] \
            + self.condition_change_per_day
        self.new_season_batting_data['Condition'] = self.new_season_batting_data['Condition'].clip(lower=0, upper=100)
        self.new_season_batting_data['Injured List'] = self.new_season_batting_data['Injured List'] - 1
        self.new_season_batting_data['Injured List'] = self.new_season_batting_data['Injured List'].clip(lower=0)
        self.new_season_batting_data['Injured'] = \
            self.new_season_batting_data['Injured List'].apply(lambda x: 'Injured' if x != 0 else 'Healthy')

        # copy over results in new season to prior season for game management
        self.pitching_data.loc[:, 'Condition'] = self.new_season_pitching_data.loc[:, 'Condition']
        self.pitching_data.loc[:, 'Injured List'] = self.new_season_pitching_data.loc[:, 'Injured List']
        self.batting_data.loc[:, 'Condition'] = self.new_season_batting_data.loc[:, 'Condition']
        self.batting_data.loc[:, 'Injured List'] = self.new_season_batting_data.loc[:, 'Injured List']
        return

    def update_season_stats(self):
        self.new_season_pitching_data = \
            team_pitching_stats(self.new_season_pitching_data[self.new_season_pitching_data['IP'] > 0].fillna(0))
        self.new_season_batting_data = \
            team_batting_stats(self.new_season_batting_data[self.new_season_batting_data['AB'] > 0].fillna(0))

    def print_current_season(self, teams=['MIL'], summary_only_b=False):
        teams.append('')  # add blank team for totals
        df = self.new_season_batting_data.copy().sort_values(by='OPS', ascending=False)  # take copy to add totals
        df = team_batting_totals(df, team_name='', concat=True)
        df = remove_non_print_cols(df, False)
        if summary_only_b:
            df = df.tail(1)
        print(df[df['Team'].isin(teams)].to_string(justify='right'))
        print('\n\n')
        df = self.new_season_pitching_data.copy().sort_values(by='ERA', ascending=True)
        df = team_pitching_totals(df, team_name='', concat=True)
        df = remove_non_print_cols(df, True)
        df = df.reindex(['Player', 'Team', 'Age', 'G', 'GS', 'CG', 'SHO', 'IP', 'AB', 'H', '2B', '3B', 'ER', 'K', 'BB',
                         'HR', 'W', 'L', 'SV', 'BS', 'HLD', 'ERA', 'WHIP', 'AVG', 'OBP', 'SLG', 'OPS',
                         'Condition', 'Injured', 'Injured List'], axis=1)
        if 'Total_Outs' in df.columns:
            df.drop(['Total_Outs'], axis=1, inplace=False)
        if summary_only_b:
            df = df.tail(1)
        print(df[df['Team'].isin(teams)].to_string(justify='right'))
        return

    def print_prior_season(self, teams=['MIN'], summary_only_b=False):
        teams.append('')  # add blank team for totals
        df = self.batting_data.copy().sort_values(by='OPS', ascending=False)  # take copy to add totals
        df = team_batting_totals(df, team_name='', concat=True)
        df = remove_non_print_cols(df, False)
        if summary_only_b:
            df = df.tail(1)
        print(df[df['Team'].isin(teams)].to_string(justify='right'))
        print('\n\n')
        df = self.pitching_data.copy().sort_values(by='ERA', ascending=True)
        df = team_pitching_totals(df, team_name='', concat=True)
        df = remove_non_print_cols(df, True)
        df = df.reindex(['Player', 'Team', 'Age', 'G', 'GS', 'CG', 'SHO', 'IP', 'AB', 'H', '2B', '3B', 'ER', 'K', 'BB',
                         'HR', 'W', 'L', 'SV', 'BS', 'HLD', 'ERA', 'WHIP', 'AVG', 'OBP', 'SLG', 'OPS',
                         'Condition', 'Injured', 'Injured List'], axis=1)
        if summary_only_b:
            df = df.tail(1)
        print(df[df['Team'].isin(teams)].to_string(justify='right'))
        return


# static function start
def remove_non_print_cols(df_input, bpitchers=False):
    if bpitchers:
        df = df_input.drop(['Season', 'Total_OB', 'AVG_faced', 'Game_Fatigue_Factor'], axis=1)
    else:
        df = df_input.drop(['Season', 'Total_OB', 'Total_Outs', 'Game_Fatigue_Factor'], axis=1)
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
        df['OPS'] = trunc_col(df['OBP'] + df['SLG'], 3)
        df['Condition'] = trunc_col(df['Condition'], 0)
    except ZeroDivisionError:
        pass  # skip calculation for zero div error
    return df


def team_pitching_stats(df):
    # hbp is 0, 2b are 0, 3b are 0
    df = df[df['IP'] > 0]
    df = df[df['AB'] > 0]
    df['AB'] = trunc_col(df['AB'], 0)
    df['IP'] = trunc_col(df['IP'], 2)
    df['AVG'] = trunc_col(df['H'] / df['AB'], 3)
    df['OBP'] = trunc_col((df['H'] + df['BB'] + 0) / (df['AB'] + df['BB'] + 0), 3)
    df['SLG'] = trunc_col(
        ((df['H'] - df['2B'] - df['3B'] - df['HR']) + df['2B'] * 2 + df['3B'] * 3 + df['HR'] * 4) / df['AB'], 3)
    df['OPS'] = trunc_col(df['OBP'] + df['SLG'], 3)
    df['WHIP'] = trunc_col((df['BB'] + df['H']) / df['IP'], 3)
    df['ERA'] = trunc_col((df['ER'] / df['IP']) * 9, 2)
    df['Condition'] = trunc_col(df['Condition'], 0)
    return df


def team_batting_totals(batting_df, team_name='', concat=True):
    df = batting_df.copy()
    df = df[['AB', 'R', 'H', '2B', '3B', 'HR', 'RBI', 'SB', 'CS', 'BB', 'SO', 'SH', 'SF', 'HBP']].sum()
    df['Player'] = 'Totals'
    df['Team'] = team_name
    df['Age'] = ''
    df['Pos'] = ''
    df['Injured'] = ''
    df['Injured List'] = ''
    df['G'] = np.max(batting_df['G'])
    df['Condition'] = np.average(batting_df['Condition'])
    df = df.to_frame().T
    if concat:
        df = pd.concat([batting_df, df], ignore_index=True)
    df = team_batting_stats(df)
    return df


def team_pitching_totals(pitching_df, team_name='', concat=True):
    df = pitching_df.copy()
    df = df[['GS', 'CG', 'SHO', 'IP', 'AB', 'H', '2B', '3B', 'ER', 'K', 'BB', 'HR', 'W', 'L', 'SV', 'BS',
             'HLD', 'Total_Outs']].sum()
    cols_to_trunc = ['GS', 'CG', 'SHO', 'H', 'AB', 'ER', 'K', 'BB', 'HR', 'W', 'L', 'SV', 'BS', 'HLD', 'Total_Outs']
    df['Player'] = 'Totals'
    df['Team'] = team_name
    df['Age'] = ''
    df['Injured'] = ''
    df['Injured List'] = ''
    df['G'] = np.max(pitching_df['G'])
    df['Condition'] = np.average(pitching_df['Condition'])

    df = df.to_frame().T
    if concat:
        df = pd.concat([pitching_df, df], ignore_index=True)
    df = team_pitching_stats(df)
    for col in cols_to_trunc:  # remove trailing zeros after decimal
        df[col] = np.floor(df[col])
    return df


if __name__ == '__main__':
    baseball_data = BaseballStats(load_seasons=[2022], new_season=2023, random_data=False, only_nl_b=True)

    print(*baseball_data.pitching_data.columns)
    print(*baseball_data.batting_data.columns)
    print(baseball_data.batting_data.Team.unique())
    #teams = ['CHC', 'CIN', 'COL', 'MIL', 'PIT', 'STL']  # included COL for balance in scheduling
    teams = list(baseball_data.batting_data.Team.unique())
    baseball_data.print_prior_season(teams=teams)
    # print(baseball_data.new_season_pitching_data.to_string())