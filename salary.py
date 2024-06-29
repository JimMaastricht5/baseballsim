import pandas as pd
import hashlib
import numpy as np
from sklearn.linear_model import LinearRegression
from sklearn.model_selection import train_test_split


def retrieve_war(war_season, war_file_name, hashfunc, debug=False):
    # war files include full seasons up to and including 2023
    try:
        df = pd.read_csv(f'{str(war_season)} war-{war_file_name}')
    except FileNotFoundError:
        return None
    df = df[df['year_ID'] == war_season]
    df['Hashcode'] = df['name_common'].apply(hashfunc)
    df.set_index(keys=['Hashcode'], drop=True, append=False, inplace=True)
    df = df[['WAR', 'salary']]  # keep salary and rebuild using WAR
    df = df.fillna(0)
    return df


def set_league_min_salary(df):
    if df is not None:
        league_min_salary_2013 = 720000
        league_min_salary = np.min(df['salary'].where(df['salary'] > 0))
        league_min_salary = league_min_salary if league_min_salary >= league_min_salary_2013 else league_min_salary_2013
        df = df.fillna(0)
        df['salary'] = df['salary'].apply(lambda x: league_min_salary if x < league_min_salary else x)
    return df


def impute_war_salary(df, debug=False):
    # na must be replaced with zero before this call
    if df is None:
        return None

    df_fit = df[df['salary'] > 0]  # drop rows that are missing salary data
    x = df_fit['WAR'].to_numpy().reshape(-1, 1)  # create X for model, using only WAR
    y = df_fit['salary'].to_numpy().reshape(-1, 1)
    x_train, x_test, y_train, y_test = train_test_split(x, y, test_size=0.2, random_state=42)  # Split 20% for testing
    model = LinearRegression()  # Create and fit the linear regression model

    model.fit(x_train, y_train)  # simple fit
    training_score = model.score(x_test, y_test)
    if debug:
        print(f'training score is {training_score}')

    # impute missing salary values
    predict_salary = lambda x, y: int(model.predict(np.array(x).reshape(1, -1)) if y <= 0 else y)
    df['salary'] = df.apply(lambda row: predict_salary(row['WAR'], row['salary']), axis=1)
    df = set_league_min_salary(df)
    # print(df)
    return df


def build_war_salary(season, war_file, hash_func, debug=False):
    return impute_war_salary(retrieve_war(season, war_file, hash_func, debug), debug)


if __name__ == '__main__':
    season = 2023
    war_pitcher_file = 'player-stats-Pitching.csv'
    war_batting_file = 'Player-stats-Batters.csv'
    war_files = [war_pitcher_file, war_batting_file]
    for wf in war_files:
        # df_war = retrieve_war(season, wf, lambda text: int(hashlib.sha256(text.encode('utf-8')).hexdigest()[:5], 16))
        # # print(df_war.head(5).to_string())
        # # print(df_war.shape)
        # # print(np.min(df_war['WAR']))
        # # print(np.max(df_war['WAR']))
        # df_salary = impute_war_salary(df_war)
        df_salary = \
            build_war_salary(season, wf, lambda text: int(hashlib.sha256(text.encode('utf-8')).hexdigest()[:5], 16),
                             debug=True)
        print(df_salary.head(5).to_string())
        print(df_salary.shape)
        print(np.min(df_salary['salary']))
        print(np.max(df_salary['salary']))
        print(df_salary[df_salary['salary'] < 720000])
