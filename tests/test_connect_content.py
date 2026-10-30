import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# Appended, not prepended: connect/ has its own pelicanconf.py, which must not shadow the stats one.
sys.path.append(str(ROOT / "connect"))
sys.path.append(str(ROOT / "connect" / "plugins"))
sys.path.append(str(ROOT / "scripts"))

import connect_content as cc  # noqa: E402


def test_stick_record_becomes_a_review_page_item() -> None:
    record = {
        "id": "2df1e0bb-8812-8051-9667-fd93005d056c",
        "fields": {"Name": "AIRLIGHT", "Brand": "ZONE", "Overall Rating": "4", "Shooting Rating": "4.5", "Passing Rating": "4", "Dribbling Rating": "4", "Flex": ["27", "29"], "Images": ["images/sticks/a.webp"]},
        "reviews": [{"id": "r1", "fields": {"Headline": "Good", "Review": "Nice stick", "Overall Rating": 4, "Shooting Rating ": 5, "Display Name": "Viktor j", "Instagram Handle": "@Vjakobsson0", "Anonymous": "with your name/ Instagram"}}],
    }
    item = cc.normalize(cc.BY_KEY["sticks"], record)
    assert item.title == "AIRLIGHT"
    assert item.subtitle == "ZONE"
    assert item.slug == "zone-airlight"
    assert item.ratings == {"Overall": 4.0, "Shooting": 4.5, "Passing": 4.0, "Dribbling": 4.0}
    assert ("Flex", "27, 29") in item.facts
    review = item.reviews[0]
    # The form wrote "Shooting Rating " with a trailing space.
    assert review["ratings"] == {"Overall": 4.0, "Shooting": 5.0}
    assert review["name"] == "Viktor j"
    assert review["instagram"] == "Vjakobsson0"


def test_anonymous_reviews_show_no_name_or_handle() -> None:
    review = cc.review({"Display Name": "Real Name", "Instagram Handle": "real", "Anonymous": "Anonymous", "Review": "Fine"})
    assert review["name"] == "Anonymous"
    assert review["instagram"] == ""


def test_import_drops_identity_of_anonymous_reviewers_and_unlisted_fields() -> None:
    from import_connect_softr import review_fields

    kept = review_fields({"Display Name": "Real Name", "Instagram Handle": "real", "Name": "Real Name", "Email": "x@example.com", "Anonymous": {"label": "Anonymous"}, "Review": "Fine"})
    assert kept == {"Anonymous": {"label": "Anonymous"}, "Review": "Fine"}
    assert review_fields({"Headline": "someone@example.com", "Review": "Great, write me at a.b@example.org"}) == {"Headline": None, "Review": "Great, write me at"}
    named = review_fields({"Display Name": "Nova", "Anonymous": {"label": "with your name/ Instagram"}, "Email": "x@example.com"})
    assert named == {"Display Name": "Nova", "Anonymous": {"label": "with your name/ Instagram"}}


def test_documentary_links_to_its_youtube_video() -> None:
    record = {"id": "d1", "fields": {"Name": "Ein Film", "English Titel": "A film", "Thumbnail": ["https://i.ytimg.com/vi/nZ6ga35sn8w/maxresdefault.jpg"], "EN Subtitles": "yes", "Language": "German", "Year": "2024"}}
    item = cc.normalize(cc.BY_KEY["documentaries"], record)
    assert item.title == "A film"
    assert item.subtitle == "Ein Film"
    assert item.video == "nZ6ga35sn8w"
    assert item.link == "https://www.youtube.com/watch?v=nZ6ga35sn8w"
    assert ("English subtitles", "Yes") in item.facts


def test_youtube_id_reads_every_link_shape() -> None:
    for url in ("https://youtu.be/nZ6ga35sn8w", "https://www.youtube.com/watch?v=nZ6ga35sn8w&t=3", "https://www.youtube.com/embed/nZ6ga35sn8w", "https://i.ytimg.com/vi/nZ6ga35sn8w/hq.jpg"):
        assert cc.youtube_id(url) == "nZ6ga35sn8w"
    assert cc.youtube_id("https://www.youtube.com/@thefloorballshow") == ""


def test_load_gives_unique_slugs_and_urls(tmp_path) -> None:
    drills = {"items": [
        {"id": "a", "fields": {"Name": "1 vs 1", "Categories": ["1vs1"]}},
        {"id": "b", "fields": {"Name": "1 vs 1", "Categories": ["1vs1"]}},
        {"id": "c", "fields": {"Name": ""}},
    ]}
    (tmp_path / "drills.json").write_text(json.dumps(drills), encoding="utf-8")
    (tmp_path / "podcasts.json").write_text(json.dumps({"items": [{"id": "p", "fields": {"Title": "The Floorball Show", "Language": "Latvian"}}]}), encoding="utf-8")
    items = cc.load(tmp_path)
    assert [item.slug for item in items["drills"]] == ["1-vs-1", "1-vs-1-2"]
    assert items["drills"][1].url == "floorball-drills/1-vs-1-2/"
    # Podcasts have no own page; they link to their place on the list.
    assert items["podcasts"][0].url == "floorball-podcasts/#the-floorball-show"
    assert items["sticks"] == []


def test_softr_detail_urls_redirect_to_the_new_pages(tmp_path) -> None:
    import connect_pages as plugin

    (tmp_path / "drills.json").write_text(json.dumps({"items": [{"id": "2621e0bb", "fields": {"Name": "1 vs 1 from Middleline"}}]}), encoding="utf-8")
    lines = plugin.redirects(cc.load(tmp_path))
    assert "/floorball-drill recordId=2621e0bb /floorball-drills/1-vs-1-from-middleline/ 301!" in lines
    # A record that is gone still lands on its list.
    assert "/floorball-drill /floorball-drills/ 301!" in lines


def test_committed_data_loads_for_every_collection() -> None:
    items = cc.load(ROOT / "connect" / "data")
    for collection in cc.COLLECTIONS:
        assert items[collection.key], collection.key
        for item in items[collection.key]:
            assert item.title and item.slug
            for path in [item.image, *(src for review in item.reviews for src in review["images"])]:
                if path and not path.startswith("http"):
                    assert (ROOT / "connect" / "content" / path).exists(), path
