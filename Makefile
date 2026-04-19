PY?=
PYTHON ?= python
PELICAN?=pelican
PELICANOPTS=

BASEDIR=$(CURDIR)
INPUTDIR=$(BASEDIR)/content
OUTPUTDIR=$(BASEDIR)/output
CONFFILE=$(BASEDIR)/pelicanconf.py
PUBLISHCONF=$(BASEDIR)/publishconf.py


DEBUG ?= 0
ifeq ($(DEBUG), 1)
	PELICANOPTS += -D
endif

RELATIVE ?= 0
ifeq ($(RELATIVE), 1)
	PELICANOPTS += --relative-urls
endif

SERVER ?= "0.0.0.0"

PORT ?= 0
ifneq ($(PORT), 0)
	PELICANOPTS += -p $(PORT)
endif

# Data pipeline defaults for current 1. FBL Herren season
LEAGUE_ID ?= 1890
SEASON ?= 25-26
PHASE ?= regular-season
GERMANY_PLAYOFFS_LEAGUE_CONFIG ?= config/leagues/germany-1fbl-playoffs.json
GERMANY_PLAYOFFS_CSV ?= data/data_$(SEASON)_playoffs.csv
# Sweden pipeline defaults (SSL StatsApp)
SWEDEN_COMPETITION_ID ?= 40693
SWEDEN_SEASON ?= se-25-26
SWEDEN_PLAYOFFS_LEAGUE_CONFIG ?= config/leagues/sweden-ssl-playoffs.json
SWEDEN_PLAYOFFS_SEASON ?= $(SWEDEN_SEASON)
SWEDEN_PLAYOFFS_CSV ?= data/data_$(SWEDEN_PLAYOFFS_SEASON)_playoffs.csv
# Switzerland pipeline defaults (Swiss Unihockey renderengine)
SWISS_LEAGUE ?= 24
SWISS_SEASON ?= 2025
SWISS_GAME_CLASS ?= 11
SWISS_SEASON_SLUG ?= ch-25-26
SWISS_PLAYOFFS_SLUG ?= ch-25-26
SWISS_GROUP ?= Gruppe 1
SWISS_PLAYOFFS_LEAGUE_CONFIG ?= config/leagues/switzerland-lupl-playoffs.json
SWISS_PLAYOFFS_CSV ?= data/data_$(SWISS_PLAYOFFS_SLUG)_playoffs.csv
# Finland pipeline defaults (F-Liiga)
FINLAND_SEASON ?= fi-25-26
FINLAND_SCHEDULE_URL ?= https://fliiga.com/en/matches/men/
FINLAND_LEAGUE_CONFIG ?= config/leagues/finland-fliiga.json
FINLAND_PLAYOFFS_LEAGUE_CONFIG ?= config/leagues/finland-fliiga-playoffs.json
FINLAND_PLAYOFFS_SEASON ?= $(FINLAND_SEASON)
FINLAND_PLAYOFFS_CSV ?= data/data_$(FINLAND_PLAYOFFS_SEASON)_playoffs.csv
# Czech pipeline defaults (Czech Extraliga config)
CZECH_LEAGUE_CONFIG ?= config/leagues/czech-cez-extraliga.json
CZECH_PLAYOFFS_LEAGUE_CONFIG ?= config/leagues/czech-cez-extraliga-playoffs.json
# Slovakia pipeline defaults (SZFB Extraliga)
SLOVAKIA_LEAGUE_CONFIG ?= config/leagues/slovakia-extraliga.json
SLOVAKIA_PLAYOFFS_LEAGUE_CONFIG ?= config/leagues/slovakia-extraliga-playoffs.json
SLOVAKIA_PLAYOFFS_SEASON ?= sk-25-26
SLOVAKIA_PLAYOFFS_CSV ?= data/data_$(SLOVAKIA_PLAYOFFS_SEASON)_playoffs.csv
# Latvia pipeline defaults (ELVI men)
LATVIA_LEAGUE_CONFIG ?= config/leagues/latvia-elvi-vv.json
LATVIA_PLAYOFFS_LEAGUE_CONFIG ?= config/leagues/latvia-elvi-vv-playoffs.json
LATVIA_PLAYOFFS_SEASON ?= lv-25-26
LATVIA_PLAYOFFS_CSV ?= data/data_$(LATVIA_PLAYOFFS_SEASON)_playoffs.csv
# WFC / IFF competitions
WFC_REGULAR_SEASON_LEAGUE_CONFIG ?= config/leagues/iff-mens-wfc-2024-regular-season.json
WFC_LEAGUE_CONFIG ?= config/leagues/iff-mens-wfc-2024.json

help:
	@echo 'Makefile for a pelican Web site                                           '
	@echo '                                                                          '
	@echo 'Usage:                                                                    '
	@echo '   make html                           (re)generate the web site          '
	@echo '   make clean                          remove the generated files         '
	@echo '   make regenerate                     regenerate files upon modification '
	@echo '   make publish                        generate using production settings '
	@echo '   make serve [PORT=8000]              serve site at http://localhost:8000'
	@echo '   make serve-global [SERVER=0.0.0.0]  serve (as root) to $(SERVER):80    '
	@echo '   make devserver [PORT=8000]          serve and regenerate together      '
	@echo '   make devserver-global               regenerate and serve on 0.0.0.0    '
	@echo '   make refresh-current-season         full pipeline for 1. FBL Herren     '
	@echo '   make refresh-current-season-playoffs playoffs pipeline for 1. FBL Herren '
	@echo '   make refresh-current-season-smart   Germany smart regular/playoffs refresh'
	@echo '   make refresh-sweden                 full pipeline for Sweden (StatsApp) '
	@echo '   make refresh-sweden-playoffs        playoffs pipeline for Sweden SSL     '
	@echo '   make refresh-sweden-smart           Sweden smart regular/playoffs refresh'
	@echo '   make refresh-switzerland            full pipeline for Switzerland       '
	@echo '   make refresh-switzerland-playoffs   Switzerland playoffs pipeline       '
	@echo '   make refresh-finland                full pipeline for Finland (F-Liiga)  '
	@echo '   make refresh-finland-playoffs       playoffs pipeline for Finland (F-Liiga)'
	@echo '   make refresh-finland-smart          Finland smart regular/playoffs refresh'
	@echo '   make refresh-czech                  full pipeline for Czech Extraliga   '
	@echo '   make refresh-czech-playoffs         playoffs pipeline for Czech Extraliga'
	@echo '   make refresh-czech-smart            Czech smart regular/playoffs refresh'
	@echo '   make refresh-slovakia               full pipeline for Slovak Extraliga  '
	@echo '   make refresh-slovakia-playoffs      playoffs pipeline for Slovak Extraliga'
	@echo '   make refresh-latvia                 full pipeline for Latvian ELVI men   '
	@echo '   make refresh-latvia-playoffs        playoffs pipeline for Latvian ELVI men'
	@echo '   make refresh-wfc                    one-off pipeline for WFC/IFF content '
	@echo '   make refresh-all-leagues            run all league pipelines + player stats + html'
	@echo '   make refresh-all-leagues-bootstrap  one-time full regular+playoffs bootstrap + html'
	@echo '   make refresh-everything             alias for refresh-all-leagues        '
	@echo '   make refresh-player-stats           rebuild player stats artifacts       '
	@echo '   make refresh-player-pages           generate player pages (DB-first)     '
	@echo '   make refresh-player-stats-pages     generate player ranking pages (DB-first)'
	@echo '   make refresh-sqlite                 rebuild derived local SQLite mirror   '
	@echo '   make refresh-postgres               rebuild derived Postgres runtime tables'
	@echo '   make refresh-player-stats-germany   rebuild Germany player stats artifacts'
	@echo '   make refresh-player-pages-germany   update Germany player markdown (DB-first)'
	@echo '   make refresh-germany-full           4-step Germany pipeline + html       '
	@echo '   make refresh-player-stats-sweden-only rebuild Sweden player stats artifacts'
	@echo '   make refresh-player-pages-sweden    update Sweden player markdown (DB-first)'
	@echo '   make refresh-sweden-full            4-step Sweden pipeline + html        '
	@echo '   make refresh-player-stats-switzerland rebuild Switzerland player stats artifacts'
	@echo '   make refresh-player-pages-switzerland update Switzerland markdown (DB-first)'
	@echo '   make refresh-switzerland-full       4-step Switzerland pipeline + html   '
	@echo '   make refresh-player-stats-finland   rebuild Finland player stats artifacts'
	@echo '   make refresh-player-pages-finland   update Finland player markdown (DB-first)'
	@echo '   make refresh-finland-full           4-step Finland pipeline + html       '
	@echo '   make refresh-player-stats-czech     rebuild Czech player stats artifacts '
	@echo '   make refresh-player-pages-czech     update Czech player markdown (DB-first)'
	@echo '   make refresh-czech-full             4-step Czech pipeline + html         '
	@echo '   make refresh-player-stats-slovakia  rebuild Slovakia player stats artifacts'
	@echo '   make refresh-player-pages-slovakia  update Slovakia player markdown (DB-first)'
	@echo '   make refresh-slovakia-full          4-step Slovakia pipeline + html      '
	@echo '   make refresh-player-stats-latvia    rebuild Latvia player stats artifacts'
	@echo '   make refresh-player-pages-latvia    update Latvia player markdown (DB-first)'
	@echo '   make refresh-latvia-full            4-step Latvia pipeline + html        '
	@echo '   make refresh-player-stats-wfc       rebuild WFC player stats artifacts   '
	@echo '   make refresh-player-pages-wfc       update WFC player markdown (DB-first)'
	@echo '   make refresh-wfc-players-full       WFC pipeline + WFC player pages + html'
	@echo '                                                                          '
	@echo 'Set the DEBUG variable to 1 to enable debugging, e.g. make DEBUG=1 html   '
	@echo 'Set the RELATIVE variable to 1 to enable relative urls                    '
	@echo 'Set LEAGUE_ID/SEASON/PHASE to override refresh-current-season             '
	@echo 'Set GERMANY_PLAYOFFS_LEAGUE_CONFIG to override refresh-current-season-playoffs'
	@echo 'Set GERMANY_PLAYOFFS_CSV to override refresh-current-season-smart           '
	@echo 'Set SWEDEN_COMPETITION_ID/SWEDEN_SEASON to override refresh-sweden         '
	@echo 'Set SWEDEN_PLAYOFFS_LEAGUE_CONFIG to override refresh-sweden-playoffs      '
	@echo 'Set SWEDEN_PLAYOFFS_* to override refresh-sweden-smart                     '
	@echo 'Set SWISS_* to override refresh-switzerland                                '
	@echo 'Set SWISS_PLAYOFFS_LEAGUE_CONFIG to override refresh-switzerland-playoffs  '
	@echo 'Set FINLAND_LEAGUE_CONFIG to override refresh-finland                       '
	@echo 'Set FINLAND_PLAYOFFS_LEAGUE_CONFIG to override refresh-finland-playoffs     '
	@echo 'Set FINLAND_PLAYOFFS_* to override refresh-finland-smart                    '
	@echo 'Set CZECH_LEAGUE_CONFIG to override refresh-czech                           '
	@echo 'Set CZECH_PLAYOFFS_LEAGUE_CONFIG to override refresh-czech-playoffs         '
	@echo 'Set SLOVAKIA_LEAGUE_CONFIG to override refresh-slovakia                     '
	@echo 'Set SLOVAKIA_PLAYOFFS_LEAGUE_CONFIG to override refresh-slovakia-playoffs   '
	@echo 'Set LATVIA_LEAGUE_CONFIG to override refresh-latvia                         '
	@echo 'Set LATVIA_PLAYOFFS_LEAGUE_CONFIG to override refresh-latvia-playoffs       '
	@echo 'Set WFC_REGULAR_SEASON_LEAGUE_CONFIG/WFC_LEAGUE_CONFIG to override refresh-wfc'
	@echo '                                                                          '

html:
	"$(PELICAN)" "$(INPUTDIR)" -o "$(OUTPUTDIR)" -s "$(CONFFILE)" $(PELICANOPTS)

clean:
	[ ! -d "$(OUTPUTDIR)" ] || rm -rf "$(OUTPUTDIR)"

regenerate:
	"$(PELICAN)" -r "$(INPUTDIR)" -o "$(OUTPUTDIR)" -s "$(CONFFILE)" $(PELICANOPTS)

serve:
	"$(PELICAN)" -l "$(INPUTDIR)" -o "$(OUTPUTDIR)" -s "$(CONFFILE)" $(PELICANOPTS)

serve-global:
	"$(PELICAN)" -l "$(INPUTDIR)" -o "$(OUTPUTDIR)" -s "$(CONFFILE)" $(PELICANOPTS) -b $(SERVER)

devserver:
	"$(PELICAN)" -lr "$(INPUTDIR)" -o "$(OUTPUTDIR)" -s "$(CONFFILE)" $(PELICANOPTS)

devserver-global:
	$(PELICAN) -lr $(INPUTDIR) -o $(OUTPUTDIR) -s $(CONFFILE) $(PELICANOPTS) -b 0.0.0.0

publish:
	"$(PELICAN)" "$(INPUTDIR)" -o "$(OUTPUTDIR)" -s "$(PUBLISHCONF)" $(PELICANOPTS)

refresh-current-season:
	"$(PYTHON)" -m src.pipeline --league_id "$(LEAGUE_ID)" --season "$(SEASON)" --phase "$(PHASE)"

refresh-current-season-playoffs:
	"$(PYTHON)" -m src.pipeline --league_config "$(GERMANY_PLAYOFFS_LEAGUE_CONFIG)"

refresh-current-season-smart:
	$(MAKE) refresh-current-season-playoffs
	@if [ -f "$(GERMANY_PLAYOFFS_CSV)" ] && [ "$$(wc -l < "$(GERMANY_PLAYOFFS_CSV)")" -gt 1 ]; then \
		echo "Playoffs detected in $(GERMANY_PLAYOFFS_CSV); skipping refresh-current-season."; \
	else \
		$(MAKE) refresh-current-season; \
	fi

refresh-sweden:
	"$(PYTHON)" -m src.pipeline --backend sweden --competition_id "$(SWEDEN_COMPETITION_ID)" --season "$(SWEDEN_SEASON)" --phase "$(PHASE)"

refresh-sweden-playoffs:
	"$(PYTHON)" -m src.pipeline --league_config "$(SWEDEN_PLAYOFFS_LEAGUE_CONFIG)"

refresh-sweden-smart:
	$(MAKE) refresh-sweden-playoffs
	@if [ -f "$(SWEDEN_PLAYOFFS_CSV)" ] && [ "$$(wc -l < "$(SWEDEN_PLAYOFFS_CSV)")" -gt 1 ]; then \
		echo "Playoffs detected in $(SWEDEN_PLAYOFFS_CSV); skipping refresh-sweden."; \
	else \
		$(MAKE) refresh-sweden; \
	fi

refresh-switzerland:
	"$(PYTHON)" -m src.pipeline --backend switzerland --swiss_league "$(SWISS_LEAGUE)" --swiss_season "$(SWISS_SEASON)" --swiss_game_class "$(SWISS_GAME_CLASS)" --swiss_group "$(SWISS_GROUP)" --season "$(SWISS_SEASON_SLUG)" --phase "$(PHASE)"

refresh-switzerland-playoffs:
	"$(PYTHON)" -m src.pipeline --league_config "$(SWISS_PLAYOFFS_LEAGUE_CONFIG)"

refresh-finland:
	"$(PYTHON)" -m src.pipeline --league_config "$(FINLAND_LEAGUE_CONFIG)"

refresh-finland-playoffs:
	"$(PYTHON)" -m src.pipeline --league_config "$(FINLAND_PLAYOFFS_LEAGUE_CONFIG)"

refresh-finland-smart:
	$(MAKE) refresh-finland-playoffs
	@if [ -f "$(FINLAND_PLAYOFFS_CSV)" ] && [ "$$(wc -l < "$(FINLAND_PLAYOFFS_CSV)")" -gt 1 ]; then \
		echo "Playoffs detected in $(FINLAND_PLAYOFFS_CSV); skipping refresh-finland."; \
	else \
		$(MAKE) refresh-finland; \
	fi

refresh-czech:
	"$(PYTHON)" -m src.pipeline --league_config "$(CZECH_LEAGUE_CONFIG)"

refresh-czech-playoffs:
	"$(PYTHON)" -m src.pipeline --league_config "$(CZECH_PLAYOFFS_LEAGUE_CONFIG)"

refresh-czech-smart:
	$(MAKE) refresh-czech-playoffs
	@if [ -f "data/data_cz-25-26_playoffs.csv" ] && [ "$$(wc -l < "data/data_cz-25-26_playoffs.csv")" -gt 1 ]; then \
		echo "Playoffs detected in data/data_cz-25-26_playoffs.csv; skipping refresh-czech."; \
	else \
		$(MAKE) refresh-czech; \
	fi

refresh-slovakia:
	"$(PYTHON)" -m src.pipeline --league_config "$(SLOVAKIA_LEAGUE_CONFIG)"

refresh-slovakia-playoffs:
	"$(PYTHON)" -m src.pipeline --league_config "$(SLOVAKIA_PLAYOFFS_LEAGUE_CONFIG)"

refresh-latvia:
	"$(PYTHON)" -m src.pipeline --league_config "$(LATVIA_LEAGUE_CONFIG)"

refresh-latvia-playoffs:
	"$(PYTHON)" -m src.pipeline --league_config "$(LATVIA_PLAYOFFS_LEAGUE_CONFIG)"

refresh-wfc:
	"$(PYTHON)" -m src.pipeline --league_config "$(WFC_REGULAR_SEASON_LEAGUE_CONFIG)"
	"$(PYTHON)" -m src.pipeline --league_config "$(WFC_LEAGUE_CONFIG)"
	"$(PYTHON)" -m src.generate_wfc_tournament_page

refresh-switzerland-smart:
	$(MAKE) refresh-switzerland-playoffs
	@if [ -f "$(SWISS_PLAYOFFS_CSV)" ] && [ "$$(wc -l < "$(SWISS_PLAYOFFS_CSV)")" -gt 1 ]; then \
		echo "Playoffs detected in $(SWISS_PLAYOFFS_CSV); skipping refresh-switzerland."; \
	else \
		$(MAKE) refresh-switzerland; \
	fi

refresh-slovakia-smart:
	$(MAKE) refresh-slovakia-playoffs
	@if [ -f "$(SLOVAKIA_PLAYOFFS_CSV)" ] && [ "$$(wc -l < "$(SLOVAKIA_PLAYOFFS_CSV)")" -gt 1 ]; then \
		echo "Playoffs detected in $(SLOVAKIA_PLAYOFFS_CSV); skipping refresh-slovakia."; \
	else \
		$(MAKE) refresh-slovakia; \
	fi

refresh-latvia-smart:
	$(MAKE) refresh-latvia-playoffs
	@if [ -f "$(LATVIA_PLAYOFFS_CSV)" ] && [ "$$(wc -l < "$(LATVIA_PLAYOFFS_CSV)")" -gt 1 ]; then \
		echo "Playoffs detected in $(LATVIA_PLAYOFFS_CSV); skipping refresh-latvia."; \
	else \
		$(MAKE) refresh-latvia; \
	fi

refresh-all-leagues-bootstrap:
	$(MAKE) refresh-current-season
	$(MAKE) refresh-current-season-playoffs
	$(MAKE) refresh-sweden
	$(MAKE) refresh-sweden-playoffs
	$(MAKE) refresh-switzerland
	$(MAKE) refresh-switzerland-playoffs
	$(MAKE) refresh-finland
	$(MAKE) refresh-finland-playoffs
	$(MAKE) refresh-czech
	$(MAKE) refresh-czech-playoffs
	$(MAKE) refresh-slovakia
	$(MAKE) refresh-slovakia-playoffs
	$(MAKE) refresh-latvia
	$(MAKE) refresh-latvia-playoffs
	$(MAKE) refresh-player-stats
	$(MAKE) refresh-postgres
	$(MAKE) refresh-player-pages
	$(MAKE) refresh-search-index
	$(MAKE) html

refresh-all-leagues:
	$(MAKE) refresh-current-season-smart
	$(MAKE) refresh-sweden-smart
	$(MAKE) refresh-switzerland-smart
	$(MAKE) refresh-finland-smart
	$(MAKE) refresh-czech-smart
	$(MAKE) refresh-slovakia-smart
	$(MAKE) refresh-latvia-smart
	$(MAKE) refresh-player-stats
	$(MAKE) refresh-player-pages
	$(MAKE) refresh-search-index
	$(MAKE) html

refresh-everything:
	$(MAKE) refresh-all-leagues

refresh-player-pages:
	@if [ -z "$${NEON_DATABASE_URL:-$${DATABASE_URL:-}}" ]; then \
		echo "Missing NEON_DATABASE_URL (or DATABASE_URL). Player markdown generation is DB-only."; \
		exit 1; \
	fi
	"$(PYTHON)" -m src.generate_player_markdown --database-url "$${NEON_DATABASE_URL:-$${DATABASE_URL}}" --output-dir "content/players"
	"$(PYTHON)" -m src.generate_player_stats_index_markdown --database-url "$${NEON_DATABASE_URL:-$${DATABASE_URL}}" --output-dir "content/player-stats"

refresh-search-index:
	"$(PYTHON)" -m src.build_search_index --content-dir "content" --output-path "themes/my-theme/static/search/search-index.json"

refresh-player-stats-pages:
	@if [ -z "$${NEON_DATABASE_URL:-$${DATABASE_URL:-}}" ]; then \
		echo "Missing NEON_DATABASE_URL (or DATABASE_URL). Player stats index generation is DB-only."; \
		exit 1; \
	fi
	"$(PYTHON)" -m src.generate_player_stats_index_markdown --database-url "$${NEON_DATABASE_URL:-$${DATABASE_URL}}" --output-dir "content/player-stats"

refresh-player-stats:
	@if [ -z "$${NEON_DATABASE_URL:-$${DATABASE_URL:-}}" ]; then \
		echo "Missing NEON_DATABASE_URL (or DATABASE_URL). Player stats are DB-only."; \
		exit 1; \
	fi
	"$(PYTHON)" -m src.build_player_stats_postgres --database-url "$${NEON_DATABASE_URL:-$${DATABASE_URL}}"

refresh-sqlite:
	"$(PYTHON)" -m src.build_sqlite --db-path "data/stats.db" --data-dir "data"

refresh-postgres:
	@if [ -z "$${NEON_DATABASE_URL:-$${DATABASE_URL:-}}" ]; then \
		echo "Missing NEON_DATABASE_URL (or DATABASE_URL)."; \
		exit 1; \
	fi
	"$(PYTHON)" -m src.build_postgres --database-url "$${NEON_DATABASE_URL:-$${DATABASE_URL}}" --data-dir "data" $$( [ "$${POSTGRES_RESET:-0}" = "1" ] && echo "--reset-existing" )

refresh-player-stats-sweden:
	$(MAKE) refresh-player-stats

refresh-player-stats-germany:
	$(MAKE) refresh-player-stats

refresh-player-pages-germany:
	@if [ -z "$${NEON_DATABASE_URL:-$${DATABASE_URL:-}}" ]; then \
		echo "Missing NEON_DATABASE_URL (or DATABASE_URL). Player markdown generation is DB-only."; \
		exit 1; \
	fi
	"$(PYTHON)" -m src.generate_player_markdown --database-url "$${NEON_DATABASE_URL:-$${DATABASE_URL}}" --output-dir "content/players" --season-prefixes "de" --no-prune
	"$(PYTHON)" -m src.generate_player_stats_index_markdown --database-url "$${NEON_DATABASE_URL:-$${DATABASE_URL}}" --output-dir "content/player-stats" --season-prefixes "de" --no-prune

refresh-germany-full:
	$(MAKE) refresh-current-season
	$(MAKE) refresh-current-season-playoffs
	$(MAKE) refresh-player-stats-germany
	$(MAKE) refresh-player-pages-germany
	$(MAKE) html

refresh-player-stats-sweden-only:
	$(MAKE) refresh-player-stats

refresh-player-pages-sweden:
	@if [ -z "$${NEON_DATABASE_URL:-$${DATABASE_URL:-}}" ]; then \
		echo "Missing NEON_DATABASE_URL (or DATABASE_URL). Player markdown generation is DB-only."; \
		exit 1; \
	fi
	"$(PYTHON)" -m src.generate_player_markdown --database-url "$${NEON_DATABASE_URL:-$${DATABASE_URL}}" --output-dir "content/players" --season-prefixes "se" --no-prune
	"$(PYTHON)" -m src.generate_player_stats_index_markdown --database-url "$${NEON_DATABASE_URL:-$${DATABASE_URL}}" --output-dir "content/player-stats" --season-prefixes "se" --no-prune

refresh-sweden-full:
	$(MAKE) refresh-sweden
	$(MAKE) refresh-sweden-playoffs
	$(MAKE) refresh-player-stats-sweden-only
	$(MAKE) refresh-player-pages-sweden
	$(MAKE) html

refresh-player-stats-switzerland:
	$(MAKE) refresh-player-stats

refresh-player-pages-switzerland:
	@if [ -z "$${NEON_DATABASE_URL:-$${DATABASE_URL:-}}" ]; then \
		echo "Missing NEON_DATABASE_URL (or DATABASE_URL). Player markdown generation is DB-only."; \
		exit 1; \
	fi
	"$(PYTHON)" -m src.generate_player_markdown --database-url "$${NEON_DATABASE_URL:-$${DATABASE_URL}}" --output-dir "content/players" --season-prefixes "ch" --no-prune
	"$(PYTHON)" -m src.generate_player_stats_index_markdown --database-url "$${NEON_DATABASE_URL:-$${DATABASE_URL}}" --output-dir "content/player-stats" --season-prefixes "ch" --no-prune

refresh-switzerland-full:
	$(MAKE) refresh-switzerland
	$(MAKE) refresh-switzerland-playoffs
	$(MAKE) refresh-player-stats-switzerland
	$(MAKE) refresh-player-pages-switzerland
	$(MAKE) html

refresh-player-stats-finland:
	$(MAKE) refresh-player-stats

refresh-player-pages-finland:
	@if [ -z "$${NEON_DATABASE_URL:-$${DATABASE_URL:-}}" ]; then \
		echo "Missing NEON_DATABASE_URL (or DATABASE_URL). Player markdown generation is DB-only."; \
		exit 1; \
	fi
	"$(PYTHON)" -m src.generate_player_markdown --database-url "$${NEON_DATABASE_URL:-$${DATABASE_URL}}" --output-dir "content/players" --season-prefixes "fi" --no-prune
	"$(PYTHON)" -m src.generate_player_stats_index_markdown --database-url "$${NEON_DATABASE_URL:-$${DATABASE_URL}}" --output-dir "content/player-stats" --season-prefixes "fi" --no-prune

refresh-finland-full:
	$(MAKE) refresh-finland
	$(MAKE) refresh-finland-playoffs
	$(MAKE) refresh-player-stats-finland
	$(MAKE) refresh-player-pages-finland
	$(MAKE) html

refresh-player-stats-czech:
	$(MAKE) refresh-player-stats

refresh-player-pages-czech:
	@if [ -z "$${NEON_DATABASE_URL:-$${DATABASE_URL:-}}" ]; then \
		echo "Missing NEON_DATABASE_URL (or DATABASE_URL). Player markdown generation is DB-only."; \
		exit 1; \
	fi
	"$(PYTHON)" -m src.generate_player_markdown --database-url "$${NEON_DATABASE_URL:-$${DATABASE_URL}}" --output-dir "content/players" --season-prefixes "cz" --no-prune
	"$(PYTHON)" -m src.generate_player_stats_index_markdown --database-url "$${NEON_DATABASE_URL:-$${DATABASE_URL}}" --output-dir "content/player-stats" --season-prefixes "cz" --no-prune

refresh-czech-full:
	$(MAKE) refresh-czech
	$(MAKE) refresh-czech-playoffs
	$(MAKE) refresh-player-stats-czech
	$(MAKE) refresh-player-pages-czech
	$(MAKE) html

refresh-player-stats-slovakia:
	$(MAKE) refresh-player-stats

refresh-player-pages-slovakia:
	@if [ -z "$${NEON_DATABASE_URL:-$${DATABASE_URL:-}}" ]; then \
		echo "Missing NEON_DATABASE_URL (or DATABASE_URL). Player markdown generation is DB-only."; \
		exit 1; \
	fi
	"$(PYTHON)" -m src.generate_player_markdown --database-url "$${NEON_DATABASE_URL:-$${DATABASE_URL}}" --output-dir "content/players" --season-prefixes "sk" --no-prune
	"$(PYTHON)" -m src.generate_player_stats_index_markdown --database-url "$${NEON_DATABASE_URL:-$${DATABASE_URL}}" --output-dir "content/player-stats" --season-prefixes "sk" --no-prune

refresh-slovakia-full:
	$(MAKE) refresh-slovakia
	$(MAKE) refresh-slovakia-playoffs
	$(MAKE) refresh-player-stats-slovakia
	$(MAKE) refresh-player-pages-slovakia
	$(MAKE) html

refresh-player-stats-latvia:
	$(MAKE) refresh-player-stats

refresh-player-pages-latvia:
	@if [ -z "$${NEON_DATABASE_URL:-$${DATABASE_URL:-}}" ]; then \
		echo "Missing NEON_DATABASE_URL (or DATABASE_URL). Player markdown generation is DB-only."; \
		exit 1; \
	fi
	"$(PYTHON)" -m src.generate_player_markdown --database-url "$${NEON_DATABASE_URL:-$${DATABASE_URL}}" --output-dir "content/players" --season-prefixes "lv" --no-prune
	"$(PYTHON)" -m src.generate_player_stats_index_markdown --database-url "$${NEON_DATABASE_URL:-$${DATABASE_URL}}" --output-dir "content/player-stats" --season-prefixes "lv" --no-prune

refresh-latvia-full:
	$(MAKE) refresh-latvia
	$(MAKE) refresh-latvia-playoffs
	$(MAKE) refresh-player-stats-latvia
	$(MAKE) refresh-player-pages-latvia
	$(MAKE) html

refresh-player-stats-wfc:
	$(MAKE) refresh-player-stats

refresh-player-pages-wfc:
	@if [ -z "$${NEON_DATABASE_URL:-$${DATABASE_URL:-}}" ]; then \
		echo "Missing NEON_DATABASE_URL (or DATABASE_URL). Player markdown generation is DB-only."; \
		exit 1; \
	fi
	"$(PYTHON)" -m src.generate_player_markdown --database-url "$${NEON_DATABASE_URL:-$${DATABASE_URL}}" --output-dir "content/players" --season-prefixes "wfc" --no-prune
	"$(PYTHON)" -m src.generate_player_stats_index_markdown --database-url "$${NEON_DATABASE_URL:-$${DATABASE_URL}}" --output-dir "content/player-stats" --season-prefixes "wfc" --no-prune

refresh-wfc-full:
	$(MAKE) refresh-wfc
	$(MAKE) html

refresh-wfc-players-full:
	$(MAKE) refresh-wfc
	$(MAKE) refresh-player-stats-wfc
	$(MAKE) refresh-player-pages-wfc
	$(MAKE) html

.PHONY: html help clean regenerate serve serve-global devserver publish refresh-current-season refresh-current-season-playoffs refresh-current-season-smart refresh-sweden refresh-sweden-playoffs refresh-sweden-smart refresh-switzerland refresh-switzerland-playoffs refresh-switzerland-smart refresh-finland refresh-finland-playoffs refresh-finland-smart refresh-czech refresh-czech-playoffs refresh-czech-smart refresh-slovakia refresh-slovakia-playoffs refresh-slovakia-smart refresh-latvia refresh-latvia-playoffs refresh-latvia-smart refresh-wfc refresh-wfc-full refresh-wfc-players-full refresh-all-leagues refresh-all-leagues-bootstrap refresh-everything refresh-player-pages refresh-search-index refresh-player-stats refresh-player-stats-pages refresh-sqlite refresh-postgres refresh-player-stats-sweden refresh-player-stats-germany refresh-player-pages-germany refresh-germany-full refresh-player-stats-sweden-only refresh-player-pages-sweden refresh-sweden-full refresh-player-stats-switzerland refresh-player-pages-switzerland refresh-switzerland-full refresh-player-stats-finland refresh-player-pages-finland refresh-finland-full refresh-player-stats-czech refresh-player-pages-czech refresh-czech-full refresh-player-stats-slovakia refresh-player-pages-slovakia refresh-slovakia-full refresh-player-stats-latvia refresh-player-pages-latvia refresh-latvia-full refresh-player-stats-wfc refresh-player-pages-wfc
