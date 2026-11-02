"""Cup competitions as their own season phase.

A national cup is stored next to a league season under the phase ``cup``
(``events.phase = 'cup'``, source key ``data_<prefix>-<season>_cup``, content
category ``<prefix><season>-cup``). Every consumer that builds league tables,
league averages, leaders, power rankings or player rankings only reads the
phases ``regular-season`` and ``playoffs``, so cup games cannot leak into them.

Cup games are marked by:
- ``phase == 'cup'`` (events table, ``game_stats``) / category slug ending in ``-cup``,
- ``competition_name`` (for example "Svenska Cupen Herrar"),
- ``tournament_stage_type`` (``elimination`` or ``group-stage``) and
  ``tournament_stage_label`` (the source's round name, for example "Kvartsfinaler").
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

CUP_PHASE = "cup"
STAGE_ELIMINATION = "elimination"
STAGE_GROUP = "group-stage"
CUP_COLUMNS = ("competition_name", "tournament_stage_type", "tournament_stage_label", "tournament_group")


def is_cup_phase(phase: Any) -> bool:
    return str(phase or "").strip() == CUP_PHASE


def is_cup_category(slug: Any) -> bool:
    """True for a content category such as ``ch-26-27-cup``."""
    return str(slug or "").strip().endswith(f"-{CUP_PHASE}")


def cup_columns(
    competition_name: str | None,
    *,
    stage_type: str | None = STAGE_ELIMINATION,
    stage_label: str | None = None,
    group: str | None = None,
) -> dict[str, Any]:
    """The marker columns every event row of a cup game carries."""
    return {
        "competition_name": competition_name or None,
        "tournament_stage_type": stage_type or None,
        "tournament_stage_label": stage_label or None,
        "tournament_group": group or None,
    }


def tag_cup_frame(frame: pd.DataFrame, competition_name: str | None) -> pd.DataFrame:
    """Fill the cup marker columns where a backend did not set them.

    ``competition_name`` comes from the league config and only applies to rows
    without their own; a stage type defaults to ``elimination`` (a cup round).
    """
    tagged = frame.copy()
    for column in CUP_COLUMNS:
        if column not in tagged.columns:
            tagged[column] = None
    if competition_name:
        empty = tagged["competition_name"].isna() | (tagged["competition_name"].astype(str).str.strip() == "")
        tagged.loc[empty, "competition_name"] = competition_name
    empty = tagged["tournament_stage_type"].isna() | (tagged["tournament_stage_type"].astype(str).str.strip() == "")
    tagged.loc[empty, "tournament_stage_type"] = STAGE_ELIMINATION
    return tagged


def tag_cup_csv(csv_path: str | Path, competition_name: str | None) -> int:
    """Tag a freshly scraped cup CSV in place; returns the number of rows."""
    path = Path(csv_path)
    try:
        frame = pd.read_csv(path)
    except pd.errors.EmptyDataError:
        return 0  # nothing scraped; the pipeline reports "no games" itself
    tag_cup_frame(frame, competition_name).to_csv(path, index=False)
    return len(frame)
