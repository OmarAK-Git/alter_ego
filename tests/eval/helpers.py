from __future__ import annotations

from core.schemas.scorecard import LOCKED_SCENARIO_IDS, ScorecardRow


def scorecard_pairs(rows: list[ScorecardRow]) -> set[tuple[str, str]]:
    return {(r.scenario_id, r.arm) for r in rows}


def expected_pairs() -> set[tuple[str, str]]:
    return {(sid, arm) for sid in LOCKED_SCENARIO_IDS for arm in ("old_build", "new_build")}
