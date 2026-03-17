from typing import Any


EVENT_SCHEDULED = "scheduled"
SCHEDULED_SORTKEY = "0-00:00"


def build_scheduled_game_row(
    *,
    game_id: Any,
    home_team: str | None,
    away_team: str | None,
    game_date: str | None,
    game_start_time: str | None,
    attendance: int | None = None,
    game_status: str | None = "Scheduled",
    ingame_status: str | None = None,
    result_string: str | None = None,
) -> dict[str, Any]:
    return {
        "event_type": EVENT_SCHEDULED,
        "event_team": None,
        "period": 0,
        "sortkey": SCHEDULED_SORTKEY,
        "game_id": game_id,
        "home_team_name": home_team,
        "away_team_name": away_team,
        "home_goals": None,
        "guest_goals": None,
        "goal_type": None,
        "penalty_type": None,
        "game_date": game_date,
        "game_start_time": game_start_time,
        "attendance": attendance,
        "game_status": game_status,
        "ingame_status": ingame_status,
        "result_string": result_string,
        "scorer_name": None,
        "assist_name": None,
        "scorer_number": None,
        "assist_number": None,
        "penalty_player_name": None,
    }
