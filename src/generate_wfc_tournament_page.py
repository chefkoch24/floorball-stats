from __future__ import annotations

import argparse
import html
from dataclasses import dataclass
from pathlib import Path


ROUND_LABELS = {
    "Play-Off 1": "Qualification 1",
    "Play-Off 2": "Qualification 2",
    "Play-Off 3": "Qualification 3",
    "Play-Off 4": "Qualification 4",
    "5th-8th:1": "5th-8th Semifinal 1",
    "5th-8th:2": "5th-8th Semifinal 2",
    "9th-12th:1": "9th-12th Semifinal 1",
    "9th-12th:2": "9th-12th Semifinal 2",
    "13th-16th:1": "13th-16th Semifinal 1",
    "13th-16th:2": "13th-16th Semifinal 2",
}
GROUP_LABELS = ["Group A", "Group B", "Group C", "Group D"]


@dataclass
class TeamRow:
    title: str
    slug: str
    team: str
    games: str
    points: str
    goals: str
    goals_against: str
    goal_difference: str
    rank: int
    group: str


@dataclass
class GameRow:
    title: str
    slug: str
    home_team: str
    away_team: str
    home_goals: str
    away_goals: str
    date: str
    start_time: str
    group: str
    round_label: str
    result_string: str
    ingame_status: str
    home_ot_goals: str
    away_ot_goals: str
    home_ps_goals: str
    away_ps_goals: str


def _parse_metadata(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        values[key.strip()] = value.strip()
    return values


def _strip_men(value: str) -> str:
    return (value or "").replace(" Men", "").strip()


def _load_team_rows(directory: Path) -> list[TeamRow]:
    rows: list[TeamRow] = []
    for path in sorted(directory.glob("*.md")):
        meta = _parse_metadata(path)
        rows.append(
            TeamRow(
                title=meta.get("Title", ""),
                slug=meta.get("Slug", ""),
                team=_strip_men(meta.get("team", meta.get("Title", ""))),
                games=meta.get("games", "–"),
                points=meta.get("points", "–"),
                goals=meta.get("goals", "–"),
                goals_against=meta.get("goals_against", "–"),
                goal_difference=meta.get("goal_difference", "–"),
                rank=int(meta.get("rank", "999") or 999),
                group=meta.get("tournament_group", ""),
            )
        )
    return rows


def _load_game_rows(directory: Path, *, group_key: str, round_key: str) -> list[GameRow]:
    rows: list[GameRow] = []
    for path in sorted(directory.glob("*.md")):
        meta = _parse_metadata(path)
        rows.append(
            GameRow(
                title=meta.get("Title", ""),
                slug=meta.get("Slug", ""),
                home_team=_strip_men(meta.get("home_team", "")),
                away_team=_strip_men(meta.get("away_team", "")),
                home_goals=meta.get("home_goals", "–"),
                away_goals=meta.get("away_goals", "–"),
                date=meta.get("Date", ""),
                start_time=meta.get("start_time", "–"),
                group=meta.get(group_key, ""),
                round_label=meta.get(round_key, ""),
                result_string=meta.get("result_string", ""),
                ingame_status=meta.get("ingame_status", ""),
                home_ot_goals=meta.get("home_ot_goals", "0"),
                away_ot_goals=meta.get("away_ot_goals", "0"),
                home_ps_goals=meta.get("home_penalty_shootout_goals", "0"),
                away_ps_goals=meta.get("away_penalty_shootout_goals", "0"),
            )
        )
    return rows


def _to_int(value: str) -> int:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return 0


def _to_int_optional(value: str) -> int | None:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def _result_cell_html(game: GameRow) -> str:
    result_string = game.result_string or ""
    status = (game.ingame_status or "").strip().lower()
    home_ot_goals = _to_int(game.home_ot_goals)
    away_ot_goals = _to_int(game.away_ot_goals)
    home_ps_goals = _to_int(game.home_ps_goals)
    away_ps_goals = _to_int(game.away_ps_goals)
    ended_ps = (home_ps_goals + away_ps_goals) > 0 or ("n.P." in result_string) or ("penalty" in status)
    ended_ot = (
        (not ended_ps)
        and ((home_ot_goals + away_ot_goals) > 0 or ("n.V." in result_string) or (status in {"extratime", "overtime"}) or ("OT" in result_string))
    )
    extra = "<span class=\"result-extra\">PS</span>" if ended_ps else "<span class=\"result-extra\">OT</span>" if ended_ot else ""
    return f"<td class=\"wfc-result-col\"><span class=\"wfc-scoreline\">{html.escape(game.home_goals)} : {html.escape(game.away_goals)}</span>{extra}</td>"


def _team_row_html(team: TeamRow, *, rank: int) -> str:
    return (
        "<tr>"
        f"<td>{rank}</td>"
        f"<td><a href=\"/{html.escape(team.slug)}.html\">{html.escape(team.team)}</a></td>"
        f"<td>{html.escape(team.games)}</td>"
        f"<td>{html.escape(team.points)}</td>"
        f"<td>{html.escape(team.goals)}</td>"
        f"<td>{html.escape(team.goals_against)}</td>"
        f"<td>{html.escape(team.goal_difference)}</td>"
        "</tr>"
    )


def _empty_team_row_html(rank: int) -> str:
    return (
        "<tr>"
        f"<td>{rank}</td>"
        "<td>–</td>"
        "<td>–</td>"
        "<td>–</td>"
        "<td>–</td>"
        "<td>–</td>"
        "<td>–</td>"
        "</tr>"
    )


def _game_row_html(game: GameRow, *, include_group: bool) -> str:
    group_cell = f"<td>{html.escape(game.group or '–')}</td>" if include_group else ""
    home_goals = _to_int_optional(game.home_goals)
    away_goals = _to_int_optional(game.away_goals)
    is_draw = (home_goals is not None) and (away_goals is not None) and (home_goals == away_goals)
    home_winner = (home_goals is not None) and (away_goals is not None) and (home_goals > away_goals)
    away_winner = (home_goals is not None) and (away_goals is not None) and (away_goals > home_goals)
    home_class = "game-team-winner" if (not is_draw and home_winner) else ""
    away_class = "game-team-winner" if (not is_draw and away_winner) else ""
    home_team_html = f"<span class=\"{home_class}\">{html.escape(game.home_team)}</span>" if home_class else html.escape(game.home_team)
    away_team_html = f"<span class=\"{away_class}\">{html.escape(game.away_team)}</span>" if away_class else html.escape(game.away_team)
    return (
        "<tr>"
        f"<td>{html.escape(game.date)}</td>"
        f"<td>{html.escape(game.start_time)}</td>"
        f"{group_cell}"
        f"<td class=\"wfc-game-col\">{home_team_html} vs {away_team_html}</td>"
        f"{_result_cell_html(game)}"
        f"<td><a href=\"/{html.escape(game.slug)}.html\">Details</a></td>"
        "</tr>"
    )


def _normalized_time_value(value: str) -> str:
    raw = (value or "").strip()
    if not raw or ":" not in raw:
        return "99:99"
    hours_raw, minutes_raw = raw.split(":", 1)
    try:
        hours = int(hours_raw)
        minutes = int(minutes_raw)
    except ValueError:
        return "99:99"
    return f"{hours:02d}:{minutes:02d}"


def _game_sort_key(game: GameRow) -> tuple[str, str, str]:
    return ((game.date or "9999-12-31"), _normalized_time_value(game.start_time), game.title)


def _build_page_content(teams: list[TeamRow], regular_games: list[GameRow], playoff_games: list[GameRow]) -> str:
    parts: list[str] = []
    parts.append('<section class="hero">')
    parts.append('  <div class="hero-top"><div><h1 class="hero-title">IFF WFC 2024</h1><p class="hero-subtitle">Group tables, game reports, and the full elimination path in one place.</p></div></div>')
    parts.append('  <div class="chip-row">')
    parts.append(f'    <span class="chip">Teams: {len(teams)}</span>')
    parts.append(f'    <span class="chip">Group games: {len(regular_games)}</span>')
    parts.append(f'    <span class="chip">Elimination games: {len(playoff_games)}</span>')
    parts.append('  </div>')
    parts.append('</section>')

    parts.append('<section class="section-grid">')
    for group_label in GROUP_LABELS:
        group_teams = sorted((team for team in teams if team.group == group_label), key=lambda item: item.rank)
        parts.append('<article class="panel">')
        parts.append(f'  <h2 class="panel-title">{html.escape(group_label)}</h2>')
        parts.append('  <div class="table-wrapper"><table class="data-table"><thead><tr><th>Rank</th><th>Team</th><th>GP</th><th>Pts</th><th>GF</th><th>GA</th><th>GD</th></tr></thead><tbody>')
        for rank in range(1, 5):
            idx = rank - 1
            if idx < len(group_teams):
                parts.append(_team_row_html(group_teams[idx], rank=rank))
            else:
                parts.append(_empty_team_row_html(rank))
        parts.append('  </tbody></table></div>')
        parts.append('</article>')
    parts.append('</section>')

    parts.append('<details class="panel">')
    parts.append('  <summary class="panel-title" style="cursor: pointer;">Group Stage Games</summary>')
    parts.append('  <div class="table-wrapper"><table class="data-table"><thead><tr><th>Date</th><th>Time</th><th>Group</th><th>Game</th><th class="wfc-result-col">Result</th><th>Report</th></tr></thead><tbody>')
    for game in sorted(regular_games, key=_game_sort_key):
        parts.append(_game_row_html(game, include_group=True))
    parts.append('  </tbody></table></div>')
    parts.append('</details>')

    parts.append('<section class="panel">')
    parts.append('  <h2 class="panel-title">Elimination</h2>')
    parts.append('  <div class="table-wrapper"><table class="data-table"><thead><tr><th>Date</th><th>Time</th><th>Round</th><th>Game</th><th class="wfc-result-col">Result</th><th>Report</th></tr></thead><tbody>')
    for game in sorted(playoff_games, key=_game_sort_key):
        round_name = html.escape(ROUND_LABELS.get(game.round_label, game.round_label or "Elimination"))
        game_row = _game_row_html(game, include_group=False)
        game_row = game_row.replace(
            f'<td class="wfc-game-col">{html.escape(game.home_team)} vs {html.escape(game.away_team)}</td>',
            f'<td>{round_name}</td><td class="wfc-game-col">{html.escape(game.home_team)} vs {html.escape(game.away_team)}</td>',
            1,
        )
        parts.append(game_row)
    parts.append('  </tbody></table></div>')
    parts.append('</section>')
    return "\n".join(parts)


def generate_wfc_tournament_page(
    *,
    regular_teams_dir: Path,
    regular_games_dir: Path,
    playoffs_games_dir: Path,
    output_path: Path,
) -> None:
    teams = _load_team_rows(regular_teams_dir)
    regular_games = _load_game_rows(regular_games_dir, group_key="tournament_group", round_key="tournament_round")
    playoff_games = _load_game_rows(playoffs_games_dir, group_key="tournament_group", round_key="tournament_round")

    content = _build_page_content(teams, regular_games, playoff_games)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        "\n".join(
            [
                "Title: IFF WFC 2024",
                "Slug: wfc-2024",
                f"Date: {max([game.date for game in playoff_games if game.date] or ['2024-12-15'])}",
                "",
                content,
                "",
            ]
        ),
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--regular-teams-dir", default="content/wfc-2024-regular-season/teams")
    parser.add_argument("--regular-games-dir", default="content/wfc-2024-regular-season/games")
    parser.add_argument("--playoffs-games-dir", default="content/wfc-2024-playoffs/games")
    parser.add_argument("--output-path", default="content/pages/wfc-2024.md")
    args = parser.parse_args()
    generate_wfc_tournament_page(
        regular_teams_dir=Path(args.regular_teams_dir),
        regular_games_dir=Path(args.regular_games_dir),
        playoffs_games_dir=Path(args.playoffs_games_dir),
        output_path=Path(args.output_path),
    )


if __name__ == "__main__":
    main()
