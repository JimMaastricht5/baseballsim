import pandas as pd
import random
import city_names as city
import numpy as np


class BaseballStats:
    def __init__(self, load_seasons, new_season, generate_random_data=False, only_nl_b=False,
                 load_batter_file='player-stats-Batters.csv', load_pitcher_file='player-stats-Pitching.csv'):

        self.rnd = lambda: np.random.default_rng().uniform(low=0.0, high=1.001)  # random generator between 0 and 1

        self.numeric_bcols = ['G', 'AB', 'R', 'H', '2B', '3B', 'HR', 'RBI', 'SB', 'CS', 'BB', 'SO', 'SH', 'SF',
                              'HBP']  # these cols will get added to running season total
        self.numeric_pcols = ['G', 'GS', 'CG', 'SHO', 'IP', 'AB', 'H', '2B', '3B', 'HR', 'ER', 'K', 'BB', 'W', 'L',
                              'SV', 'BS', 'HLD', 'Total_Outs']  # these cols will get added to running season total
        self.pcols_to_print = ['Player', 'League', 'Team', 'Age', 'G', 'GS', 'CG', 'SHO', 'IP', 'H', '2B', '3B', 'ER',
                               'K', 'BB', 'HR', 'W', 'L', 'SV', 'BS', 'HLD', 'ERA', 'WHIP', 'AVG', 'OBP', 'SLG', 'OPS',
                               'Status']  # 'Condition', 'Injured Days']
        self.bcols_to_print = ['Player', 'League', 'Team', 'Pos', 'Age', 'G', 'AB', 'R', 'H', '2B', '3B', 'HR', 'RBI',
                               'SB', 'CS', 'BB', 'SO', 'SH', 'SF', 'HBP', 'AVG', 'OBP', 'SLG',
                               'OPS', 'Status']  # 'Condition', , 'Injured Days']
        self.icols_to_print = ['Player', 'Team', 'Age', 'G', 'Status']  # add 'Injured Days' if you want to see time
        self.nl = ['CHC', 'CIN', 'MIL', 'PIT', 'STL', 'ATL', 'MIA', 'NYM', 'PHI', 'WAS', 'AZ', 'COL', 'LA', 'SD', 'SF']
        self.only_nl_b = only_nl_b
        self.load_seasons = load_seasons  # list of seasons to load from csv files
        self.new_season = new_season
        self.pitching_data = None
        self.batting_data = None
        self.new_season_pitching_data = None
        self.new_season_batting_data = None
        self.get_seasons(load_batter_file, load_pitcher_file)  # get existing data file
        if generate_random_data:  # generate new data from existing
            self.randomize_data()  # generate random data
            self.save_data()
        self.create_new_season_from_existing()

        # ***************** game to game stats and settings for injury and rest
        # condition and injury odds
        # 64% of injuries are to pitchers (188 of 684); 26% position players (87 of 634)
        # 27.5% of pitchers w > 5 in will spend time on IL per season (188 out of 684)
        # 26.3% of pitching injuries affect the throwing elbow results in avg of 74 days lost
        # position player (non-pitcher) longevitiy: https://www.nytimes.com/2007/07/15/sports/baseball/15careers.html
        self.condition_change_per_day = 20  # improve with rest, mid point of normal dist for recovery
        self.pitching_injury_rate = .275  # 27.5 out of 100 players injured per season-> per game
        self.pitching_injury_odds_for_season = 1 - (1 - self.pitching_injury_rate) ** (1/162)
        self.pitching_injury_avg_len = 32  # according to mlb avg len is 74 but that cant be a normal dist
        self.batting_injury_rate = .137  # 2022 87 out of 634 injured per season .137 avg age 27
        self.batting_injury_odds_for_season = 1 - (1 - self.batting_injury_rate) ** (1/162)
        # self.odds_of_survival_age_20 = .90  # 90 chance for a 20 year-old to play the following year, base injury rate
        self.odd_of_adjustment_for_age = .0328  # 3.28% inc in injury per year above age 20 w/ .90 survival at age 20
        self.batting_injury_avg_len = 15  # made this up
        # self.age_adj_inj_odds_batting = lambda: 1 - (1 - self.batting_injury_rate - ()) ** (1/162)
        self.rnd_condition_chg = lambda: abs(np.random.normal(loc=self.condition_change_per_day,
                                                              scale=self.condition_change_per_day / 2, size=1)[0])
        self.rnd_p_inj = lambda: abs(np.random.normal(loc=self.pitching_injury_avg_len,
                                                      scale=self.pitching_injury_avg_len / 2, size=1)[0])
        self.rnd_b_inj = lambda: abs(np.random.normal(loc=self.batting_injury_avg_len,
                                                      scale=self.batting_injury_avg_len / 2, size=1)[0])
        return

    def save_data(self):
        self.pitching_data.to_csv(f'{self.load_seasons[0]} random-player-stats-Pitching.csv', index=False, header=True)
        self.batting_data.to_csv(f'{self.load_seasons[0]} random-player-stats-Batters.csv', index=False, header=True)
        return

    def injured_list(self, idays):
        # mlb is 10 for pos min, 15 for pitcher min, and 60 day
        return 'Healthy' if idays == 0 else \
            '10 Day DL' if idays <= 10 else '15 Day DL' if idays <= 15 else '60 Day DL'

    def get_seasons(self, batter_file, pitcher_file):
        if self.pitching_data is None or self.batting_data is None:  # need to read data... else skip as cached
            for season in self.load_seasons:
                pitching_data = pd.read_csv(str(season) + f" {pitcher_file}")
                pitching_data['AB'] = pitching_data['IP'] * 3 + pitching_data['H']
                pitching_data['2B'] = 0
                pitching_data['3B'] = 0
                pitching_data['HBP'] = 0
                pitching_data['Season'] = str(season)
                pitching_data['OBP'] = pitching_data['WHIP'] / (3 + pitching_data['WHIP'])  # bat reached / number faced
                pitching_data['Total_OB'] = pitching_data['H'] + pitching_data['BB']  # + pitching_data['HBP']
                pitching_data['Total_Outs'] = pitching_data['IP'] * 3  # 3 outs per inning
                pitching_data = pitching_data[pitching_data['IP'] >= 10]  # drop pitchers without enough innings
                pitching_data['AVG_faced'] = (pitching_data['Total_OB'] + pitching_data['Total_Outs']) / pitching_data.G
                pitching_data['Game_Fatigue_Factor'] = 0
                pitching_data['Condition'] = 100
                pitching_data['Status'] = 'Healthy'  # status
                pitching_data['Injured Days'] = 0  # days to spend in IL
                pitching_data.index += 1
                if ('League' in pitching_data.columns) is False:  # if no league set one up
                    pitching_data['League'] = \
                        pitching_data['Team'].apply(lambda x: 'NL' if x in self.nl else 'AL')

                batting_data = pd.read_csv(str(season) + f" {batter_file}")
                batting_data['Season'] = str(season)
                batting_data['Total_OB'] = batting_data['H'] + batting_data['BB'] + batting_data['HBP']
                batting_data['Total_Outs'] = batting_data['AB'] - batting_data['H'] + batting_data['HBP']
                batting_data = batting_data[batting_data['AB'] >= 25]  # drop players without enough AB
                batting_data['Game_Fatigue_Factor'] = 0
                batting_data['Condition'] = 100
                batting_data['Status'] = 'Healthy'
                batting_data['Injured Days'] = 0
                batting_data.index += 1
                if ('League' in batting_data.columns) is False:
                    batting_data['League'] = \
                        batting_data['Team'].apply(lambda league: 'NL' if league in self.nl else 'AL')

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
        self.create_leagues()
        self.randomize_city_names()
        self.randomize_player_names()
        if np.min(self.batting_data.index) == 0 or np.min(self.pitching_data.index) == 0:  # last ditch check for error
            raise Exception('Index value cannot be zero')  # screws up bases where 0 is no runner
        return

    def randomize_mascots(self, length):
        with open('animals.txt', 'r') as f:
            animals = f.readlines()
        animals = [animal.strip() for animal in animals]
        mascots = random.sample(animals, length)
        return mascots

    def create_leagues(self):
        league_list = ['ACB', 'NBL', 'SOL', 'NNL']  # Armchair Baseball and Nerd Baseball, Some Other League, No Name
        league_names = random.sample(league_list, 2)  # replace AL and NL
        self.pitching_data.loc[self.pitching_data['League'] == 'AL', 'League'] = league_names[0]
        self.pitching_data.loc[self.pitching_data['League'] == 'NL', 'League'] = league_names[1]
        self.batting_data.loc[self.batting_data['League'] == 'AL', 'League'] = league_names[0]
        self.batting_data.loc[self.batting_data['League'] == 'NL', 'League'] = league_names[1]
        return

    def randomize_city_names(self):
        city_dict = {}
        current_team_names = self.batting_data.Team.unique()  # get list of current team names
        city.abbrev = [str(name[:3]).upper() for name in city.names]  # city names are imported
        mascots = self.randomize_mascots(len(city.names))
        for ii, team_abbrev in enumerate(city.abbrev):
            city_dict.update({city.abbrev[ii]: [city.names[ii], mascots[ii]]})  # update will use the last unique abbrev

        new_teams = list(random.sample(city.abbrev, len(current_team_names)))
        for ii, team in enumerate(current_team_names):  # do not use a df merge her resets the index, thats bad
            new_team = new_teams[ii]
            mascot = city_dict[new_team][1]
            city_name = city_dict[new_team][0]
            self.pitching_data.replace([team], [new_team], inplace=True)
            self.pitching_data.loc[self.pitching_data['Team'] == new_team, 'City'] = city_name
            self.pitching_data.loc[self.pitching_data['Team'] == new_team, 'Mascot'] = mascot
            self.batting_data.replace([team], [new_team], inplace=True)
            self.batting_data.loc[self.batting_data['Team'] == new_team, 'City'] = city_name
            self.batting_data.loc[self.batting_data['Team'] == new_team, 'Mascot'] = mascot
        return

    def randomize_player_names(self):
        # change pitching_data and batting data names, team name, etc
        df = pd.concat([self.batting_data.Player.str.split(pat=' ', n=1, expand=True),
                        self.pitching_data.Player.str.split(pat=' ', n=1, expand=True)])
        first_names = df[0].values.tolist()
        last_names = df[1].values.tolist()
        random_names = []
        for ii in range(1, (df.shape[0] + 1) * 2):  # generate twice as many random names as needed
            random_names.append(random.choice(first_names) + ' ' + random.choice(last_names))
        random_names = list(set(random_names))  # drop non-unique names
        random_names = random.sample(random_names, self.batting_data.shape[0] + self.pitching_data.shape[0])
        df['Player'] = pd.DataFrame(random_names)
        df.reset_index(inplace=True, drop=True)  # clear duplicate index error, should not happen but leave this alone!
        self.batting_data['Player'] = df['Player'][0:self.batting_data.shape[0] + 1]
        self.pitching_data['Player'] = df['Player'][0:self.pitching_data.shape[0] + 1]
        return

    def create_new_season_from_existing(self):
        # print('creating new season of data....')
        if self.pitching_data is None or self.batting_data is None:
            raise Exception('load at least one season of pitching and batting')

        self.new_season_pitching_data = self.pitching_data.copy()
        # self.new_season_pitching_data[self.numeric_pcols] = 0
        self.new_season_pitching_data[self.numeric_pcols] = \
            self.new_season_pitching_data[self.numeric_pcols].astype('int')
        self.new_season_pitching_data[['OBP', 'Total_OB', 'Total_Outs', 'AB', 'Injured Days']] = 0
        self.new_season_pitching_data['Condition'] = 100
        self.new_season_pitching_data.drop(['Total_OB', 'Total_Outs'], axis=1)
        self.new_season_pitching_data['Season'] = str(self.new_season)
        self.new_season_pitching_data['Age'] = self.new_season_pitching_data['Age'] + 1  # everyone is a year older
        self.new_season_pitching_data.fillna(0)

        self.new_season_batting_data = self.batting_data.copy()
        self.new_season_batting_data[self.numeric_bcols] = 0
        self.new_season_batting_data[['Total_OB', 'Total_Outs', 'Injured Days']] = 0  # zero out calculated fields
        self.new_season_batting_data['Condition'] = 100
        self.new_season_batting_data.drop(['Total_OB', 'Total_Outs'], axis=1)
        self.new_season_batting_data['Season'] = str(self.new_season)
        self.new_season_batting_data['Age'] = self.new_season_batting_data['Age'] + 1  # everyone is a year older
        self.new_season_batting_data = self.new_season_batting_data.fillna(0)
        return

    def game_results_to_season(self, box_score_class):
        batting_box_score = box_score_class.get_batter_game_stats()
        batting_box_score = self.end_game_day(batting_box_score)  # reduce condition for pos players that played today
        print(f'in bbstats,py game_results_to_season {batting_box_score}')
        pitching_box_score = box_score_class.get_pitcher_game_stats()
        numeric_cols = self.numeric_bcols
        for index, row in batting_box_score.iterrows():
            # print(index, row)
            new_row = batting_box_score.loc[index][numeric_cols] + self.new_season_batting_data.loc[index][numeric_cols]
            new_row['Condition'] = batting_box_score.loc[index, 'Condition']
            new_row['Injured Days'] = batting_box_score.loc[index, 'Injured Days']
            self.new_season_batting_data.loc[index, numeric_cols] = new_row
        numeric_cols = self.numeric_pcols
        for index, row in pitching_box_score.iterrows():
            new_row = pitching_box_score.loc[index][numeric_cols] + \
                      self.new_season_pitching_data.loc[index][numeric_cols]
            new_row['Condition'] = pitching_box_score.loc[index, 'Condition']
            new_row['Injured Days'] = pitching_box_score.loc[index, 'Injured Days']
            self.new_season_pitching_data.loc[index, numeric_cols] = new_row
        return

    def is_injured(self):
        self.new_season_pitching_data['Injured Days'] = self.new_season_pitching_data.\
            apply(lambda row: 0 if self.rnd() > self.pitching_injury_odds_for_season and row['Injured Days'] == 0 else
                  row['Injured Days'] - 1 if row['Injured Days'] > 0 else
                  int(self.rnd_p_inj()), axis=1)
        self.new_season_batting_data['Injured Days'] = self.new_season_batting_data.\
            apply(lambda row: 0 if self.rnd() > self.batting_injury_odds_for_season and row['Injured Days'] == 0 else
                  row['Injured Days'] - 1 if row['Injured Days'] > 0 else
                  int(self.rnd_b_inj()), axis=1)

        self.new_season_pitching_data['Status'] = \
            self.new_season_pitching_data['Injured Days'].apply(self.injured_list)
        self.new_season_batting_data['Status'] = \
            self.new_season_batting_data['Injured Days'].apply(self.injured_list)

        if self.new_season_pitching_data[self.new_season_pitching_data["Injured Days"] > 0].shape[0] > 0:
            df = self.new_season_pitching_data[self.new_season_pitching_data["Injured Days"] > 0]
            print(f'{df[self.icols_to_print].to_string(justify="right")}\n')
        if self.new_season_batting_data[self.new_season_batting_data["Injured Days"] > 0].shape[0] > 0:
            df = self.new_season_batting_data[self.new_season_batting_data["Injured Days"] > 0]
            print(f'{df[self.icols_to_print].to_string(justify="right")}\n')
        return

    def new_game_day(self):
        self.is_injured()
        self.new_season_pitching_data['Condition'] = self.new_season_pitching_data.\
            apply(lambda row: self.rnd_condition_chg() + row['Condition'], axis=1)
        self.new_season_pitching_data['Condition'] = self.new_season_pitching_data['Condition'].clip(lower=0, upper=100)
        self.new_season_batting_data['Condition'] = self.new_season_batting_data.\
            apply(lambda row: self.rnd_condition_chg() + row['Condition'], axis=1)
        self.new_season_batting_data['Condition'] = self.new_season_batting_data['Condition'].clip(lower=0, upper=100)

        # copy over results in new season to prior season for game management
        self.pitching_data.loc[:, 'Condition'] = self.new_season_pitching_data.loc[:, 'Condition']
        self.pitching_data.loc[:, 'Injured Days'] = self.new_season_pitching_data.loc[:, 'Injured Days']
        self.batting_data.loc[:, 'Condition'] = self.new_season_batting_data.loc[:, 'Condition']
        self.batting_data.loc[:, 'Injured Days'] = self.new_season_batting_data.loc[:, 'Injured Days']
        return

    def end_game_day(self, box_batting_df):
        box_batting_df['Condition'] = box_batting_df. \
            apply(lambda row: row['Condition'] - self.rnd_condition_chg(), axis=1)
        box_batting_df['Condition'] = box_batting_df['Condition'].clip(lower=0, upper=100)
        return box_batting_df

    def update_season_stats(self):
        self.new_season_pitching_data = \
            team_pitching_stats(self.new_season_pitching_data[self.new_season_pitching_data['IP'] > 0].fillna(0))
        self.new_season_batting_data = \
            team_batting_stats(self.new_season_batting_data[self.new_season_batting_data['AB'] > 0].fillna(0))

    def print_current_season(self, teams, summary_only_b=False):
        self.print_season(self.new_season_batting_data, self.new_season_pitching_data, teams=teams,
                          summary_only_b=summary_only_b)
        return

    def print_prior_season(self, teams, summary_only_b=False):
        self.print_season(team_batting_stats(self.batting_data), team_pitching_stats(self.pitching_data), teams=teams,
                          summary_only_b=summary_only_b)
        return

    def print_season(self, df_b, df_p, teams, summary_only_b=False):
        teams.append('')  # add blank team for totals
        df = df_p[df_p['Team'].isin(teams)]
        df_totals = team_pitching_totals(df, team_name='', concat=False)
        if summary_only_b is False:
            print(df[self.pcols_to_print].to_string(justify='right'))

        print('\nTeam Pitching Totals:')
        print(df_totals[self.numeric_pcols].to_string(justify='right', index=False))
        print('\n\n')

        df = df_b[df_b['Team'].isin(teams)]
        df_totals = team_batting_totals(df, team_name='', concat=False)
        if summary_only_b is False:
            print(df[self.bcols_to_print].to_string(justify='right'))

        print('\nTeam Batting Totals:')
        print(df_totals[self.numeric_bcols].to_string(justify='right', index=False))
        print('\n\n')
        return


# static function start
def remove_non_print_cols(df):
    non_print_cols = set(['Season', 'Total_OB', 'AVG_faced', 'Game_Fatigue_Factor'])  # 'Total_Outs',
    cols_to_drop = non_print_cols.intersection(df.columns)
    if cols_to_drop:
        df = df.drop(cols_to_drop, axis=1)
    return df


def trunc_col(df_n, d=3):
    return (df_n * 10 ** d).astype(int) / 10 ** d


def team_batting_stats(df):
    df = df[df['AB'] > 0]
    df['AVG'] = trunc_col(np.nan_to_num(np.divide(df['H'], df['AB']), nan=0.0, posinf=0.0), 3)
    df['OBP'] = trunc_col(np.nan_to_num(np.divide(df['H'] + df['BB'] + df['HBP'], df['AB'] + df['BB'] + df['HBP']),
                          nan=0.0, posinf=0.0), 3)
    df['SLG'] = trunc_col(np.nan_to_num(np.divide((df['H'] - df['2B'] - df['3B'] - df['HR']) + df['2B'] * 2 +
                          df['3B'] * 3 + df['HR'] * 4, df['AB']), nan=0.0, posinf=0.0), 3)
    df['OPS'] = trunc_col(np.nan_to_num(df['OBP'] + df['SLG'], nan=0.0, posinf=0.0), 3)
    df['Condition'] = (df['Condition'] * 10 ** 0).astype(int) / 10 ** 0
    return df


def team_pitching_stats(df):
    # hbp is 0, 2b are 0, 3b are 0
    df = df[(df['IP'] > 0) & (df['AB'] > 0)]
    df['AB'] = trunc_col(df['AB'], 0)
    df['IP'] = trunc_col(df['IP'], 2)
    df['AVG'] = trunc_col(df['H'] / df['AB'], 3)
    df['OBP'] = trunc_col((df['H'] + df['BB']) / (df['AB'] + df['BB']), 3)

    # Calculate 'SLG' column
    slg_numerator = (df['H'] - df['2B'] - df['3B'] - df['HR']) + df['2B'] * 2 + df['3B'] * 3 + df['HR'] * 4
    df['SLG'] = trunc_col(slg_numerator / df['AB'], 3)
    # Calculate 'OPS' column
    df['OPS'] = trunc_col(df['OBP'] + df['SLG'], 3)
    # Calculate 'WHIP' and 'ERA' columns
    df['WHIP'] = trunc_col((df['BB'] + df['H']) / df['IP'], 3)
    df['ERA'] = trunc_col((df['ER'] / df['IP']) * 9, 2)
    # Truncate 'Condition' column
    df['Condition'] = trunc_col(df['Condition'], 0)
    return df


def team_batting_totals(batting_df, team_name='', concat=True):
    df = batting_df[['AB', 'R', 'H', '2B', '3B', 'HR', 'RBI', 'SB', 'CS', 'BB', 'SO', 'SH', 'SF', 'HBP']].sum()
    df['Player'] = 'Totals'
    df['Team'] = team_name
    df['Age'] = ''
    df['Pos'] = ''
    df['Status'] = ''
    df['Injured Days'] = ''
    df['G'] = np.max(batting_df['G'])
    df['Condition'] = 0
    df = df.to_frame().T
    if concat:
        df = pd.concat([batting_df, df], ignore_index=True)
    df = team_batting_stats(df)
    return df


def team_pitching_totals(pitching_df, team_name='', concat=True):
    df = pitching_df[['GS', 'CG', 'SHO', 'IP', 'AB', 'H', '2B', '3B', 'ER', 'K', 'BB', 'HR', 'W', 'L', 'SV', 'BS',
                      'HLD', 'Total_Outs']].sum()
    df = df.to_frame().T
    df = df.assign(Player='Totals', Team=team_name, Age='', Status='', Injured_Days='',
                   G=np.max(pitching_df['G']), Condition=0)
    if concat:
        df = pd.concat([pitching_df, df], ignore_index=True)
    df = team_pitching_stats(df)
    # Vectorized the truncation operation using pandas' apply function
    cols_to_trunc = ['GS', 'CG', 'SHO', 'H', 'AB', 'ER', 'K', 'BB', 'HR', 'W', 'L', 'SV', 'BS', 'HLD', 'Total_Outs']
    df[cols_to_trunc] = df[cols_to_trunc].apply(np.floor)
    return df


if __name__ == '__main__':
    baseball_data = BaseballStats(load_seasons=[2023], new_season=2024, generate_random_data=False, only_nl_b=False,
                                  load_batter_file='player-stats-Batters.csv',
                                  load_pitcher_file='player-stats-Pitching.csv')
    #baseball_data.print_season(df_b=baseball_data.batting_data, df_p=baseball_data.pitching_data, teams=['MIL', 'ARI'])
    print(*baseball_data.pitching_data.columns)
    print(*baseball_data.batting_data.columns)
    print(baseball_data.batting_data.Team.unique())
    # print(baseball_data.batting_data.Mascot.unique())
    teams = list(baseball_data.batting_data.Team.unique())
    teams = ['MIL']  # MIL, NYM, etc
    baseball_data.print_prior_season(teams=teams)
    # baseball_data.print_current_season(teams=teams)
    # print(baseball_data.pitching_data.to_string())  # maintains index numbers
    # print(baseball_data.batting_data.to_string())
    # print(team_batting_totals(baseball_data.batting_data, concat=False).to_string())