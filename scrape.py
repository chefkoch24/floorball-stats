import json
import pandas as pd
import requests
from tqdm import tqdm
import argparse

class Scraper:
    def __init__(self):
        arg_parser = argparse.ArgumentParser()
        arg_parser.add_argument("--input_path", type=str, default="leagues/1204/schedule.json")
        arg_parser.add_argument("--output_path", type=str, default="data/data_regular_season.csv")
        args, _ = arg_parser.parse_known_args()
        self.input_path = args.input_path
        self.output_path = args.output_path
        self.api = 'https://saisonmanager.de/api/v2/'


    def scrape(self):
        game_id = 0
        games = 'games/'
        all_games = json.loads(requests.request("GET", self.api+self.input_path).content)
        game_ids = [x['game_id'] for x in all_games]
        all_events = []
        for game_id in tqdm(game_ids):
            game = json.loads(requests.request("GET", self.api+games+str(game_id)).content)
            home_team_name = game['home_team_name']
            away_team_name = game['guest_team_name']
            events = game['events']
            for event in events:
                event['event_team'] = home_team_name if event['event_team'] == 'home' else away_team_name
                event['game_id'] = game_id
                event['home_team_name'] = home_team_name
                event['away_team_name'] = away_team_name
                all_events.append(event)

        pd.DataFrame(all_events).to_csv(self.output_path)

if __name__ == '__main__':
    scraper = Scraper()
    scraper.scrape()

