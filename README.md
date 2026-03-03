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
