import os
import pandas as pd
from supabase import create_client, Client
from dotenv import load_dotenv
load_dotenv()

url: str = os.getenv("SUPABASE_URL")
key: str = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(supabase_url=url, supabase_key=key)

df = pd.read_csv('../data/processed_stats.csv')
# Remove the unnamed column if it exists
if 'Unnamed: 0' in df.columns:
    df.drop(columns=['Unnamed: 0'], inplace=True)


league = {'year': '2023-2024', 'league_name': 'Floorball Bundesliga'}

response = supabase.table('leagues').insert(league).execute()

df_teams = df['team'].unique()
for team in df_teams:
    team = {'team_name': team}#, 'league': league}
    response = supabase.table('teams').insert(team).execute()

teams = supabase.table('teams').select('*').execute()
teams = teams.data
stat_ids, team_ids, points_against = [], [], []
for i, team in enumerate(teams):
    json_string = df[df['team'] == team['team_name']]['points_against'].to_list()[0].replace("'", '"')
    points_against.append(json_string)
    stat_ids.append(i+1)
    team_ids.append(team['team_id'])
    print(team['team_name'])

df['team_id'] = team_ids
df['points_against'] = points_against
df.drop(columns=['team'], inplace=True)

for index, row in df.iterrows():
    response = supabase.table('stats').insert(row.to_dict()).execute()
