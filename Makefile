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
# Sweden pipeline defaults (SSL StatsApp)
SWEDEN_COMPETITION_ID ?= 40693
SWEDEN_SEASON ?= se-25-26
# Switzerland pipeline defaults (Swiss Unihockey renderengine)
SWISS_LEAGUE ?= 24
SWISS_SEASON ?= 2025
SWISS_GAME_CLASS ?= 11
SWISS_SEASON_SLUG ?= ch-25-26
SWISS_PLAYOFFS_SLUG ?= ch-25-26
SWISS_GROUP ?= Gruppe 1
# Finland pipeline defaults (F-Liiga)
FINLAND_SEASON ?= fi-25-26
FINLAND_SCHEDULE_URL ?= https://fliiga.com/en/matches/men/

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
	@echo '   make refresh-sweden                 full pipeline for Sweden (StatsApp) '
	@echo '   make refresh-switzerland            full pipeline for Switzerland       '
	@echo '   make refresh-switzerland-playoffs   Switzerland playoffs pipeline       '
	@echo '   make refresh-finland                full pipeline for Finland (F-Liiga)  '
	@echo '                                                                          '
	@echo 'Set the DEBUG variable to 1 to enable debugging, e.g. make DEBUG=1 html   '
	@echo 'Set the RELATIVE variable to 1 to enable relative urls                    '
	@echo 'Set LEAGUE_ID/SEASON/PHASE to override refresh-current-season             '
	@echo 'Set SWEDEN_COMPETITION_ID/SWEDEN_SEASON to override refresh-sweden         '
	@echo 'Set SWISS_* to override refresh-switzerland                                '
	@echo 'Set FINLAND_* to override refresh-finland                                   '
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

refresh-sweden:
	"$(PYTHON)" -m src.pipeline --backend sweden --competition_id "$(SWEDEN_COMPETITION_ID)" --season "$(SWEDEN_SEASON)" --phase "$(PHASE)"

refresh-switzerland:
	"$(PYTHON)" -m src.pipeline --backend switzerland --swiss_league "$(SWISS_LEAGUE)" --swiss_season "$(SWISS_SEASON)" --swiss_game_class "$(SWISS_GAME_CLASS)" --swiss_group "$(SWISS_GROUP)" --season "$(SWISS_SEASON_SLUG)" --phase "$(PHASE)"

refresh-switzerland-playoffs:
	"$(PYTHON)" -m src.pipeline --backend switzerland --swiss_league "$(SWISS_LEAGUE)" --swiss_season "$(SWISS_SEASON)" --swiss_game_class "$(SWISS_GAME_CLASS)" --season "$(SWISS_PLAYOFFS_SLUG)" --phase "playoffs"

refresh-finland:
	"$(PYTHON)" -m src.pipeline --backend finland --finland_schedule_url "$(FINLAND_SCHEDULE_URL)" --season "$(FINLAND_SEASON)" --phase "$(PHASE)"

.PHONY: html help clean regenerate serve serve-global devserver publish refresh-current-season refresh-sweden refresh-switzerland refresh-switzerland-playoffs refresh-finland
