# Drill diagrams

> **Status:** partly shipped (all 35 drills drawn; more drills and category pages open) · Backlog: [Drill database](../../BACKLOG.md#open) · Code: `connect/drill_diagram.py`, `themes/connect/static/js/drill-diagram.js`, data in `connect/data/drill-diagrams/` and `connect/data/drills_local.json`

## Goal

"floorball drills", "floorball exercises" and "floorball training" bring the most search clicks of all queries (Search Console, November 2026: 47 clicks, 330 impressions). The drill database had 31 drills, every picture drawn by hand in tactical-board.com (with its watermark). Drawing was the bottleneck for adding more.

A drill is now drawn as data. Claude writes the JSON from a drill's description, the build turns it into an SVG, and the page plays it step by step. Adding a drill means writing text and a JSON file, no drawing tool.

## Decisions

- 2026-11-13, Felix: start with the drill database (before per-game stream links). Drills may be taken from public coaching material and rewritten; they are drawn in our own format.
- Own format instead of tactical-board.com or Manim: an SVG is light, works without JavaScript, is readable by crawlers, follows dark mode and can be played step by step. Manim videos stay an option for social clips.
- Copyright: the idea of a drill is free to use, the text and the drawing are not. New drills are written in our own words, drawn fresh and credit the source ("Based on" plus a link to the original). Whole collections are not copied.
- Drills from other sources live in the repo (`connect/data/drills_local.json`), not in Notion, so the Notion sync does not overwrite them and every change is reviewed in a PR. Drills that Felix writes himself can keep coming from Notion; their diagram is added by slug.

## Format

One file per drill: `connect/data/drill-diagrams/<drill slug>.json`. A diagram whose slug matches no drill (for example after a rename in Notion) is skipped with a warning, so the nightly deploy still runs; `tests/test_drill_diagram.py` fails on it in a PR.

```json
{
  "view": "right",
  "players": [
    {"id": "1", "team": "red", "at": [20.9, 2.4]},
    {"id": "2", "team": "blue", "at": [36.6, 2.3]},
    {"id": "G", "team": "goalie", "at": [35.7, 10]}
  ],
  "balls": [{"id": "b", "with": "1"}],
  "cones": [[30, 4]],
  "steps": [
    {"text": "Player 1 passes to Player 2.", "actions": [{"pass": "1", "to": "2"}]},
    {"text": "Player 1 runs, Player 2 passes back into the run.",
     "actions": [{"run": "1", "to": [26.5, 3.2]}, {"pass": "2", "to": "1", "stage": 0}]},
    {"text": "Player 1 attacks and shoots.",
     "actions": [{"dribble": "1", "to": [31.5, 8.2], "via": [[29.6, 4.9]]}, {"shot": "1", "stage": 1}]}
  ]
}
```

- Coordinates in metres on the 40 × 20 m rink: x from the left end board, y from the top board. The right goal line is at x = 36.5, the left one at x = 3.5.
- `view`: `full`, `left`, `right`, or a detail `[x0, x1, y0, y1]`. Players, lines and numbers scale with the size of the view.
- `markings: false` draws a plain floor without lines and goals (drills in free space, squares with cones).
- Teams: `red`, `blue`, `goalie`, `coach`. Field players always carry a number (decided 2026-11-14, Felix: no letters); goalies show G, coaches C. Where the drill text counts per team (Red 1, Blue 1), the label repeats per colour (`"id": "b1", "label": "1"`). Every goal in view gets a goalie automatically unless the drill has one there (`"goalies": false` turns that off).
- `overview`: how many steps the still picture (page, list card, PNG) shows. For drills that go back and forth several times; the rest appears when the drill is played.
- `goals`: goals somewhere else than the two ends, e.g. in the middle or small goals at the boards: `[{"at": [x, y], "facing": "left|right|up|down", "size": "full|small"}]`, the mouth at `at`, open towards `facing`. `"standard_goals": false` removes the two end goals, their creases and the automatic goalies.
- Team `joker` (green, label J) for a player who always plays with the team on the ball.
- Actions: `run` and `dribble` (with `to` and optional `via` points; a dribbling player takes the ball along), `pass` (to a player id or a point), `shot` (to `goal`, the goal on the side the shooter attacks, or `left`, `right`, a point), `pickup` (the nearest free ball within 3 m).
- Order inside a step: moves in stage 0, ball actions in stage 1. An action can set its own `stage`. A pass with `"stage": 0` to a running player arrives where the run ends (pass into the run). Use `"stage": 0` on a pass and `"stage": 1` on the passer's run for "pass, then move".

The drawing: starting positions plus every action as an arrow with its step number. Pass solid, run dashed, dribble wavy, shot thick orange. The player on the page plays the steps one after another; previous steps fade, coming ones are hidden. The play button is tracked as CTA `play_drill_diagram`. Below the legend, "Share on Instagram" makes an image (PNG) or a video (MP4) of the drill as Story/Reel (1080 × 1920) or Post (1080 × 1350), dark or light, in the look of the share studio on the stats site: "Floorball Connect" on top, the title, the rink, the step text (or the numbered steps on the image), floorballconnect.com at the bottom, inside the zones Instagram leaves free. The video runs overview, every step, and an end card. On a phone, Share hands the file to the share sheet (Instagram); elsewhere it is downloaded. Everything is drawn in the browser; the video is recorded in real time with MediaRecorder, MP4 only (Chrome, Safari; Firefox cannot make MP4, so the video button is off there). CTAs `create_drill_video`, `create_drill_image`; completion `share_drill_completed` with `share_method` share_sheet or download.

## Workflow for a new drill

1. Read the source and write the drill in our own words: Setup, Sequence, Coaching Points, Variations, as in the existing drills. Add it to `drills_local.json` with `Source` and `Source URL`.
2. Write the diagram JSON. For an existing drill with a picture, read the positions from the picture (rink in the tactical-board images: x 68 to 1333 px, y 62 to 695 px).
3. `make connect-html` and look at the page; `pytest tests/test_drill_diagram.py`.

## Sources checked (November 2026)

- mobilesport.ch (BASPO / swiss unihockey): many single exercise PDFs and the dossier [Unihockey Grossfeld](https://www.mobilesport.ch/assets/lbwp-cdn/mobilesport/files/2016/07/Unihockey_Grossfeld_d.pdf) (24 pages: warm-up, technique, tactics, small games, sample sessions). Main source so far.
- innebandy.se: [Spelbaserad träning](https://innebandy.se/media/5ztnbc5t/spelbaserad-träning-som-träningsmetodik.pdf), Knäkontroll+ (injury prevention).
- IFF coaching manuals (Individual Technique and Tactics, Team Tactics, Goalkeeping): the floorball.sport links redirect to the IFF home page. Copies exist in the Wayback Machine (floorball.fr, 2014–2023), but the archive blocks automated downloads; not used so far. Felix could download them by hand.
- Czech bachelor theses: [Malkus 2021, attacking combinations](https://dspace5.zcu.cz/bitstream/11025/48024/1/BC%20MALKUS.pdf) used. theses.cz is behind a bot check and was not used; a Budweis thesis (2010) shows its drills only as drawings.
- Floorball Deutschland: [Rahmentrainingskonzeption 04/2026](https://floorball.de/wp-content/uploads/2026/04/RTK-Floorball-Deutschland-26-04.pdf), appendix 3 has small games as short notes; two used.
- No public exercise bank of the Finnish federation found. Paid collections (XPS, the Jukka Aro book) are not used.

## Shipped

- Format, renderer, player script, list thumbnails ("▶ Animated" badge) and tests.
- Decided 2026-11-15, Felix: the Reel (9:16 video) is the default and the main button ("Create Reel"); Reels did very well on Instagram before. Post (4:5) stays as the second option.
- Instagram sharing (2026-11-15): Story/Reel and Post, image or video, dark or light, share sheet on phones. Not yet tested on a real phone.
- Diagrams for all 35 drills (2026-11-14): the 31 from Notion and the 4 from mobilesport.ch. Drills without a written sequence (most video drills) show the diagram steps as "Sequence" on their page. The list cards always show the diagram, not the old picture.
- 4 new drills from mobilesport.ch: Centre-line 2 vs 1 with Backcheck, Attack from the Goalie Throw, 1 vs 1 Dribble Square, Follow-the-Pass Square.
- 13 more drills from the mobilesport.ch dossier (2026-11-14): Shot, Breakout and 2 vs 1; 2 vs 2 with Outside Passers; Streetball 2 vs 2 on One Goal; Goals in the Middle; Three-Goal Game 4 vs 3; Goal Fight 3 vs 3; 2 vs 1 in Both Halves; Joker Game 3 vs 3; Keep-Away; Race to the Ball at the Board; Number Passing; Ego Game; Pass and Duel. 48 drills in all.
- 15 more drills (2026-11-14), 63 in all: 6 kids drills from mobilesport.ch "Unihockey spielend entdecken" (Fruit Salad, Newspaper Reader, Passing Stations, Star Passing, Dribble Round the Cone and Shoot, Knock Down the Cones), 7 attacking combinations from David Malkus' bachelor thesis (University of West Bohemia, 2021), 2 small games from the Floorball Deutschland Rahmentrainingskonzeption 04/2026.

## Open

- Felix to review the diagrams drawn from videos without text; the least certain: 1vs1-2vs1-3vs2, Passing-Queue, Passingsquare with Shot, Double Rondo 5 vs 3, 3 vs 2 Transitions (read from the clips, the exact sequence may differ). Four drills had the wrong picture in Notion (1vs1 into 2vs1, Championship Ball, 1 vs 1, 2vs2, 3 vs 2, Double Shot) and were drawn from their text alone.
- More drills from the sources above, aiming for about 100, including kids drills (`Kids` tag).
- Category pages (passing, shooting, warm-up, kids, 1 vs 1) with an intro text, see the SEO findings in the backlog.
- Notion pictures: "Double Shot", "1vs1 into 2vs1", "Championship Ball" and "1 vs 1, 2vs2, 3 vs 2" carry the picture of "1 vs 1 from Middleline". The pages show the diagram now, the wrong picture is only left in Notion.
- Share image: the `og:image` of drills without a picture is the default image; a PNG of the diagram would be better.
