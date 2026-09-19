from __future__ import annotations

import argparse
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

import batch.eval.runner as runner_module
import core.database as database_module
from batch.eval.kernel_fixtures import write_mini_pipeline_jsonl
from batch.eval.runner import run_pipeline
from batch.eval.scorecard import (
    IncompleteScorecardError,
    assert_scorecard_complete,
    write_scorecard,
)
from core.database import Base, engine  # noqa: F401 — registers SQLite compilers
from core.models import (
    DecisionRecordModel,
    EventModel,
    ProfileArtifactModel,
    ResolvedEventModel,
)
from core.schemas.scorecard import ScorecardRow

_PRODUCTION_STAGES = (
    "ingest_events",
    "process_unresolved_events",
    "build_profiles",
    "process_unscored_events",
    "record_decision",
)


@dataclass
class ProductionCallResult:
    db: Session
    stages: dict[str, bool]
    event_count: int
    resolved_count: int
    profile_count: int
    decision_count: int
    seeded_decision_insert: bool


def _sqlite_url(sqlite_path: Path) -> str:
    return f"sqlite:///{sqlite_path.resolve().as_posix()}"


def bind_sqlite(sqlite_path: Path) -> None:
    """Rebind global engine/SessionLocal to a fresh SQLite file for eval."""
    from sqlalchemy import create_engine

    sqlite_path.parent.mkdir(parents=True, exist_ok=True)
    bound_engine = create_engine(_sqlite_url(sqlite_path))
    Base.metadata.create_all(bound_engine)
    bound_session = sessionmaker(autocommit=False, autoflush=False, bind=bound_engine)

    database_module.engine = bound_engine
    database_module.SessionLocal = bound_session
    runner_module.engine = bound_engine
    runner_module.SessionLocal = bound_session


def dispose_eval_bind(db: Session | None = None) -> None:
    """Close the eval session and dispose the rebound SQLite engine (Windows file lock)."""
    if db is not None:
        db.close()
    bound = getattr(runner_module, "engine", None)
    if bound is not None:
        bound.dispose()
    core_bound = getattr(database_module, "engine", None)
    if core_bound is not None and core_bound is not bound:
        core_bound.dispose()


def run_production_call(
    events_path: Path | str,
    labels_path: Path | str,
    *,
    sqlite_path: Path,
) -> ProductionCallResult:
    bind_sqlite(sqlite_path)
    db, _has_more, _nxt = run_pipeline(Path(events_path), Path(labels_path))
    try:
        event_count = db.scalar(select(func.count()).select_from(EventModel)) or 0
        resolved_count = db.scalar(select(func.count()).select_from(ResolvedEventModel)) or 0
        profile_count = db.scalar(select(func.count()).select_from(ProfileArtifactModel)) or 0
        decision_count = db.scalar(select(func.count()).select_from(DecisionRecordModel)) or 0
        stages = {
            "ingest_events": event_count > 0,
            "process_unresolved_events": resolved_count > 0,
            "build_profiles": profile_count > 0,
            "process_unscored_events": decision_count > 0,
            "record_decision": decision_count > 0,
        }
        if not all(stages.values()):
            missing = [k for k, v in stages.items() if not v]
            raise RuntimeError(f"production call missing stages: {missing}")
        return ProductionCallResult(
            db=db,
            stages=stages,
            event_count=event_count,
            resolved_count=resolved_count,
            profile_count=profile_count,
            decision_count=decision_count,
            seeded_decision_insert=False,
        )
    except Exception:
        dispose_eval_bind(db)
        raise


def _production_call_shape_row() -> ScorecardRow:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        events_path, labels_path = write_mini_pipeline_jsonl(tmp_path)
        result = run_production_call(
            events_path,
            labels_path,
            sqlite_path=tmp_path / "eval.db",
        )
        try:
            return ScorecardRow(
                schema_version="1",
                scenario_id="des.production_call_shape",
                realm="design",
                arm="old_build",
                status="pass",
                failure_class="none",
                expected={"stages": list(_PRODUCTION_STAGES)},
                observed={
                    "stages": result.stages,
                    "event_count": result.event_count,
                    "resolved_count": result.resolved_count,
                    "profile_count": result.profile_count,
                    "decision_count": result.decision_count,
                },
                fixture="deterministic",
                notes="",
            )
        finally:
            dispose_eval_bind(result.db)


def _scenarios_dir() -> Path:
    return Path(__file__).resolve().parents[2] / "tests" / "eval" / "scenarios"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="ALTER_EGO eval kernel (Sprint 1)")
    parser.add_argument("--scorecard-out", type=Path, required=True)
    parser.add_argument("--assert-complete", action="store_true")
    parser.add_argument("--only", dest="only_scenario", default=None)
    args = parser.parse_args(argv)

    rows: list[ScorecardRow] = []
    if args.only_scenario == "des.production_call_shape":
        rows.append(_production_call_shape_row())
    elif args.only_scenario is not None:
        print(f"unknown scenario: {args.only_scenario}", file=sys.stderr)
        return 1
    else:
        scenarios_dir = _scenarios_dir()
        if scenarios_dir.is_dir():
            pass  # YAML loader lands in Task 3+

    write_scorecard(args.scorecard_out, rows)

    if args.assert_complete:
        try:
            assert_scorecard_complete(rows)
        except IncompleteScorecardError as exc:
            print(str(exc), file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
