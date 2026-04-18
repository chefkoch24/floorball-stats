import argparse
import base64
import re
import numpy as np
import pandas as pd
import json
from pathlib import Path

from src.social_media.tables import write_home_away_split_table
from src.scheduled_games import EVENT_RESULT, EVENT_SCHEDULED
from src.stats_engine import StatsEngine
from src.team_stats import TeamStats
from src.utils import add_penalties, is_powerplay, is_boxplay, normalize_slug_fragment, safe_div

EVENT_PENALTY = 'penalty'
EVENT_GOAL = 'goal'
OWN_GOAL_LABEL = "Own goal"
OWN_GOAL_TAG = "own_goal"
_OWN_GOAL_MARKERS = {
    "owngoal",
    "selfgoal",
    "autogoal",
    "autogol",
    "sjalvmal",
    "sjalvmaal",
    "eigentor",
    "omamaali",
    "vlastnigol",
    "vlastnibranka",
    "samoboj",
    "samobojczygol",
    "butcontresoncamp",
    "autorete",
}


def _team_identity_key(name: object) -> str:
    raw = str(name or "").strip().lower()
    if not raw:
        return ""
    ascii_name = (
        raw.replace("ä", "ae")
        .replace("ö", "oe")
        .replace("ü", "ue")
        .replace("ß", "ss")
    )
    ascii_name = re.sub(r"[^a-z0-9]+", "", ascii_name)
    # Fold common umlaut transliterations so variants like "vaxjo/vaexjoe"
    # and "zurich/zuerich" resolve to the same identity.
    ascii_name = re.sub(r"([bcdfghjklmnpqrstvwxyz])ae([bcdfghjklmnpqrstvwxyz])", r"\1a\2", ascii_name)
    ascii_name = re.sub(r"([bcdfghjklmnpqrstvwxyz])oe([bcdfghjklmnpqrstvwxyz])", r"\1o\2", ascii_name)
    ascii_name = re.sub(r"([bcdfghjklmnpqrstvwxyz])ue([bcdfghjklmnpqrstvwxyz])", r"\1u\2", ascii_name)
    return ascii_name


def _canonicalize_team_names(df: pd.DataFrame) -> pd.DataFrame:
    columns = [col for col in ("home_team_name", "away_team_name", "event_team") if col in df.columns]
    if not columns:
        return df

    candidates: list[str] = []
    for col in columns:
        values = df[col].dropna().astype(str).str.strip()
        candidates.extend(v for v in values if v)
    if not candidates:
        return df

    counts = pd.Series(candidates).value_counts().to_dict()
    by_key: dict[str, list[str]] = {}
    for name in counts:
        key = _team_identity_key(name)
        if not key:
            continue
        by_key.setdefault(key, []).append(name)

    canonical_for_key: dict[str, str] = {}
    for key, names in by_key.items():
        canonical_for_key[key] = sorted(
            names,
            key=lambda n: (
                -sum(1 for ch in n if ord(ch) > 127),  # prefer original diacritics
                -counts.get(n, 0),                     # then the most frequent
                -len(n),                               # then richest label
                n,
            ),
        )[0]

    name_map: dict[str, str] = {}
    for key, names in by_key.items():
        canonical = canonical_for_key[key]
        for name in names:
            name_map[name] = canonical

    if not name_map:
        return df

    normalized = df.copy()
    for col in columns:
        normalized[col] = (
            normalized[col]
            .astype(str)
            .str.strip()
            .map(lambda value: name_map.get(value, value))
        )
        normalized.loc[normalized[col].isin({"", "nan", "None"}), col] = pd.NA
    return normalized


def _deduplicate_event_rows(df: pd.DataFrame) -> pd.DataFrame:
    # Defensive guard: sources can return repeated records for the same event/game.
    # Drop exact duplicates after team-name normalization to prevent inflated timelines.
    if df.empty:
        return df
    return df.drop_duplicates(ignore_index=True)


from typing import Optional, Tuple, Union, List, Any


def _parse_result_string_score(result_string: object) -> Optional[Tuple[int, int]]:
    if result_string is None:
        return None
    match = pd.Series([result_string]).astype(str).str.extract(r"(\d+)\s*[:-]\s*(\d+)").iloc[0]
    if match.isna().any():
        return None
    return int(match[0]), int(match[1])


def _result_string_indicates_extra_time(result_string: object) -> bool:
    text = str(result_string or "").lower()
    if not text:
        return False
    return any(
        marker in text
        for marker in ("n.p", "penalty", "n.v", "overtime", "ot", "extratime")
    )


def _powerplay_efficiency(goals_in_powerplay: object, powerplay: object) -> Union[float, str]:
    raw = safe_div(goals_in_powerplay, powerplay, 4, True, "n.a.")
    if isinstance(raw, str):
        return raw
    return max(0.0, min(100.0, float(raw)))


def _penalty_kill_efficiency(goals_against_in_boxplay: object, boxplay: object) -> Union[float, str]:
    raw_against = safe_div(goals_against_in_boxplay, boxplay, 4, True, "n.a.")
    if isinstance(raw_against, str):
        return raw_against
    return max(0.0, min(100.0, 100.0 - float(raw_against)))

def _parse_sortkey_to_minute(sortkey: str) -> float:
    try:
        period_str, clock = str(sortkey).split("-", 1)
        minute_str, second_str = clock.split(":", 1)
        period = int(period_str)
        minute = int(minute_str)
        second = int(second_str)
    except (ValueError, AttributeError):
        return 0.0
    # Most providers use period-relative clock (00:00..19:59), but some
    # (notably Czech) provide absolute game clock in sortkey (e.g. 53:05 in P3).
    if period > 1 and minute >= 20:
        return round(minute + second / 60.0, 2)
    return round((period - 1) * 20 + minute + second / 60.0, 2)


def _build_gameflow_timeline(game_df: pd.DataFrame, home_team: str, away_team: str) -> dict:
    periods = pd.to_numeric(game_df.get("period"), errors="coerce").fillna(0).astype(int)
    has_extra_time = bool((periods >= 4).any())

    goals = game_df[game_df["event_type"] == EVENT_GOAL].copy()
    if {"home_goals", "guest_goals"}.issubset(goals.columns):
        goals = goals[~(goals["home_goals"].isna() & goals["guest_goals"].isna())]
    goals = goals[goals["period"].astype(int) <= 4]
    goals = goals.sort_values(by=["period", "sortkey"])

    timeline_minutes = [0.0]
    timeline_diffs = [0]
    timeline_home_goals = [0]
    timeline_away_goals = [0]
    home_goal_minutes = []
    home_goal_diffs = []
    away_goal_minutes = []
    away_goal_diffs = []
    home_penalty_minutes = []
    home_penalty_goals = []
    home_penalty_ends = []
    away_penalty_minutes = []
    away_penalty_goals = []
    away_penalty_ends = []
    home_major_penalty_minutes = []
    away_major_penalty_minutes = []

    def _to_int(value: object) -> int:
        if pd.isna(value):
            return 0
        try:
            return int(value)
        except (TypeError, ValueError):
            return 0

    running_home_goals = 0
    running_away_goals = 0
    goal_times: list[tuple[float, str]] = []

    for _, event in goals.iterrows():
        minute = _parse_sortkey_to_minute(event.get("sortkey", ""))
        scoring_team = str(event.get("event_team", ""))
        if scoring_team == home_team:
            running_home_goals += 1
        elif scoring_team == away_team:
            running_away_goals += 1
        else:
            # Unknown scoring team cannot be placed on a home/away timeline.
            continue

        home_goals = running_home_goals
        away_goals = running_away_goals
        diff = running_home_goals - running_away_goals
        timeline_minutes.append(minute)
        timeline_diffs.append(diff)
        timeline_home_goals.append(home_goals)
        timeline_away_goals.append(away_goals)
        goal_times.append((minute, scoring_team))

        if scoring_team == home_team:
            home_goal_minutes.append(minute)
            home_goal_diffs.append(diff)
        elif scoring_team == away_team:
            away_goal_minutes.append(minute)
            away_goal_diffs.append(diff)

    penalties = game_df[game_df["event_type"] == EVENT_PENALTY].copy()
    penalties = penalties[penalties["period"].astype(int) <= 4]
    penalties = penalties.sort_values(by=["period", "sortkey"])
    goal_events = game_df[game_df["event_type"] == EVENT_GOAL].copy()
    goal_events = goal_events[goal_events["period"].astype(int) <= 4]
    goal_events = goal_events.sort_values(by=["period", "sortkey"])

    timeline_events = list(zip(timeline_minutes, timeline_home_goals, timeline_away_goals))
    if not goal_times:
        goal_times = [
            (_parse_sortkey_to_minute(event.get("sortkey", "")), str(event.get("event_team", "")))
            for _, event in goal_events.iterrows()
        ]

    def _score_at(minute: float) -> tuple[int, int]:
        home = 0
        away = 0
        for m, h, a in timeline_events:
            if m <= minute:
                home = h
                away = a
            else:
                break
        return home, away

    for _, event in penalties.iterrows():
        minute = _parse_sortkey_to_minute(event.get("sortkey", ""))
        home_score, away_score = _score_at(minute)
        penalized_team = str(event.get("event_team", ""))
        penalty_type = str(event.get("penalty_type") or "")
        if penalty_type in {"penalty_10", "penalty_ms_full", "penalty_ms_tech"}:
            if penalized_team == home_team:
                home_major_penalty_minutes.append(minute)
            elif penalized_team == away_team:
                away_major_penalty_minutes.append(minute)
            continue
        if penalty_type not in {"penalty_2", "penalty_2and2"}:
            continue
        duration = 2
        if penalty_type == "penalty_2and2":
            duration = 4
        natural_end = round(minute + duration, 2)
        end_minute = natural_end
        # Minor penalties end early when the non-penalized team scores.
        if penalty_type in {"penalty_2", "penalty_2and2"}:
            for goal_minute, goal_team in goal_times:
                if goal_minute < minute or goal_minute > natural_end:
                    continue
                if goal_team and goal_team != penalized_team:
                    end_minute = goal_minute
                    break

        if penalized_team == home_team:
            home_penalty_minutes.append(minute)
            home_penalty_goals.append(home_score)
            home_penalty_ends.append(end_minute)
        elif penalized_team == away_team:
            away_penalty_minutes.append(minute)
            away_penalty_goals.append(away_score)
            away_penalty_ends.append(end_minute)

    timeline_max_minute = 70.0 if has_extra_time else 60.0

    def _csv(values: List[Union[float, int]]) -> str:
        return ",".join(str(v) for v in values)

    return {
        "timeline_minutes_csv": _csv(timeline_minutes),
        "timeline_diffs_csv": _csv(timeline_diffs),
        "timeline_home_goals_csv": _csv(timeline_home_goals),
        "timeline_away_goals_csv": _csv(timeline_away_goals),
        "home_goal_minutes_csv": _csv(home_goal_minutes),
        "home_goal_diffs_csv": _csv(home_goal_diffs),
        "away_goal_minutes_csv": _csv(away_goal_minutes),
        "away_goal_diffs_csv": _csv(away_goal_diffs),
        "home_penalty_minutes_csv": _csv(home_penalty_minutes),
        "home_penalty_goals_csv": _csv(home_penalty_goals),
        "home_penalty_ends_csv": _csv(home_penalty_ends),
        "away_penalty_minutes_csv": _csv(away_penalty_minutes),
        "away_penalty_goals_csv": _csv(away_penalty_goals),
        "away_penalty_ends_csv": _csv(away_penalty_ends),
        "home_major_penalty_minutes_csv": _csv(home_major_penalty_minutes),
        "away_major_penalty_minutes_csv": _csv(away_major_penalty_minutes),
        "timeline_max_minute": round(timeline_max_minute, 2),
    }


def _clean_nullable_text(value: object) -> Optional[str]:
    if value is None or pd.isna(value):
        return None
    text = str(value).strip()
    return text or None


def _clean_optional_player_ref(value: object) -> Optional[str]:
    text = _clean_nullable_text(value)
    if text in {"0", "0.0"}:
        return None
    return text


def _normalize_marker_token(value: object) -> str:
    text = _clean_nullable_text(value)
    if not text:
        return ""
    return normalize_slug_fragment(text).replace("-", "")


def _is_own_goal_marker(value: object) -> bool:
    token = _normalize_marker_token(value)
    return bool(token) and token in _OWN_GOAL_MARKERS


def _normalize_goal_event_text(scorer_label: str, goal_type: object) -> tuple[str, str, bool]:
    is_own_goal = _is_own_goal_marker(scorer_label) or _is_own_goal_marker(goal_type)
    if is_own_goal:
        return OWN_GOAL_LABEL, OWN_GOAL_TAG, True
    return scorer_label, (_clean_nullable_text(goal_type) or "goal"), False


def _to_int_or_zero(value: object) -> int:
    numeric = pd.to_numeric(value, errors="coerce")
    if pd.isna(numeric):
        return 0
    return int(numeric)


def _json_scalar(value: object) -> object:
    if value is None or pd.isna(value):
        return None
    if isinstance(value, np.generic):
        return value.item()
    return value


def _normalize_player_key(name: object) -> str:
    return normalize_slug_fragment(str(name or "").strip())


def _alternate_player_keys(name: object) -> list[str]:
    raw = str(name or "").strip()
    primary = _normalize_player_key(raw)
    if not primary:
        return []
    keys = [primary]
    parts = [part for part in raw.split() if part]
    if len(parts) == 2:
        swapped = _normalize_player_key(f"{parts[1]} {parts[0]}")
        if swapped and swapped not in keys:
            keys.append(swapped)
    return keys


def _load_player_uid_lookup(player_stats_csv: Path, season: Optional[str], phase: Optional[str]) -> tuple[dict[tuple[str, str], str], dict[str, str]]:
    exact_lookup: dict[tuple[str, str], str] = {}
    fallback_candidates: dict[str, set[str]] = {}
    if not player_stats_csv.exists():
        return exact_lookup, {}

    player_df = pd.read_csv(player_stats_csv, dtype=str).fillna("")
    if season:
        player_df = player_df[player_df["season"].astype(str).str.strip() == str(season).strip()]
    if phase:
        player_df = player_df[player_df["phase"].astype(str).str.strip() == str(phase).strip()]

    for _, row in player_df.iterrows():
        uid = str(row.get("player_uid", "")).strip()
        player_key = _normalize_player_key(row.get("player", ""))
        team_key = _team_identity_key(row.get("team", ""))
        if not uid or not player_key:
            continue
        if team_key:
            exact_lookup.setdefault((team_key, player_key), uid)
        fallback_candidates.setdefault(player_key, set()).add(uid)

    fallback_lookup = {
        player_key: next(iter(uids))
        for player_key, uids in fallback_candidates.items()
        if len(uids) == 1
    }
    return exact_lookup, fallback_lookup


def _resolve_player_uid(
    name: object,
    team: object,
    exact_lookup: dict[tuple[str, str], str],
    fallback_lookup: dict[str, str],
) -> Optional[str]:
    player_keys = _alternate_player_keys(name)
    if not player_keys:
        return None
    team_key = _team_identity_key(team)
    for player_key in player_keys:
        if team_key:
            exact = exact_lookup.get((team_key, player_key))
            if exact:
                return exact
    for player_key in player_keys:
        fallback = fallback_lookup.get(player_key)
        if fallback:
            return fallback
    return None


def _display_minute_for_event(event: pd.Series) -> str:
    period = _to_int_or_zero(event.get("period"))
    sortkey = str(event.get("sortkey") or "")
    clock = sortkey.split("-", 1)[1] if "-" in sortkey else "00:00"
    if period == 4:
        return f"OT {clock}"
    if period == 5:
        return "PS"
    return clock


def _period_break_label(period: int) -> Optional[str]:
    if period == 1:
        return "End 1st period"
    if period == 2:
        return "End 2nd period"
    if period == 3:
        return "End of regulation"
    if period == 4:
        return "End of overtime"
    return None


def _period_break_minute(period: int) -> Optional[int]:
    if period == 1:
        return 20
    if period == 2:
        return 40
    if period == 3:
        return 60
    if period == 4:
        return 70
    return None


def _penalty_type_label(penalty_type: Optional[str]) -> str:
    mapping = {
        "penalty_2": "2 min penalty",
        "penalty_2and2": "2+2 min penalty",
        "penalty_5": "5 min penalty",
        "penalty_10": "10 min misconduct",
        "penalty_ms": "Match penalty",
        "penalty_ms_full": "Match penalty",
        "penalty_ms_tech": "Technical match penalty",
    }
    normalized = _clean_nullable_text(penalty_type)
    return mapping.get(normalized or "", "Penalty")


def _played_events_only(game_df: pd.DataFrame) -> pd.DataFrame:
    if "event_type" not in game_df.columns:
        return game_df.copy()
    return game_df[game_df["event_type"].isin([EVENT_GOAL, EVENT_PENALTY, EVENT_RESULT])].copy()


def _apply_result_summary(
    stats: dict[str, Any],
    *,
    goals_for: int,
    goals_against: int,
    points: int,
    venue: str,
    ot_ps_decision: bool,
) -> None:
    stats["goals"] = goals_for
    stats["goals_against"] = goals_against
    stats["goal_difference"] = goals_for - goals_against
    stats["points"] = points
    stats["games"] = 1

    stats["wins"] = 0
    stats["losses"] = 0
    stats["draws"] = 0
    stats["over_time_wins"] = 0
    stats["over_time_losses"] = 0
    stats["penalty_shootout_wins"] = 0
    stats["penalty_shootout_losses"] = 0

    if goals_for > goals_against:
        if ot_ps_decision:
            stats["over_time_wins"] = 1
        else:
            stats["wins"] = 1
    elif goals_for < goals_against:
        if ot_ps_decision:
            stats["over_time_losses"] = 1
        else:
            stats["losses"] = 1
    else:
        stats["draws"] = 1

    stats["goals_home"] = goals_for if venue == "home" else 0
    stats["goals_away"] = goals_for if venue == "away" else 0
    stats["goals_against_home"] = goals_against if venue == "home" else 0
    stats["goals_against_away"] = goals_against if venue == "away" else 0
    stats["home_points"] = points if venue == "home" else 0
    stats["away_points"] = points if venue == "away" else 0


def _is_scheduled_game(game_df: pd.DataFrame) -> bool:
    return _played_events_only(game_df).empty


def _build_game_events_payload(
    game_df: pd.DataFrame,
    home_team: str,
    away_team: str,
    exact_player_lookup: dict[tuple[str, str], str],
    fallback_player_lookup: dict[str, str],
) -> dict[str, object]:
    relevant_events = game_df[game_df["event_type"].isin([EVENT_GOAL, EVENT_PENALTY])].copy()
    if relevant_events.empty:
        return {"game_events_b64": "", "game_events_count": 0}

    relevant_events = _sort_events_chronologically(relevant_events)
    payload: list[dict[str, object]] = []

    periods_present = {
        _to_int_or_zero(period)
        for period in pd.to_numeric(relevant_events.get("period"), errors="coerce").fillna(0).tolist()
        if _to_int_or_zero(period) > 0
    }

    for _, event in relevant_events.iterrows():
        event_team = _clean_nullable_text(event.get("event_team"))
        if not event_team:
            continue
        side = "home" if event_team == home_team else "away" if event_team == away_team else "neutral"
        event_type = _clean_nullable_text(event.get("event_type")) or ""
        base_event = {
            "minute": _display_minute_for_event(event),
            "period": _to_int_or_zero(event.get("period")),
            "team": event_team,
            "side": side,
            "score": f"{_to_int_or_zero(event.get('home_goals'))}:{_to_int_or_zero(event.get('guest_goals'))}",
        }

        if event_type == EVENT_GOAL:
            scorer_name = _clean_nullable_text(event.get("scorer_name"))
            scorer_number = _clean_optional_player_ref(event.get("scorer_number"))
            assist_name = _clean_nullable_text(event.get("assist_name"))
            assist_number = _clean_optional_player_ref(event.get("assist_number"))
            scorer_label = scorer_name or scorer_number or "Unknown"
            scorer_label, goal_tag, is_own_goal = _normalize_goal_event_text(scorer_label, event.get("goal_type"))
            assist_label = assist_name or assist_number
            payload.append(
                {
                    **base_event,
                    "event_kind": "goal",
                    "title": scorer_label,
                    "title_uid": None if is_own_goal else _resolve_player_uid(scorer_label, event_team, exact_player_lookup, fallback_player_lookup),
                    "assist": assist_label,
                    "assist_uid": _resolve_player_uid(assist_label, event_team, exact_player_lookup, fallback_player_lookup),
                    "tag": goal_tag,
                }
            )
        elif event_type == EVENT_PENALTY:
            penalty_player_name = _clean_nullable_text(event.get("penalty_player_name"))
            payload.append(
                {
                    **base_event,
                    "event_kind": "penalty",
                    "title": _penalty_type_label(event.get("penalty_type")),
                    "assist": penalty_player_name,
                    "assist_uid": _resolve_player_uid(penalty_player_name, event_team, exact_player_lookup, fallback_player_lookup),
                    "tag": _clean_nullable_text(event.get("penalty_type")) or "penalty",
                }
            )

    for period in sorted(periods_present):
        if period not in {1, 2, 3, 4}:
            continue
        if not any(p > period for p in periods_present):
            continue
        label = _period_break_label(period)
        minute = _period_break_minute(period)
        if not label or minute is None:
            continue
        payload.append(
            {
                "minute": f"{minute:02d}:00" if period <= 3 else ("OT 10:00" if period == 4 else ""),
                "period": period,
                "team": None,
                "side": "break",
                "score": None,
                "event_kind": "break",
                "title": label,
                "assist": None,
                "tag": None,
                "_minute_sort": float(minute),
                "_sequence": 99,
            }
        )

    def _sort_value(item: dict[str, object]) -> tuple[float, int]:
        minute_label = str(item.get("minute") or "")
        if "_minute_sort" in item:
            minute_value = float(item["_minute_sort"])
        elif minute_label == "PS":
            minute_value = 80.0
        elif minute_label.startswith("OT "):
            clock = minute_label.split(" ", 1)[1]
            mm, ss = clock.split(":", 1)
            minute_value = 60.0 + int(mm) + int(ss) / 60.0
        else:
            mm, ss = minute_label.split(":", 1)
            minute_value = (int(mm) + int(ss) / 60.0) + max(0, (_to_int_or_zero(item.get("period")) - 1) * 20 if _to_int_or_zero(item.get("period")) <= 3 else 0)
        sequence = int(item.get("_sequence") or (2 if item.get("event_kind") == "break" else 1))
        return (minute_value, sequence)

    payload = sorted(payload, key=_sort_value)
    for item in payload:
        item.pop("_minute_sort", None)
        item.pop("_sequence", None)

    encoded = base64.b64encode(json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")).decode("ascii")
    return {"game_events_b64": encoded, "game_events_count": len(payload)}


def _is_extra_time_period(period: int, ingame_status: Optional[str] = None) -> bool:
    try:
        if int(period) >= 4:
            return True
    except (TypeError, ValueError):
        pass
    status = str(ingame_status or "").strip().lower()
    return status in {"extratime", "penalty_shots"}


def _is_extra_time_decision(period: int, ingame_status: Optional[str] = None, result_string: object = None) -> bool:
    return _is_extra_time_period(period, ingame_status) or _result_string_indicates_extra_time(result_string)


def _points_from_final_score(
    team_goals: int,
    opp_goals: int,
    period: int,
    ingame_status: Optional[str] = None,
    result_string: object = None,
) -> int:
    decided_in_extra_time = _is_extra_time_decision(period, ingame_status, result_string)
    if team_goals > opp_goals:
        return 2 if decided_in_extra_time else 3
    if team_goals == opp_goals:
        return 1
    return 1 if decided_in_extra_time else 0


def stat_goals(events: pd.DataFrame, team: str):
    return int((events[(events['event_type'] == EVENT_GOAL) & (events['event_team'] == team)]).shape[0])

def stat_goals_against(events: pd.DataFrame, team: str):
    return int((events[(events['event_type'] == EVENT_GOAL) & (events['event_team'] != team)]).shape[0])

def stat_games(events: pd.DataFrame, team: str):
    return int(events['game_id'].nunique())


def _final_score_for_team(last_goal: pd.Series, team: str):
    is_home = team == last_goal['home_team_name']
    if is_home:
        team_goals = last_goal['home_goals']
        opp_goals = last_goal['guest_goals']
    else:
        team_goals = last_goal['guest_goals']
        opp_goals = last_goal['home_goals']

    period = last_goal['period']
    ingame_status = last_goal.get('ingame_status')
    if team_goals == opp_goals and _is_extra_time_decision(period, ingame_status, last_goal.get('result_string')):
        parsed = _parse_result_string_score(last_goal.get('result_string'))
        if parsed is not None:
            home_final, away_final = parsed
            if is_home:
                team_goals, opp_goals = home_final, away_final
            else:
                team_goals, opp_goals = away_final, home_final
    return team_goals, opp_goals, period


def _sort_events_chronologically(events: pd.DataFrame) -> pd.DataFrame:
    if events.empty:
        return events
    ordered = events.copy()
    if "sortkey" in ordered.columns:
        ordered["_minute_sort"] = ordered["sortkey"].apply(_parse_sortkey_to_minute)
    else:
        ordered["_minute_sort"] = 0.0
    if "period" in ordered.columns:
        ordered["_period_sort"] = pd.to_numeric(ordered["period"], errors="coerce").fillna(0).astype(int)
    else:
        ordered["_period_sort"] = 0
    ordered = ordered.sort_values(
        by=["_minute_sort", "_period_sort", "sortkey"] if "sortkey" in ordered.columns else ["_minute_sort", "_period_sort"]
    )
    return ordered.drop(columns=["_minute_sort", "_period_sort"], errors="ignore")


def _last_goal_event(events: pd.DataFrame) -> Optional[pd.Series]:
    goals = events[events['event_type'] == EVENT_GOAL]
    if goals.empty:
        return None
    goals = _sort_events_chronologically(goals)
    return goals.iloc[-1]


def _last_goals_per_game(events: pd.DataFrame):
    for _, game_df in events.groupby('game_id'):
        last_goal = _last_goal_event(game_df)
        if last_goal is not None:
            yield last_goal


def _max_in_game_goal_diff(events: pd.DataFrame, team: str) -> int:
    goals = events[events['event_type'] == EVENT_GOAL]
    if goals.empty:
        return 0
    goals = _sort_events_chronologically(goals)
    max_diff = 0
    for _, goal in goals.iterrows():
        team_goals, opp_goals = _team_score_state(goal, team)
        if team_goals is None or opp_goals is None:
            continue
        max_diff = max(max_diff, abs(int(team_goals) - int(opp_goals)))
    return max_diff


def stat_wins(events: pd.DataFrame, team: str):
    wins = 0
    for last_goal in _last_goals_per_game(events):
        team_goals, opp_goals, period = _final_score_for_team(last_goal, team)
        if team_goals > opp_goals and int(period) <= 3:
            wins += 1
    return wins


def stat_over_time_wins(events: pd.DataFrame, team: str):
    wins = 0
    for last_goal in _last_goals_per_game(events):
        team_goals, opp_goals, period = _final_score_for_team(last_goal, team)
        if team_goals > opp_goals and int(period) == 4:
            wins += 1
    return wins


def stat_draws(events: pd.DataFrame, team: str):
    draws = 0
    for last_goal in _last_goals_per_game(events):
        team_goals, opp_goals, _ = _final_score_for_team(last_goal, team)
        if team_goals == opp_goals:
            draws += 1
    return draws


def stat_losses(events: pd.DataFrame, team: str):
    losses = 0
    for last_goal in _last_goals_per_game(events):
        team_goals, opp_goals, period = _final_score_for_team(last_goal, team)
        if team_goals < opp_goals and int(period) <= 3:
            losses += 1
    return losses


def stat_over_time_losses(events: pd.DataFrame, team: str):
    losses = 0
    for last_goal in _last_goals_per_game(events):
        team_goals, opp_goals, period = _final_score_for_team(last_goal, team)
        if team_goals < opp_goals and int(period) == 4:
            losses += 1
    return losses


def stat_penalty_shootout_wins(events: pd.DataFrame, team: str):
    wins = 0
    for last_goal in _last_goals_per_game(events):
        team_goals, opp_goals, period = _final_score_for_team(last_goal, team)
        if team_goals > opp_goals and int(period) == 5:
            wins += 1
    return wins


def stat_penalty_shootout_losses(events: pd.DataFrame, team: str):
    losses = 0
    for last_goal in _last_goals_per_game(events):
        team_goals, opp_goals, period = _final_score_for_team(last_goal, team)
        if team_goals < opp_goals and int(period) == 5:
            losses += 1
    return losses

def stat_points(events: pd.DataFrame, team: str):
    points = 0
    last_goal = _last_goal_event(events)
    if last_goal is not None:
        team_goals, opp_goals, period = _final_score_for_team(last_goal, team)
        points += _points_from_final_score(
            team_goals,
            opp_goals,
            period,
            last_goal.get('ingame_status'),
            last_goal.get('result_string'),
        )
    return points

def stat_goal_difference(events: pd.DataFrame, team: str):
    return stat_goals(events, team) - stat_goals_against(events, team)

def stat_points_max_difference(events: pd.DataFrame, team: str, num_goals: int = 2):
    points = 0
    last_goal = _last_goal_event(events)
    if last_goal is not None:
        team_goals, opp_goals, period = _final_score_for_team(last_goal, team)
        max_in_game_diff = _max_in_game_goal_diff(events, team)
        if max_in_game_diff <= num_goals:
            points += _points_from_final_score(
                team_goals,
                opp_goals,
                period,
                last_goal.get('ingame_status'),
                last_goal.get('result_string'),
            )
    return points

def stat_goals_in_first_period(events: pd.DataFrame, team: str):
    return int(events[(events['event_type'] == EVENT_GOAL) & (events['event_team'] == team) & (events['period'] == 1)].shape[0])

def stat_goals_in_second_period(events: pd.DataFrame, team: str):
    return int(events[(events['event_type'] == EVENT_GOAL) & (events['event_team'] == team) & (events['period'] == 2)].shape[0])

def stat_goals_in_third_period(events: pd.DataFrame, team: str):
    return int(events[(events['event_type'] == EVENT_GOAL) & (events['event_team'] == team) & (events['period'] == 3)].shape[0])

def stat_goals_in_overtime(events: pd.DataFrame, team: str):
    return int(events[(events['event_type'] == EVENT_GOAL) & (events['event_team'] == team) & (events['period'] == 4)].shape[0])


def stat_goals_in_penalty_shootout(events: pd.DataFrame, team: str):
    return int(events[(events['event_type'] == EVENT_GOAL) & (events['event_team'] == team) & (events['period'] == 5)].shape[0])

def stat_goals_in_powerplay(events: pd.DataFrame, team: str):
    penalties_against = []
    penalties_for = []
    goals_in_powerplay = 0
    events_sorted = events.sort_values(by='time_in_s')
    for _, event in events_sorted.iterrows():
        if len(penalties_for) > 0:
            if event['time_in_s'] - penalties_for[0] >= 120:
                penalties_for.pop(0)
        if len(penalties_against) > 0:
            if event['time_in_s'] - penalties_against[0] >= 120:
                penalties_against.pop(0)

        if event['event_type'] == EVENT_PENALTY and event['event_team'] != team:
            penalties_against = add_penalties(event['penalty_type'], penalties_against, event['time_in_s'])
        if event['event_type'] == EVENT_PENALTY and event['event_team'] == team:
            penalties_for = add_penalties(event['penalty_type'], penalties_for, event['time_in_s'])

        if event['event_type'] == EVENT_GOAL and event['event_team'] == team:
            if is_powerplay(event['time_in_s'], penalties_for, penalties_against):
                goals_in_powerplay += 1
                penalties_against.pop(0)

    return goals_in_powerplay

def stat_goals_in_boxplay(events: pd.DataFrame, team: str):
    penalties_against = []
    penalties_for = []
    goals_in_boxplay = 0
    events_sorted = events.sort_values(by='time_in_s')
    for _, event in events_sorted.iterrows():
        if len(penalties_for) > 0:
            if event['time_in_s'] - penalties_for[0] >= 120:
                penalties_for.pop(0)
        if len(penalties_against) > 0:
            if event['time_in_s'] - penalties_against[0] >= 120:
                penalties_against.pop(0)

        if event['event_type'] == EVENT_PENALTY and event['event_team'] != team:
            penalties_against = add_penalties(event['penalty_type'], penalties_against, event['time_in_s'])
        if event['event_type'] == EVENT_PENALTY and event['event_team'] == team:
            penalties_for = add_penalties(event['penalty_type'], penalties_for, event['time_in_s'])

        if event['event_type'] == EVENT_GOAL and event['event_team'] == team:
            if is_boxplay(event['time_in_s'], penalties_for, penalties_against):
                goals_in_boxplay += 1

    return goals_in_boxplay

def stat_goals_against_in_boxplay(events: pd.DataFrame, team: str):
    penalties_against = []
    penalties_for = []
    goals_against_in_boxplay = 0
    events_sorted = events.sort_values(by='time_in_s')
    for _, event in events_sorted.iterrows():
        if len(penalties_for) > 0:
            if event['time_in_s'] - penalties_for[0] >= 120:
                penalties_for.pop(0)
        if len(penalties_against) > 0:
            if event['time_in_s'] - penalties_against[0] >= 120:
                penalties_against.pop(0)

        if event['event_type'] == EVENT_PENALTY and event['event_team'] != team:
            penalties_against = add_penalties(event['penalty_type'], penalties_against, event['time_in_s'])
        if event['event_type'] == EVENT_PENALTY and event['event_team'] == team:
            penalties_for = add_penalties(event['penalty_type'], penalties_for, event['time_in_s'])

        if event['event_type'] == EVENT_GOAL and event['event_team'] != team:
            if is_boxplay(event['time_in_s'], penalties_for, penalties_against):
                goals_against_in_boxplay += 1
                penalties_for.pop(0)

    return goals_against_in_boxplay

def stat_goals_against_in_powerplay(events: pd.DataFrame, team: str):
    penalties_against = []
    penalties_for = []
    goals_against_in_powerplay = 0
    events_sorted = events.sort_values(by='time_in_s')
    for _, event in events_sorted.iterrows():
        if len(penalties_for) > 0:
            if event['time_in_s'] - penalties_for[0] >= 120:
                penalties_for.pop(0)
        if len(penalties_against) > 0:
            if event['time_in_s'] - penalties_against[0] >= 120:
                penalties_against.pop(0)

        if event['event_type'] == EVENT_PENALTY and event['event_team'] != team:
            penalties_against = add_penalties(event['penalty_type'], penalties_against, event['time_in_s'])
        if event['event_type'] == EVENT_PENALTY and event['event_team'] == team:
            penalties_for = add_penalties(event['penalty_type'], penalties_for, event['time_in_s'])

        if event['event_type'] == EVENT_GOAL and event['event_team'] != team:
            if is_powerplay(event['time_in_s'], penalties_for, penalties_against):
                goals_against_in_powerplay += 1

    return goals_against_in_powerplay

def stat_penalties_for_opponent(events: pd.DataFrame, team: str):
    # number of penalities for the opponent
    return int(events[(events['event_type'] == EVENT_PENALTY) & (events['event_team'] != team)].shape[0])

def stat_penalties_for_team(events: pd.DataFrame, team: str):
    # number of penalities for the team
    return int(events[(events['event_type'] == EVENT_PENALTY) & (events['event_team'] == team)].shape[0])

def _penalty_opportunity_segments(bucket: pd.DataFrame) -> int:
    explicit_segments = 0
    has_ten_minute_penalty = False
    has_match_penalty = False

    for _, event in bucket.iterrows():
        penalty_type = event['penalty_type']
        if penalty_type == 'penalty_2':
            explicit_segments += 1
        elif penalty_type == 'penalty_2and2':
            explicit_segments += 2
        elif penalty_type == 'penalty_10':
            has_ten_minute_penalty = True
        elif penalty_type in {'penalty_ms_full', 'penalty_ms_tech'}:
            has_match_penalty = True

    # A 10-minute misconduct still carries one 2-minute powerplay segment.
    if has_ten_minute_penalty and explicit_segments < 1:
        explicit_segments = 1

    # Match penalties imply an additional 2+2 even if the feed omitted it.
    if has_match_penalty and explicit_segments < 2:
        explicit_segments = 2

    return int(explicit_segments)

def stat_powerplay(events: pd.DataFrame, team: str):
    penalties = events[events['event_type'] == EVENT_PENALTY].sort_values(by='time_in_s')
    powerplays = 0

    for _, bucket in penalties.groupby('time_in_s', sort=True):
        opponent_segments = _penalty_opportunity_segments(bucket[bucket['event_team'] != team])
        team_segments = _penalty_opportunity_segments(bucket[bucket['event_team'] == team])
        powerplays += max(0, opponent_segments - team_segments)

    return int(powerplays)

def _events_for_period(events: pd.DataFrame, period: int) -> pd.DataFrame:
    return events[events['period'] == period]

def stat_powerplay_first_period(events: pd.DataFrame, team: str):
    return stat_powerplay(_events_for_period(events, 1), team)

def stat_powerplay_second_period(events: pd.DataFrame, team: str):
    return stat_powerplay(_events_for_period(events, 2), team)

def stat_powerplay_third_period(events: pd.DataFrame, team: str):
    return stat_powerplay(_events_for_period(events, 3), team)

def stat_powerplay_overtime(events: pd.DataFrame, team: str):
    return stat_powerplay(_events_for_period(events, 4), team)


def stat_boxplay(events: pd.DataFrame, team: str):
    penalties = events[events['event_type'] == EVENT_PENALTY].sort_values(by='time_in_s')
    boxplays = 0

    for _, bucket in penalties.groupby('time_in_s', sort=True):
        team_segments = _penalty_opportunity_segments(bucket[bucket['event_team'] == team])
        opponent_segments = _penalty_opportunity_segments(bucket[bucket['event_team'] != team])
        boxplays += max(0, team_segments - opponent_segments)

    return int(boxplays)

def stat_boxplay_first_period(events: pd.DataFrame, team: str):
    return stat_boxplay(_events_for_period(events, 1), team)

def stat_boxplay_second_period(events: pd.DataFrame, team: str):
    return stat_boxplay(_events_for_period(events, 2), team)

def stat_boxplay_third_period(events: pd.DataFrame, team: str):
    return stat_boxplay(_events_for_period(events, 3), team)

def stat_boxplay_overtime(events: pd.DataFrame, team: str):
    return stat_boxplay(_events_for_period(events, 4), team)

def _stat_points_after_period(events: pd.DataFrame, team: str, period: int):
    points = 0
    period_events = events[((events['event_type'] == EVENT_GOAL) | (events['event_type'] == EVENT_PENALTY)) & (events['period'] <= period)]
    if not period_events.empty:
        last_goal = _sort_events_chronologically(period_events).iloc[-1]
        if team == last_goal['home_team_name']:
            team_goals = last_goal['home_goals']
            opp_goals = last_goal['guest_goals']
        else:
            team_goals = last_goal['guest_goals']
            opp_goals = last_goal['home_goals']
        if team_goals > opp_goals:
            points += 3
        elif team_goals == opp_goals:
            points += 1
    return points


def stat_points_after_first_period(events: pd.DataFrame, team: str):
    return _stat_points_after_period(events, team, period=1)



def stat_points_after_second_period(events: pd.DataFrame, team: str):
    return _stat_points_after_period(events, team, period=2)

def stat_points_after_third_period(events: pd.DataFrame, team: str):
    return _stat_points_after_period(events, team, period=3)

def stat_points_after_55_minutes(events: pd.DataFrame, team: str):
    return _stat_points_after_minute(events, team, minute=55)

def stat_points_after_58_minutes(events: pd.DataFrame, team: str):
    return _stat_points_after_minute(events, team, minute=58)

def stat_points_after_59_minutes(events: pd.DataFrame, team: str):
    return _stat_points_after_minute(events, team, minute=59)

def _stat_points_after_minute(events: pd.DataFrame, team: str, minute: int):
    points = 0
    period_events = events[((events['event_type'] == EVENT_GOAL) | (events['event_type'] == EVENT_PENALTY))  &  (events.get('time_in_s', 0) <= minute * 60)]
    if not period_events.empty:
        last_goal = _sort_events_chronologically(period_events).iloc[-1]
        team_goals, opp_goals, period = _final_score_for_team(last_goal, team)
        points += _points_from_final_score(
            team_goals,
            opp_goals,
            period,
            last_goal.get('ingame_status'),
            last_goal.get('result_string'),
        )
    return points

def stat_win_1(events: pd.DataFrame, team: str):
    win_1 = 0
    last_goal = _last_goal_event(events)
    if last_goal is not None:
        if team == last_goal['home_team_name']:
            diff = last_goal['home_goals'] - last_goal['guest_goals']
        else:
            diff = last_goal['guest_goals'] - last_goal['home_goals']
        if diff == 1:
            win_1 += 1
    return win_1

def stat_loss_1(events: pd.DataFrame, team: str):
    loss_1 = 0
    last_goal = _last_goal_event(events)
    if last_goal is not None:
        if team == last_goal['home_team_name']:
            diff = last_goal['home_goals'] - last_goal['guest_goals']
        else:
            diff = last_goal['guest_goals'] - last_goal['home_goals']
        if diff == -1:
            loss_1 += 1
    return loss_1

def stat_points_more_2_difference(events: pd.DataFrame, team: str):
    points = 0
    last_goal = _last_goal_event(events)
    if last_goal is not None:
        team_goals, opp_goals, period = _final_score_for_team(last_goal, team)
        max_in_game_diff = _max_in_game_goal_diff(events, team)
        if max_in_game_diff > 2:
            points += _points_from_final_score(
                team_goals,
                opp_goals,
                period,
                last_goal.get('ingame_status'),
                last_goal.get('result_string'),
            )
    return points

def stat_close_game_win(events: pd.DataFrame, team: str):
    close_game_win = 0
    last_goal = _last_goal_event(events)
    if last_goal is not None:
        max_in_game_diff = _max_in_game_goal_diff(events, team)
        if team == last_goal['home_team_name']:
            team_goals = last_goal['home_goals']
            opp_goals = last_goal['guest_goals']
        else:
            team_goals = last_goal['guest_goals']
            opp_goals = last_goal['home_goals']
        if max_in_game_diff < 3 and team_goals > opp_goals:
            close_game_win += 1
    return close_game_win

def stat_close_game_loss(events: pd.DataFrame, team: str):
    close_game_loss = 0
    last_goal = _last_goal_event(events)
    if last_goal is not None:
        max_in_game_diff = _max_in_game_goal_diff(events, team)
        if team == last_goal['home_team_name']:
            team_goals = last_goal['home_goals']
            opp_goals = last_goal['guest_goals']
        else:
            team_goals = last_goal['guest_goals']
            opp_goals = last_goal['home_goals']
        if max_in_game_diff < 3 and team_goals < opp_goals:
            close_game_loss += 1
    return close_game_loss

def stat_close_game_overtime(events: pd.DataFrame, team: str):
    close_game_ot = 0
    last_goal = _last_goal_event(events)
    if last_goal is not None:
        max_in_game_diff = _max_in_game_goal_diff(events, team)
        if team == last_goal['home_team_name']:
            team_goals = last_goal['home_goals']
            opp_goals = last_goal['guest_goals']
            period = last_goal['period']
        else:
            team_goals = last_goal['guest_goals']
            opp_goals = last_goal['home_goals']
            period = last_goal['period']
        if max_in_game_diff < 3 and team_goals != opp_goals and int(period) == 4:
            close_game_ot += 1
    return close_game_ot

def stat_penalty_shot_goals(events: pd.DataFrame, team: str):
    return int(events[(events['event_type'] == EVENT_GOAL) & (events['event_team'] == team) & (events['goal_type'] == 'penalty_shot')].shape[0])

def stat_penalty_shot_goals_against(events: pd.DataFrame, team: str):
    return int(events[(events['event_type'] == EVENT_GOAL) & (events['event_team'] != team) & (events['goal_type'] == 'penalty_shot')].shape[0])

def stat_penalty_2(events: pd.DataFrame, team: str):
    return int(events[(events['event_type'] == EVENT_PENALTY) & (events['event_team'] == team) & (events['penalty_type'] == 'penalty_2')].shape[0])

def stat_penalty_2and2(events: pd.DataFrame, team: str):
    return int(events[(events['event_type'] == EVENT_PENALTY) & (events['event_team'] == team) & (events['penalty_type'] == 'penalty_2and2')].shape[0])

def stat_penalty_10(events: pd.DataFrame, team: str):
    return int(events[(events['event_type'] == EVENT_PENALTY) & (events['event_team'] == team) & (events['penalty_type'] == 'penalty_10')].shape[0])

def stat_penalty_ms(events: pd.DataFrame, team: str):
    return int(events[(events['event_type'] == EVENT_PENALTY) & (events['event_team'] == team) & ((events['penalty_type'] == 'penalty_ms_full') | (events['penalty_type'] == 'penalty_ms_tech'))].shape[0])

def stat_penalty_first_period(events: pd.DataFrame, team: str):
    return int(events[(events['event_type'] == EVENT_PENALTY) & (events['event_team'] == team) & (events['period'] == 1)].shape[0])

def stat_penalty_second_period(events: pd.DataFrame, team: str):
    return int(events[(events['event_type'] == EVENT_PENALTY) & (events['event_team'] == team) & (events['period'] == 2)].shape[0])

def stat_penalty_third_period(events: pd.DataFrame, team: str):
    return int(events[(events['event_type'] == EVENT_PENALTY) & (events['event_team'] == team) & (events['period'] == 3)].shape[0])

def stat_penalty_overtime(events: pd.DataFrame, team: str):
    return int(events[(events['event_type'] == EVENT_PENALTY) & (events['event_team'] == team) & (events['period'] == 4)].shape[0])

def _team_score_state(event: pd.Series, team: str):
    if event.get('home_team_name') == team:
        return event['home_goals'], event['guest_goals']
    if event.get('away_team_name') == team:
        return event['guest_goals'], event['home_goals']
    return None, None

def _goal_progression(events: pd.DataFrame) -> pd.DataFrame:
    """Return deduplicated in-game goals (periods 1-4) in chronological order."""
    goals = events[(events['event_type'] == EVENT_GOAL) & (events['period'] <= 4)].copy()
    if goals.empty:
        return goals
    goals = goals.sort_values(by=['time_in_s', 'sortkey'])
    goals['score_key'] = goals['home_goals'].astype(str) + ":" + goals['guest_goals'].astype(str)
    goals = goals[goals['score_key'].ne(goals['score_key'].shift())].copy()
    return goals.drop(columns=['score_key'])

def stat_take_the_lead_goals(events: pd.DataFrame, team: str):
    count = 0
    for _, event in _goal_progression(events).iterrows():
        if event['event_team'] == team:
            team_goals, opp_goals = _team_score_state(event, team)
            if team_goals is None:
                continue
            # Leading goal: a goal that turns a tie into a lead.
            if team_goals == opp_goals + 1:
                count += 1
    return count

def stat_equalizer_goals(events: pd.DataFrame, team: str):
    count = 0
    for _, event in _goal_progression(events).iterrows():
        if event['event_team'] == team:
            if event['home_goals'] - event['guest_goals'] == 0:
                count += 1
    return count

def stat_first_goal_of_match(events: pd.DataFrame, team: str):
    goals = _goal_progression(events)
    if goals.empty:
        return 0
    first = goals.iloc[0]
    return int(first['event_team'] == team)

def stat_take_the_lead_goals_against(events: pd.DataFrame, team: str):
    count = 0
    for _, event in _goal_progression(events).iterrows():
        if event['event_team'] != team:
            team_goals, opp_goals = _team_score_state(event, team)
            if team_goals is None:
                continue
            # Against: opponent scores to take the lead from a tie.
            if opp_goals == team_goals + 1:
                count += 1
    return count

def stat_equalizer_goals_against(events: pd.DataFrame, team: str):
    count = 0
    for _, event in _goal_progression(events).iterrows():
        if event['event_team'] != team:
            if event['home_goals'] - event['guest_goals'] == 0:
                count += 1
    return count

def stat_first_goal_of_match_against(events: pd.DataFrame, team: str):
    goals = _goal_progression(events)
    if goals.empty:
        return 0
    first = goals.iloc[0]
    return int(first['event_team'] != team)

def stat_goals_in_first_period_against(events: pd.DataFrame, team: str):
    return int(events[(events['event_type'] == EVENT_GOAL) & (events['event_team'] != team) & (events['period'] == 1)].shape[0])

def stat_goals_in_second_period_against(events: pd.DataFrame, team: str):
    return int(events[(events['event_type'] == EVENT_GOAL) & (events['event_team'] != team) & (events['period'] == 2)].shape[0])

def stat_goals_in_third_period_against(events: pd.DataFrame, team: str):
    return int(events[(events['event_type'] == EVENT_GOAL) & (events['event_team'] != team) & (events['period'] == 3)].shape[0])

def stat_goals_in_overtime_against(events: pd.DataFrame, team: str):
    return int(events[(events['event_type'] == EVENT_GOAL) & (events['event_team'] != team) & (events['period'] == 4)].shape[0])


def stat_goals_in_penalty_shootout_against(events: pd.DataFrame, team: str):
    return int(events[(events['event_type'] == EVENT_GOAL) & (events['event_team'] != team) & (events['period'] == 5)].shape[0])

def stat_goals_not_in_boxplay(events: pd.DataFrame, team: str):
    total_goals_against = stat_goals_against(events, team)
    boxplay_goals_against = stat_goals_against_in_boxplay(events, team)
    return total_goals_against - boxplay_goals_against


def stat_goals_home(events: pd.DataFrame, team: str):
    return int(events[(events['event_type'] == EVENT_GOAL) & (events['event_team'] == team) & (events['home_team_name'] == team)].shape[0])

def stat_goals_away(events: pd.DataFrame, team: str):
    return int(events[(events['event_type'] == EVENT_GOAL) & (events['event_team'] == team) & (events['away_team_name'] == team)].shape[0])

def stat_goals_against_home(events: pd.DataFrame, team: str):
    return int(events[(events['event_type'] == EVENT_GOAL) & (events['event_team'] != team) & (events['home_team_name'] == team)].shape[0])

def stat_goals_against_away(events: pd.DataFrame, team: str):
    return int(events[(events['event_type'] == EVENT_GOAL) & (events['event_team'] != team) & (events['away_team_name'] == team)].shape[0])

def stat_home_points(events: pd.DataFrame, team: str):
    points = 0
    last_goal = _last_goal_event(events)
    if last_goal is not None and last_goal['home_team_name'] == team:
        team_goals, opp_goals, period = _final_score_for_team(last_goal, team)
        points += _points_from_final_score(
            team_goals,
            opp_goals,
            period,
            last_goal.get('ingame_status'),
            last_goal.get('result_string'),
        )
    return points

def stat_away_points(events: pd.DataFrame, team: str):
    points = 0
    for game_id, game_df in events.groupby('game_id'):
        last_goal = _last_goal_event(game_df)
        if last_goal is not None and last_goal['away_team_name'] == team:
            team_goals, opp_goals, period = _final_score_for_team(last_goal, team)
            points += _points_from_final_score(
                team_goals,
                opp_goals,
                period,
                last_goal.get('ingame_status'),
                last_goal.get('result_string'),
            )
    return points



def stat_points_against(events: pd.DataFrame, team: str):
    teams = list(events['home_team_name'].unique()) + list(events['away_team_name'].unique())
    teams = np.unique(teams)
    points_against = {str(t): 0 for t in teams if t != team}
    last_goal = _last_goal_event(events)
    if last_goal is not None:
        opponent = last_goal['away_team_name'] if last_goal['home_team_name'] == team else last_goal['home_team_name']
        team_goals, opp_goals, period = _final_score_for_team(last_goal, team)
        points = _points_from_final_score(
            team_goals,
            opp_goals,
            period,
            last_goal.get('ingame_status'),
            last_goal.get('result_string'),
        )
        points_against[str(opponent)] += points
    return points_against

def build_engine() -> StatsEngine:
    engine = StatsEngine()
    engine.register_stat('points', stat_points)
    engine.register_stat('wins', stat_wins)
    engine.register_stat('over_time_wins', stat_over_time_wins)
    engine.register_stat('penalty_shootout_wins', stat_penalty_shootout_wins)
    engine.register_stat('draws', stat_draws)
    engine.register_stat('losses', stat_losses)
    engine.register_stat('over_time_losses', stat_over_time_losses)
    engine.register_stat('penalty_shootout_losses', stat_penalty_shootout_losses)
    engine.register_stat('goals', stat_goals)
    engine.register_stat('goals_against', stat_goals_against)
    engine.register_stat('games', stat_games)
    engine.register_stat('goal_difference', stat_goal_difference)
    engine.register_stat('points_max_difference_2', stat_points_max_difference)
    engine.register_stat('goals_in_first_period', stat_goals_in_first_period)
    engine.register_stat('goals_in_second_period', stat_goals_in_second_period)
    engine.register_stat('goals_in_third_period', stat_goals_in_third_period)
    engine.register_stat('goals_in_overtime', stat_goals_in_overtime)
    engine.register_stat('goals_in_penalty_shootout', stat_goals_in_penalty_shootout)
    engine.register_stat('goals_in_powerplay', stat_goals_in_powerplay)
    engine.register_stat('goals_in_boxplay', stat_goals_in_boxplay)
    engine.register_stat('goals_against_in_powerplay', stat_goals_against_in_powerplay)
    engine.register_stat('goals_against_in_boxplay', stat_goals_against_in_boxplay)
    engine.register_stat('powerplay', stat_powerplay)
    engine.register_stat('boxplay', stat_boxplay)
    engine.register_stat('powerplay_first_period', stat_powerplay_first_period)
    engine.register_stat('powerplay_second_period', stat_powerplay_second_period)
    engine.register_stat('powerplay_third_period', stat_powerplay_third_period)
    engine.register_stat('powerplay_overtime', stat_powerplay_overtime)
    engine.register_stat('boxplay_first_period', stat_boxplay_first_period)
    engine.register_stat('boxplay_second_period', stat_boxplay_second_period)
    engine.register_stat('boxplay_third_period', stat_boxplay_third_period)
    engine.register_stat('boxplay_overtime', stat_boxplay_overtime)
    engine.register_stat('points_after_first_period', stat_points_after_first_period)
    engine.register_stat('points_after_second_period', stat_points_after_second_period)
    engine.register_stat('points_after_third_period', stat_points_after_third_period)
    engine.register_stat('points_after_55_min', stat_points_after_55_minutes)
    engine.register_stat('points_after_58_min', stat_points_after_58_minutes)
    engine.register_stat('points_after_59_min', stat_points_after_59_minutes)
    engine.register_stat('win_1', stat_win_1)
    engine.register_stat('loss_1', stat_loss_1)
    engine.register_stat('points_more_2_difference', stat_points_more_2_difference)
    engine.register_stat('close_game_win', stat_close_game_win)
    engine.register_stat('close_game_loss', stat_close_game_loss)
    engine.register_stat('close_game_overtime', stat_close_game_overtime)
    engine.register_stat('penalty_shot_goals', stat_penalty_shot_goals)
    engine.register_stat('penalty_shot_goals_against', stat_penalty_shot_goals_against)
    engine.register_stat('penalty_2', stat_penalty_2)
    engine.register_stat('penalty_2and2', stat_penalty_2and2)
    engine.register_stat('penalty_10', stat_penalty_10)
    engine.register_stat('penalty_ms', stat_penalty_ms)
    engine.register_stat('penalty_first_period', stat_penalty_first_period)
    engine.register_stat('penalty_second_period', stat_penalty_second_period)
    engine.register_stat('penalty_third_period', stat_penalty_third_period)
    engine.register_stat('penalty_overtime', stat_penalty_overtime)
    engine.register_stat('take_the_lead_goals', stat_take_the_lead_goals)
    engine.register_stat('equalizer_goals', stat_equalizer_goals)
    engine.register_stat('first_goal_of_match', stat_first_goal_of_match)
    engine.register_stat('goals_in_first_period_against', stat_goals_in_first_period_against)
    engine.register_stat('goals_in_second_period_against', stat_goals_in_second_period_against)
    engine.register_stat('goals_in_third_period_against', stat_goals_in_third_period_against)
    engine.register_stat('goals_in_overtime_against', stat_goals_in_overtime_against)
    engine.register_stat('goals_in_penalty_shootout_against', stat_goals_in_penalty_shootout_against)
    engine.register_stat('goals_against_in_boxplay', stat_goals_against_in_boxplay)
    engine.register_stat('goals_home', stat_goals_home)
    engine.register_stat('goals_away', stat_goals_away)
    engine.register_stat('goals_against_home', stat_goals_against_home)
    engine.register_stat('goals_against_away', stat_goals_against_away)
    engine.register_stat('home_points', stat_home_points)
    engine.register_stat('away_points', stat_away_points)
    engine.register_stat('take_the_lead_goals_against', stat_take_the_lead_goals_against)
    engine.register_stat('equalizer_goals_against', stat_equalizer_goals_against)
    engine.register_stat('first_goal_of_match_against', stat_first_goal_of_match_against)
    engine.register_stat('points_against', stat_points_against)
    return engine


def _update_team_stats(current_totals: dict, increment: dict):
    for key, value in increment.items():
        if key == "points_against":
            if key not in current_totals:
                current_totals[key] = {}
            for opponent, pts in value.items():
                current_totals[key][opponent] = current_totals[key].get(opponent, 0) + pts
        elif key not in ["powerplay_efficiency", "boxplay_efficiency"]:
            if key not in current_totals:
                current_totals[key] = value
            else:
                try:
                    current_totals[key] += value
                except (TypeError, ValueError):
                    pass
    return current_totals


def _enhance_team_stats(stats: dict):
    enhanced = stats.copy()
    
    # Ensure basic keys exist
    for key in ["games", "goals", "goals_against", "points", "wins", "losses", "draws", "powerplay", "boxplay"]:
        if key not in enhanced:
            enhanced[key] = 0
            
    enhanced["powerplay_efficiency"] = _powerplay_efficiency(enhanced.get("goals_in_powerplay", 0), enhanced.get("powerplay", 0))
    enhanced["boxplay_efficiency"] = _penalty_kill_efficiency(enhanced.get("goals_against_in_boxplay", 0), enhanced.get("boxplay", 0))

    games = enhanced.get("games", 0)
    goals = enhanced.get("goals", 0)
    goals_against = enhanced.get("goals_against", 0)

    enhanced["percent_goals_first_period"] = safe_div(enhanced.get("goals_in_first_period", 0), goals, 4, True, "n.a.")
    enhanced["percent_goals_second_period"] = safe_div(enhanced.get("goals_in_second_period", 0), goals, 4, True, "n.a.")
    enhanced["percent_goals_third_period"] = safe_div(enhanced.get("goals_in_third_period", 0), goals, 4, True, "n.a.")
    enhanced["percent_goals_overtime"] = safe_div(enhanced.get("goals_in_overtime", 0), goals, 4, True, "n.a.")

    enhanced["percent_goals_first_period_against"] = safe_div(
        enhanced.get("goals_in_first_period_against", 0), goals_against, 4, True, "n.a."
    )
    enhanced["percent_goals_second_period_against"] = safe_div(
        enhanced.get("goals_in_second_period_against", 0), goals_against, 4, True, "n.a."
    )
    enhanced["percent_goals_third_period_against"] = safe_div(
        enhanced.get("goals_in_third_period_against", 0), goals_against, 4, True, "n.a."
    )
    enhanced["percent_goals_overtime_against"] = safe_div(
        enhanced.get("goals_in_overtime_against", 0), goals_against, 4, True, "n.a."
    )
    enhanced["points_per_game"] = safe_div(enhanced.get("points", 0), games)
    enhanced["goal_difference"] = goals - goals_against
    enhanced["goal_difference_per_game"] = safe_div(enhanced["goal_difference"], games)

    enhanced["scoring_ratio"] = safe_div(goals, goals_against, 2, False, "n.a.")
    enhanced["goals_per_game"] = safe_div(goals, games, 2)
    enhanced["goals_against_per_game"] = safe_div(goals_against, games, 2)
    enhanced["boxplay_per_game"] = safe_div(enhanced.get("boxplay", 0), games, 2)
    enhanced["powerplay_per_game"] = safe_div(enhanced.get("powerplay", 0), games, 2)
    enhanced["first_period_goals_per_game"] = safe_div(enhanced.get("goals_in_first_period", 0), games, 2)
    enhanced["first_period_goals_against_per_game"] = safe_div(enhanced.get("goals_in_first_period_against", 0), games, 2)
    enhanced["points_after_first_period_per_game"] = safe_div(enhanced.get("points_after_first_period", 0), games, 2)
    enhanced["penalties_per_game"] = safe_div(enhanced.get("penalties", 0), games, 2)
    enhanced["goals_against_in_boxplay_per_game"] = safe_div(enhanced.get("goals_against_in_boxplay", 0), games, 2)
    close_games = enhanced.get("close_game_win", 0) + enhanced.get("close_game_loss", 0) + enhanced.get("close_game_overtime", 0)
    enhanced["close_games"] = close_games
    enhanced["close_game_points_per_game"] = safe_div(enhanced.get("points_max_difference_2", 0), close_games, 2, False, "n.a.")
    enhanced["close_game_points_share"] = safe_div(enhanced.get("points_max_difference_2", 0), close_games * 3, 4, True, "n.a.")

    return enhanced


def _history_window_metrics(
    history: List[dict[str, Any]],
    *,
    limit: Optional[int] = None,
    venue: Optional[str] = None,
    opponent: Optional[str] = None,
) -> dict[str, Any]:
    filtered = history
    if venue:
        filtered = [entry for entry in filtered if entry.get("venue") == venue]
    if opponent:
        filtered = [entry for entry in filtered if entry.get("opponent") == opponent]
    if limit is not None:
        filtered = filtered[-limit:]

    games = len(filtered)
    if games == 0:
        return {
            "games": 0,
            "wins": 0,
            "losses": 0,
            "draws": 0,
            "points": 0,
            "points_per_game": 0.0,
            "goals_for_per_game": 0.0,
            "goals_against_per_game": 0.0,
            "goal_diff_per_game": 0.0,
            "first_period_goals_per_game": 0.0,
            "first_period_goals_against_per_game": 0.0,
            "points_after_first_period_per_game": 0.0,
            "penalties_per_game": 0.0,
            "goals_against_in_boxplay_per_game": 0.0,
            "powerplay_efficiency": "n.a.",
            "boxplay_efficiency": "n.a.",
            "close_games": 0,
            "close_game_points_per_game": "n.a.",
            "comeback_wins": 0,
            "blown_leads": 0,
            "ot_ps_games": 0,
            "form_tags": "n.a.",
            "form_tag_codes_csv": "",
            "form_opponents_csv": "",
        }

    wins = sum(1 for entry in filtered if entry.get("win"))
    losses = sum(1 for entry in filtered if entry.get("loss"))
    draws = sum(1 for entry in filtered if entry.get("draw"))
    points = sum(int(entry.get("points", 0)) for entry in filtered)
    goals_for = sum(int(entry.get("goals_for", 0)) for entry in filtered)
    goals_against = sum(int(entry.get("goals_against", 0)) for entry in filtered)
    first_period_goals = sum(int(entry.get("goals_in_first_period", 0)) for entry in filtered)
    first_period_goals_against = sum(int(entry.get("goals_in_first_period_against", 0)) for entry in filtered)
    points_after_first_period = sum(int(entry.get("points_after_first_period", 0)) for entry in filtered)
    penalties = sum(int(entry.get("penalties", 0)) for entry in filtered)
    goals_against_in_boxplay = sum(int(entry.get("goals_against_in_boxplay", 0)) for entry in filtered)
    goals_in_powerplay = sum(int(entry.get("goals_in_powerplay", 0)) for entry in filtered)
    powerplay = sum(int(entry.get("powerplay", 0)) for entry in filtered)
    boxplay = sum(int(entry.get("boxplay", 0)) for entry in filtered)
    close_games = sum(1 for entry in filtered if entry.get("close_game"))
    close_points = sum(int(entry.get("points", 0)) for entry in filtered if entry.get("close_game"))
    comeback_wins = sum(1 for entry in filtered if entry.get("win") and entry.get("first_goal_against"))
    blown_leads = sum(1 for entry in filtered if not entry.get("win") and entry.get("first_goal_for"))
    ot_ps_games = sum(1 for entry in filtered if entry.get("ot_ps_decision"))
    form_tags = []
    form_tag_codes = []
    for entry in filtered:
        if entry.get("draw"):
            form_tags.append("D")
            form_tag_codes.append("D")
        elif entry.get("win"):
            if entry.get("ot_ps_decision"):
                form_tags.append("OTW")
                form_tag_codes.append("OW")
            else:
                form_tags.append("W")
                form_tag_codes.append("W")
        else:
            if entry.get("ot_ps_decision"):
                form_tags.append("OTL")
                form_tag_codes.append("OL")
            else:
                form_tags.append("L")
                form_tag_codes.append("L")
    form_opponents = [str(entry.get("opponent") or "") for entry in filtered]

    return {
        "games": games,
        "wins": wins,
        "losses": losses,
        "draws": draws,
        "points": points,
        "points_per_game": safe_div(points, games, 2),
        "goals_for_per_game": safe_div(goals_for, games, 2),
        "goals_against_per_game": safe_div(goals_against, games, 2),
        "goal_diff_per_game": safe_div(goals_for - goals_against, games, 2),
        "first_period_goals_per_game": safe_div(first_period_goals, games, 2),
        "first_period_goals_against_per_game": safe_div(first_period_goals_against, games, 2),
        "points_after_first_period_per_game": safe_div(points_after_first_period, games, 2),
        "penalties_per_game": safe_div(penalties, games, 2),
        "goals_against_in_boxplay_per_game": safe_div(goals_against_in_boxplay, games, 2),
        "powerplay_efficiency": _powerplay_efficiency(goals_in_powerplay, powerplay),
        "boxplay_efficiency": _penalty_kill_efficiency(goals_against_in_boxplay, boxplay),
        "close_games": close_games,
        "close_game_points_per_game": safe_div(close_points, close_games, 2, False, "n.a."),
        "comeback_wins": comeback_wins,
        "blown_leads": blown_leads,
        "ot_ps_games": ot_ps_games,
        "form_tags": " ".join(form_tags),
        "form_tag_codes_csv": ",".join(form_tag_codes),
        "form_opponents_csv": "||".join(form_opponents),
    }


def _common_opponents_metrics(home_history: List[dict[str, Any]], away_history: List[dict[str, Any]]) -> dict[str, Any]:
    def _build_map(history: List[dict[str, Any]]) -> dict[str, dict[str, int]]:
        result: dict[str, dict[str, int]] = {}
        for entry in history:
            opponent = str(entry.get("opponent") or "").strip()
            if not opponent:
                continue
            bucket = result.setdefault(opponent, {"games": 0, "points": 0, "goal_diff": 0})
            bucket["games"] += 1
            bucket["points"] += int(entry.get("points", 0))
            bucket["goal_diff"] += int(entry.get("goals_for", 0)) - int(entry.get("goals_against", 0))
        return result

    home_map = _build_map(home_history)
    away_map = _build_map(away_history)
    common = sorted(set(home_map).intersection(away_map))

    home_games = sum(home_map[opp]["games"] for opp in common)
    away_games = sum(away_map[opp]["games"] for opp in common)
    home_points = sum(home_map[opp]["points"] for opp in common)
    away_points = sum(away_map[opp]["points"] for opp in common)
    home_goal_diff = sum(home_map[opp]["goal_diff"] for opp in common)
    away_goal_diff = sum(away_map[opp]["goal_diff"] for opp in common)

    return {
        "count": len(common),
        "home_games": home_games,
        "away_games": away_games,
        "home_points_per_game": safe_div(home_points, home_games, 2, False, "n.a."),
        "away_points_per_game": safe_div(away_points, away_games, 2, False, "n.a."),
        "home_goal_diff_per_game": safe_div(home_goal_diff, home_games, 2, False, "n.a."),
        "away_goal_diff_per_game": safe_div(away_goal_diff, away_games, 2, False, "n.a."),
    }


def _pregame_h2h_metrics(
    home_team: str,
    away_team: str,
    home_history: List[dict[str, Any]],
    away_history: List[dict[str, Any]],
) -> dict[str, Any]:
    home_form5 = _history_window_metrics(home_history, limit=5)
    away_form5 = _history_window_metrics(away_history, limit=5)
    home_home = _history_window_metrics(home_history, venue="home")
    away_away = _history_window_metrics(away_history, venue="away")
    h2h = _history_window_metrics(home_history, opponent=away_team)
    common = _common_opponents_metrics(home_history, away_history)

    return {
        # 1) Form (last 5)
        "pregame_h2h_form5_home_tags": home_form5["form_tags"],
        "pregame_h2h_form5_away_tags": away_form5["form_tags"],
        "pregame_h2h_form5_home_tag_codes_csv": home_form5["form_tag_codes_csv"],
        "pregame_h2h_form5_away_tag_codes_csv": away_form5["form_tag_codes_csv"],
        "pregame_h2h_form5_home_opponents_csv": home_form5["form_opponents_csv"],
        "pregame_h2h_form5_away_opponents_csv": away_form5["form_opponents_csv"],
        "pregame_h2h_form5_home_points_per_game": home_form5["points_per_game"],
        "pregame_h2h_form5_away_points_per_game": away_form5["points_per_game"],
        "pregame_h2h_form5_home_goal_diff_per_game": home_form5["goal_diff_per_game"],
        "pregame_h2h_form5_away_goal_diff_per_game": away_form5["goal_diff_per_game"],
        "pregame_h2h_form5_home_wins": home_form5["wins"],
        "pregame_h2h_form5_away_wins": away_form5["wins"],
        # 2) Home vs Away strength
        "pregame_h2h_home_split_points_per_game": home_home["points_per_game"],
        "pregame_h2h_away_split_points_per_game": away_away["points_per_game"],
        "pregame_h2h_home_split_goal_diff_per_game": home_home["goal_diff_per_game"],
        "pregame_h2h_away_split_goal_diff_per_game": away_away["goal_diff_per_game"],
        # 3) Direct H2H
        "pregame_h2h_direct_games": h2h["games"],
        "pregame_h2h_direct_home_wins": h2h["wins"],
        "pregame_h2h_direct_away_wins": h2h["losses"],
        "pregame_h2h_direct_draws": h2h["draws"],
        "pregame_h2h_direct_home_points_per_game": h2h["points_per_game"],
        "pregame_h2h_direct_ot_ps_games": h2h["ot_ps_games"],
        # 4) Common opponents
        "pregame_h2h_common_opponents_count": common["count"],
        "pregame_h2h_common_home_points_per_game": common["home_points_per_game"],
        "pregame_h2h_common_away_points_per_game": common["away_points_per_game"],
        "pregame_h2h_common_home_goal_diff_per_game": common["home_goal_diff_per_game"],
        "pregame_h2h_common_away_goal_diff_per_game": common["away_goal_diff_per_game"],
        # 5) First-period profile
        "pregame_h2h_first_period_home_goals_per_game": home_form5["first_period_goals_per_game"],
        "pregame_h2h_first_period_away_goals_per_game": away_form5["first_period_goals_per_game"],
        "pregame_h2h_first_period_home_goals_against_per_game": home_form5["first_period_goals_against_per_game"],
        "pregame_h2h_first_period_away_goals_against_per_game": away_form5["first_period_goals_against_per_game"],
        "pregame_h2h_first_period_home_points_after_first_per_game": home_form5["points_after_first_period_per_game"],
        "pregame_h2h_first_period_away_points_after_first_per_game": away_form5["points_after_first_period_per_game"],
        # 6) Special teams matchup (cross)
        "pregame_h2h_special_home_pp_eff": home_form5["powerplay_efficiency"],
        "pregame_h2h_special_away_pp_eff": away_form5["powerplay_efficiency"],
        "pregame_h2h_special_home_pk_eff": home_form5["boxplay_efficiency"],
        "pregame_h2h_special_away_pk_eff": away_form5["boxplay_efficiency"],
        # 7) Discipline pressure
        "pregame_h2h_discipline_home_penalties_per_game": home_form5["penalties_per_game"],
        "pregame_h2h_discipline_away_penalties_per_game": away_form5["penalties_per_game"],
        "pregame_h2h_discipline_home_pk_goals_against_per_game": home_form5["goals_against_in_boxplay_per_game"],
        "pregame_h2h_discipline_away_pk_goals_against_per_game": away_form5["goals_against_in_boxplay_per_game"],
        # 8) Game-state resilience
        "pregame_h2h_resilience_home_comeback_wins": home_form5["comeback_wins"],
        "pregame_h2h_resilience_away_comeback_wins": away_form5["comeback_wins"],
        "pregame_h2h_resilience_home_blown_leads": home_form5["blown_leads"],
        "pregame_h2h_resilience_away_blown_leads": away_form5["blown_leads"],
        "pregame_h2h_resilience_home_close_game_points_per_game": home_form5["close_game_points_per_game"],
        "pregame_h2h_resilience_away_close_game_points_per_game": away_form5["close_game_points_per_game"],
    }


def run_stats_pipeline(
    input_csv_path: str,
    output_dir: str,
    season: Optional[str] = None,
    phase: Optional[str] = None,
    pregame_history_csv_paths: Optional[List[str]] = None,
    playoff_cut: int = 8,
) -> dict:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    def _prepare_df(raw_df: pd.DataFrame) -> pd.DataFrame:
        prepared = _canonicalize_team_names(raw_df)
        prepared = _deduplicate_event_rows(prepared)
        if {"event_type", "home_goals", "guest_goals"}.issubset(prepared.columns):
            # Some sources include malformed goal rows (e.g. mixed timeline blocks)
            # without any score snapshot. Drop them before computing stats.
            invalid_goals = (prepared["event_type"] == EVENT_GOAL) & prepared["home_goals"].isna() & prepared["guest_goals"].isna()
            prepared = prepared.loc[~invalid_goals].copy()
        return prepared

    df = _prepare_df(pd.read_csv(input_csv_path))
    exact_player_lookup, fallback_player_lookup = _load_player_uid_lookup(
        Path(input_csv_path).resolve().parent / "player_stats.csv",
        season=season,
        phase=phase,
    )
    teams = list(df["home_team_name"].unique()) + list(df["away_team_name"].unique())
    teams = np.unique(teams)
    engine = build_engine()
    game_stats = []
    played_game_stats = []

    # Sort games chronologically to track pregame stats
    game_groups = []
    for game_id, game_df in df.groupby("game_id"):
        game_groups.append(
            {
                "game_id": game_id,
                "game_df": game_df,
                "date": _json_scalar(game_df["game_date"].iloc[0] if "game_date" in game_df.columns else ""),
                "start_time": _json_scalar(game_df["game_start_time"].iloc[0] if "game_start_time" in game_df.columns else ""),
            }
        )

    # Use an empty string if date or time is None for sorting
    game_groups.sort(key=lambda x: (x["date"] or "", x["start_time"] or ""))

    # Keep table accumulators independent from pregame-history accumulators so
    # playoffs can have a fresh table while pregame comparisons can still use
    # prior phase context.
    team_accumulators = {}
    team_game_history: dict[str, List[dict[str, Any]]] = {}
    pregame_accumulators = {}
    pregame_game_history: dict[str, List[dict[str, Any]]] = {}

    def _ingest_played_game_into_history(
        game_df: pd.DataFrame,
        target_accumulators: dict[str, dict[str, Any]],
        target_history: dict[str, List[dict[str, Any]]],
    ):
        played_df = _played_events_only(game_df)
        if played_df.empty:
            return
        home_team_name = game_df["home_team_name"].iloc[0]
        away_team_name = game_df["away_team_name"].iloc[0]
        home_stats_local = engine.calculate_team_stats(played_df, home_team_name).stats.copy()
        away_stats_local = engine.calculate_team_stats(played_df, away_team_name).stats.copy()

        final_score_local = _parse_result_string_score(game_df["result_string"].iloc[0] if "result_string" in game_df.columns else None)
        if final_score_local is not None:
            home_final_local, away_final_local = final_score_local
            home_stats_local["goals"] = home_final_local
            home_stats_local["goals_against"] = away_final_local
            away_stats_local["goals"] = away_final_local
            away_stats_local["goals_against"] = home_final_local

        for stats_local in [home_stats_local, away_stats_local]:
            stats_local["powerplay_efficiency"] = _powerplay_efficiency(stats_local["goals_in_powerplay"], stats_local["powerplay"])
            stats_local["boxplay_efficiency"] = _penalty_kill_efficiency(stats_local["goals_against_in_boxplay"], stats_local["boxplay"])
            stats_local["penalties"] = stats_local["penalty_2"] + stats_local["penalty_2and2"] + stats_local["penalty_10"] + stats_local["penalty_ms"]

        period_local = int(pd.to_numeric(played_df.get("period"), errors="coerce").max()) if not played_df.empty else 0
        ingame_status_local = _json_scalar(game_df["ingame_status"].iloc[0] if "ingame_status" in game_df.columns else None)
        result_string_local = _json_scalar(game_df["result_string"].iloc[0] if "result_string" in game_df.columns else None)
        home_goals_local = int(home_stats_local.get("goals", 0))
        away_goals_local = int(away_stats_local.get("goals", 0))
        home_points_local = _points_from_final_score(home_goals_local, away_goals_local, period_local, ingame_status_local, result_string_local)
        away_points_local = _points_from_final_score(away_goals_local, home_goals_local, period_local, ingame_status_local, result_string_local)
        ot_ps_decision_local = _is_extra_time_decision(period_local, ingame_status_local, result_string_local)

        _apply_result_summary(
            home_stats_local,
            goals_for=home_goals_local,
            goals_against=away_goals_local,
            points=home_points_local,
            venue="home",
            ot_ps_decision=ot_ps_decision_local,
        )
        _apply_result_summary(
            away_stats_local,
            goals_for=away_goals_local,
            goals_against=home_goals_local,
            points=away_points_local,
            venue="away",
            ot_ps_decision=ot_ps_decision_local,
        )

        home_entry_local = {
            "opponent": away_team_name,
            "venue": "home",
            "goals_for": home_goals_local,
            "goals_against": away_goals_local,
            "points": home_points_local,
            "win": home_goals_local > away_goals_local,
            "loss": home_goals_local < away_goals_local,
            "draw": home_goals_local == away_goals_local,
            "ot_ps_decision": ot_ps_decision_local,
            "close_game": abs(home_goals_local - away_goals_local) <= 2,
            "first_goal_for": int(home_stats_local.get("first_goal_of_match", 0)) > 0,
            "first_goal_against": int(home_stats_local.get("first_goal_of_match_against", 0)) > 0,
            "goals_in_first_period": int(home_stats_local.get("goals_in_first_period", 0)),
            "goals_in_first_period_against": int(home_stats_local.get("goals_in_first_period_against", 0)),
            "points_after_first_period": int(home_stats_local.get("points_after_first_period", 0)),
            "penalties": int(home_stats_local.get("penalties", 0)),
            "goals_against_in_boxplay": int(home_stats_local.get("goals_against_in_boxplay", 0)),
            "goals_in_powerplay": int(home_stats_local.get("goals_in_powerplay", 0)),
            "powerplay": int(home_stats_local.get("powerplay", 0)),
            "boxplay": int(home_stats_local.get("boxplay", 0)),
        }
        away_entry_local = {
            "opponent": home_team_name,
            "venue": "away",
            "goals_for": away_goals_local,
            "goals_against": home_goals_local,
            "points": away_points_local,
            "win": away_goals_local > home_goals_local,
            "loss": away_goals_local < home_goals_local,
            "draw": away_goals_local == home_goals_local,
            "ot_ps_decision": ot_ps_decision_local,
            "close_game": abs(home_goals_local - away_goals_local) <= 2,
            "first_goal_for": int(away_stats_local.get("first_goal_of_match", 0)) > 0,
            "first_goal_against": int(away_stats_local.get("first_goal_of_match_against", 0)) > 0,
            "goals_in_first_period": int(away_stats_local.get("goals_in_first_period", 0)),
            "goals_in_first_period_against": int(away_stats_local.get("goals_in_first_period_against", 0)),
            "points_after_first_period": int(away_stats_local.get("points_after_first_period", 0)),
            "penalties": int(away_stats_local.get("penalties", 0)),
            "goals_against_in_boxplay": int(away_stats_local.get("goals_against_in_boxplay", 0)),
            "goals_in_powerplay": int(away_stats_local.get("goals_in_powerplay", 0)),
            "powerplay": int(away_stats_local.get("powerplay", 0)),
            "boxplay": int(away_stats_local.get("boxplay", 0)),
        }
        target_history.setdefault(home_team_name, []).append(home_entry_local)
        target_history.setdefault(away_team_name, []).append(away_entry_local)
        target_accumulators[home_team_name] = _update_team_stats(target_accumulators.get(home_team_name, {}), home_stats_local)
        target_accumulators[away_team_name] = _update_team_stats(target_accumulators.get(away_team_name, {}), away_stats_local)

    playoff_eligible_teams: Optional[set[str]] = None

    def _derive_playoff_eligible_teams_from_history_df(history_df: pd.DataFrame) -> set[str]:
        regular_accumulators: dict[str, dict[str, Any]] = {}
        regular_history: dict[str, List[dict[str, Any]]] = {}
        regular_game_groups = []
        for history_game_id, history_game_df in history_df.groupby("game_id"):
            regular_game_groups.append(
                {
                    "game_id": history_game_id,
                    "game_df": history_game_df,
                    "date": _json_scalar(history_game_df["game_date"].iloc[0] if "game_date" in history_df.columns else ""),
                    "start_time": _json_scalar(history_game_df["game_start_time"].iloc[0] if "game_start_time" in history_df.columns else ""),
                }
            )
        regular_game_groups.sort(key=lambda x: (x["date"] or "", x["start_time"] or ""))
        for regular_group in regular_game_groups:
            _ingest_played_game_into_history(
                regular_group["game_df"],
                regular_accumulators,
                regular_history,
            )
        regular_all_stats = [TeamStats(team, stats) for team, stats in regular_accumulators.items()]
        regular_ranking = sorted(
            regular_all_stats,
            key=lambda x: (-x.stats.get("points", 0), -x.stats.get("goal_difference", 0), -x.stats.get("goals", 0)),
        )
        return {entry.team for entry in regular_ranking[:playoff_cut]}

    for history_path in pregame_history_csv_paths or []:
        history_file = Path(history_path)
        if not history_file.exists():
            continue
        history_df = _prepare_df(pd.read_csv(history_file))
        if phase == "playoffs" and playoff_eligible_teams is None:
            playoff_eligible_teams = _derive_playoff_eligible_teams_from_history_df(history_df)
        history_groups = []
        for history_game_id, history_game_df in history_df.groupby("game_id"):
            history_groups.append(
                {
                    "game_id": history_game_id,
                    "game_df": history_game_df,
                    "date": _json_scalar(history_game_df["game_date"].iloc[0] if "game_date" in history_game_df.columns else ""),
                    "start_time": _json_scalar(history_game_df["game_start_time"].iloc[0] if "game_start_time" in history_game_df.columns else ""),
                }
            )
        history_groups.sort(key=lambda x: (x["date"] or "", x["start_time"] or ""))
        for history_group in history_groups:
            _ingest_played_game_into_history(
                history_group["game_df"],
                pregame_accumulators,
                pregame_game_history,
            )

    for group in game_groups:
        game_id = group["game_id"]
        game_df = group["game_df"]

        home_team = game_df["home_team_name"].iloc[0]
        away_team = game_df["away_team_name"].iloc[0]
        if phase == "playoffs" and playoff_eligible_teams is not None:
            if home_team not in playoff_eligible_teams or away_team not in playoff_eligible_teams:
                # Exclude playdown/non-playoff pairings entirely from playoff outputs.
                continue

        played_game_df = _played_events_only(game_df)
        is_scheduled = played_game_df.empty

        # Get pregame stats (enhanced)
        home_pregame_stats = _enhance_team_stats(pregame_accumulators.get(home_team, {}))
        away_pregame_stats = _enhance_team_stats(pregame_accumulators.get(away_team, {}))
        home_history = pregame_game_history.get(home_team, [])
        away_history = pregame_game_history.get(away_team, [])
        pregame_h2h_stats = _pregame_h2h_metrics(home_team, away_team, home_history, away_history)

        home_stats = engine.calculate_team_stats(played_game_df, home_team).stats.copy()
        away_stats = engine.calculate_team_stats(played_game_df, away_team).stats.copy()

        # Prefer an explicit final score snapshot when available. Some feeds contain
        # inconsistent scorer flags for individual events, which can otherwise
        # misclassify games as draws even though a final result is present.
        final_score = _parse_result_string_score(game_df["result_string"].iloc[0] if "result_string" in game_df.columns else None)
        if final_score is not None:
            home_final, away_final = final_score
            home_stats["goals"] = home_final
            home_stats["goals_against"] = away_final
            home_stats["goal_difference"] = home_final - away_final
            home_stats["goals_home"] = home_final
            home_stats["goals_away"] = 0
            home_stats["goals_against_home"] = away_final
            home_stats["goals_against_away"] = 0

            away_stats["goals"] = away_final
            away_stats["goals_against"] = home_final
            away_stats["goal_difference"] = away_final - home_final
            away_stats["goals_home"] = 0
            away_stats["goals_away"] = away_final
            away_stats["goals_against_home"] = 0
            away_stats["goals_against_away"] = home_final

        for stats in [home_stats, away_stats]:
            stats["powerplay_efficiency"] = _powerplay_efficiency(stats["goals_in_powerplay"], stats["powerplay"])
            stats["boxplay_efficiency"] = _penalty_kill_efficiency(stats["goals_against_in_boxplay"], stats["boxplay"])
            stats["penalties"] = stats["penalty_2"] + stats["penalty_2and2"] + stats["penalty_10"] + stats["penalty_ms"]

        period_local = int(pd.to_numeric(played_game_df.get("period"), errors="coerce").max()) if not played_game_df.empty else 0
        ingame_status_local = _json_scalar(game_df["ingame_status"].iloc[0] if "ingame_status" in game_df.columns else None)
        result_string_local = _json_scalar(game_df["result_string"].iloc[0] if "result_string" in game_df.columns else None)
        home_goals_local = int(home_stats.get("goals", 0))
        away_goals_local = int(away_stats.get("goals", 0))
        home_points_local = _points_from_final_score(home_goals_local, away_goals_local, period_local, ingame_status_local, result_string_local)
        away_points_local = _points_from_final_score(away_goals_local, home_goals_local, period_local, ingame_status_local, result_string_local)
        ot_ps_decision_local = _is_extra_time_decision(period_local, ingame_status_local, result_string_local)

        _apply_result_summary(
            home_stats,
            goals_for=home_goals_local,
            goals_against=away_goals_local,
            points=home_points_local,
            venue="home",
            ot_ps_decision=ot_ps_decision_local,
        )
        _apply_result_summary(
            away_stats,
            goals_for=away_goals_local,
            goals_against=home_goals_local,
            points=away_points_local,
            venue="away",
            ot_ps_decision=ot_ps_decision_local,
        )

        venue_value = None
        for venue_column in ("venue", "arena", "location", "venue_name"):
            if venue_column in game_df.columns:
                raw_value = _json_scalar(game_df[venue_column].iloc[0])
                if raw_value not in (None, "", "None"):
                    venue_value = raw_value
                    break

        venue_address_value = None
        for address_column in ("venue_address", "address"):
            if address_column in game_df.columns:
                raw_value = _json_scalar(game_df[address_column].iloc[0])
                if raw_value not in (None, "", "None"):
                    venue_address_value = raw_value
                    break

        passthrough_metadata: dict[str, Any] = {}
        for metadata_column in (
            "competition_name",
            "league_name",
            "tournament_stage_type",
            "tournament_stage_label",
            "tournament_group",
            "tournament_round",
            "tournament_round_order",
        ):
            if metadata_column not in game_df.columns:
                continue
            raw_value = _json_scalar(game_df[metadata_column].iloc[0])
            if raw_value in (None, "", "None"):
                continue
            passthrough_metadata[metadata_column] = raw_value

        game_stat = {
            "game_id": game_id,
            "date": _json_scalar(game_df["game_date"].iloc[0] if "game_date" in game_df.columns else None),
            "start_time": _json_scalar(game_df["game_start_time"].iloc[0] if "game_start_time" in game_df.columns else None),
            "attendance": _json_scalar(game_df["attendance"].iloc[0] if "attendance" in game_df.columns else None),
            "game_status": _json_scalar(game_df["game_status"].iloc[0] if "game_status" in game_df.columns else None),
            "result_string": _json_scalar(game_df["result_string"].iloc[0] if "result_string" in game_df.columns else None),
            "ingame_status": _json_scalar(game_df["ingame_status"].iloc[0] if "ingame_status" in game_df.columns else None),
            "game_state": "scheduled" if is_scheduled else "played",
            "home_team": home_team,
            "home_stats": home_stats,
            "home_pregame_stats": home_pregame_stats,
            "away_team": away_team,
            "away_stats": away_stats,
            "away_pregame_stats": away_pregame_stats,
        }
        if venue_value is not None:
            game_stat["venue"] = venue_value
        if venue_address_value is not None:
            game_stat["venue_address"] = venue_address_value
        game_stat.update(passthrough_metadata)
        game_stat.update(pregame_h2h_stats)
        game_stat.update(_build_gameflow_timeline(played_game_df, home_team, away_team))
        game_stat.update(
            _build_game_events_payload(
                played_game_df,
                home_team,
                away_team,
                exact_player_lookup,
                fallback_player_lookup,
            )
        )
        game_stats.append(game_stat)
        if not is_scheduled:
            played_game_stats.append(game_stat)
            _ingest_played_game_into_history(game_df, team_accumulators, team_game_history)
            _ingest_played_game_into_history(game_df, pregame_accumulators, pregame_game_history)

    # save to json
    with open(output_path / "game_stats.json", "w") as f:
        json.dump(game_stats, f, indent=4)

    # Final team stats from accumulators
    team_stats = {}
    for team, stats in team_accumulators.items():
        team_stats[team] = _enhance_team_stats(stats)

    # convert to a list of dicts
    all_stats = [TeamStats(team, stats) for team, stats in team_stats.items()]

    home_away_split_table = write_home_away_split_table(
        team_stats,
        output_path / 'home_away_split_table.json',
        game_stats,
        season=season,
        phase=phase,
    )

    playoff_stats, playdown_stats, top4_stats = engine.split_by_rank(
        all_stats,
        playoff_cut=playoff_cut,
        top4_cut=4,
        playoff_eligible_teams=playoff_eligible_teams if phase == "playoffs" else None,
    )

    # Assign ranks after splitting so playoff standings are not skewed by
    # playdown teams during mixed playoff/playdown phases.
    if phase == "playoffs":
        for i, entry in enumerate(playoff_stats):
            team_stats[entry.team]["rank"] = i + 1
        for i, entry in enumerate(playdown_stats):
            team_stats[entry.team]["rank"] = i + 1
    else:
        ranking = sorted(
            all_stats, key=lambda x: (-x.stats.get("points", 0), -x.stats.get("goal_difference", 0), -x.stats.get("goals", 0))
        )
        for i, entry in enumerate(ranking):
            team_stats[entry.team]["rank"] = i + 1

    with open(output_path / "team_stats_enhanced.json", "w") as f:
        json.dump(team_stats, f, indent=4)
    league_stats = engine.aggregate_stats(all_stats)
    playoff_averages = engine.aggregate_stats(playoff_stats)
    playdown_averages = engine.aggregate_stats(playdown_stats)
    top4_averages = engine.aggregate_stats(top4_stats)
    with open(output_path / 'playoff_stats.json', 'w') as f:
        json.dump([team.to_dict() for team in playoff_stats], f, indent=4)

    with open(output_path / 'playdown_stats.json', 'w') as f:
        json.dump([team.to_dict() for team in playdown_stats], f, indent=4)

    with open(output_path / 'top4_stats.json', 'w') as f:
        json.dump([team.to_dict() for team in top4_stats], f, indent=4)

    with open(output_path / 'playoff_averages.json', 'w') as f:
        json.dump(playoff_averages, f, indent=4)

    with open(output_path / 'playdown_averages.json', 'w') as f:
        json.dump(playdown_averages, f, indent=4)

    with open(output_path / 'top4_averages.json', 'w') as f:
        json.dump(top4_averages, f, indent=4)

    with open(output_path / 'league_averages.json', 'w') as f:
        json.dump(league_stats, f, indent=4)
    return {
        "game_stats": game_stats,
        "team_stats_enhanced": team_stats,
        "home_away_split_table": home_away_split_table,
        "playoff_stats": [team.to_dict() for team in playoff_stats],
        "playdown_stats": [team.to_dict() for team in playdown_stats],
        "top4_stats": [team.to_dict() for team in top4_stats],
        "playoff_averages": playoff_averages,
        "playdown_averages": playdown_averages,
        "top4_averages": top4_averages,
        "league_averages": league_stats,
    }


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input_csv_path", default="data/data_regular_season.csv")
    parser.add_argument("--output_dir", default="data")
    return parser.parse_args()


def main():
    args = parse_args()
    run_stats_pipeline(input_csv_path=args.input_csv_path, output_dir=args.output_dir)


if __name__ == "__main__":
    main()
