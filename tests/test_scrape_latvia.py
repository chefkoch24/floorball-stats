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
