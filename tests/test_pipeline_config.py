import json

import pytest

from src import pipeline
from src.league_config import apply_league_config, load_league_config
from pathlib import Path


CONFIG_DIR = Path(__file__).resolve().parents[1] / "config" / "leagues"


def test_saisonmanager_backend_requires_league_id(tmp_path):
    with pytest.raises(ValueError, match="league_id is required"):
        pipeline.run_pipeline(
            league_id=None,
            season="26-27",
            phase="playoffs",
            backend="saisonmanager",
            data_dir=str(tmp_path / "data"),
            content_dir=str(tmp_path / "content"),
        )


def test_germany_playoffs_config_without_league_id_does_not_fall_back(monkeypatch):
    monkeypatch.setattr("sys.argv", ["pipeline", "--league_config", str(CONFIG_DIR / "germany-1fbl-26-27-playoffs.json")])
    args = pipeline.parse_args()
    apply_league_config(args, load_league_config(args.league_config))

    assert args.league_id is None
    assert args.season == "26-27"


@pytest.mark.parametrize("path", sorted(CONFIG_DIR.glob("*-26-27*.json")), ids=lambda p: p.name)
def test_current_season_configs_match_their_file_name(path):
    cfg = json.loads(path.read_text(encoding="utf-8"))
    expected_phase = "playoffs" if path.stem.endswith("-playoffs") else "regular-season"

    assert cfg["season"].endswith("26-27")
    assert cfg["phase"] == expected_phase


def test_empty_scrape_result_raises_instead_of_building_empty_pages(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "data_lv-26-27_playoffs.csv").write_text('""\n', encoding="utf-8")

    with pytest.raises(ValueError, match="No playoffs games found"):
        pipeline.run_pipeline(
            league_id=None,
            season="lv-26-27",
            phase="playoffs",
            backend="latvia",
            data_dir=str(data_dir),
            content_dir=str(tmp_path / "content"),
            skip_scrape=True,
        )


def test_events_source_db_requires_a_database_url(tmp_path):
    with pytest.raises(ValueError, match="events_source=db needs a database URL"):
        pipeline.run_pipeline(
            league_id=None,
            season="cz-26-27",
            phase="regular-season",
            backend="czech",
            data_dir=str(tmp_path / "data"),
            content_dir=str(tmp_path / "content"),
            database_url=None,
            events_source="db",
        )


def test_events_source_db_rejects_empty_slices(monkeypatch, tmp_path):
    class _Cursor:
        description = [type("Col", (), {"name": name})() for name in ("source_key", "season", "phase", "game_id")]

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return None

        def execute(self, *args):
            return None

        def fetchall(self):
            return []

    class _Conn:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return None

        def cursor(self):
            return _Cursor()

    import psycopg

    monkeypatch.setattr(psycopg, "connect", lambda url: _Conn())

    with pytest.raises(ValueError, match="No playoffs events stored in Postgres for season cz-26-27"):
        pipeline._write_events_from_db("postgresql://test", "cz-26-27", "playoffs", tmp_path / "events.csv")
