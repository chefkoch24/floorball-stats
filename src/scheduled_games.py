from typing import Any, Optional


EVENT_SCHEDULED = "scheduled"
SCHEDULED_SORTKEY = "0-00:00"


def build_scheduled_game_row(
    *,
    game_id: Any,
    home_team: Optional[str],
    away_team: Optional[str],
    game_date: Optional[str],
    game_start_time: Optional[str],
    attendance: Optional[int] = None,
    game_status: Optional[str] = "Scheduled",
    ingame_status: Optional[str] = None,
    result_string: Optional[str] = None,
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
