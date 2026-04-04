# README

## Setup

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
```

## Canonical pipeline (scrape -> stats -> markdown)

```bash
make refresh-current-season
```

This runs the new unified module entrypoint:

```bash
python -m src.pipeline --league_id 1890 --season 25-26 --phase regular-season
```

German playoffs (Saisonmanager league id `1963`) via config:

```bash
make refresh-current-season-playoffs
```

## Sweden (StatsApp backend)

Pipeline entrypoint with Sweden backend:

```bash
python -m src.pipeline --backend sweden --competition_id 40693 --season se-25-26 --phase regular-season
```

Make target:

```bash
make refresh-sweden SWEDEN_COMPETITION_ID=40693 SWEDEN_SEASON=se-25-26 PHASE=regular-season
```

Playoffs / smart refresh:

```bash
make refresh-sweden-playoffs
make refresh-sweden-smart
```

## Slovakia (SZFB backend)

Pipeline entrypoint with Slovakia backend:

```bash
python -m src.pipeline --backend slovakia --slovakia_schedule_url "https://www.szfb.sk/sk/stats/results-date/1164/florbalova-extraliga-muzov" --season sk-25-26 --phase regular-season
```

Make target:

```bash
make refresh-slovakia SLOVAKIA_LEAGUE_CONFIG=config/leagues/slovakia-extraliga.json
```

## Latvia (floorball.lv backend)

Pipeline entrypoint with Latvia backend:

```bash
python -m src.pipeline --backend latvia --latvia_calendar_url "https://www.floorball.lv/lv/2025/chempionats/vv/kalendars" --latvia_season_start_year 2025 --season lv-25-26 --phase regular-season
```

Make target:

```bash
make refresh-latvia LATVIA_LEAGUE_CONFIG=config/leagues/latvia-elvi-vv.json
```

## Finland playoffs

Playoffs / smart refresh:

```bash
make refresh-finland-playoffs
make refresh-finland-smart
```

## Player pages from CSV

Build Swedish player stats CSV (all available Sweden season files) and generate unique player pages:

```bash
make refresh-player-stats-sweden
make refresh-player-pages
```

Player pages are canonical per player (`player_uid`) and include:
- current season totals
- current regular-season and playoffs splits
- previous season totals (when older season CSVs exist in `data/`)

Then build or serve the site as usual:

```bash
make html
pelican --autoreload --listen --port 8000
```

## Switzerland (renderengine backend)

Use a schedule page URL (the scraper extracts `game_id` links) or pass explicit IDs:

```bash
python -m src.pipeline --backend switzerland --swiss_schedule_url "https://www.swissunihockey.ch/de/game-detail?game_id=1073873" --season ch-25-26 --phase regular-season
```

```bash
python -m src.pipeline --backend switzerland --swiss_game_ids "1073873,1073807" --season ch-25-26 --phase regular-season
```

Use renderengine schedule parameters with round traversal (recommended for L-UPL/NLB pages):

```bash
python -m src.pipeline --backend switzerland --swiss_league 24 --swiss_season 2025 --swiss_game_class 11 --swiss_group "Gruppe 1" --season ch-25-26 --phase regular-season
```

## Refresh current 1. FBL Herren season data

Defaults:
- `LEAGUE_ID=1890`
- `SEASON=25-26`
- `PHASE=regular-season`

Override:

```bash
make refresh-current-season LEAGUE_ID=1890 SEASON=25-26 PHASE=regular-season
```

Playoffs:

```bash
make refresh-current-season-playoffs GERMANY_PLAYOFFS_LEAGUE_CONFIG=config/leagues/germany-1fbl-playoffs.json
```

## Run tests

```bash
pytest -q
```

## Pipeline without scraping (local/e2e workflows)

```bash
python -m src.pipeline --season 25-26 --phase regular-season --skip_scrape
```

## Start server for development

```bash
pelican --autoreload --listen
```
