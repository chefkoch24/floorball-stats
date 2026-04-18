from __future__ import annotations

import argparse
import html
from dataclasses import dataclass
from pathlib import Path


ROUND_ORDER = [
    "Play-Off 1",
    "Play-Off 2",
    "Play-Off 3",
    "Play-Off 4",
    "Quarterfinal 1",
    "Quarterfinal 2",
    "Quarterfinal 3",
    "Quarterfinal 4",
    "Semifinal 1",
    "Semifinal 2",
    "3rd Place",
    "Final",
    "5th-8th:1",
    "5th-8th:2",
    "5th Place",
    "7th Place",
    "9th-12th:1",
    "9th-12th:2",
    "9th Place",
    "11th Place",
    "13th-16th:1",
    "13th-16th:2",
    "13th Place",
    "15th Place",
]
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
            )
        )
    return rows


def _team_row_html(team: TeamRow) -> str:
    return (
        "<tr>"
        f"<td>{team.rank}</td>"
        f"<td><a href=\"/{html.escape(team.slug)}.html\">{html.escape(team.team)}</a></td>"
        f"<td>{html.escape(team.games)}</td>"
        f"<td>{html.escape(team.points)}</td>"
        f"<td>{html.escape(team.goals)}</td>"
        f"<td>{html.escape(team.goals_against)}</td>"
        f"<td>{html.escape(team.goal_difference)}</td>"
        "</tr>"
    )


def _game_row_html(game: GameRow, *, include_group: bool) -> str:
    group_cell = f"<td>{html.escape(game.group or '–')}</td>" if include_group else ""
    return (
        "<tr>"
        f"<td>{html.escape(game.date)}</td>"
        f"<td>{html.escape(game.start_time)}</td>"
        f"{group_cell}"
        f"<td class=\"wfc-game-col\">{html.escape(game.home_team)} vs {html.escape(game.away_team)}</td>"
        f"<td class=\"wfc-result-col\"><span class=\"wfc-scoreline\">{html.escape(game.home_goals)} : {html.escape(game.away_goals)}</span></td>"
        f"<td><a href=\"/{html.escape(game.slug)}.html\">Details</a></td>"
        "</tr>"
    )


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
        parts.extend(_team_row_html(team) for team in group_teams)
        parts.append('  </tbody></table></div>')
        parts.append('</article>')
    parts.append('</section>')

    parts.append('<details class="panel">')
    parts.append('  <summary class="panel-title" style="cursor: pointer;">Group Stage Games</summary>')
    parts.append('  <div class="table-wrapper"><table class="data-table"><thead><tr><th>Date</th><th>Time</th><th>Group</th><th>Game</th><th class="wfc-result-col">Result</th><th>Report</th></tr></thead><tbody>')
    for game in sorted(regular_games, key=lambda item: (item.date, item.start_time)):
        parts.append(_game_row_html(game, include_group=True))
    parts.append('  </tbody></table></div>')
    parts.append('</details>')

    parts.append('<section class="panel">')
    parts.append('  <h2 class="panel-title">Elimination</h2>')
    for round_label in ROUND_ORDER:
        round_games = [game for game in playoff_games if game.round_label == round_label]
        if not round_games:
            continue
        display_label = ROUND_LABELS.get(round_label, round_label)
        parts.append('  <div class="panel" style="margin-top: 1rem;">')
        parts.append(f'    <h3 class="panel-title">{html.escape(display_label)}</h3>')
        parts.append('    <div class="table-wrapper"><table class="data-table"><thead><tr><th>Date</th><th>Time</th><th>Game</th><th class="wfc-result-col">Result</th><th>Report</th></tr></thead><tbody>')
        for game in sorted(round_games, key=lambda item: (item.date, item.start_time)):
            parts.append(_game_row_html(game, include_group=False))
        parts.append('    </tbody></table></div>')
        parts.append('  </div>')
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
