"""Drill diagrams: a drill drawn as data, rendered to SVG at build time, played step by step in the browser.

A diagram is a JSON file in connect/data/drill-diagrams/<drill slug>.json. The format is
described in docs/features/drill-diagrams.md; in short:

    {
      "view": "full" | "left" | "right" | [x0, x1, y0, y1],  # rink, a half or a detail
      "players": [{"id": "1", "team": "red", "at": [22, 4]}, ...],
      "balls":   [{"id": "b", "with": "1"}] or [{"id": "b", "at": [x, y]}],
      "cones":   [[x, y], ...],
      "overview": 2,                                  # optional: steps the still picture shows
      "intro": "3 vs 3 on one goal ...",              # optional: the rule of a game, shown first; the steps are an example run
      "steps": [
        {"text": "1 passes to 2.", "actions": [{"pass": "1", "to": "2"}]},
        {"text": "1 runs, 2 passes back into the run.",
         "actions": [{"run": "1", "to": [30, 5]}, {"pass": "2", "to": "1", "stage": 0}]},
        ...
      ]
    }

Coordinates are metres on a 40 x 20 m rink, x from the left end board to the right one,
y from the top board down. Teams: red, blue, goalie, coach; field players are numbered, goalies show G, coaches C,
and every goal in view gets a goalie unless the drill has one there ("goalies": false turns
that off). Actions: run, dribble (the
player takes the ball along), pass (to a player or a point), shot (to "goal", the goal on
the side the shooter attacks, or "left"/"right"/a point) and pickup (take the free ball
nearest to the player). Moves (run, dribble) happen in stage 0 and ball actions in stage 1
of a step unless an action names its own "stage"; a pass with "stage": 0 to a running
player arrives as the run ends (pass into the run).

render(diagram, uid) returns the SVG plus the playback data for drill-diagram.js. The SVG
alone already shows the whole drill: starting positions and every action as an arrow
numbered by its step, so the page works without JavaScript and crawlers see the steps.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from html import escape
from pathlib import Path

RINK_W, RINK_H = 40.0, 20.0
UNIT = 10.0  # SVG units per metre
CORNER_R = 3.0
GOAL_LINE = 3.5  # distance of the goal line from the end board
GOAL_HALF = 0.8  # half the goal width (1.6 m)
GOAL_DEPTH = 0.65
CREASE = (2.85, 6.85, 7.5, 12.5)  # goal area: 4 x 5 m
KEEPER_BOX = (3.5, 4.5, 8.75, 11.25)  # goalkeeper area: 1 x 2.5 m
FACEOFF_Y = (1.5, 18.5)
PLAYER_R = 0.75
BALL_R = 0.28
BALL_OFFSET = (0.75, 0.55)  # where a carried ball sits next to the player
VIEWS = {"full": (-1.0, 41.0), "left": (-1.0, 21.5), "right": (18.5, 41.0)}
TEAMS = ("red", "blue", "goalie", "coach", "joker")
ROLE_LABELS = {"goalie": "G", "coach": "C", "joker": "J"}  # roles carry a letter, field players a number
GOAL_SIZES = {"full": (GOAL_HALF, GOAL_DEPTH), "small": (0.5, 0.4)}
FACINGS = ("left", "right", "up", "down")
MOVES = ("run", "dribble")
BALL_ACTIONS = ("pass", "shot", "pickup")


class DiagramError(ValueError):
    """A diagram file that cannot be drawn; the message names the step and the action."""


@dataclass
class Ball:
    id: str
    holder: str | None
    at: tuple[float, float]


def _point(value, where: str) -> tuple[float, float]:
    if not (isinstance(value, (list, tuple)) and len(value) == 2 and all(isinstance(v, (int, float)) for v in value)):
        raise DiagramError(f"{where}: expected a point [x, y], got {value!r}")
    x, y = float(value[0]), float(value[1])
    if not (-0.5 <= x <= RINK_W + 0.5 and -0.5 <= y <= RINK_H + 0.5):
        raise DiagramError(f"{where}: point {value!r} is outside the 40 x 20 m rink")
    return x, y


def _svg(point: tuple[float, float]) -> tuple[float, float]:
    return round(point[0] * UNIT, 1), round(point[1] * UNIT, 1)


def _fmt(points: list[tuple[float, float]]) -> str:
    return "M" + " L".join(f"{x:.1f} {y:.1f}" for x, y in (_svg(p) for p in points))


def _smooth(points: list[tuple[float, float]], samples: int = 14) -> list[tuple[float, float]]:
    """A Catmull-Rom curve through the points, as a polyline. Two points stay a straight line."""
    if len(points) < 3:
        return list(points)
    padded = [points[0], *points, points[-1]]
    out = [points[0]]
    for i in range(1, len(padded) - 2):
        p0, p1, p2, p3 = padded[i - 1], padded[i], padded[i + 1], padded[i + 2]
        for step in range(1, samples + 1):
            t = step / samples
            t2, t3 = t * t, t * t * t
            out.append(tuple(
                0.5 * (2 * p1[k] + (-p0[k] + p2[k]) * t + (2 * p0[k] - 5 * p1[k] + 4 * p2[k] - p3[k]) * t2 + (-p0[k] + 3 * p1[k] - 3 * p2[k] + p3[k]) * t3)
                for k in (0, 1)
            ))
    return out


def _length(points) -> float:
    return sum(math.dist(a, b) for a, b in zip(points, points[1:]))


def _trim(points: list[tuple[float, float]], start: float, end: float) -> list[tuple[float, float]]:
    """The polyline without its first `start` and last `end` metres (arrows stop at a player's edge)."""
    def cut_front(pts, amount):
        while len(pts) > 1 and amount > 0:
            seg = math.dist(pts[0], pts[1])
            if seg > amount:
                f = amount / seg
                return [(pts[0][0] + (pts[1][0] - pts[0][0]) * f, pts[0][1] + (pts[1][1] - pts[0][1]) * f), *pts[1:]]
            amount -= seg
            pts = pts[1:]
        return pts
    if _length(points) <= start + end + 0.3:
        return points
    return list(reversed(cut_front(list(reversed(cut_front(list(points), start))), end)))


def _wave(points: list[tuple[float, float]], amplitude: float = 0.28, wavelength: float = 1.1) -> list[tuple[float, float]]:
    """A dribble line: the path with a sine wave on it, flat again for the last metre before the arrowhead."""
    dense = []
    for a, b in zip(points, points[1:]):
        n = max(1, int(math.dist(a, b) / 0.12))
        dense += [(a[0] + (b[0] - a[0]) * i / n, a[1] + (b[1] - a[1]) * i / n) for i in range(n)]
    dense.append(points[-1])
    total, run, out = _length(dense), 0.0, []
    for i, p in enumerate(dense):
        if i:
            run += math.dist(dense[i - 1], p)
        a, b = dense[max(0, i - 1)], dense[min(len(dense) - 1, i + 1)]
        dx, dy = b[0] - a[0], b[1] - a[1]
        norm = math.hypot(dx, dy) or 1.0
        fade = max(0.0, min(1.0, (total - run - 0.4) / 0.8))
        offset = amplitude * fade * math.sin(2 * math.pi * run / wavelength)
        out.append((p[0] - dy / norm * offset, p[1] + dx / norm * offset))
    return out


def symbol_scale(width: float) -> float:
    """Size of players, balls, lines and labels relative to a half-rink view, so a detail of a
    few metres does not show giant players and a full rink does not show tiny ones."""
    return max(0.5, min(1.5, width / 22.5))


class _Builder:
    def __init__(self, diagram: dict, uid: str):
        self.uid = uid
        view = diagram.get("view", "full")
        if isinstance(view, str) and view in VIEWS:
            self.box = (*VIEWS[view], -1.0, RINK_H + 1.0)
        elif isinstance(view, list) and len(view) == 4 and all(isinstance(v, (int, float)) for v in view) and view[0] < view[1] and view[2] < view[3]:
            self.box = tuple(float(v) for v in view)  # a detail: [x0, x1, y0, y1] in metres
        else:
            raise DiagramError(f"view must be one of {', '.join(VIEWS)} or [x0, x1, y0, y1], got {view!r}")
        self.k = symbol_scale(self.box[1] - self.box[0])
        self.markings = diagram.get("markings", True) is not False  # false: plain floor, e.g. a drill in free space
        self.players: dict[str, dict] = {}
        self.pos: dict[str, tuple[float, float]] = {}
        for index, player in enumerate(diagram.get("players") or []):
            pid = str(player.get("id", "")).strip()
            if not pid or pid in self.players:
                raise DiagramError(f"players[{index}]: missing or repeated id {pid!r}")
            team = player.get("team", "red")
            if team not in TEAMS:
                raise DiagramError(f"player {pid}: team must be one of {', '.join(TEAMS)}")
            if team in ROLE_LABELS:
                label = ROLE_LABELS[team]
            else:
                # Field players are numbered on every drill; the team is the colour.
                label = str(player.get("label", pid))
                if not label.isdigit():
                    raise DiagramError(f"player {pid}: field players carry a number, got {label!r}")
            self.players[pid] = {"id": pid, "team": team, "label": label}
            self.pos[pid] = _point(player.get("at"), f"player {pid}")
        if not self.players:
            raise DiagramError("a diagram needs at least one player")
        # Goals somewhere else than the two ends (in the middle, small goals at the boards):
        # "goals": [{"at": [x, y], "facing": "left", "size": "small"}], the mouth at "at", open
        # towards "facing". "standard_goals": false removes the two end goals and their creases.
        self.standard_goals = diagram.get("standard_goals", True) is not False
        self.extra_goals = []
        for index, goal in enumerate(diagram.get("goals") or []):
            facing, size = goal.get("facing", "left"), goal.get("size", "full")
            if facing not in FACINGS or size not in GOAL_SIZES:
                raise DiagramError(f"goals[{index}]: facing must be one of {', '.join(FACINGS)}, size full or small")
            self.extra_goals.append((_point(goal.get("at"), f"goals[{index}]"), facing, size))
        if self.markings and self.standard_goals and diagram.get("goalies", True) is not False:
            self._add_goalies()
        self.balls: list[Ball] = []
        for index, ball in enumerate(diagram.get("balls") or []):
            bid = str(ball.get("id") or f"b{index + 1}")
            holder = ball.get("with")
            if holder is not None:
                holder = str(holder)
                if holder not in self.players:
                    raise DiagramError(f"ball {bid}: unknown player {holder!r}")
                self.balls.append(Ball(bid, holder, self._carried(self.pos[holder])))
            else:
                self.balls.append(Ball(bid, None, _point(ball.get("at"), f"ball {bid}")))
        self.cones = [_point(cone, f"cones[{i}]") for i, cone in enumerate(diagram.get("cones") or [])]
        # The rule of the game in a sentence or two. The video opens with it, the page shows it above
        # the picture; the steps then read as one example run of the game.
        self.intro = str(diagram.get("intro") or "").strip()
        if len(self.intro) > 170:
            raise DiagramError(f"intro is {len(self.intro)} characters; keep it to 170 so it fits the video")
        self.steps = diagram.get("steps") or []
        # How many steps the still picture shows; drills that go back and forth several times
        # would be a tangle of arrows otherwise. The rest appears when the drill is played.
        self.overview = int(diagram.get("overview") or len(self.steps))
        if self.steps and not 1 <= self.overview <= len(self.steps):
            raise DiagramError(f"overview must be between 1 and the number of steps, got {self.overview}")
        if not self.steps:
            raise DiagramError("a diagram needs at least one step")
        self.arrows: list[str] = []
        self.motion: list[str] = []
        self.labels: list[str] = []
        self.timeline: list[dict] = []
        self.counter = 0
        self.taken: list[tuple[float, float]] = list(self.pos.values())  # spots step labels keep clear of

    def _add_goalies(self) -> None:
        """A goalie in every goal the view shows, unless the drill already has one there."""
        for gid, x, goal_x in (("GL", GOAL_LINE + 0.8, GOAL_LINE), ("GR", RINK_W - GOAL_LINE - 0.8, RINK_W - GOAL_LINE)):
            if not (self.box[0] <= goal_x <= self.box[1]) or not (self.box[2] <= RINK_H / 2 <= self.box[3]):
                continue
            taken = any(p["team"] == "goalie" and abs(self.pos[pid][0] - goal_x) < 4 for pid, p in self.players.items())
            if not taken and gid not in self.players:
                self.players[gid] = {"id": gid, "team": "goalie", "label": "G"}
                self.pos[gid] = (x, RINK_H / 2)

    def _later(self, step: int) -> str:
        return " is-later" if step >= self.overview else ""

    def _carried(self, at: tuple[float, float]) -> tuple[float, float]:
        return at[0] + BALL_OFFSET[0] * self.k, at[1] + BALL_OFFSET[1] * self.k

    # -- state -----------------------------------------------------------------------------
    def _positions(self) -> dict[str, list[float]]:
        out = {f"p-{pid}": list(_svg(at)) for pid, at in self.pos.items()}
        out.update({f"b-{ball.id}": list(_svg(ball.at)) for ball in self.balls})
        return out

    def _ball_of(self, pid: str, where: str) -> Ball:
        for ball in self.balls:
            if ball.holder == pid:
                return ball
        raise DiagramError(f"{where}: player {pid} has no ball to play")

    def _player(self, value, where: str) -> str:
        pid = str(value)
        if pid not in self.players:
            raise DiagramError(f"{where}: unknown player {value!r}")
        return pid

    def _goal(self, target, shooter_at, where: str) -> tuple[float, float]:
        if target in (None, "goal"):
            side = "right" if shooter_at[0] >= RINK_W / 2 else "left"
        elif target in ("left", "right"):
            side = target
        else:
            return _point(target, where)
        # Aim at the post on the shooter's side, so the arrow is not hidden behind the goalie.
        y = RINK_H / 2 + (-0.5 if shooter_at[1] < RINK_H / 2 else 0.5)
        return (RINK_W - GOAL_LINE + 0.3, y) if side == "right" else (GOAL_LINE - 0.3, y)

    def _id(self, kind: str) -> str:
        self.counter += 1
        return f"{self.uid}-{kind}{self.counter}"

    def _arrow(self, kind: str, points, step: int, trim_start: float, trim_end: float) -> str:
        arrow_id = self._id("a")
        line = _trim(_smooth(points), trim_start, trim_end)
        if kind == "dribble":
            line = _wave(line, 0.28 * self.k, 1.1 * self.k)
        head = "shot" if kind == "shot" else "line"
        self.arrows.append(
            f'<path id="{arrow_id}" class="dd-arrow dd-arrow--{kind}{self._later(step)}" data-step="{step}" d="{_fmt(line)}" '
            f'marker-end="url(#{self.uid}-head-{head})"/>'
        )
        # The number sits beside the middle of the arrow, on the side away from the rink centre.
        dense = _trim(line, 0, 0)
        half, run, mid, direction = _length(dense) / 2, 0.0, dense[0], (1.0, 0.0)
        for a, b in zip(dense, dense[1:]):
            seg = math.dist(a, b)
            if run + seg >= half and seg:
                f = (half - run) / seg
                mid, direction = (a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f), ((b[0] - a[0]) / seg, (b[1] - a[1]) / seg)
                break
            run += seg
        normal = (-direction[1], direction[0])
        if (mid[0] - RINK_W / 2) * normal[0] + (mid[1] - RINK_H / 2) * normal[1] < 0:
            normal = (-normal[0], -normal[1])
        # First choice beside the arrow, away from the centre; then the other side, then further out
        # or along the arrow, whichever keeps the most room to other labels and players.
        candidates = []
        for distance in (0.85, 1.5, 2.2):
            for side in (1, -1):
                candidates.append((mid[0] + side * normal[0] * distance * self.k, mid[1] + side * normal[1] * distance * self.k))
        for shift in (-1.4, 1.4, -2.4, 2.4):
            along = (mid[0] + direction[0] * shift * self.k, mid[1] + direction[1] * shift * self.k)
            candidates.append((along[0] + normal[0] * 0.85 * self.k, along[1] + normal[1] * 0.85 * self.k))
        def room(point):
            return min((math.dist(point, other) for other in self.taken), default=99.0)
        clear = 1.25 * self.k
        spot = next((c for c in candidates if room(c) >= clear), max(candidates, key=room))
        self.taken.append(spot)
        x, y = _svg(spot)
        self.labels.append(
            f'<g class="dd-step-label{self._later(step)}" data-step="{step}" transform="translate({x:.1f} {y:.1f}) scale({self.k:.2f})">'
            f'<circle r="5.2"/><text dy="1.9">{step + 1}</text></g>'
        )
        return arrow_id

    def _goalie_reaction(self, aim: tuple[float, float]) -> dict | None:
        """The goalie in the goal a shot flies at leans towards the ball, so the save is not a statue.
        Only a few decimetres; the player script plays it as long as the shot flies and the goalie stays
        where he ended up (the next step starts from there)."""
        goal_x = RINK_W - GOAL_LINE if aim[0] > RINK_W / 2 else GOAL_LINE
        keepers = [pid for pid, player in self.players.items()
                   if player["team"] == "goalie" and abs(self.pos[pid][0] - goal_x) < 4]
        if not keepers:
            return None
        pid = keepers[0]
        at = self.pos[pid]
        lean = max(-0.7, min(0.7, (aim[1] - at[1]) * 1.4)) * self.k
        if abs(lean) < 0.05:
            return None
        end = (at[0], at[1] + lean)
        self.pos[pid] = end
        return {"e": f"p-{pid}", "path": self._motion([at, end]), "kind": "react"}

    def _motion(self, points) -> str:
        motion_id = self._id("m")
        self.motion.append(f'<path id="{motion_id}" class="dd-motion" d="{_fmt(_smooth(points))}"/>')
        return motion_id

    # -- steps -----------------------------------------------------------------------------
    def build(self) -> None:
        for step_index, step in enumerate(self.steps):
            where_step = f"step {step_index + 1}"
            actions = step.get("actions") or []
            if not actions:
                raise DiagramError(f"{where_step}: no actions")
            entry = {"text": str(step.get("text", "")).strip(), "start": self._positions(), "stages": []}
            groups: dict[int, list[tuple[int, dict]]] = {}
            for action_index, action in enumerate(actions):
                kind = next((k for k in (*MOVES, *BALL_ACTIONS) if k in action), None)
                if kind is None:
                    raise DiagramError(f"{where_step}, action {action_index + 1}: unknown action {action!r}")
                stage = int(action.get("stage", 0 if kind in MOVES else 1))
                groups.setdefault(stage, []).append((action_index, action))
            for stage in sorted(groups):
                entry["stages"].append(self._stage(groups[stage], step_index, where_step))
            self.timeline.append(entry)

    def _stage(self, actions, step: int, where_step: str) -> list[dict]:
        moves, starts, moved = [], dict(self.pos), set()
        # Moves first, so a pass in the same stage can go to where the runner ends up.
        for action_index, action in actions:
            kind = next((k for k in MOVES if k in action), None)
            if kind is None:
                continue
            where = f"{where_step}, action {action_index + 1}"
            pid = self._player(action[kind], where)
            start = self.pos[pid]
            end = _point(action.get("to"), where)
            via = [_point(p, where) for p in action.get("via") or []]
            points = [start, *via, end]
            self._arrow(kind, points, step, (PLAYER_R + 0.15) * self.k, (PLAYER_R + 0.25) * self.k)
            moves.append({"e": f"p-{pid}", "path": self._motion(points), "kind": kind})
            self.pos[pid] = end
            moved.add(pid)
            for ball in self.balls:
                if ball.holder == pid:
                    ball.at = self._carried(end)
                    # A carried ball moves with its player: same timing, so it never runs on alone.
                    moves.append({"e": f"b-{ball.id}", "path": self._motion([self._carried(p) for p in points]), "with": f"p-{pid}"})
        for action_index, action in actions:
            kind = next((k for k in BALL_ACTIONS if k in action), None)
            if kind is None:
                continue
            where = f"{where_step}, action {action_index + 1}"
            pid = self._player(action[kind], where)
            from_at = starts[pid]
            if kind == "pickup":
                free = [b for b in self.balls if b.holder is None]
                if not free:
                    raise DiagramError(f"{where}: no free ball to pick up")
                ball = min(free, key=lambda b: math.dist(b.at, self.pos[pid]))
                if math.dist(ball.at, self.pos[pid]) > 3:
                    raise DiagramError(f"{where}: the nearest free ball is more than 3 m away from {pid}")
                ball.holder = pid
                target = self._carried(self.pos[pid])
                moves.append({"e": f"b-{ball.id}", "path": self._motion([ball.at, target]), "ball": True, "kind": "pickup"})
                ball.at = target
                continue
            ball = self._ball_of(pid, where)
            source = ball.at if ball.holder == pid and self.pos[pid] == from_at else self._carried(from_at)
            target = action.get("to")
            into = None
            if kind == "pass":
                if isinstance(target, (str, int)) and str(target) in self.players:
                    receiver = self._player(target, where)
                    end_player = self.pos[receiver]
                    self._arrow("pass", [from_at, end_player], step, (PLAYER_R + 0.2) * self.k, (PLAYER_R + 0.3) * self.k)
                    ball.holder, end = receiver, self._carried(end_player)
                    if receiver in moved:
                        into = f"p-{receiver}"  # pass into the run: arrives when the run ends
                else:
                    end = _point(target, where)
                    self._arrow("pass", [from_at, end], step, (PLAYER_R + 0.2) * self.k, 0.2)
                    ball.holder = None
            else:  # shot
                end = self._goal(target, from_at, where)
                self._arrow("shot", [from_at, end], step, (PLAYER_R + 0.2) * self.k, 0.1)
                ball.holder = None
            move = {"e": f"b-{ball.id}", "path": self._motion([source, end]), "ball": True, "kind": kind}
            if into:
                move["into"] = into
            moves.append(move)
            ball.at = end
            if kind == "shot" and target in (None, "goal", "left", "right"):
                reaction = self._goalie_reaction(end)
                if reaction:
                    moves.append(reaction)
        return moves

    # -- drawing ---------------------------------------------------------------------------
    def rink(self) -> str:
        w, h, r = RINK_W * UNIT, RINK_H * UNIT, CORNER_R * UNIT
        if not self.markings:
            return f'<rect class="dd-floor" x="0" y="0" width="{w:.0f}" height="{h:.0f}" rx="{r:.0f}"/>' + self._extra_goals()
        parts = [f'<rect class="dd-floor" x="0" y="0" width="{w:.0f}" height="{h:.0f}" rx="{r:.0f}"/>',
                 f'<line class="dd-line" x1="{w / 2:.0f}" y1="0" x2="{w / 2:.0f}" y2="{h:.0f}"/>',
                 f'<circle class="dd-spot" cx="{w / 2:.0f}" cy="{h / 2:.0f}" r="2.5"/>']
        for x in (GOAL_LINE, RINK_W / 2, RINK_W - GOAL_LINE):
            for y in FACEOFF_Y:
                cx, cy = _svg((x, y))
                parts.append(f'<path class="dd-line" d="M{cx - 6:.1f} {cy:.1f} H{cx + 6:.1f} M{cx:.1f} {cy - 6:.1f} V{cy + 6:.1f}"/>')
        for mirror in ((False, True) if self.standard_goals else ()):
            def fx(x):
                return RINK_W - x if mirror else x
            x0, x1, y0, y1 = CREASE
            k0, k1, ky0, ky1 = KEEPER_BOX
            parts.append(self._box(fx(x0), fx(x1), y0, y1, "dd-line"))
            parts.append(self._box(fx(k0), fx(k1), ky0, ky1, "dd-line"))
            gx0, gx1 = sorted((fx(GOAL_LINE), fx(GOAL_LINE - GOAL_DEPTH)))
            parts.append(self._box(gx0, gx1, RINK_H / 2 - GOAL_HALF, RINK_H / 2 + GOAL_HALF, "dd-goal"))
        parts.append(self._extra_goals())
        parts.append(f'<rect class="dd-board" x="0" y="0" width="{w:.0f}" height="{h:.0f}" rx="{r:.0f}"/>')
        return "".join(parts)

    def _extra_goals(self) -> str:
        out = []
        for (x, y), facing, size in self.extra_goals:
            half, depth = GOAL_SIZES[size]
            if facing in ("left", "right"):
                back = x + depth if facing == "left" else x - depth
                out.append(self._box(min(x, back), max(x, back), y - half, y + half, "dd-goal"))
            else:
                back = y - depth if facing == "down" else y + depth
                (ax, ay), (bx, by) = _svg((x - half, min(y, back))), _svg((x + half, max(y, back)))
                out.append(f'<rect class="dd-goal" x="{ax:.1f}" y="{ay:.1f}" width="{bx - ax:.1f}" height="{by - ay:.1f}"/>')
        return "".join(out)

    @staticmethod
    def _box(x0, x1, y0, y1, cls) -> str:
        (ax, ay), (bx, by) = _svg((min(x0, x1), y0)), _svg((max(x0, x1), y1))
        return f'<rect class="{cls}" x="{ax:.1f}" y="{ay:.1f}" width="{bx - ax:.1f}" height="{by - ay:.1f}"/>'

    def entities(self, start: dict[str, list[float]]) -> str:
        out = []
        k = self.k
        for x, y in self.cones:
            cx, cy = _svg((x, y))
            out.append(f'<path class="dd-cone" transform="translate({cx:.1f} {cy:.1f}) scale({k:.2f})" d="M0 -4.5 L4 3.5 L-4 3.5 Z"/>')
        r = PLAYER_R * UNIT
        for pid, player in self.players.items():
            x, y = start[f"p-{pid}"]
            out.append(
                f'<g class="dd-player dd-player--{player["team"]}" data-entity="p-{escape(pid)}" transform="translate({x:.1f} {y:.1f})">'
                f'<g transform="scale({k:.2f})"><circle r="{r:.1f}"/><text dy="2.9">{escape(player["label"])}</text></g></g>'
            )
        for ball in self.balls:
            x, y = start[f"b-{ball.id}"]
            out.append(f'<g class="dd-ball" data-entity="b-{escape(ball.id)}" transform="translate({x:.1f} {y:.1f})"><circle r="{BALL_R * UNIT * k:.1f}"/></g>')
        return "".join(out)


def render(diagram: dict, uid: str = "dd", title: str = "") -> dict:
    """{"svg": the SVG markup, "data": playback data for drill-diagram.js, "steps": step texts}."""
    builder = _Builder(diagram, uid)
    initial = builder._positions()
    builder.build()
    x0, x1, y0, y1 = builder.box
    view_box = f"{x0 * UNIT:.0f} {y0 * UNIT:.0f} {(x1 - x0) * UNIT:.0f} {(y1 - y0) * UNIT:.0f}"
    heads = (
        f'<marker id="{uid}-head-line" class="dd-head" viewBox="0 0 10 10" refX="7" refY="5" markerWidth="5" markerHeight="5" orient="auto-start-reverse"><path d="M0 0 L10 5 L0 10 Z"/></marker>'
        f'<marker id="{uid}-head-shot" class="dd-head dd-head--shot" viewBox="0 0 10 10" refX="7" refY="5" markerWidth="4" markerHeight="4" orient="auto-start-reverse"><path d="M0 0 L10 5 L0 10 Z"/></marker>'
    )
    label = escape(title or "Drill diagram")
    svg = (
        f'<svg class="dd-svg" viewBox="{view_box}" style="--dd-k:{builder.k:.2f}" role="img" aria-labelledby="{uid}-title" xmlns="http://www.w3.org/2000/svg">'
        f'<title id="{uid}-title">{label}</title><defs>{heads}</defs>'
        f'<g class="dd-rink">{builder.rink()}</g>'
        f'<g class="dd-motions">{"".join(builder.motion)}</g>'
        f'<g class="dd-arrows">{"".join(builder.arrows)}</g>'
        f'<g class="dd-entities">{builder.entities(initial)}</g>'
        f'<g class="dd-labels">{"".join(builder.labels)}</g>'
        f'</svg>'
    )
    data = {"initial": initial, "steps": builder.timeline, "intro": builder.intro}
    return {"svg": svg, "data": data, "steps": [entry["text"] for entry in builder.timeline], "overview": builder.overview, "intro": builder.intro}


def load_all(directory: Path | str) -> dict[str, dict]:
    """Every diagram file in the directory, by drill slug (the file name without .json)."""
    out = {}
    for path in sorted(Path(directory).glob("*.json")):
        try:
            out[path.stem] = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as error:
            raise DiagramError(f"{path.name}: not valid JSON ({error})") from error
    return out
