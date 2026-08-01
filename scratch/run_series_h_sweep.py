"""Series H sweep harness: precision gate + staged drift enabled (seed 42, thr=45)."""
from __future__ import annotations

import contextlib
import json
import logging
import os
import shutil
import sys
from collections import Counter, defaultdict
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
os.chdir(REPO_ROOT)
sys.path.insert(0, str(REPO_ROOT))

DB_PATH = REPO_ROOT / "alter_ego_calibrate_series_h.db"
EVENTS_PATH = REPO_ROOT / "scratch" / "series_h_events.jsonl"
LABELS_PATH = REPO_ROOT / "scratch" / "series_h_ground_truth.jsonl"
METRICS_PATH = REPO_ROOT / "scratch" / "series_h_metrics.json"
ANOMALY_THRESHOLD = 45.0
GENERATOR_SEED = 42
CONFIG_VERSION = "2.2"

CONFIG_PATH = REPO_ROOT / "config" / "scoring_config.yaml"
CONFIG_BACKUP_PATH = REPO_ROOT / "config" / "scoring_config.yaml.series_h_backup"

IN_WINDOW_STALENESS_DAYS = 5

os.environ["DATABASE_URL"] = f"sqlite:///{DB_PATH.as_posix()}"

from batch.eval.runner import calculate_metrics, run_pipeline  # noqa: E402
from batch.synthetic.generator import EventGenerator  # noqa: E402
from core.database import engine  # noqa: E402
from core.models import (  # noqa: E402
    AlertWorkflowStateModel,
    DecisionRecordModel,
    EventModel,
    EvalGroundTruthModel,
    ProfileArtifactModel,
)
from sqlalchemy import func, select  # noqa: E402
from worker.profile_store import ProfileStore  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

ACTIVE_ALERT_STATES = frozenset({"new", "acknowledged", "investigating"})


def with_enabled_flags_for_sweep(enable_paths: list[tuple[tuple[str, ...], bool]]):
    """Temporarily flip config/scoring_config.yaml enabled flags; restore after."""

    @contextlib.contextmanager
    def _ctx():
        shutil.copy2(CONFIG_PATH, CONFIG_BACKUP_PATH)
        try:
            with open(CONFIG_PATH, encoding="utf-8") as f:
                config = yaml.safe_load(f)
            for key_path, value in enable_paths:
                node = config
                for key in key_path[:-1]:
                    if key not in node or not isinstance(node[key], dict):
                        node[key] = {}
                    node = node[key]
                node[key_path[-1]] = value
            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                yaml.safe_dump(config, f)
            yield
        finally:
            if CONFIG_BACKUP_PATH.exists():
                shutil.move(str(CONFIG_BACKUP_PATH), str(CONFIG_PATH))

    return _ctx()


def end_of_day(day: date) -> datetime:
    return datetime.combine(day, time(23, 59, 59))


def promotion_coverage_ever(db) -> dict[str, Any]:
    scored_entities = {
        row[0]
        for row in db.execute(select(DecisionRecordModel.entity_id).distinct()).all()
    }
    promoted_entities = {
        row[0]
        for row in db.execute(
            select(ProfileArtifactModel.entity_id)
            .where(
                ProfileArtifactModel.is_shadow.is_(False),
                ProfileArtifactModel.promoted_at.isnot(None),
                ProfileArtifactModel.superseded_at.is_(None),
            )
            .distinct()
        ).all()
    }
    covered = promoted_entities & scored_entities
    return {
        "entities_with_active_promoted_profile": len(covered),
        "entities_scored": len(scored_entities),
        "fraction": (
            len(covered) / len(scored_entities) if scored_entities else None
        ),
    }


def promotion_coverage_in_window(
    db, n_days: int = IN_WINDOW_STALENESS_DAYS
) -> dict[str, Any]:
    store = ProfileStore(db)
    entity_days: dict[str, set[date]] = defaultdict(set)

    for entity_id, ts in db.execute(
        select(DecisionRecordModel.entity_id, DecisionRecordModel.timestamp)
    ).all():
        score_day = ts.date() if hasattr(ts, "date") else ts
        entity_days[entity_id].add(score_day)

    per_entity_fractions: list[float] = []
    total_fresh = 0
    total_scored_days = 0
    serving_profile_missing_days = 0
    stale_entity_days = 0

    for entity_id, days in entity_days.items():
        fresh_count = 0
        for score_day in sorted(days):
            profile = store.get_active_profile(entity_id, end_of_day(score_day))
            if profile is None:
                serving_profile_missing_days += 1
                continue
            delta = (score_day - profile.data_window_end.date()).days
            if delta <= n_days:
                fresh_count += 1
            else:
                stale_entity_days += 1

        scored_day_count = len(days)
        total_scored_days += scored_day_count
        total_fresh += fresh_count
        if scored_day_count:
            per_entity_fractions.append(fresh_count / scored_day_count)

    return {
        "entities_scored": len(entity_days),
        "scored_entity_days": total_scored_days,
        "in_window_entity_days": total_fresh,
        "stale_entity_days": stale_entity_days,
        "serving_profile_missing_days": serving_profile_missing_days,
        "n_days": n_days,
        "fraction": (
            sum(per_entity_fractions) / len(per_entity_fractions)
            if per_entity_fractions
            else None
        ),
    }


def generate_series_h_mix() -> None:
    gen = EventGenerator(seed=GENERATOR_SEED)
    start_date = datetime(2026, 1, 1)
    end_date = datetime(2026, 1, 22)

    events, labels = gen.generate_baseline(start_date, end_date)
    events = gen.inject_tooling_rollout(
        events, start_date + timedelta(days=5), "Engineer", "new_sec_agent.exe"
    )
    events, labels = gen.inject_scenario_1_sharp_misuse(
        events, labels, start_date + timedelta(days=10)
    )
    events, labels = gen.inject_scenario_2_slow_roll(
        events, labels, start_date + timedelta(days=8)
    )

    s2_label = next(lb for lb in labels if lb.get("scenario") == "scenario_2_slow_roll")
    s2_event = next(e for e in events if e.event_id == s2_label["event_id"])
    s2_victim = s2_event.raw_entity_id

    events, labels = gen.inject_scenario_5_patient_cycle(
        events,
        labels,
        start_date + timedelta(days=2),
        exclude_entity_ids={s2_victim},
    )
    events, labels = gen.inject_scenario_3_coordinated(
        events, labels, start_date + timedelta(days=11)
    )
    events, labels = gen.inject_scenario_4_service_abuse(
        events, labels, start_date + timedelta(days=12)
    )

    EVENTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    gen.save_to_disk(events, labels, str(EVENTS_PATH), str(LABELS_PATH))
    logger.info(
        "Generated %s events and %s labels (S2 victim=%s excluded from S5)",
        len(events),
        len(labels),
        s2_victim,
    )


def confirm_eval_partitions(db) -> dict:
    rows = db.execute(
        select(EventModel.simulation_partition, EventModel.event_id).where(
            EventModel.simulation_partition.like("eval_scenario_%")
        )
    ).all()
    partitions = Counter(p for p, _ in rows)
    malicious_scenarios = set()
    with open(LABELS_PATH, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                rec = json.loads(line)
                if rec.get("is_malicious"):
                    malicious_scenarios.add(rec.get("scenario"))
    return {
        "attack_partitions": dict(sorted(partitions.items())),
        "attack_event_count": sum(partitions.values()),
        "malicious_scenarios_in_labels": sorted(malicious_scenarios),
        "all_partitions_eval_scenario": all(
            p.startswith("eval_scenario_") for p in partitions
        ),
    }


def _contrib_drift(decision: DecisionRecordModel) -> float:
    for c in decision.contributions or []:
        if isinstance(c, dict) and c.get("feature_name") == "drift_alert":
            return float(c.get("contribution_score", 0.0) or 0.0)
    return 0.0


def _is_drift_necessary(decision: DecisionRecordModel, threshold: float) -> bool:
    score = float(decision.score)
    if score < threshold:
        return False
    return (score - _contrib_drift(decision)) < threshold


def signal_family_agreement_distribution(db, threshold: float) -> dict[str, Any]:
    """H14 Stage A: benign-FP vs TP agreement_count distributions separately."""
    decisions = list(db.execute(select(DecisionRecordModel)).scalars().all())
    malicious_event_ids = {
        row[0]
        for row in db.execute(
            select(EvalGroundTruthModel.event_id).where(
                EvalGroundTruthModel.is_malicious.is_(True)
            )
        ).all()
    }
    benign_counts = [
        d.signal_family_agreement_count
        for d in decisions
        if d.is_anomaly and d.event_id not in malicious_event_ids
    ]
    tp_counts = [
        d.signal_family_agreement_count
        for d in decisions
        if d.is_anomaly and d.event_id in malicious_event_ids
    ]

    def _dist(counts: list[int]) -> dict[str, Any]:
        if not counts:
            return {"n": 0}
        c = Counter(counts)
        return {
            "n": len(counts),
            "histogram": dict(sorted(c.items())),
            "mean": sum(counts) / len(counts),
        }

    return {
        "benign_fp_agreement_distribution": _dist(benign_counts),
        "tp_agreement_distribution": _dist(tp_counts),
        "anomaly_threshold": threshold,
    }


def compute_series_h_extras(db, metrics: dict, threshold: float) -> dict[str, Any]:
    active_rows = list(
        db.execute(
            select(AlertWorkflowStateModel).where(
                AlertWorkflowStateModel.state.in_(list(ACTIVE_ALERT_STATES))
            )
        )
        .scalars()
        .all()
    )
    auto_resolved_count = db.execute(
        select(func.count())
        .select_from(AlertWorkflowStateModel)
        .where(AlertWorkflowStateModel.state == "auto_resolved")
    ).scalar_one()

    blocked_entity_ids = {row.entity_id for row in active_rows}
    shadow_rows = list(
        db.execute(
            select(
                ProfileArtifactModel.entity_id,
                ProfileArtifactModel.data_window_end,
            ).where(ProfileArtifactModel.is_shadow.is_(True))
        ).all()
    )
    blocked_entity_days = len(
        {
            (eid, end.date() if hasattr(end, "date") else end)
            for eid, end in shadow_rows
            if eid in blocked_entity_ids
        }
    )
    if blocked_entity_days == 0 and blocked_entity_ids:
        blocked_entity_days = len(blocked_entity_ids)

    gt_rows = db.execute(
        select(
            EvalGroundTruthModel.event_id,
            EvalGroundTruthModel.scenario,
            EvalGroundTruthModel.is_malicious,
        )
    ).all()
    malicious_by_scenario: dict[str, set[str]] = defaultdict(set)
    for event_id, scenario, is_mal in gt_rows:
        if is_mal:
            malicious_by_scenario[scenario].add(event_id)

    all_decisions = list(db.execute(select(DecisionRecordModel)).scalars().all())
    decisions_by_event = {d.event_id: d for d in all_decisions}

    event_entity = {
        row.event_id: row.raw_entity_id
        for row in db.execute(select(EventModel)).scalars().all()
    }

    scenario_attribution: dict[str, Any] = {}
    for scenario, event_ids in malicious_by_scenario.items():
        scenario_block = dict(metrics.get("scenarios", {}).get(scenario, {}))
        tps = []
        scores = []
        for eid in event_ids:
            d = decisions_by_event.get(eid)
            if d is None:
                continue
            scores.append(float(d.score))
            if float(d.score) >= threshold:
                tps.append(d)

        if tps:
            dn = sum(1 for d in tps if _is_drift_necessary(d, threshold))
            scenario_block["drift_necessary_tp_fraction"] = dn / len(tps)
            scenario_block["pre_absorption_tp_fraction"] = None
        else:
            scenario_block["drift_necessary_tp_fraction"] = None
            scenario_block["pre_absorption_tp_fraction"] = None

        if scores:
            scenario_block["early_below_threshold_fraction"] = sum(
                1 for s in scores if s < threshold
            ) / len(scores)
        else:
            scenario_block["early_below_threshold_fraction"] = None

        attack_entities = {event_entity[eid] for eid in event_ids if eid in event_entity}
        cum_max = 0.0
        for entity_id in attack_entities:
            for p in (
                db.execute(
                    select(ProfileArtifactModel).where(
                        ProfileArtifactModel.entity_id == entity_id
                    )
                )
                .scalars()
                .all()
            ):
                cum = float((p.features or {}).get("cumulative_drift", 0.0) or 0.0)
                if cum > cum_max:
                    cum_max = cum
        scenario_block["attack_raised_cumulative_drift_max"] = cum_max

        scenario_block["caught_before_absorption_proxy"] = bool(
            tps and any(_is_drift_necessary(d, threshold) for d in tps)
        )
        scenario_attribution[scenario] = scenario_block

    return {
        "active_alert_workflow_rows": len(active_rows),
        "auto_resolved_count": int(auto_resolved_count or 0),
        "blocked_entity_count": len(blocked_entity_ids),
        "blocked_entity_days_estimate": blocked_entity_days,
        "promotion_coverage_ever": promotion_coverage_ever(db),
        "promotion_coverage_in_window": promotion_coverage_in_window(db),
        "scenarios_with_attribution": scenario_attribution,
    }


def _reset_calibration_db() -> None:
    """Dispose SQLAlchemy pool and ensure a fresh SQLite file for each sweep."""
    import time

    engine.dispose()
    if not DB_PATH.exists():
        return
    for attempt in range(3):
        try:
            DB_PATH.unlink()
            return
        except OSError as exc:
            logger.warning("unlink attempt %s failed for %s: %s", attempt + 1, DB_PATH, exc)
            engine.dispose()
            time.sleep(2)
    quarantine = DB_PATH.with_name(f"{DB_PATH.stem}_quarantine_{int(time.time())}.db")
    try:
        DB_PATH.rename(quarantine)
        logger.warning("Quarantined locked sweep DB to %s", quarantine)
    except OSError as exc:
        logger.warning(
            "Could not quarantine %s (%s); proceeding with in-place table clear",
            DB_PATH,
            exc,
        )


CHECKPOINT_PATH = REPO_ROOT / "scratch" / "series_h_checkpoint.json"
_SWEEP_FLAG_PATHS = [
    (("precision_gate", "enabled"), True),
    (("staged_drift", "enabled"), True),
]


def _run_pipeline_chunked() -> tuple[Any, bool]:
    """One day-window per invocation; returns (db, has_more)."""
    import sys
    from datetime import datetime

    chunked = "--chunked" in sys.argv
    if not chunked:
        with with_enabled_flags_for_sweep(_SWEEP_FLAG_PATHS):
            db, _, _ = run_pipeline(EVENTS_PATH, LABELS_PATH, window_delta_days=1)
        return db, False

    if CHECKPOINT_PATH.exists():
        cp = json.loads(CHECKPOINT_PATH.read_text(encoding="utf-8"))
        resume_from = datetime.fromisoformat(cp["resume_from"])
        clear_first = False
    else:
        _reset_calibration_db()
        if not EVENTS_PATH.exists():
            generate_series_h_mix()
        resume_from = None
        clear_first = True

    with with_enabled_flags_for_sweep(_SWEEP_FLAG_PATHS):
        db, has_more, next_start = run_pipeline(
            EVENTS_PATH,
            LABELS_PATH,
            window_delta_days=1,
            clear_first=clear_first,
            resume_from=resume_from,
            windows_per_invocation=1,
        )
    if has_more and next_start is not None:
        CHECKPOINT_PATH.write_text(
            json.dumps({"resume_from": next_start.isoformat()}), encoding="utf-8"
        )
    else:
        CHECKPOINT_PATH.unlink(missing_ok=True)
    return db, has_more


def main() -> int:
    import sys

    if "--chunked" not in sys.argv:
        _reset_calibration_db()
        generate_series_h_mix()

    logger.info(
        "Running day-window pipeline against %s (precision_gate + staged_drift enabled)",
        DB_PATH,
    )
    db, has_more = _run_pipeline_chunked()
    if db is None:
        logger.error("Pipeline returned no session")
        return 1

    if has_more:
        logger.info("Chunked sweep: more windows remain (exit 2)")
        db.close()
        return 2

    try:
        partition_check = confirm_eval_partitions(db)
        metrics = calculate_metrics(db, threshold=ANOMALY_THRESHOLD)
        extras = compute_series_h_extras(db, metrics, ANOMALY_THRESHOLD)

        merged_scenarios = dict(metrics.get("scenarios", {}))
        for scenario, attr in extras["scenarios_with_attribution"].items():
            merged_scenarios[scenario] = attr
        metrics = dict(metrics)
        metrics["scenarios"] = merged_scenarios
        metrics["active_alert_workflow_rows"] = extras["active_alert_workflow_rows"]
        metrics["auto_resolved_count"] = extras["auto_resolved_count"]
        metrics["blocked_entity_count"] = extras["blocked_entity_count"]
        metrics["blocked_entity_days_estimate"] = extras[
            "blocked_entity_days_estimate"
        ]
        metrics["promotion_coverage_ever"] = extras["promotion_coverage_ever"]
        metrics["promotion_coverage_in_window"] = extras["promotion_coverage_in_window"]
        metrics["signal_family_agreement_distribution"] = (
            signal_family_agreement_distribution(db, ANOMALY_THRESHOLD)
        )
        s3 = merged_scenarios.get("scenario_3_subtle", {})
        metrics["s3_recall"] = s3.get("recall")

        payload = {
            "series": "H",
            "anomaly_threshold": ANOMALY_THRESHOLD,
            "config_version": CONFIG_VERSION,
            "database": str(DB_PATH),
            "events_path": str(EVENTS_PATH),
            "labels_path": str(LABELS_PATH),
            "generator_seed": GENERATOR_SEED,
            "calibrated": False,
            "enabled_flags": {
                "precision_gate.enabled": True,
                "staged_drift.enabled": True,
            },
            "note": (
                "NOT CALIBRATED. Series H harness output (Phases 5–6: precision gate "
                "Stage A + staged drift enabled). Benign-vs-TP agreement histograms are "
                "the evidence base for any future Stage-B threshold proposal. Do not "
                "compare headline FP/P/R to Series A/B/C/D/E/F/G."
            ),
            "partition_check": partition_check,
            "metrics": metrics,
        }
        METRICS_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        logger.info(
            "Metrics at threshold=%s:\n%s",
            ANOMALY_THRESHOLD,
            json.dumps(metrics, indent=2),
        )
        print(json.dumps(payload, indent=2))
        return 0
    finally:
        db.close()
        engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
