"""Series I sweep harness: configurable flags/weights (seed 42, thr=45, config 2.2).

Usage examples:
  python scratch/run_series_i_sweep.py --step ws_cadence_5 \\
      --set drift_weights.cadence.enabled=true \\
      --set drift_weights.cadence.weight=5

  python scratch/run_series_i_sweep.py --step fold_01_cadence \\
      --set drift_weights.cadence.enabled=true \\
      --set drift_weights.cadence.weight=5
"""
from __future__ import annotations

import argparse
import contextlib
import json
import logging
import os
import shutil
import sys
import time
from collections import Counter, defaultdict
from datetime import date, datetime, time as dtime, timedelta, timezone
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
os.chdir(REPO_ROOT)
sys.path.insert(0, str(REPO_ROOT))

ANOMALY_THRESHOLD = 45.0
GENERATOR_SEED = 42
CONFIG_VERSION = "2.2"

CONFIG_PATH = REPO_ROOT / "config" / "scoring_config.yaml"
RESULTS_DIR = REPO_ROOT / ".workflow" / "2026-08-02-series-i-serial-calibration" / "results"
SCRATCH_DIR = REPO_ROOT / "scratch"
EVENTS_PATH = SCRATCH_DIR / "series_i_events.jsonl"
LABELS_PATH = SCRATCH_DIR / "series_i_ground_truth.jsonl"

IN_WINDOW_STALENESS_DAYS = 5
ACTIVE_ALERT_STATES = frozenset({"new", "acknowledged", "investigating"})

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)
# Quiet hot-path loggers — per-entity INFO floods dominate wall time on long sweeps.
for _noisy in (
    "batch.profile_builder.builder",
    "worker.scorer",
    "worker.ingest",
    "worker.resolver",
    "worker.recorder",
    "batch.eval.runner",
):
    logging.getLogger(_noisy).setLevel(logging.WARNING)


def _parse_set_arg(raw: str) -> tuple[tuple[str, ...], Any]:
    """Parse ``a.b.c=value`` into ((a,b,c), coerced_value)."""
    if "=" not in raw:
        raise argparse.ArgumentTypeError(f"--set requires key=value, got {raw!r}")
    key, value = raw.split("=", 1)
    path = tuple(p for p in key.split(".") if p)
    if not path:
        raise argparse.ArgumentTypeError(f"empty key in {raw!r}")
    low = value.strip().lower()
    if low in {"true", "false"}:
        coerced: Any = low == "true"
    else:
        try:
            coerced = int(value) if "." not in value else float(value)
        except ValueError:
            try:
                coerced = float(value)
            except ValueError:
                coerced = value
    return path, coerced


def with_config_overrides(overrides: list[tuple[tuple[str, ...], Any]], backup_path: Path):
    """Temporarily patch scoring_config.yaml; restore after."""

    @contextlib.contextmanager
    def _ctx():
        shutil.copy2(CONFIG_PATH, backup_path)
        try:
            with open(CONFIG_PATH, encoding="utf-8") as f:
                config = yaml.safe_load(f)
            for key_path, value in overrides:
                node = config
                for key in key_path[:-1]:
                    if key not in node or not isinstance(node[key], dict):
                        node[key] = {}
                    node = node[key]
                node[key_path[-1]] = value
            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                yaml.safe_dump(config, f, default_flow_style=False, sort_keys=False)
            yield
        finally:
            if backup_path.exists():
                shutil.move(str(backup_path), str(CONFIG_PATH))

    return _ctx()


def end_of_day(day: date) -> datetime:
    return datetime.combine(day, dtime(23, 59, 59))


def generate_series_i_mix() -> None:
    from batch.synthetic.generator import EventGenerator

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


def confirm_eval_partitions(db, labels_path: Path) -> dict:
    from core.models import EventModel
    from sqlalchemy import select

    rows = db.execute(
        select(EventModel.simulation_partition, EventModel.event_id).where(
            EventModel.simulation_partition.like("eval_scenario_%")
        )
    ).all()
    partitions = Counter(p for p, _ in rows)
    malicious_scenarios = set()
    with open(labels_path, encoding="utf-8") as f:
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


def _contrib_drift(decision) -> float:
    for c in decision.contributions or []:
        if isinstance(c, dict) and c.get("feature_name") == "drift_alert":
            return float(c.get("contribution_score", 0.0) or 0.0)
    return 0.0


def _is_drift_necessary(decision, threshold: float) -> bool:
    score = float(decision.score)
    if score < threshold:
        return False
    return (score - _contrib_drift(decision)) < threshold


def promotion_coverage_ever(db) -> dict[str, Any]:
    from core.models import DecisionRecordModel, ProfileArtifactModel
    from sqlalchemy import select

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
        "fraction": (len(covered) / len(scored_entities) if scored_entities else None),
    }


def promotion_coverage_in_window(db, n_days: int = IN_WINDOW_STALENESS_DAYS) -> dict[str, Any]:
    from core.models import DecisionRecordModel
    from sqlalchemy import select
    from worker.profile_store import ProfileStore

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


def per_dimension_drift_decomposition(db) -> dict[str, Any]:
    from core.models import ProfileArtifactModel
    from sqlalchemy import select

    profiles = list(db.execute(select(ProfileArtifactModel)).scalars().all())
    per_dim: dict[str, list[float]] = defaultdict(list)
    for p in profiles:
        for dim in (
            "login_hour",
            "geolocation",
            "endpoint_set",
            "process_name",
            "embedding",
            "cadence",
            "total_volume_delta",
            "geo_velocity",
        ):
            val = (p.features or {}).get(f"{dim}_delta_last_build")
            if val is not None:
                per_dim[dim].append(float(val))
    return {
        dim: {
            "mean": sum(vals) / len(vals) if vals else None,
            "max": max(vals) if vals else None,
            "n": len(vals),
        }
        for dim, vals in per_dim.items()
    }


def compute_extras(db, metrics: dict, threshold: float) -> dict[str, Any]:
    from core.models import (
        AlertWorkflowStateModel,
        DecisionRecordModel,
        EventModel,
        EvalGroundTruthModel,
        ProfileArtifactModel,
    )
    from sqlalchemy import func, select

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


def _reset_calibration_db(db_path: Path, engine) -> None:
    engine.dispose()
    if not db_path.exists():
        return
    for attempt in range(3):
        try:
            db_path.unlink()
            return
        except OSError as exc:
            logger.warning("unlink attempt %s failed for %s: %s", attempt + 1, db_path, exc)
            engine.dispose()
            time.sleep(2)
    quarantine = db_path.with_name(f"{db_path.stem}_quarantine_{int(time.time())}.db")
    try:
        db_path.rename(quarantine)
        logger.warning("Quarantined locked sweep DB to %s", quarantine)
    except OSError as exc:
        logger.warning(
            "Could not quarantine %s (%s); proceeding with in-place table clear",
            db_path,
            exc,
        )


def _scenario_recalls(metrics: dict) -> dict[str, float | None]:
    scenarios = metrics.get("scenarios", {})
    mapping = {
        "s1": "scenario_1_sharp_misuse",
        "s2": "scenario_2_slow_roll",
        "s3": "scenario_3_subtle",
        "s4": "scenario_4_service_abuse",
        "s5": "scenario_5_patient_cycle",
    }
    out: dict[str, float | None] = {}
    for short, key in mapping.items():
        block = scenarios.get(key) or {}
        out[short] = block.get("recall")
    return out


def run_sweep(step: str, overrides: list[tuple[tuple[str, ...], Any]]) -> int:
    db_path = REPO_ROOT / f"alter_ego_calibrate_series_i_{step}.db"
    backup_path = REPO_ROOT / f"config/scoring_config.yaml.series_i_{step}_backup"
    metrics_scratch = SCRATCH_DIR / f"series_i_{step}_metrics.json"
    metrics_workflow = RESULTS_DIR / f"series_i_{step}_metrics.json"
    log_path = RESULTS_DIR / f"series_i_{step}_sweep.log"

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    SCRATCH_DIR.mkdir(parents=True, exist_ok=True)

    os.environ["DATABASE_URL"] = f"sqlite:///{db_path.as_posix()}"

    # Late imports so DATABASE_URL is set first.
    from batch.eval.runner import calculate_metrics, run_pipeline
    from core.database import engine

    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    logging.getLogger().addHandler(file_handler)

    started = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    logger.info("=== Series I step=%s started %s ===", step, started)
    logger.info("Overrides: %s", [( ".".join(k), v) for k, v in overrides])
    logger.info("DB: %s", db_path)

    _reset_calibration_db(db_path, engine)
    if not EVENTS_PATH.exists() or not LABELS_PATH.exists():
        generate_series_i_mix()
    else:
        logger.info("Reusing existing events/labels at %s", EVENTS_PATH)

    t0 = time.time()
    with with_config_overrides(overrides, backup_path):
        db, _, _ = run_pipeline(EVENTS_PATH, LABELS_PATH, window_delta_days=1)

    if db is None:
        logger.error("Pipeline returned no session")
        return 1

    try:
        partition_check = confirm_eval_partitions(db, LABELS_PATH)
        metrics = calculate_metrics(db, threshold=ANOMALY_THRESHOLD)
        extras = compute_extras(db, metrics, ANOMALY_THRESHOLD)

        merged_scenarios = dict(metrics.get("scenarios", {}))
        for scenario, attr in extras["scenarios_with_attribution"].items():
            merged_scenarios[scenario] = attr
        metrics = dict(metrics)
        metrics["scenarios"] = merged_scenarios
        metrics["active_alert_workflow_rows"] = extras["active_alert_workflow_rows"]
        metrics["auto_resolved_count"] = extras["auto_resolved_count"]
        metrics["blocked_entity_count"] = extras["blocked_entity_count"]
        metrics["blocked_entity_days_estimate"] = extras["blocked_entity_days_estimate"]
        metrics["promotion_coverage_ever"] = extras["promotion_coverage_ever"]
        metrics["promotion_coverage_in_window"] = extras["promotion_coverage_in_window"]
        metrics["per_dimension_drift_decomposition"] = per_dimension_drift_decomposition(db)

        elapsed_s = round(time.time() - t0, 1)
        recalls = _scenario_recalls(metrics)
        enabled_flags = {".".join(k): v for k, v in overrides}

        payload = {
            "series": "I",
            "step": step,
            "anomaly_threshold": ANOMALY_THRESHOLD,
            "config_version": CONFIG_VERSION,
            "database": str(db_path),
            "events_path": str(EVENTS_PATH),
            "labels_path": str(LABELS_PATH),
            "generator_seed": GENERATOR_SEED,
            "calibrated": False,
            "enabled_flags_and_weights": enabled_flags,
            "started_at": started,
            "elapsed_seconds": elapsed_s,
            "note": (
                "NOT CALIBRATED. Series I serial calibration campaign harness output. "
                "Do not claim CALIBRATED. Compare against Series E–H baseline and prior "
                "Series I accepted branch baseline only."
            ),
            "partition_check": partition_check,
            "headline": {
                "precision": metrics.get("precision"),
                "recall": metrics.get("recall"),
                "f1": metrics.get("f1"),
                "tp": metrics.get("tp"),
                "fp": metrics.get("fp"),
                "fn": metrics.get("fn"),
                **recalls,
            },
            "metrics": metrics,
        }
        text = json.dumps(payload, indent=2)
        metrics_scratch.write_text(text, encoding="utf-8")
        metrics_workflow.write_text(text, encoding="utf-8")
        logger.info(
            "DONE step=%s elapsed=%.1fs F1=%s R=%s FP=%s S1=%s S4=%s",
            step,
            elapsed_s,
            metrics.get("f1"),
            metrics.get("recall"),
            metrics.get("fp"),
            recalls.get("s1"),
            recalls.get("s4"),
        )
        print(text)
        return 0
    finally:
        db.close()
        engine.dispose()
        logging.getLogger().removeHandler(file_handler)
        file_handler.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Series I configurable calibration sweep")
    parser.add_argument("--step", required=True, help="Step id, e.g. ws_cadence_5")
    parser.add_argument(
        "--set",
        dest="sets",
        action="append",
        default=[],
        type=_parse_set_arg,
        help="Config override path=value (repeatable)",
    )
    parser.add_argument(
        "--generate-only",
        action="store_true",
        help="Only generate events/labels, then exit",
    )
    args = parser.parse_args()

    if args.generate_only:
        generate_series_i_mix()
        return 0

    if not args.sets:
        logger.warning("No --set overrides; running with committed YAML as-is (baseline)")

    return run_sweep(args.step, args.sets)


if __name__ == "__main__":
    raise SystemExit(main())
