import pandas as pd
import hashlib

def retrieve_salary(war_season, war_file_name, hashfunc):
    # war files include full seasons up to and including 2023
    df = pd.read_csv(f'{str(war_season)} war-{war_file_name}')
    df = df[df['year_ID'] == war_season]
    df['Hashcode'] = df['name_common'].apply(hashfunc)
    df.set_index(keys=['Hashcode'], drop=True, append=False, inplace=True)
    df = df[['WAR', 'salary']]
    df = df.dropna()  # about 50% missing
    return df


if __name__ == '__main__':
    create_hash = lambda text: int(hashlib.sha256(text.encode('utf-8')).hexdigest()[:5], 16)

    season = 2023
    war_pitcher_file = 'player-stats-Pitching.csv'
    war_batting_file = 'Player-stats-Batters.csv'
    war_files = [war_pitcher_file, war_batting_file]
    for wf in war_files:
        df = retrieve_salary(season, wf, create_hash)
        print(df.head(5).to_string())
        print(df.shape)
