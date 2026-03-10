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

## Sweden (StatsApp backend)

Pipeline entrypoint with Sweden backend:

```bash
python -m src.pipeline --backend sweden --competition_id 40693 --season se-25-26 --phase regular-season
```

Make target:

```bash
make refresh-sweden SWEDEN_COMPETITION_ID=40693 SWEDEN_SEASON=se-25-26 PHASE=regular-season
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
