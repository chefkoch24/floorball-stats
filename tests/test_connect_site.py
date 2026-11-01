import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1] / "plugins"))

from connect_site import host_rules  # noqa: E402


def test_main_site_rules_route_its_domain_to_its_folder() -> None:
    redirects = """# Old Softr pages.
/login            /subscribe/                              301
/floorball-stick-details recordId=2df1 /floorball-sticks/zone-airlight/ 301!
/stats            https://stats.floorballconnect.com/       301
"""
    rules = host_rules(redirects, "www.floorballconnect.com", "connect-site", "floorballconnect.com")
    assert rules[0] == "https://floorballconnect.com/* https://www.floorballconnect.com/:splat 301!"
    assert "https://www.floorballconnect.com/login /subscribe/ 301" in rules
    assert "https://www.floorballconnect.com/floorball-stick-details recordId=2df1 /floorball-sticks/zone-airlight/ 301!" in rules
    assert "https://www.floorballconnect.com/stats https://stats.floorballconnect.com/ 301" in rules
    # Specific rules first, the catch-all rewrite last.
    assert rules[-2] == "https://www.floorballconnect.com/connect-site/* https://www.floorballconnect.com/:splat 301!"
    assert rules[-1] == "https://www.floorballconnect.com/* /connect-site/:splat 200!"
