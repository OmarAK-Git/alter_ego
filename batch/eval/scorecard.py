from __future__ import annotations

from pathlib import Path

from core.schemas.scorecard import LOCKED_SCENARIO_IDS, ScorecardRow


class IncompleteScorecardError(RuntimeError):
    pass


def write_scorecard(path: Path, rows: list[ScorecardRow]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(row.model_dump_json() + "\n")


def read_scorecard(path: Path) -> list[ScorecardRow]:
    rows = []
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                rows.append(ScorecardRow.model_validate_json(line))
    return rows


def assert_scorecard_complete(rows: list[ScorecardRow]) -> None:
    seen = {(r.scenario_id, r.arm) for r in rows}
    expected = {
        (sid, arm) for sid in LOCKED_SCENARIO_IDS for arm in ("old_build", "new_build")
    }
    missing = expected - seen
    if missing:
        raise IncompleteScorecardError(f"missing scorecard rows: {sorted(missing)}")
    if any(r.status in {"fail", "error"} for r in rows):
        bad = [r.scenario_id + ":" + r.arm for r in rows if r.status in {"fail", "error"}]
        raise IncompleteScorecardError(f"fail/error rows: {bad}")
