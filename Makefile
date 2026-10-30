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

# Current club season. Every league reads its IDs/URLs from
#   config/leagues/<league>-$(CURRENT_SEASON).json           (regular season)
#   config/leagues/<league>-$(CURRENT_SEASON)-playoffs.json  (playoffs)
# Season rollover: add the new config files, bump CURRENT_SEASON and add the
# season to SEASONS in pelicanconf.py. Re-run an old season with
# `make refresh-sweden CURRENT_SEASON=25-26`.
CURRENT_SEASON ?= 26-27
CONFIG_DIR ?= config/leagues

# Germany (1. FBL Herren, Saisonmanager API; needs SAISONMANAGER_API_KEY)
GERMANY_LEAGUE_CONFIG ?= $(CONFIG_DIR)/germany-1fbl-$(CURRENT_SEASON).json
GERMANY_PLAYOFFS_LEAGUE_CONFIG ?= $(CONFIG_DIR)/germany-1fbl-$(CURRENT_SEASON)-playoffs.json
GERMANY_PLAYOFFS_CSV ?= data/data_$(CURRENT_SEASON)_playoffs.csv
# Sweden (SSL, StatsApp API)
SWEDEN_LEAGUE_CONFIG ?= $(CONFIG_DIR)/sweden-ssl-$(CURRENT_SEASON).json
SWEDEN_PLAYOFFS_LEAGUE_CONFIG ?= $(CONFIG_DIR)/sweden-ssl-$(CURRENT_SEASON)-playoffs.json
SWEDEN_PLAYOFFS_CSV ?= data/data_se-$(CURRENT_SEASON)_playoffs.csv
SWEDEN_WOMEN_LEAGUE_CONFIG ?= $(CONFIG_DIR)/sweden-ssl-women-$(CURRENT_SEASON).json
SWEDEN_WOMEN_PLAYOFFS_LEAGUE_CONFIG ?= $(CONFIG_DIR)/sweden-ssl-women-$(CURRENT_SEASON)-playoffs.json
SWEDEN_WOMEN_PLAYOFFS_CSV ?= data/data_sew-$(CURRENT_SEASON)_playoffs.csv
# Women's top leagues reuse their country's backend (prefix = country + "w").
# Playoff configs (except Sweden) still need each league's series format before March.
SWISS_WOMEN_LEAGUE_CONFIG ?= $(CONFIG_DIR)/switzerland-lupl-women-$(CURRENT_SEASON).json
FINLAND_WOMEN_LEAGUE_CONFIG ?= $(CONFIG_DIR)/finland-fliiga-women-$(CURRENT_SEASON).json
CZECH_WOMEN_LEAGUE_CONFIG ?= $(CONFIG_DIR)/czech-cez-extraliga-women-$(CURRENT_SEASON).json
SLOVAKIA_WOMEN_LEAGUE_CONFIG ?= $(CONFIG_DIR)/slovakia-extraliga-women-$(CURRENT_SEASON).json
LATVIA_WOMEN_LEAGUE_CONFIG ?= $(CONFIG_DIR)/latvia-elvi-sv-$(CURRENT_SEASON).json
GERMANY_WOMEN_LEAGUE_CONFIG ?= $(CONFIG_DIR)/germany-1fbl-women-$(CURRENT_SEASON).json
# Switzerland (L-UPL, Swiss Unihockey renderengine)
SWISS_LEAGUE_CONFIG ?= $(CONFIG_DIR)/switzerland-lupl-$(CURRENT_SEASON).json
SWISS_PLAYOFFS_LEAGUE_CONFIG ?= $(CONFIG_DIR)/switzerland-lupl-$(CURRENT_SEASON)-playoffs.json
SWISS_PLAYOFFS_CSV ?= data/data_ch-$(CURRENT_SEASON)_playoffs.csv
# Finland (F-Liiga)
FINLAND_LEAGUE_CONFIG ?= $(CONFIG_DIR)/finland-fliiga-$(CURRENT_SEASON).json
FINLAND_PLAYOFFS_LEAGUE_CONFIG ?= $(CONFIG_DIR)/finland-fliiga-$(CURRENT_SEASON)-playoffs.json
FINLAND_PLAYOFFS_CSV ?= data/data_fi-$(CURRENT_SEASON)_playoffs.csv
# Czech Republic (Livesport Superliga, ceskyflorbal.cz)
CZECH_LEAGUE_CONFIG ?= $(CONFIG_DIR)/czech-cez-extraliga-$(CURRENT_SEASON).json
CZECH_PLAYOFFS_LEAGUE_CONFIG ?= $(CONFIG_DIR)/czech-cez-extraliga-$(CURRENT_SEASON)-playoffs.json
CZECH_PLAYOFFS_CSV ?= data/data_cz-$(CURRENT_SEASON)_playoffs.csv
# ceskyflorbal.cz (Cloudflare) blocks datacenter IPs such as GitHub runners.
# CI therefore builds Czech pages from Neon (CZECH_PIPELINE_ARGS=--events_source db)
# and `make refresh-czech-local` keeps Neon current from a regular connection.
CZECH_PIPELINE_ARGS ?=
CZECH_JOB_LABEL ?= com.floorballconnect.czech-refresh
CZECH_JOB_PLIST ?= $(HOME)/Library/LaunchAgents/$(CZECH_JOB_LABEL).plist
CZECH_JOB_LOG ?= $(HOME)/Library/Logs/floorball-czech-refresh.log
# Slovakia (Extraliga mužov, SZFB)
SLOVAKIA_LEAGUE_CONFIG ?= $(CONFIG_DIR)/slovakia-extraliga-$(CURRENT_SEASON).json
SLOVAKIA_PLAYOFFS_LEAGUE_CONFIG ?= $(CONFIG_DIR)/slovakia-extraliga-$(CURRENT_SEASON)-playoffs.json
SLOVAKIA_PLAYOFFS_CSV ?= data/data_sk-$(CURRENT_SEASON)_playoffs.csv
# Latvia (ELVI men, floorball.lv)
LATVIA_LEAGUE_CONFIG ?= $(CONFIG_DIR)/latvia-elvi-vv-$(CURRENT_SEASON).json
LATVIA_PLAYOFFS_LEAGUE_CONFIG ?= $(CONFIG_DIR)/latvia-elvi-vv-$(CURRENT_SEASON)-playoffs.json
LATVIA_PLAYOFFS_CSV ?= data/data_lv-$(CURRENT_SEASON)_playoffs.csv
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
	@echo '   make refresh-women-leagues          all women top leagues (SE, CH, FI, CZ, SK, LV, DE)'
	@echo '   make refresh-switzerland            full pipeline for Switzerland       '
	@echo '   make refresh-switzerland-playoffs   Switzerland playoffs pipeline       '
	@echo '   make refresh-finland                full pipeline for Finland (F-Liiga)  '
	@echo '   make css                            rebuild the Tailwind theme stylesheet (needs npm install)'
	@echo '   make refresh-finland-playoffs       playoffs pipeline for Finland (F-Liiga)'
	@echo '   make refresh-finland-smart          Finland smart regular/playoffs refresh'
	@echo '   make refresh-czech                  full pipeline for Czech Extraliga   '
	@echo '   make refresh-czech-playoffs         playoffs pipeline for Czech Extraliga'
	@echo '   make refresh-czech-smart            Czech smart regular/playoffs refresh'
	@echo '   make refresh-czech-local            Czech scrape -> Neon (run off GitHub, see README)'
	@echo '   make install-czech-job              install the daily macOS job for refresh-czech-local'
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
	@echo 'Set CURRENT_SEASON=25-26 to run any league target for another season      '
	@echo 'Set <LEAGUE>_LEAGUE_CONFIG / <LEAGUE>_PLAYOFFS_LEAGUE_CONFIG to use other configs'
	@echo 'Germany needs SAISONMANAGER_API_KEY (X-Api-Key, request on saisonmanager.de)'
	@echo 'Set WFC_REGULAR_SEASON_LEAGUE_CONFIG/WFC_LEAGUE_CONFIG to override refresh-wfc'
	@echo '                                                                          '

html:
	"$(PELICAN)" "$(INPUTDIR)" -o "$(OUTPUTDIR)" -s "$(CONFFILE)" $(PELICANOPTS)

clean:
# Theme stylesheet (Tailwind v4): tokens from themes/my-theme/design-system/tokens.json,
# compiled to themes/my-theme/static/css/app.css, which is committed so Netlify needs no Node step.
css:
	"$(PYTHON)" scripts/build_design_tokens.py
	npm run --silent css

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

# $(call smart_refresh,<playoffs target>,<regular target>,<playoffs csv>)
# Playoffs first; once they have rows the regular season is final and skipped.
# A failing playoffs step (not published yet, upstream hiccup) never blocks the
# regular-season refresh.
define smart_refresh
	@if ! $(MAKE) $(1); then echo "[INFO] $(1) failed or not published yet; continuing."; fi
	@if [ -f "$(3)" ] && [ "$$(wc -l < "$(3)")" -gt 1 ]; then \
		echo "Playoffs detected in $(3); skipping $(2)."; \
	else \
		$(MAKE) $(2); \
	fi
endef

refresh-current-season:
	"$(PYTHON)" -m src.pipeline --league_config "$(GERMANY_LEAGUE_CONFIG)"

refresh-current-season-playoffs:
	"$(PYTHON)" -m src.pipeline --league_config "$(GERMANY_PLAYOFFS_LEAGUE_CONFIG)"

refresh-current-season-smart:
	$(call smart_refresh,refresh-current-season-playoffs,refresh-current-season,$(GERMANY_PLAYOFFS_CSV))

refresh-sweden:
	"$(PYTHON)" -m src.pipeline --league_config "$(SWEDEN_LEAGUE_CONFIG)"

refresh-sweden-playoffs:
	"$(PYTHON)" -m src.pipeline --league_config "$(SWEDEN_PLAYOFFS_LEAGUE_CONFIG)"

refresh-sweden-smart:
	$(call smart_refresh,refresh-sweden-playoffs,refresh-sweden,$(SWEDEN_PLAYOFFS_CSV))

refresh-sweden-women:
	"$(PYTHON)" -m src.pipeline --league_config "$(SWEDEN_WOMEN_LEAGUE_CONFIG)"

refresh-sweden-women-playoffs:
	"$(PYTHON)" -m src.pipeline --league_config "$(SWEDEN_WOMEN_PLAYOFFS_LEAGUE_CONFIG)"

refresh-sweden-women-smart:
	$(call smart_refresh,refresh-sweden-women-playoffs,refresh-sweden-women,$(SWEDEN_WOMEN_PLAYOFFS_CSV))

refresh-switzerland-women:
	"$(PYTHON)" -m src.pipeline --league_config "$(SWISS_WOMEN_LEAGUE_CONFIG)"

refresh-finland-women:
	"$(PYTHON)" -m src.pipeline --league_config "$(FINLAND_WOMEN_LEAGUE_CONFIG)"

refresh-czech-women:
	"$(PYTHON)" -m src.pipeline --league_config "$(CZECH_WOMEN_LEAGUE_CONFIG)" $(CZECH_PIPELINE_ARGS)

refresh-slovakia-women:
	"$(PYTHON)" -m src.pipeline --league_config "$(SLOVAKIA_WOMEN_LEAGUE_CONFIG)"

refresh-latvia-women:
	"$(PYTHON)" -m src.pipeline --league_config "$(LATVIA_WOMEN_LEAGUE_CONFIG)"

refresh-germany-women:
	"$(PYTHON)" -m src.pipeline --league_config "$(GERMANY_WOMEN_LEAGUE_CONFIG)"

refresh-women-leagues:
	@failed=""; \
	for target in \
		refresh-sweden-women-smart \
		refresh-switzerland-women \
		refresh-finland-women \
		refresh-czech-women \
		refresh-slovakia-women \
		refresh-latvia-women \
		refresh-germany-women; do \
		echo "==> $$target"; \
		if ! $(MAKE) $$target; then \
			echo "[WARN] step failed: $$target"; \
			failed="$$failed $$target"; \
		fi; \
	done; \
	if [ -n "$$failed" ]; then \
		echo "[WARN] refresh-women-leagues completed with failed steps:$$failed"; \
	fi

refresh-switzerland:
	"$(PYTHON)" -m src.pipeline --league_config "$(SWISS_LEAGUE_CONFIG)"

refresh-switzerland-playoffs:
	"$(PYTHON)" -m src.pipeline --league_config "$(SWISS_PLAYOFFS_LEAGUE_CONFIG)"

refresh-switzerland-smart:
	$(call smart_refresh,refresh-switzerland-playoffs,refresh-switzerland,$(SWISS_PLAYOFFS_CSV))

refresh-finland:
	"$(PYTHON)" -m src.pipeline --league_config "$(FINLAND_LEAGUE_CONFIG)"

refresh-finland-playoffs:
	"$(PYTHON)" -m src.pipeline --league_config "$(FINLAND_PLAYOFFS_LEAGUE_CONFIG)"

refresh-finland-smart:
	$(call smart_refresh,refresh-finland-playoffs,refresh-finland,$(FINLAND_PLAYOFFS_CSV))

refresh-czech:
	"$(PYTHON)" -m src.pipeline --league_config "$(CZECH_LEAGUE_CONFIG)" $(CZECH_PIPELINE_ARGS)

refresh-czech-playoffs:
	"$(PYTHON)" -m src.pipeline --league_config "$(CZECH_PLAYOFFS_LEAGUE_CONFIG)" $(CZECH_PIPELINE_ARGS)

refresh-czech-smart:
	$(call smart_refresh,refresh-czech-playoffs,refresh-czech,$(CZECH_PLAYOFFS_CSV))

# Scrape the Czech league into Neon from a machine ceskyflorbal.cz does not
# block, plus the Czech player stats. Uses a temp dir, so the working copy stays
# untouched; the nightly CI run builds the pages from Neon.
refresh-czech-local:
	@if [ -z "$${NEON_DATABASE_URL:-$${DATABASE_URL:-}}" ]; then \
		echo "Missing NEON_DATABASE_URL (or DATABASE_URL)."; \
		exit 1; \
	fi
	@tmp="$$(mktemp -d)"; trap 'rm -rf "$$tmp"' EXIT; \
	if "$(PYTHON)" -m src.pipeline --league_config "$(CZECH_PLAYOFFS_LEAGUE_CONFIG)" --data_dir "$$tmp/data" --content_dir "$$tmp/content"; then \
		echo "Czech playoffs synced to Neon."; \
	else \
		echo "[INFO] Czech playoffs not available; syncing the regular season."; \
		"$(PYTHON)" -m src.pipeline --league_config "$(CZECH_LEAGUE_CONFIG)" --data_dir "$$tmp/data" --content_dir "$$tmp/content"; \
	fi
	@tmp="$$(mktemp -d)"; trap 'rm -rf "$$tmp"' EXIT; \
	"$(PYTHON)" -m src.pipeline --league_config "$(CZECH_WOMEN_LEAGUE_CONFIG)" --data_dir "$$tmp/data" --content_dir "$$tmp/content" \
		|| echo "[WARN] Czech women's league sync failed."
	"$(PYTHON)" -m src.build_player_stats_postgres --database-url "$${NEON_DATABASE_URL:-$${DATABASE_URL}}" --prefixes cz,czw

# macOS launchd agent running scripts/czech_refresh_job.sh daily at 22:00
# (a missed run is started when the Mac wakes up).
install-czech-job:
	@mkdir -p "$(dir $(CZECH_JOB_PLIST))" "$(dir $(CZECH_JOB_LOG))"
	@sed -e 's#__LABEL__#$(CZECH_JOB_LABEL)#g' -e 's#__REPO__#$(CURDIR)#g' -e 's#__LOG__#$(CZECH_JOB_LOG)#g' \
		scripts/czech-refresh.plist.template > "$(CZECH_JOB_PLIST)"
	@launchctl bootout "gui/$$(id -u)/$(CZECH_JOB_LABEL)" 2>/dev/null || true
	launchctl bootstrap "gui/$$(id -u)" "$(CZECH_JOB_PLIST)"
	@echo "Installed $(CZECH_JOB_PLIST); log: $(CZECH_JOB_LOG)"

uninstall-czech-job:
	@launchctl bootout "gui/$$(id -u)/$(CZECH_JOB_LABEL)" 2>/dev/null || true
	rm -f "$(CZECH_JOB_PLIST)"

refresh-slovakia:
	"$(PYTHON)" -m src.pipeline --league_config "$(SLOVAKIA_LEAGUE_CONFIG)"

refresh-slovakia-playoffs:
	"$(PYTHON)" -m src.pipeline --league_config "$(SLOVAKIA_PLAYOFFS_LEAGUE_CONFIG)"

refresh-slovakia-smart:
	$(call smart_refresh,refresh-slovakia-playoffs,refresh-slovakia,$(SLOVAKIA_PLAYOFFS_CSV))

refresh-latvia:
	"$(PYTHON)" -m src.pipeline --league_config "$(LATVIA_LEAGUE_CONFIG)"

refresh-latvia-playoffs:
	"$(PYTHON)" -m src.pipeline --league_config "$(LATVIA_PLAYOFFS_LEAGUE_CONFIG)"

refresh-latvia-smart:
	$(call smart_refresh,refresh-latvia-playoffs,refresh-latvia,$(LATVIA_PLAYOFFS_CSV))

refresh-wfc:
	@if [ -z "$${NEON_DATABASE_URL:-$${DATABASE_URL:-}}" ]; then \
		echo "Missing NEON_DATABASE_URL (or DATABASE_URL). WFC pipeline is DB-first."; \
		exit 1; \
	fi
	"$(PYTHON)" -m src.pipeline --league_config "$(WFC_REGULAR_SEASON_LEAGUE_CONFIG)" --database_url "$${NEON_DATABASE_URL:-$${DATABASE_URL}}"
	"$(PYTHON)" -m src.pipeline --league_config "$(WFC_LEAGUE_CONFIG)" --database_url "$${NEON_DATABASE_URL:-$${DATABASE_URL}}"
	"$(PYTHON)" -m src.generate_wfc_tournament_page

refresh-all-leagues-bootstrap:
	@failed=""; \
	for target in \
		refresh-current-season \
		refresh-current-season-playoffs \
		refresh-sweden \
		refresh-sweden-playoffs \
		refresh-sweden-women \
		refresh-sweden-women-playoffs \
		refresh-switzerland \
		refresh-switzerland-playoffs \
		refresh-finland \
		refresh-finland-playoffs \
		refresh-czech \
		refresh-czech-playoffs \
		refresh-slovakia \
		refresh-slovakia-playoffs \
		refresh-latvia \
		refresh-latvia-playoffs \
		refresh-player-stats \
		refresh-postgres \
		refresh-player-pages \
		refresh-search-index \
		html; do \
		echo "==> $$target"; \
		if ! $(MAKE) $$target; then \
			echo "[WARN] step failed: $$target"; \
			failed="$$failed $$target"; \
		fi; \
	done; \
	if [ -n "$$failed" ]; then \
		echo "[WARN] refresh-all-leagues-bootstrap completed with failed steps:$$failed"; \
	fi

refresh-all-leagues:
	@failed=""; \
	for target in \
		refresh-current-season-smart \
		refresh-sweden-smart \
		refresh-switzerland-smart \
		refresh-finland-smart \
		refresh-czech-smart \
		refresh-slovakia-smart \
		refresh-latvia-smart \
		refresh-women-leagues \
		refresh-player-stats \
		refresh-player-pages \
		refresh-search-index \
		html; do \
		echo "==> $$target"; \
		if ! $(MAKE) $$target; then \
			echo "[WARN] step failed: $$target"; \
			failed="$$failed $$target"; \
		fi; \
	done; \
	if [ -n "$$failed" ]; then \
		echo "[WARN] refresh-all-leagues completed with failed steps:$$failed"; \
	fi

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
	"$(PYTHON)" -m src.generate_player_markdown --database-url "$${NEON_DATABASE_URL:-$${DATABASE_URL}}" --output-dir "content/players" --season-prefixes "se,sew" --no-prune
	"$(PYTHON)" -m src.generate_player_stats_index_markdown --database-url "$${NEON_DATABASE_URL:-$${DATABASE_URL}}" --output-dir "content/player-stats" --season-prefixes "se,sew" --no-prune

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

.PHONY: html help clean regenerate serve serve-global devserver publish refresh-current-season refresh-current-season-playoffs refresh-current-season-smart refresh-sweden refresh-sweden-playoffs refresh-sweden-smart refresh-switzerland refresh-switzerland-playoffs refresh-switzerland-smart refresh-finland refresh-finland-playoffs refresh-finland-smart refresh-czech refresh-czech-playoffs refresh-czech-smart refresh-czech-local install-czech-job uninstall-czech-job refresh-slovakia refresh-slovakia-playoffs refresh-slovakia-smart refresh-latvia refresh-latvia-playoffs refresh-latvia-smart refresh-wfc refresh-wfc-full refresh-wfc-players-full refresh-all-leagues refresh-all-leagues-bootstrap refresh-everything refresh-player-pages refresh-search-index refresh-player-stats refresh-player-stats-pages refresh-sqlite refresh-postgres refresh-player-stats-sweden refresh-player-stats-germany refresh-player-pages-germany refresh-germany-full refresh-player-stats-sweden-only refresh-player-pages-sweden refresh-sweden-full refresh-player-stats-switzerland refresh-player-pages-switzerland refresh-switzerland-full refresh-player-stats-finland refresh-player-pages-finland refresh-finland-full refresh-player-stats-czech refresh-player-pages-czech refresh-czech-full refresh-player-stats-slovakia refresh-player-pages-slovakia refresh-slovakia-full refresh-player-stats-latvia refresh-player-pages-latvia refresh-latvia-full refresh-player-stats-wfc refresh-player-pages-wfc connect-css connect-html connect-publish connect-import-softr connect-sync-notion

# floorballconnect.com (connect/): its own small Pelican site on the stats design system.
# The stylesheet is committed like the stats one, so Netlify needs no Node step.
connect-css:
	npm run --silent css:connect

connect-html:
	"$(PELICAN)" connect/content -o connect/output -s connect/pelicanconf.py

connect-publish:
	"$(PELICAN)" connect/content -o connect/output -s connect/publishconf.py

connect-import-softr:
	"$(PYTHON)" scripts/import_connect_softr.py

connect-sync-notion:
	"$(PYTHON)" scripts/sync_connect_notion.py
