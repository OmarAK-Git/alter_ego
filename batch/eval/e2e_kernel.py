from __future__ import annotations

import argparse
import hashlib
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

import yaml
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

import batch.eval.runner as runner_module
import core.database as database_module
from batch.eval.kernel_fixtures import write_mini_pipeline_jsonl
from batch.audit_integrity import run_integrity_check
from batch.eval.runner import run_pipeline
from batch.eval.scenario_loader import ScenarioSpec, load_scenario
from batch.eval.scorecard import (
    IncompleteScorecardError,
    assert_scorecard_complete,
    write_scorecard,
)
from batch.eval.theater import TheaterContext, run_theater_detector
from core.database import Base, engine  # noqa: F401 — registers SQLite compilers
from core.models import (
    AlertWorkflowStateModel,
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


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _scenarios_dir() -> Path:
    return _repo_root() / "tests" / "eval" / "scenarios"


def _row(
    spec: ScenarioSpec,
    *,
    arm: str,
    status: str,
    failure_class: str,
    expected: dict,
    observed: dict,
    notes: str = "",
) -> ScorecardRow:
    return ScorecardRow(
        schema_version="1",
        scenario_id=spec.scenario_id,
        realm=spec.realm,
        arm=arm,  # type: ignore[arg-type]
        status=status,  # type: ignore[arg-type]
        failure_class=failure_class,  # type: ignore[arg-type]
        expected=expected,
        observed=observed,
        fixture="deterministic",
        notes=notes,
    )


def _eval_gov_no_knob_without_sweep(spec: ScenarioSpec) -> list[ScorecardRow]:
    yaml_path = _repo_root() / "config" / "scoring_config.yaml"
    baseline_path = _repo_root() / "tests" / "eval" / "fixtures" / "scoring_config_baseline.sha256"
    exceptions_path = _repo_root() / "tests" / "eval" / "fixtures" / "knob_exceptions.yaml"
    digest = hashlib.sha256(yaml_path.read_bytes()).hexdigest()
    baseline = baseline_path.read_text(encoding="utf-8").strip()
    exceptions_doc = yaml.safe_load(exceptions_path.read_text(encoding="utf-8")) or {}
    allowed = {str(item.get("digest", "")) for item in exceptions_doc.get("exceptions", [])}
    unrecorded = digest != baseline and digest not in allowed
    theater_tripped, theater_detail = run_theater_detector(
        "series_j_fold", TheaterContext(staffs_series_j=False)
    )
    if theater_tripped:
        status, failure_class = "fail", "theater_detector"
    elif unrecorded:
        status, failure_class = "fail", "harness"
    else:
        status, failure_class = "pass", "none"
    observed = {
        "knob_diff_unrecorded": unrecorded,
        "yaml_sha256": digest,
    }
    notes = (
        "OPS no-knob-without-sweep pin (repo-file check; no run_pipeline). "
        f"{theater_detail}".strip()
    )
    rows = []
    for arm in ("old_build", "new_build"):
        expected = spec.arms[arm].expected
        rows.append(
            _row(
                spec,
                arm=arm,
                status=status,
                failure_class=failure_class,
                expected=expected,
                observed=observed,
                notes=notes,
            )
        )
    return rows


def _eval_gov_anomaly_opens_workflow(
    spec: ScenarioSpec, *, sqlite_root: Path
) -> list[ScorecardRow]:
    rows: list[ScorecardRow] = []
    theater_tripped, theater_detail = run_theater_detector(
        spec.theater_detector,
        TheaterContext(used_run_pipeline=True, decision_insert_path=None),
    )
    for arm in ("old_build", "new_build"):
        arm_dir = Path(sqlite_root) / spec.scenario_id / arm
        arm_dir.mkdir(parents=True, exist_ok=True)
        events_path, labels_path = write_mini_pipeline_jsonl(arm_dir, night_login=True)
        call = run_production_call(
            events_path, labels_path, sqlite_path=arm_dir / "eval.db"
        )
        try:
            anomalies = list(
                call.db.scalars(
                    select(DecisionRecordModel).where(
                        DecisionRecordModel.is_anomaly.is_(True),
                        DecisionRecordModel.event_id.notin_(
                            ("PROFILE_BUILD", "COHORT_DRIFT")
                        ),
                    )
                )
            )
            workflows = {
                row.decision_id: row.state
                for row in call.db.scalars(select(AlertWorkflowStateModel))
            }
            all_open_new = bool(anomalies) and all(
                workflows.get(dec.decision_id) == "new" for dec in anomalies
            )
            observed = {
                "anomaly_count_gt_0": len(anomalies) > 0,
                "all_anomalies_open_new": all_open_new,
                "seeded_decision_insert": call.seeded_decision_insert,
                "anomaly_count": len(anomalies),
            }
            if theater_tripped:
                status, failure_class = "fail", "theater_detector"
            elif not anomalies:
                status, failure_class = "fail", "harness"
            elif not all_open_new:
                status, failure_class = "fail", "scorer"
            else:
                status, failure_class = "pass", "none"
            rows.append(
                _row(
                    spec,
                    arm=arm,
                    status=status,
                    failure_class=failure_class,
                    expected=spec.arms[arm].expected,
                    observed=observed,
                    notes=theater_detail,
                )
            )
        finally:
            dispose_eval_bind(call.db)
    return rows


def _eval_gov_integrity_job_sees_decisions(
    spec: ScenarioSpec, *, sqlite_root: Path
) -> list[ScorecardRow]:
    rows: list[ScorecardRow] = []
    theater_tripped, theater_detail = run_theater_detector(
        spec.theater_detector,
        TheaterContext(used_run_pipeline=True),
    )
    for arm in ("old_build", "new_build"):
        arm_dir = Path(sqlite_root) / spec.scenario_id / arm
        arm_dir.mkdir(parents=True, exist_ok=True)
        events_path, labels_path = write_mini_pipeline_jsonl(arm_dir)
        call = run_production_call(
            events_path, labels_path, sqlite_path=arm_dir / "eval.db"
        )
        try:
            result = run_integrity_check(call.db, raise_on_failure=False)
            skip = None
            if result.count_check_skipped and (result.decision_audit_count in {0, None}):
                skip = "decision_audit_count==0"
            observed = {
                "decision_count_gt_0": call.decision_count > 0,
                "count_check_skipped": result.count_check_skipped,
                "integrity_skip": skip,
                "decision_audit_count": result.decision_audit_count,
            }
            if theater_tripped:
                status, failure_class = "fail", "theater_detector"
            elif skip == "decision_audit_count==0" and call.decision_count > 0:
                status, failure_class = "pass", "none"
            else:
                status, failure_class = "fail", "harness"
            rows.append(
                _row(
                    spec,
                    arm=arm,
                    status=status,
                    failure_class=failure_class,
                    expected=spec.arms[arm].expected,
                    observed=observed,
                    notes=theater_detail,
                )
            )
        finally:
            dispose_eval_bind(call.db)
    return rows


def evaluate_scenario(scenario_id: str, *, sqlite_root: Path) -> list[ScorecardRow]:
    spec = load_scenario(_scenarios_dir() / f"{scenario_id}.yaml")
    if spec.scenario_id == "gov.no_knob_without_sweep":
        return _eval_gov_no_knob_without_sweep(spec)
    if spec.scenario_id == "gov.anomaly_opens_workflow":
        return _eval_gov_anomaly_opens_workflow(spec, sqlite_root=sqlite_root)
    if spec.scenario_id == "gov.integrity_job_sees_decisions":
        return _eval_gov_integrity_job_sees_decisions(spec, sqlite_root=sqlite_root)
    raise NotImplementedError(f"evaluate_scenario dispatch missing for {scenario_id}")


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
