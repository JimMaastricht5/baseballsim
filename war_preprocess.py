import pandas as pd
import hashlib


create_hash = lambda text: int(hashlib.sha256(text.encode('utf-8')).hexdigest()[:5], 16)
season = 2023
war_pitcher_file = 'player-stats-Pitching.csv'

df = pd.read_csv(f'{str(season)} war-{war_pitcher_file}')
df = df[df['year_ID']==season]
# df['Team'] = df['Team'].apply(self.update_team_names)
df['Hashcode'] = df['name_common'].apply(create_hash)
df.set_index(keys=['Hashcode'], drop=True, append=False, inplace=True)
print(df.head(5).to_string())
df = df[['WAR', 'salary']]
print(df.head(5).to_string())
print(df.shape)
