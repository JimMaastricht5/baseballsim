import pandas as pd
import random
import city_names as city
import numpy as np
import hashlib


class BaseballStatsPreProcess:
    def __init__(self, load_seasons, new_season=None, generate_random_data=False,
                 load_batter_file='player-stats-Batters.csv', load_pitcher_file='player-stats-Pitching.csv'):
        self.create_hash = lambda text: int(hashlib.sha256(text.encode('utf-8')).hexdigest()[:5], 16)
        self.jigger_data = lambda x: x + int(np.abs(np.random.normal(loc=x * .10, scale=2, size=1)))

        self.numeric_bcols = ['G', 'AB', 'R', 'H', '2B', '3B', 'HR', 'RBI', 'SB', 'CS', 'BB', 'SO', 'SH', 'SF',
                              'HBP', 'Condition']  # these cols will get added to running season total
        self.numeric_pcols = ['G', 'GS', 'CG', 'SHO', 'IP', 'AB', 'H', '2B', '3B', 'HR', 'ER', 'K', 'BB', 'W', 'L',
                              'SV', 'BS', 'HLD', 'Total_Outs', 'Condition']  # cols will add to running season total
        self.nl = ['CHC', 'CIN', 'MIL', 'PIT', 'STL', 'ATL', 'MIA', 'NYM', 'PHI', 'WAS', 'WSH', 'AZ', 'COL', 'LA',
                   'SD', 'SF']  # keep old and new abrrev for WAS/WSH
        self.name_changes = {'WAS': 'WSH'}
        self.load_seasons = [load_seasons] if not isinstance(load_seasons, list) else load_seasons
        self.new_season = new_season
        self.pitching_data = None
        self.batting_data = None
        self.new_season_pitching_data = None
        self.new_season_batting_data = None
        self.generate_random_data = generate_random_data

        self.get_seasons(load_batter_file, load_pitcher_file)  # get existing data file
        self.generate_random_data = generate_random_data
        if self.generate_random_data:  # generate new data from existing
            self.randomize_data()  # generate random data
        if new_season is not None:
            self.create_new_season_from_existing(load_batter_file, load_pitcher_file)
        self.save_data()
        return

    def save_data(self):
        f_pname = 'random-stats-pp-Pitching.csv' if self.generate_random_data else 'stats-pp-Pitching.csv'
        f_bname = 'random-stats-pp-Batting.csv' if self.generate_random_data else 'stats-pp-Batting.csv'
        seasons_str = " ".join(str(season) for season in self.load_seasons)
        self.pitching_data.to_csv(f'{seasons_str} {f_pname}', index=True, header=True)
        self.batting_data.to_csv(f'{seasons_str} {f_bname}', index=True, header=True)
        if self.new_season is not None:
            self.new_season_pitching_data.to_csv(f'{self.new_season} New-Season-{f_pname}', index=True, header=True)
            self.new_season_batting_data.to_csv(f'{self.new_season} New-Season-{f_bname}', index=True, header=True)
        return

    def group_col_to_list(self, df, key_col, col, new_col):
        # Groups unique values in a column by a key column
        # Args: df (pd.DataFrame): The dataframe containing the columns.
        #    key_col (str): The name of the column containing the key.
        #    col (str): The name of the column to find unique values in.
        #    new_col (str): The name of the new column to contain the data
        # Returns: list: A list of dictionaries containing unique values grouped by key.
        groups = {}
        for i, row in df.iterrows():
            key = row[key_col]
            val = row[col]
            if key not in groups:
                groups[key] = set()
            groups[key].add(val)
        df[new_col] = df[key_col].map(groups)  # Create a new column to store grouped unique values
        df[new_col] = df[new_col].apply(list)  # Convert sets to lists for easier handling in DataFrame
        return df

    def find_duplicate_rows(self, df, column_names):
        #  This function finds duplicate rows in a DataFrame based on a specified column.
        # Args: df (pandas.DataFrame): The DataFrame to analyze.
        #   column_names (list): The name of the column containing strings for comparison.
        # Returns: pandas.DataFrame: A new DataFrame containing only the rows with duplicate string values.
        filtered_df = df[column_names].dropna()
        duplicates = filtered_df.duplicated(keep=False)  # keep both rows
        return df[duplicates]

    def de_dup_df(self, df, key_name, dup_column_names, stats_cols_to_sum, drop_dups=False):
        dup_hashcodes = self.find_duplicate_rows(df=df, column_names=dup_column_names)
        for dfrow_key in dup_hashcodes[key_name].unique():
            df_rows = df.loc[df[key_name] == dfrow_key]
            # if dfrow_key == 810032:
            #     print(f'bbstats preprocess de_dup_df {dfrow_key} {df_rows.to_string()}')
            for dfcol_name in stats_cols_to_sum:
                df.loc[df[key_name] == dfrow_key, dfcol_name] = df_rows[dfcol_name].sum()
        if drop_dups:
            df = df.drop_duplicates(subset='Hashcode', keep='last')
        return df

    def update_team_names(self, team):
        return self.name_changes.get(team, team)

    def get_pitching_seasons(self, pitcher_file, load_seasons):
        pitching_data = None
        stats_pcols_sum = ['G', 'GS', 'CG', 'SHO', 'IP', 'H', 'ER', 'K', 'BB', 'HR', 'W', 'L', 'SV', 'BS', 'HLD']
        for season in load_seasons:
            df = pd.read_csv(str(season) + f" {pitcher_file}")
            df['Team'] = df['Team'].apply(self.update_team_names)
            pitching_data = pd.concat([pitching_data, df], axis=0)

        pitching_data['Hashcode'] = pitching_data['Player'].apply(self.create_hash)
        if ('League' in pitching_data.columns) is False:  # if no league set one up
            pitching_data['League'] = pitching_data['Team'].apply(lambda x: 'NL' if x in self.nl else 'AL')
        pitching_data = self.group_col_to_list(df=pitching_data, key_col='Hashcode', col='Team', new_col='Teams')
        pitching_data = self.group_col_to_list(df=pitching_data, key_col='Hashcode', col='League', new_col='Leagues')
        pitching_data = self.de_dup_df(df=pitching_data, key_name='Hashcode', dup_column_names='Hashcode',
                                       stats_cols_to_sum=stats_pcols_sum, drop_dups=True)
        pitching_data.set_index(keys=['Hashcode'], drop=True, append=False, inplace=True)
        # set up additional stats
        if self.generate_random_data:
            for stats_col in stats_pcols_sum:
                pitching_data[stats_col] = pitching_data[stats_col].apply(self.jigger_data)

        pitching_data['AB'] = pitching_data['IP'] * 3 + pitching_data['H']
        pitching_data['2B'] = 0
        pitching_data['3B'] = 0
        pitching_data['HBP'] = 0
        pitching_data['Season'] = str(load_seasons)
        pitching_data['OBP'] = pitching_data['WHIP'] / (3 + pitching_data['WHIP'])  # bat reached / number faced
        pitching_data['Total_OB'] = pitching_data['H'] + pitching_data['BB']  # + pitching_data['HBP']
        pitching_data['Total_Outs'] = pitching_data['IP'] * 3  # 3 outs per inning
        pitching_data = pitching_data[pitching_data['IP'] >= 10]  # drop pitchers without enough innings
        pitching_data['AVG_faced'] = (pitching_data['Total_OB'] + pitching_data['Total_Outs']) / pitching_data.G
        pitching_data['Game_Fatigue_Factor'] = 0
        pitching_data['Condition'] = 100
        pitching_data['Status'] = 'Active'  # DL or active
        pitching_data['Injured Days'] = 0  # days to spend in IL
        return pitching_data

    def get_batting_seasons(self, batter_file, load_seasons):
        batting_data = None
        stats_bcols_sum = ['G', 'AB', 'R', 'H', '2B', '3B', 'HR', 'RBI', 'SB', 'CS', 'BB', 'SO', 'SH', 'SF', 'HBP']
        for season in load_seasons:
            df = pd.read_csv(str(season) + f" {batter_file}")
            df['Team'] = df['Team'].apply(self.update_team_names)
            batting_data = pd.concat([batting_data, df], axis=0)

        batting_data['Hashcode'] = batting_data['Player'].apply(self.create_hash)
        if ('League' in batting_data.columns) is False:  # if no league set one up
            batting_data['League'] = batting_data['Team'].apply(lambda x: 'NL' if x in self.nl else 'AL')
        batting_data = self.group_col_to_list(df=batting_data, key_col='Hashcode', col='Team', new_col='Teams')
        batting_data = self.group_col_to_list(df=batting_data, key_col='Hashcode', col='League', new_col='Leagues')
        batting_data = self.de_dup_df(df=batting_data, key_name='Hashcode', dup_column_names='Hashcode',
                                      stats_cols_to_sum=stats_bcols_sum, drop_dups=True)
        batting_data.set_index(keys=['Hashcode'], drop=True, append=False, inplace=True)
        # set up additional stats
        if self.generate_random_data:
            for stats_col in stats_bcols_sum:
                batting_data[stats_col] = batting_data[stats_col].apply(self.jigger_data)

        batting_data['Season'] = str(load_seasons)
        batting_data['OBP'] = self.trunc_col(np.nan_to_num(np.divide(batting_data['H'] + batting_data['BB'] +
                                                                     batting_data['HBP'], batting_data['AB'] +
                                                                     batting_data['BB'] + batting_data['HBP']),
                                                           nan=0.0, posinf=0.0), 3)
        batting_data['SLG'] = self.trunc_col(np.nan_to_num(np.divide((batting_data['H'] - batting_data['2B'] -
                                                                      batting_data['3B'] - batting_data['HR']) +
                                                                     batting_data['2B'] * 2 +
                                                                     batting_data['3B'] * 3 + batting_data['HR'] * 4,
                                                                     batting_data['AB']), nan=0.0, posinf=0.0), 3)
        batting_data['OPS'] = self.trunc_col(np.nan_to_num(batting_data['OBP'] + batting_data['SLG'],
                                                           nan=0.0, posinf=0.0), 3)
        batting_data['Total_OB'] = batting_data['H'] + batting_data['BB'] + batting_data['HBP']
        batting_data['Total_Outs'] = batting_data['AB'] - batting_data['H'] + batting_data['HBP']
        batting_data = batting_data[batting_data['AB'] >= 25]  # drop players without enough AB
        batting_data['Game_Fatigue_Factor'] = 0
        batting_data['Condition'] = 100
        batting_data['Status'] = 'Active'  # DL or active
        batting_data['Injured Days'] = 0
        if ('League' in batting_data.columns) is False:
            batting_data['League'] = \
                batting_data['Team'].apply(lambda league: 'NL' if league in self.nl else 'AL')

        return batting_data

    def get_seasons(self, batter_file, pitcher_file):
        self.pitching_data = self.get_pitching_seasons(pitcher_file, self.load_seasons)
        self.batting_data = self.get_batting_seasons(batter_file, self.load_seasons)
        return

    def randomize_data(self):
        self.create_leagues()
        self.randomize_city_names()
        self.randomize_player_names()
        if np.min(self.batting_data.index) == 0 or np.min(self.pitching_data.index) == 0:  # last ditch check key error
            raise Exception('Index value cannot be zero')  # screws up bases where 0 is no runner
        return

    def create_leagues(self):
        # replace AL and NL with random league names, set leagues column to match
        league_list = ['ACB', 'NBL', 'SOL', 'NNL']  # Armchair Baseball and Nerd Baseball, Some Other League, No Name
        league_names = random.sample(league_list, 2)
        self.pitching_data.loc[self.pitching_data['League'] == 'AL', 'League'] = league_names[0]
        self.pitching_data.loc[self.pitching_data['League'] == 'NL', 'League'] = league_names[1]
        self.pitching_data['Leagues'] = self.pitching_data['League'].apply(lambda x: [x])
        self.batting_data.loc[self.batting_data['League'] == 'AL', 'League'] = league_names[0]
        self.batting_data.loc[self.batting_data['League'] == 'NL', 'League'] = league_names[1]
        self.batting_data['Leagues'] = self.batting_data['League'].apply(lambda x: [x])
        return

    def randomize_city_names(self):
        # create team name and mascots, set teams column to match
        city_dict = {}
        current_team_names = self.batting_data.Team.unique()  # get list of current team names
        city_abbrev = [str(name[:3]).upper() for name in city.names]  # city names are imported
        mascots = self.randomize_mascots(len(city.names))
        for ii, team_abbrev in enumerate(city_abbrev):
            city_dict.update({city_abbrev[ii]: [city.names[ii], mascots[ii]]})  # update will use the last unique abbrev

        new_teams = list(random.sample(city_abbrev, len(current_team_names)))
        for ii, team in enumerate(current_team_names):  # do not use a df merge here resets the index, that is bad
            new_team = new_teams[ii]
            mascot = city_dict[new_team][1]
            city_name = city_dict[new_team][0]
            self.pitching_data.replace([team], [new_team], inplace=True)
            self.pitching_data.loc[self.pitching_data['Team'] == new_team, 'City'] = city_name
            self.pitching_data['Teams'] = self.pitching_data['Team'].apply(lambda x: [x])
            self.pitching_data.loc[self.pitching_data['Team'] == new_team, 'Mascot'] = mascot
            self.batting_data.replace([team], [new_team], inplace=True)
            self.batting_data.loc[self.batting_data['Team'] == new_team, 'City'] = city_name
            self.batting_data['Teams'] = self.batting_data['Team'].apply(lambda x: [x])
            self.batting_data.loc[self.batting_data['Team'] == new_team, 'Mascot'] = mascot
        return

    def randomize_mascots(self, length):
        with open('animals.txt', 'r') as f:
            animals = f.readlines()
        animals = [animal.strip() for animal in animals]
        mascots = random.sample(animals, length)
        return mascots

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

        # load new names and reset hashcode index
        self.batting_data['Player'] = random_names[: len(self.batting_data)]  # grab first x rows of list
        self.batting_data = self.batting_data.reset_index()
        self.batting_data['Hashcode'] = self.batting_data['Player'].apply(self.create_hash)
        self.batting_data = self.batting_data.set_index('Hashcode')

        self.pitching_data['Player'] = random_names[-len(self.pitching_data):]  # next x rows list
        self.pitching_data = self.pitching_data.reset_index()
        self.pitching_data['Hashcode'] = self.pitching_data['Player'].apply(self.create_hash)
        self.pitching_data = self.pitching_data.set_index('Hashcode')
        return

    def create_new_season_from_existing(self, load_batter_file, load_pitcher_file):
        if self.pitching_data is None or self.batting_data is None:
            raise Exception('load at least one season of pitching and batting')
        # blend of actual partial season, load org new season from file
        if self.load_seasons[-1] == self.new_season and self.generate_random_data is False:
            self.new_season_pitching_data = self.get_pitching_seasons(load_pitcher_file, [self.new_season])
            self.new_season_batting_data = self.get_batting_seasons(load_batter_file, [self.new_season])
        else:  # handle random league data and or consecutive seasons
            self.new_season_pitching_data = self.pitching_data.copy()
            self.new_season_pitching_data[self.numeric_pcols] = \
                self.new_season_pitching_data[self.numeric_pcols].astype('int')
            self.new_season_pitching_data[self.numeric_pcols] = 0
            self.new_season_pitching_data[['ERA', 'WHIP', 'OBP', 'AVG_faced', 'Total_OB', 'Total_Outs', 'AB',
                                           'Injured Days']] = 0
            self.new_season_pitching_data['Condition'] = 100
            self.new_season_pitching_data.drop(['Total_OB', 'Total_Outs'], axis=1)
            self.new_season_pitching_data['Season'] = str(self.new_season)
            if self.new_season not in self.load_seasons:  # add a year to age if it is the next season
                self.new_season_pitching_data['Age'] = self.new_season_pitching_data['Age'] + 1  # everyone a year older
            self.new_season_pitching_data.fillna(0)

            self.new_season_batting_data = self.batting_data.copy()
            self.new_season_batting_data[self.numeric_bcols] = 0
            self.new_season_batting_data[['AVG', 'OBP', 'SLG', 'OPS', 'Total_OB', 'Total_Outs', 'Injured Days']] = 0
            self.new_season_batting_data['Condition'] = 100
            self.new_season_batting_data.drop(['Total_OB', 'Total_Outs'], axis=1)
            self.new_season_batting_data['Season'] = str(self.new_season)
            if self.new_season not in self.load_seasons:  # add a year to age if it is the next season
                self.new_season_batting_data['Age'] = self.new_season_batting_data['Age'] + 1  # everyone a year older
            self.new_season_batting_data = self.new_season_batting_data.fillna(0)
        return

    def trunc_col(self, df_n, d=3):
        return (df_n * 10 ** d).astype(int) / 10 ** d


if __name__ == '__main__':
    baseball_data = BaseballStatsPreProcess(load_seasons=[2023], new_season=2024,
                                            generate_random_data=True,
                                            load_batter_file='player-stats-Batters.csv',
                                            load_pitcher_file='player-stats-Pitching.csv')
    print(*baseball_data.pitching_data.columns)
    print(*baseball_data.batting_data.columns)
    print(baseball_data.batting_data.Team.unique())
    # print(baseball_data.batting_data.Mascot.unique())
    print(baseball_data.pitching_data.sort_values('Hashcode').to_string())
    print(baseball_data.batting_data.sort_values('Hashcode').to_string())
    # print(baseball_data.new_season_pitching_data.sort_values('Hashcode').to_string())
