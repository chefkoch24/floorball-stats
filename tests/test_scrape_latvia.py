from src.scrape_latvia import _normalize_player_name


def test_normalize_player_name_strips_hash_and_whitespace() -> None:
    assert _normalize_player_name("  #12  Jānis  #Bērziņš  ") == "Jānis Bērziņš"
    assert _normalize_player_name("Miks Ozols#") == "Miks Ozols"
