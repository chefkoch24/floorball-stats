from src.scrape_latvia import _normalize_player_name


def test_normalize_player_name_strips_hash_and_whitespace() -> None:
    assert _normalize_player_name("  #12  Jānis  #Bērziņš  ") == "Jānis Bērziņš"
    assert _normalize_player_name("Miks Ozols#") == "Miks Ozols"


def _calendar_page(options: list[tuple[str, str]]) -> str:
    rendered = "".join(f'<option value="{value}">{label}</option>' for value, label in options)
    return f'<select id="filtrs_kalendars_spelu_veids">{rendered}</select>'


def test_playoff_game_type_is_empty_until_playoffs_are_published() -> None:
    from src.scrape_latvia import _extract_game_types

    regular_only = _calendar_page([("0", "SPĒLES"), ("1", "Regulārās spēles"), ("4", "1. aplis reg.")])
    with_playoffs = _calendar_page([("0", "SPĒLES"), ("1", "Regulārās spēles"), ("2", "Playoff")])

    assert _extract_game_types(regular_only, phase="playoffs") == []
    assert _extract_game_types(regular_only, phase="regular-season") == ["1"]
    assert _extract_game_types(with_playoffs, phase="playoffs") == ["2"]


def test_penalty_type_is_read_from_the_bracket_only() -> None:
    from src.scrape_latvia import _map_penalty_type, _parse_penalty_player

    # Jersey numbers and names used to decide the type: #10 became a 10-minute penalty,
    # #15 a 5-minute one and "Viļums" a match penalty.
    assert _map_penalty_type("#10 Markuss Strazdiņš-Stradiņš (2 min;  nepareizs sitiens)") == "penalty_2"
    assert _map_penalty_type("#15 Krišjānis Tiltiņš (2 min;  nepareizs sitiens)") == "penalty_2"
    assert _map_penalty_type("#7 Kārlis Viļums (2 min;  turēšana)") == "penalty_2"
    assert _map_penalty_type("#9 Rūdolfs Dāvis Maklers (4 min;  bīstams sitiens)") == "penalty_2and2"
    assert _map_penalty_type("#15 Krišjānis Tiltiņš (12 min;  nesportiska uzvedība) (2min sodu izcieš #27)") == "penalty_10"
    assert _map_penalty_type("#14 Oskars Siliņš (24 min;  spēles sods) (Sodu izcieš #27)") == "penalty_ms_full"
    assert _parse_penalty_player("#14 Oskars Siliņš (24 min;  spēles sods) (Sodu izcieš #27)") == "Oskars Siliņš"
