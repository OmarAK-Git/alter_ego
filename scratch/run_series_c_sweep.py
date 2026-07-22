"""Series C sweep harness: S1–S5 + tooling under R-INTERLOCK (seed 42, thr=45).

Do not claim CALIBRATED from this script alone. Full multi-minute execution is SC2.
"""
from __future__ import annotations

import json
import logging
import os
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
os.chdir(REPO_ROOT)
sys.path.insert(0, str(REPO_ROOT))

DB_PATH = REPO_ROOT / "alter_ego_calibrate_series_c.db"
EVENTS_PATH = REPO_ROOT / "scratch" / "series_c_events.jsonl"
LABELS_PATH = REPO_ROOT / "scratch" / "series_c_ground_truth.jsonl"
METRICS_PATH = REPO_ROOT / "scratch" / "series_c_metrics.json"
ANOMALY_THRESHOLD = 45.0
GENERATOR_SEED = 42
CONFIG_VERSION = "2.2"

os.environ["DATABASE_URL"] = f"sqlite:///{DB_PATH.as_posix()}"

from batch.eval.runner import calculate_metrics, run_pipeline  # noqa: E402
from batch.synthetic.generator import EventGenerator  # noqa: E402
from core.database import SessionLocal, engine  # noqa: E402
from core.models import (  # noqa: E402
    AlertWorkflowStateModel,
    DecisionRecordModel,
    EventModel,
    EvalGroundTruthModel,
    ProfileArtifactModel,
)
from sqlalchemy import func, select  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

ACTIVE_ALERT_STATES = frozenset({"new", "acknowledged", "investigating"})


def generate_series_c_mix() -> None:
    """Baseline Jan 1→Jan 22, tooling + S1–S4 as Series B, then S5 with distinct victim."""
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

    # Capture S2 victim from first scenario_2 label so S5 can exclude it
    s2_label = next(lb for lb in labels if lb.get("scenario") == "scenario_2_slow_roll")
    s2_event = next(e for e in events if e.event_id == s2_label["event_id"])
    s2_victim = s2_event.raw_entity_id

    events, labels = gen.inject_scenario_5_patient_cycle(
        events,
        labels,
        start_date + timedelta(days=2),  # ~Jan 3; schedule fits inside Jan 22 window
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


def compute_series_c_extras(db, metrics: dict, threshold: float) -> dict[str, Any]:
    """§4.7 + Design 2 attribution fields (best-effort; mirrors Series B JSON shape)."""
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
    # Best-effort blocked-entity-days: distinct (entity, calendar day) with an
    # active workflow row present at end-of-sweep (row age since updated_at).
    # Prefer shadow-build days when available for a stronger estimate.
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
        blocked_entity_days = len(blocked_entity_ids)  # fallback: ≥1 day each

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
    promotion_coverage = {
        "entities_with_active_promoted_profile": len(promoted_entities & scored_entities),
        "entities_scored": len(scored_entities),
        "fraction": (
            len(promoted_entities & scored_entities) / len(scored_entities)
            if scored_entities
            else None
        ),
    }

    # Ground truth + decisions for attribution
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
            # pre_absorption requires novel-mass vs profile; leave null unless TPs exist
            # and we can cheaply proxy (drift-necessary as weak proxy for Series B shape)
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

        # Shadow-lineage cumulative drift max for attack entity (Series B Q2 field)
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

        # Proxy: ≥1 drift-necessary TP (Design 1 caught_before_absorption without mass)
        scenario_block["caught_before_absorption_proxy"] = bool(
            tps and any(_is_drift_necessary(d, threshold) for d in tps)
        )
        scenario_attribution[scenario] = scenario_block

    return {
        "active_alert_workflow_rows": len(active_rows),
        "auto_resolved_count": int(auto_resolved_count or 0),
        "blocked_entity_count": len(blocked_entity_ids),
        "blocked_entity_days_estimate": blocked_entity_days,
        "promotion_coverage": promotion_coverage,
        "scenarios_with_attribution": scenario_attribution,
    }


def main() -> int:
    if DB_PATH.exists():
        DB_PATH.unlink()
    engine.dispose()

    generate_series_c_mix()

    logger.info("Running day-window pipeline against %s", DB_PATH)
    db = run_pipeline(EVENTS_PATH, LABELS_PATH, window_delta_days=1)
    if db is None:
        logger.error("Pipeline returned no session")
        return 1

    try:
        partition_check = confirm_eval_partitions(db)
        metrics = calculate_metrics(db, threshold=ANOMALY_THRESHOLD)
        extras = compute_series_c_extras(db, metrics, ANOMALY_THRESHOLD)

        # Merge attribution into metrics.scenarios (Series B shape) without losing base fields
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
        metrics["promotion_coverage"] = extras["promotion_coverage"]

        payload = {
            "series": "C",
            "anomaly_threshold": ANOMALY_THRESHOLD,
            "config_version": CONFIG_VERSION,
            "database": str(DB_PATH),
            "events_path": str(EVENTS_PATH),
            "labels_path": str(LABELS_PATH),
            "generator_seed": GENERATOR_SEED,
            "calibrated": False,
            "note": (
                "NOT CALIBRATED. Series C harness output. Do not compare FP/P/R to "
                "Series A or B. Do not overwrite calibration_series_b_metrics.json."
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
