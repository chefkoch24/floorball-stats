import json
from datetime import date

import pelicanconf


def test_logo_requires_review_scope_and_exact_context(tmp_path, monkeypatch):
    monkeypatch.setattr(pelicanconf, 'TEAM_LOGOS_PATH', tmp_path / 'registry.json')
    monkeypatch.setattr(pelicanconf, 'TEAM_LOGOS_ASSET_DIR', tmp_path)
    monkeypatch.setattr(pelicanconf, 'BUILD_DATE', date(2026, 11, 1))
    (tmp_path / 'club.png').write_bytes(b'fixture')
    record = dict(team='Example', league_prefixes=['se-'], seasons=['26-27'], file='club.png',
                  status='approved', rights_holder='Club', permission_evidence='written permission',
                  source_url='https://example.org/logo', reviewed_on='2026-10-31', scope=['website'])
    def save():
        (tmp_path / 'registry.json').write_text(json.dumps({'logos': [record]}))
    save()
    assert pelicanconf.team_logo('example', 'se-26-27-regular-season') == 'theme/team-logos/club.png'
    assert pelicanconf.team_logo('Example', 'sew-26-27-regular-season') is None
    assert pelicanconf.team_logo('Example', 'se-25-26-regular-season') is None
    for key, value in [('status', 'pending'), ('scope', ['social']), ('permission_evidence', ''),
                       ('expires_on', '2026-10-31'), ('file', '../club.png')]:
        original = record.get(key)
        record[key] = value
        save()
        assert pelicanconf.team_logo('Example', 'se-26-27-regular-season') is None
        if original is None:
            del record[key]
        else:
            record[key] = original
    (tmp_path / 'club.png').unlink()
    save()
    assert pelicanconf.team_logo('Example', 'se-26-27-regular-season') is None


def test_ambiguous_or_invalid_registry_falls_back(tmp_path, monkeypatch):
    monkeypatch.setattr(pelicanconf, 'TEAM_LOGOS_PATH', tmp_path / 'missing.json')
    assert pelicanconf.team_logo('Example', 'se-26-27-regular-season') is None
    assert pelicanconf.team_logo('Example', 'unknown') is None


def test_crest_template_renders_logo_and_monogram():
    from jinja2 import Environment, FileSystemLoader

    env = Environment(loader=FileSystemLoader('themes/my-theme/templates'), autoescape=True)
    env.filters.update(team_logo=lambda name, category: 'theme/team-logos/club.png',
                       crest_index=pelicanconf.crest_index, team_initials=pelicanconf.team_initials)
    template = env.from_string("{% from 'team_crest.html' import crest with context %}{{ crest('Example', 'se-26-27-regular-season') }}")
    html = template.render(SITEURL='')
    assert 'src="/theme/team-logos/club.png"' in html
    assert 'onerror="this.remove()"' in html
    assert '>EXA</span>' in html


def test_current_season_team_and_champions_cup_logos_are_available(monkeypatch):
    from pathlib import Path
    from PIL import Image

    monkeypatch.setattr(pelicanconf, 'BUILD_DATE', date(2026, 11, 1))
    folders = list(Path('content').glob('*26-27-regular-season/teams'))
    folders += list(Path('content').glob('cc*26-27-playoffs/teams'))
    missing = []
    for folder in folders:
        for page in folder.glob('*.md'):
            team = next((line[5:].strip() for line in page.read_text(encoding='utf-8').splitlines()
                         if line.startswith('team:')), None)
            if not team:
                continue
            logo = pelicanconf.team_logo(team, folder.parent.name)
            if not logo:
                missing.append((folder.parent.name, team))
                continue
            with Image.open(pelicanconf.TEAM_LOGOS_ASSET_DIR / Path(logo).name) as image:
                image.verify()
    assert not missing, missing
