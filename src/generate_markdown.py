import json

from src.utils import dict_to_markdown_game_stats, dict_to_markdown_team_stats

SEASON = "25-26"
PHASE = "regular-season"

with open('../data/game_stats.json', 'r') as f:
    game_stats = json.load(f)

for gs in game_stats:
    title = f"{gs['game_id']}_{gs['home_team']}_vs_{gs['away_team']}".replace(" ", "_").replace("/", "-").lower()
    title = title.replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")
    md = dict_to_markdown_game_stats(gs, title,  SEASON, PHASE)
    with open("../generated/games/" + title + '.md', 'w', encoding='utf-8') as f:
        f.write(md)

with open('../data/team_stats_enhanced.json', 'r') as f:
    team_stats = json.load(f)

for team, stats in team_stats.items():
    title = (f"{team}-{SEASON}-{PHASE}").replace(" ", "-").lower()
    md = dict_to_markdown_team_stats(stats, team,  SEASON, PHASE)
    title = title.replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")
    with open("../generated/teams/" + title + '.md', 'w', encoding='utf-8') as f:
        f.write(md)