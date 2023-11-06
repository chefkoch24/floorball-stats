import json

import pandas as pd
from sqlalchemy.orm import Session

from api.database import Base, engine
from api.models import League, Team, Stats

df = pd.read_csv('../data/processed_stats.csv')
# Remove the unnamed column if it exists
if 'Unnamed: 0' in df.columns:
    df.drop(columns=['Unnamed: 0'], inplace=True)

session = Session(engine)
Base.metadata.drop_all(engine)
Base.metadata.create_all(engine)
league = {'year': '2023-2024', 'league_name': 'Floorball Bundesliga'}
league = League(**league)
session.add(league)

df_teams = df['team'].unique()
for team in df_teams:
    team = {'team_name': team, 'league': league}
    team = Team(**team)
    session.add(team)

session.commit()
teams = session.query(Team).all()
stat_ids, team_ids, points_against = [], [], []
for i, team in enumerate(teams):
    json_string = df[df['team'] == team.team_name]['points_against'].to_list()[0].replace("'", '"')
    points_against.append(json_string)
    stat_ids.append(i+1)
    team_ids.append(team.team_id)
    print(team.team_name)

df['stats_id'] = stat_ids
df['team_id'] = team_ids
df['points_against'] = points_against
df.drop(columns=['team'], inplace=True)
df.to_sql('stats', engine, if_exists='append', index=False)