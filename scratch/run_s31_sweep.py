"""S3.1 full four-scenario eval sweep under current config (threshold=45)."""
import json
import logging
import os
import sys
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
os.chdir(REPO_ROOT)
sys.path.insert(0, str(REPO_ROOT))

DB_PATH = REPO_ROOT / "alter_ego_calibrate_s31.db"
EVENTS_PATH = REPO_ROOT / "scratch" / "s31_events.jsonl"
LABELS_PATH = REPO_ROOT / "scratch" / "s31_ground_truth.jsonl"
METRICS_PATH = REPO_ROOT / "scratch" / "s31_metrics.json"
ANOMALY_THRESHOLD = 45.0

os.environ["DATABASE_URL"] = f"sqlite:///{DB_PATH.as_posix()}"

from batch.eval.runner import calculate_metrics, run_pipeline  # noqa: E402
from batch.synthetic.generator import EventGenerator  # noqa: E402
from core.database import SessionLocal, engine  # noqa: E402
from core.models import EventModel  # noqa: E402
from sqlalchemy import select  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def generate_four_scenario_mix() -> None:
    gen = EventGenerator(seed=42)
    start_date = datetime(2026, 1, 1)
    end_date = datetime(2026, 1, 15)

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
    events, labels = gen.inject_scenario_3_coordinated(
        events, labels, start_date + timedelta(days=11)
    )
    events, labels = gen.inject_scenario_4_service_abuse(
        events, labels, start_date + timedelta(days=12)
    )

    EVENTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    gen.save_to_disk(events, labels, str(EVENTS_PATH), str(LABELS_PATH))
    logger.info("Generated %s events and %s labels", len(events), len(labels))


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


def main() -> int:
    if DB_PATH.exists():
        DB_PATH.unlink()
    engine.dispose()

    generate_four_scenario_mix()

    logger.info("Running day-window pipeline against %s", DB_PATH)
    db = run_pipeline(EVENTS_PATH, LABELS_PATH, window_delta_days=1)
    if db is None:
        logger.error("Pipeline returned no session")
        return 1

    try:
        partition_check = confirm_eval_partitions(db)
        metrics = calculate_metrics(db, threshold=ANOMALY_THRESHOLD)
        payload = {
            "anomaly_threshold": ANOMALY_THRESHOLD,
            "config_version": "2.2",
            "database": str(DB_PATH),
            "events_path": str(EVENTS_PATH),
            "labels_path": str(LABELS_PATH),
            "generator_seed": 42,
            "partition_check": partition_check,
            "metrics": metrics,
        }
        METRICS_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        logger.info("Metrics at threshold=%s:\n%s", ANOMALY_THRESHOLD, json.dumps(metrics, indent=2))
        print(json.dumps(payload, indent=2))
        return 0
    finally:
        db.close()
        engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
