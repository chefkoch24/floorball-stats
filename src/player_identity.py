import re
from typing import Dict, List


ABBREVIATED_FIRST_TOKEN = re.compile(r"^[A-Za-z]\.?$")


def _to_int(value: str) -> int:
    try:
        return int(float(str(value or "0")))
    except (TypeError, ValueError):
        return 0


def is_abbreviated_player_name(name: str) -> bool:
    parts = [part for part in str(name or "").strip().split() if part]
    if len(parts) < 2:
        return False
    return bool(ABBREVIATED_FIRST_TOKEN.match(parts[0]))


def _name_quality_score(name: str, stat_score: int) -> tuple[int, int, int]:
    trimmed = str(name or "").strip()
    parts = [part for part in trimmed.split() if part]
    first_len = len(parts[0]) if parts else 0
    return (
        0 if is_abbreviated_player_name(trimmed) else 1,
        stat_score,
        first_len,
    )


def harmonize_player_display_names(rows: List[Dict[str, str]]) -> List[Dict[str, str]]:
    if not rows:
        return rows

    mapped_rows = [dict(row) for row in rows]
    preferred_name_by_uid: Dict[str, str] = {}

    for row in mapped_rows:
        uid = str(row.get("player_uid", "")).strip().lower()
        name = str(row.get("player", "")).strip()
        if not uid or not name:
            continue
        stat_score = sum(_to_int(row.get(key, "0")) for key in ("goals", "assists", "points", "penalties", "pim"))
        candidate_score = _name_quality_score(name, stat_score)
        current_name = preferred_name_by_uid.get(uid)
        if not current_name:
            preferred_name_by_uid[uid] = name
            row["_display_score"] = candidate_score
            continue
        current_score = _name_quality_score(current_name, stat_score)
        if candidate_score > current_score:
            preferred_name_by_uid[uid] = name

    for row in mapped_rows:
        uid = str(row.get("player_uid", "")).strip().lower()
        preferred_name = preferred_name_by_uid.get(uid)
        if not preferred_name:
            continue
        row["player"] = preferred_name
        if str(row.get("title", "")).strip():
            row["title"] = preferred_name

    for row in mapped_rows:
        row.pop("_display_score", None)
    return mapped_rows
