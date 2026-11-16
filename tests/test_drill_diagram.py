import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT / "connect"))

import connect_content as cc  # noqa: E402
import drill_diagram as dd  # noqa: E402


def _diagram(**overrides) -> dict:
    base = {
        "view": "right",
        "players": [
            {"id": "1", "team": "red", "at": [22, 3]},
            {"id": "2", "team": "red", "at": [36, 3]},
            {"id": "G", "team": "goalie", "at": [35.7, 10]},
        ],
        "balls": [{"id": "b", "with": "1"}],
        "steps": [
            {"text": "Pass.", "actions": [{"pass": "1", "to": "2"}]},
            {"text": "Return into the run.", "actions": [{"run": "1", "to": [28, 4]}, {"pass": "2", "to": "1", "stage": 0}]},
            {"text": "Shot.", "actions": [{"dribble": "1", "to": [31, 8]}, {"shot": "1"}]},
        ],
    }
    base.update(overrides)
    return base


def test_every_action_is_an_arrow_with_its_step_number() -> None:
    out = dd.render(_diagram())
    svg = out["svg"]
    assert svg.count('class="dd-arrow ') == 5
    assert svg.count('class="dd-step-label"') == 5
    assert 'dd-arrow--dribble' in svg and 'dd-arrow--shot' in svg and 'dd-arrow--run' in svg
    assert out["steps"] == ["Pass.", "Return into the run.", "Shot."]
    assert [len(step["stages"]) for step in out["data"]["steps"]] == [1, 1, 2]


def test_pass_into_the_run_arrives_where_the_runner_ends() -> None:
    data = dd.render(_diagram())["data"]
    # Step 3 starts after step 2: player 1 stands at the end of the run and has the ball.
    start = data["steps"][2]["start"]
    assert start["p-1"] == [280.0, 40.0]
    ball_x, ball_y = start["b-b"]
    assert ball_x > 280 and ball_y > 40  # carried next to the player, not on him


def test_shot_goes_to_the_goal_the_shooter_attacks() -> None:
    data = dd.render(_diagram())["data"]
    shot = data["steps"][2]["stages"][1][0]
    assert shot["e"] == "b-b" and shot["ball"] is True


def test_detail_view_scales_symbols_down() -> None:
    small = dd.render(_diagram(view=[20, 33, 0, 12], markings=False))["svg"]
    assert 'viewBox="200 0 130 120"' in small
    assert "--dd-k:0.58" in small
    assert "dd-goal" not in small  # plain floor without markings
    assert "dd-goal" in dd.render(_diagram())["svg"]


@pytest.mark.parametrize("change, message", [
    ({"steps": [{"actions": [{"pass": "9", "to": "1"}]}]}, "unknown player"),
    ({"steps": [{"actions": [{"pass": "2", "to": "1"}]}]}, "has no ball"),
    ({"steps": [{"actions": [{"jump": "1"}]}]}, "unknown action"),
    ({"players": [{"id": "1", "at": [50, 3]}]}, "outside"),
    ({"view": "top"}, "view must be"),
    ({"steps": []}, "at least one step"),
])
def test_broken_diagrams_name_the_problem(change, message) -> None:
    with pytest.raises(dd.DiagramError, match=message):
        dd.render(_diagram(**change))


def test_every_diagram_in_the_repo_belongs_to_a_drill_and_renders() -> None:
    drills = cc.load(ROOT / "connect" / "data")["drills"]
    with_diagram = [item for item in drills if item.diagram]
    files = sorted(path.stem for path in (ROOT / "connect" / "data" / "drill-diagrams").glob("*.json"))
    assert sorted(item.slug for item in with_diagram) == files
    for item in with_diagram:
        assert item.diagram["svg"].startswith("<svg") and item.diagram["thumb"].startswith("<svg")
        assert 'id="dd-' not in item.diagram["thumb"]  # cards use their own ids


def test_local_drills_credit_their_source(tmp_path) -> None:
    drills = {item.slug: item for item in cc.load(ROOT / "connect" / "data")["drills"]}
    local = drills["follow-the-pass-square"]
    assert local.facts[0][0] == "Based on" and "mobilesport.ch" in local.facts[0][1]
    assert local.link.startswith("https://")


def test_a_diagram_without_its_drill_is_skipped_so_the_nightly_deploy_runs(tmp_path, capsys) -> None:
    (tmp_path / "drill-diagrams").mkdir()
    (tmp_path / "drill-diagrams" / "no-such-drill.json").write_text('{"players": [], "steps": []}', encoding="utf-8")
    (tmp_path / "drills.json").write_text('{"items": []}', encoding="utf-8")
    assert cc.load(tmp_path)["drills"] == []
    assert "no-such-drill.json" in capsys.readouterr().out


def test_shots_aim_beside_the_goalie() -> None:
    data = dd.render(_diagram())["data"]
    shot = data["steps"][2]["stages"][1][0]
    svg = dd.render(_diagram())["svg"]
    path = svg.split(f'id="{shot["path"]}"')[1].split('d="')[1].split('"')[0]
    end_y = float(path.split(" L")[-1].split()[1])
    assert end_y == 95.0  # shooter above the middle: upper post (y 9.5 m), not the goalie at 10 m


def test_step_labels_do_not_sit_on_top_of_each_other() -> None:
    import re
    for path in sorted((ROOT / "connect" / "data" / "drill-diagrams").glob("*.json")):
        import json
        svg = dd.render(json.loads(path.read_text(encoding="utf-8")))["svg"]
        k = float(re.search(r"--dd-k:([0-9.]+)", svg).group(1))
        spots = [tuple(map(float, m)) for m in re.findall(r'class="dd-step-label"[^>]*translate\(([-0-9.]+) ([-0-9.]+)\)', svg)]
        for i, a in enumerate(spots):
            for b in spots[i + 1:]:
                assert ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5 >= 10 * k, f"{path.name}: labels at {a} and {b} overlap"


def test_a_carried_ball_moves_with_its_player_and_a_pass_into_a_run_waits_for_the_runner() -> None:
    steps = dd.render(_diagram())["data"]["steps"]
    # Step 2: player 1 runs, player 2 passes into the run -> the pass is tied to the runner.
    run, pass_ = steps[1]["stages"][0]
    assert run == {"e": "p-1", "path": run["path"], "kind": "run"}
    assert pass_["ball"] is True and pass_["into"] == "p-1"
    # Step 3: player 1 dribbles -> the ball takes the player's timing.
    dribble, ball = steps[2]["stages"][0]
    assert dribble["e"] == "p-1" and ball["e"] == "b-b" and ball["with"] == "p-1"
    # A plain pass to a standing player is not tied to anyone.
    assert "into" not in steps[0]["stages"][0][0]


def test_the_goalie_leans_towards_a_shot_and_stays_there() -> None:
    data = dd.render(_diagram())["data"]
    shot_stage = data["steps"][2]["stages"][1]
    assert shot_stage[0]["kind"] == "shot"
    lean = shot_stage[1]
    assert lean["e"] == "p-G" and lean["kind"] == "react"
    # The shot aims at the upper post, so the goalie leans up; later steps would start from there.
    assert data["initial"]["p-G"][1] == 100.0


def test_a_game_can_open_with_its_rule_and_the_rule_must_fit_the_video() -> None:
    out = dd.render(_diagram(intro="3 vs 3 on one goal. Who scores more?"))
    assert out["intro"] == out["data"]["intro"] == "3 vs 3 on one goal. Who scores more?"
    assert dd.render(_diagram())["intro"] == ""
    with pytest.raises(dd.DiagramError, match="intro"):
        dd.render(_diagram(intro="x" * 171))


def test_field_players_are_numbered_on_every_drill() -> None:
    with pytest.raises(dd.DiagramError, match="carry a number"):
        dd.render(_diagram(players=[{"id": "A", "team": "red", "at": [22, 3]}], balls=[], steps=[{"actions": [{"run": "A", "to": [25, 3]}]}]))
    svg = dd.render(_diagram())["svg"]
    assert '<text dy="2.9">G</text>' in svg


def test_every_goal_in_view_gets_a_goalie() -> None:
    without = _diagram(players=[{"id": "1", "team": "red", "at": [22, 3]}, {"id": "2", "team": "red", "at": [36, 3]}])
    data = dd.render(without)["data"]
    assert "p-GR" in data["initial"] and "p-GL" not in data["initial"]  # right half: only the right goal
    full = dict(without, view="full")
    assert {"p-GL", "p-GR"} <= set(dd.render(full)["data"]["initial"])
    assert "p-GR" not in dd.render(dict(without, goalies=False))["data"]["initial"]
    assert "p-GR" not in dd.render(_diagram())["data"]["initial"]  # the drill's own goalie stands there


def test_overview_hides_later_steps_in_the_still_picture() -> None:
    out = dd.render(_diagram(overview=1))
    assert out["overview"] == 1
    assert out["svg"].count("is-later") == 8  # 4 arrows and 4 numbers of steps 2 and 3
    assert "is-later" not in dd.render(_diagram())["svg"]
    with pytest.raises(dd.DiagramError, match="overview"):
        dd.render(_diagram(overview=9))


def test_extra_goals_and_the_joker() -> None:
    out = dd.render(_diagram(view="full", standard_goals=False, goals=[{"at": [18, 10], "facing": "left"}, {"at": [20.8, 0.8], "facing": "down", "size": "small"}],
                             players=[{"id": "1", "team": "red", "at": [22, 3]}, {"id": "J", "team": "joker", "at": [25, 5]}],
                             balls=[], steps=[{"actions": [{"run": "J", "to": [26, 6]}]}]))
    assert out["svg"].count('class="dd-goal"') == 2  # only the two extra goals, no end goals
    assert "p-GL" not in out["data"]["initial"]  # no standard goals, no automatic goalies
    assert '<text dy="2.9">J</text>' in out["svg"]
    with pytest.raises(dd.DiagramError, match="facing"):
        dd.render(_diagram(goals=[{"at": [18, 10], "facing": "sideways"}]))
