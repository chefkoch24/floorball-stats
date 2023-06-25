import json
import pandas as pd
import requests
from tqdm import tqdm


api = 'https://saisonmanager.de/api/v2/'

schedule = 'leagues/1204/schedule.json'
game_id = 0
games = 'games/'
all_games = json.loads(requests.request("GET", api+schedule).content)
game_ids = [x['game_id'] for x in all_games]
all_events = []
for game_id in tqdm(game_ids):
    game = json.loads(requests.request("GET", api+games+str(game_id)).content)
    home_team_name = game['home_team_name']
    away_team_name = game['guest_team_name']
    events = game['events']
    for event in events:
        event['event_team'] = home_team_name if event['event_team'] == 'home' else away_team_name
        event['game_id'] = game_id
        event['home_team_name'] = home_team_name
        event['away_team_name'] = away_team_name
        all_events.append(event)

pd.DataFrame(all_events).to_csv('data/goals_team.csv')


