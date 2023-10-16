import json

import pandas as pd

from api.database import Base, engine
from api.models import League, Team, Stats

df = pd.read_csv('../data/processed_stats.csv')
# Remove the unnamed column if it exists
if 'Unnamed: 0' in df.columns:
    df.drop(columns=['Unnamed: 0'], inplace=True)

league = {'id': 1, 'year': '2023-2024', 'league_name': 'Floorball Bundesliga'}
pd.DataFrame([league]).to_csv('../data/league.csv', index=False)

df_teams = pd.DataFrame(df['team'].unique())
df_teams['team_id'] = df_teams.index + 1
df_teams.columns = ['team_name', 'team_id']
df_teams.to_csv('../data/teams.csv', index=False)


stat_ids, team_ids, points_against = [], [], []
for i, team in df_teams.iterrows():
    json_string = df[df['team'] == team.team_name]['points_against'].to_list()[0].replace("'", '"')
    points_against.append(json_string)
    stat_ids.append(i+1)
    team_ids.append(team.team_id)
    print(team.team_name)

df['stats_id'] = stat_ids
df['team_id'] = team_ids
df['points_against'] = points_against
df.drop(columns=['team'], inplace=True)
df.to_csv('../data/stats.csv', index=False)