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
	@echo '   make refresh-all-leagues            run all league pipelines + player stats + html'
	@echo '   make refresh-everything             alias for refresh-all-leagues        '
	@echo '   make refresh-player-stats           build all player stats CSV           '
	@echo '   make refresh-player-pages           generate player pages from CSV       '
	@echo '   make refresh-player-stats-pages     generate season player stats pages   '
	@echo '   make refresh-sqlite                 rebuild derived SQLite from CSV       '
	@echo '   make refresh-postgres               rebuild derived Postgres tables from CSV'
	@echo '   make refresh-player-stats-germany   build Germany-only player stats CSV  '
	@echo '   make refresh-player-pages-germany   update Germany player markdown only  '
	@echo '   make refresh-germany-full           4-step Germany pipeline + html       '
	@echo '   make refresh-player-stats-sweden-only build Sweden-only player stats CSV '
	@echo '   make refresh-player-pages-sweden    update Sweden player markdown only   '
	@echo '   make refresh-sweden-full            4-step Sweden pipeline + html        '
	@echo '   make refresh-player-stats-switzerland build Switzerland-only stats CSV   '
	@echo '   make refresh-player-pages-switzerland update Switzerland markdown only   '
	@echo '   make refresh-switzerland-full       4-step Switzerland pipeline + html   '
	@echo '   make refresh-player-stats-finland   build Finland-only player stats CSV  '
	@echo '   make refresh-player-pages-finland   update Finland player markdown only  '
	@echo '   make refresh-finland-full           4-step Finland pipeline + html       '
	@echo '   make refresh-player-stats-czech     build Czech-only player stats CSV    '
	@echo '   make refresh-player-pages-czech     update Czech player markdown only    '
	@echo '   make refresh-czech-full             4-step Czech pipeline + html         '
	@echo '   make refresh-player-stats-slovakia  build Slovakia-only player stats CSV '
	@echo '   make refresh-player-pages-slovakia  update Slovakia player markdown only '
	@echo '   make refresh-slovakia-full          4-step Slovakia pipeline + html      '
	@echo '   make refresh-player-stats-latvia    build Latvia-only player stats CSV   '
	@echo '   make refresh-player-pages-latvia    update Latvia player markdown only   '
	@echo '   make refresh-latvia-full            4-step Latvia pipeline + html        '
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
	$(MAKE) html

refresh-everything:
	$(MAKE) refresh-all-leagues

refresh-player-pages:
	"$(PYTHON)" -m src.generate_player_markdown --csv-path "data/player_stats.csv" --database-url "$${NEON_DATABASE_URL:-$${DATABASE_URL}}" --output-dir "content/players"
	"$(PYTHON)" -m src.generate_player_stats_index_markdown --csv-path "data/player_stats.csv" --database-url "$${NEON_DATABASE_URL:-$${DATABASE_URL}}" --output-dir "content/player-stats"

refresh-player-stats-pages:
	"$(PYTHON)" -m src.generate_player_stats_index_markdown --csv-path "data/player_stats.csv" --database-url "$${NEON_DATABASE_URL:-$${DATABASE_URL}}" --output-dir "content/player-stats"

refresh-player-stats:
	"$(PYTHON)" -m src.build_player_stats --data-dir "data" --output-csv "data/player_stats.csv"
	"$(PYTHON)" -m src.build_sqlite --db-path "data/stats.db" --player-stats-csv "data/player_stats.csv"

refresh-sqlite:
	"$(PYTHON)" -m src.build_sqlite --db-path "data/stats.db" --data-dir "data" --player-stats-csv "data/player_stats.csv"

refresh-postgres:
	@if [ -z "$${NEON_DATABASE_URL:-$${DATABASE_URL:-}}" ]; then \
		echo "Missing NEON_DATABASE_URL (or DATABASE_URL)."; \
		exit 1; \
	fi
	"$(PYTHON)" -m src.build_postgres --database-url "$${NEON_DATABASE_URL:-$${DATABASE_URL}}" --data-dir "data" --player-stats-csv "data/player_stats.csv" $$( [ "$${POSTGRES_RESET:-0}" = "1" ] && echo "--reset-existing" )

refresh-player-stats-sweden:
	"$(PYTHON)" -m src.build_player_stats --data-dir "data" --output-csv "data/player_stats.csv"

refresh-player-stats-germany:
	"$(PYTHON)" -m src.build_player_stats --data-dir "data" --output-csv "data/player_stats_de.csv" --season-prefixes "de"

refresh-player-pages-germany:
	"$(PYTHON)" -m src.generate_player_markdown --csv-path "data/player_stats_de.csv" --output-dir "content/players" --season-prefixes "de" --no-prune
	"$(PYTHON)" -m src.generate_player_stats_index_markdown --csv-path "data/player_stats_de.csv" --output-dir "content/player-stats" --season-prefixes "de" --no-prune

refresh-germany-full:
	$(MAKE) refresh-current-season
	$(MAKE) refresh-current-season-playoffs
	$(MAKE) refresh-player-stats-germany
	$(MAKE) refresh-player-pages-germany
	$(MAKE) html

refresh-player-stats-sweden-only:
	"$(PYTHON)" -m src.build_player_stats --data-dir "data" --output-csv "data/player_stats_se.csv" --season-prefixes "se"

refresh-player-pages-sweden:
	"$(PYTHON)" -m src.generate_player_markdown --csv-path "data/player_stats_se.csv" --output-dir "content/players" --season-prefixes "se" --no-prune
	"$(PYTHON)" -m src.generate_player_stats_index_markdown --csv-path "data/player_stats_se.csv" --output-dir "content/player-stats" --season-prefixes "se" --no-prune

refresh-sweden-full:
	$(MAKE) refresh-sweden
	$(MAKE) refresh-sweden-playoffs
	$(MAKE) refresh-player-stats-sweden-only
	$(MAKE) refresh-player-pages-sweden
	$(MAKE) html

refresh-player-stats-switzerland:
	"$(PYTHON)" -m src.build_player_stats --data-dir "data" --output-csv "data/player_stats_ch.csv" --season-prefixes "ch"

refresh-player-pages-switzerland:
	"$(PYTHON)" -m src.generate_player_markdown --csv-path "data/player_stats_ch.csv" --output-dir "content/players" --season-prefixes "ch" --no-prune
	"$(PYTHON)" -m src.generate_player_stats_index_markdown --csv-path "data/player_stats_ch.csv" --output-dir "content/player-stats" --season-prefixes "ch" --no-prune

refresh-switzerland-full:
	$(MAKE) refresh-switzerland
	$(MAKE) refresh-switzerland-playoffs
	$(MAKE) refresh-player-stats-switzerland
	$(MAKE) refresh-player-pages-switzerland
	$(MAKE) html

refresh-player-stats-finland:
	"$(PYTHON)" -m src.build_player_stats --data-dir "data" --output-csv "data/player_stats_fi.csv" --season-prefixes "fi"

refresh-player-pages-finland:
	"$(PYTHON)" -m src.generate_player_markdown --csv-path "data/player_stats_fi.csv" --output-dir "content/players" --season-prefixes "fi" --no-prune
	"$(PYTHON)" -m src.generate_player_stats_index_markdown --csv-path "data/player_stats_fi.csv" --output-dir "content/player-stats" --season-prefixes "fi" --no-prune

refresh-finland-full:
	$(MAKE) refresh-finland
	$(MAKE) refresh-finland-playoffs
	$(MAKE) refresh-player-stats-finland
	$(MAKE) refresh-player-pages-finland
	$(MAKE) html

refresh-player-stats-czech:
	"$(PYTHON)" -m src.build_player_stats --data-dir "data" --output-csv "data/player_stats_cz.csv" --season-prefixes "cz"

refresh-player-pages-czech:
	"$(PYTHON)" -m src.generate_player_markdown --csv-path "data/player_stats_cz.csv" --output-dir "content/players" --season-prefixes "cz" --no-prune
	"$(PYTHON)" -m src.generate_player_stats_index_markdown --csv-path "data/player_stats_cz.csv" --output-dir "content/player-stats" --season-prefixes "cz" --no-prune

refresh-czech-full:
	$(MAKE) refresh-czech
	$(MAKE) refresh-czech-playoffs
	$(MAKE) refresh-player-stats-czech
	$(MAKE) refresh-player-pages-czech
	$(MAKE) html

refresh-player-stats-slovakia:
	"$(PYTHON)" -m src.build_player_stats --data-dir "data" --output-csv "data/player_stats_sk.csv" --season-prefixes "sk"

refresh-player-pages-slovakia:
	"$(PYTHON)" -m src.generate_player_markdown --csv-path "data/player_stats_sk.csv" --output-dir "content/players" --season-prefixes "sk" --no-prune
	"$(PYTHON)" -m src.generate_player_stats_index_markdown --csv-path "data/player_stats_sk.csv" --output-dir "content/player-stats" --season-prefixes "sk" --no-prune

refresh-slovakia-full:
	$(MAKE) refresh-slovakia
	$(MAKE) refresh-slovakia-playoffs
	$(MAKE) refresh-player-stats-slovakia
	$(MAKE) refresh-player-pages-slovakia
	$(MAKE) html

refresh-player-stats-latvia:
	"$(PYTHON)" -m src.build_player_stats --data-dir "data" --output-csv "data/player_stats_lv.csv" --season-prefixes "lv"

refresh-player-pages-latvia:
	"$(PYTHON)" -m src.generate_player_markdown --csv-path "data/player_stats_lv.csv" --output-dir "content/players" --season-prefixes "lv" --no-prune
	"$(PYTHON)" -m src.generate_player_stats_index_markdown --csv-path "data/player_stats_lv.csv" --output-dir "content/player-stats" --season-prefixes "lv" --no-prune

refresh-latvia-full:
	$(MAKE) refresh-latvia
	$(MAKE) refresh-latvia-playoffs
	$(MAKE) refresh-player-stats-latvia
	$(MAKE) refresh-player-pages-latvia
	$(MAKE) html

.PHONY: html help clean regenerate serve serve-global devserver publish refresh-current-season refresh-current-season-playoffs refresh-current-season-smart refresh-sweden refresh-sweden-playoffs refresh-sweden-smart refresh-switzerland refresh-switzerland-playoffs refresh-switzerland-smart refresh-finland refresh-finland-playoffs refresh-finland-smart refresh-czech refresh-czech-playoffs refresh-czech-smart refresh-slovakia refresh-slovakia-playoffs refresh-slovakia-smart refresh-latvia refresh-latvia-playoffs refresh-latvia-smart refresh-all-leagues refresh-everything refresh-player-pages refresh-player-stats refresh-player-stats-pages refresh-sqlite refresh-postgres refresh-player-stats-sweden refresh-player-stats-germany refresh-player-pages-germany refresh-germany-full refresh-player-stats-sweden-only refresh-player-pages-sweden refresh-sweden-full refresh-player-stats-switzerland refresh-player-pages-switzerland refresh-switzerland-full refresh-player-stats-finland refresh-player-pages-finland refresh-finland-full refresh-player-stats-czech refresh-player-pages-czech refresh-czech-full refresh-player-stats-slovakia refresh-player-pages-slovakia refresh-slovakia-full refresh-player-stats-latvia refresh-player-pages-latvia refresh-latvia-full
