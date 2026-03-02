# README

## Scrape data

```python scrape.py```

## Generate content

```python generate_content.py```

## Refresh current 1. FBL Herren season data

Run scraping and content generation in one command:

```bash
make refresh-current-season
```

This uses defaults:
- `LEAGUE_ID=1890`
- `SEASON=25-26`

Override if needed:

```bash
make refresh-current-season LEAGUE_ID=1890 SEASON=25-26
```

## Start server for development

```pelican --autoreload --listen```
