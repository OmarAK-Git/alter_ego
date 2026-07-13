"""S3.2: refresh docs/calibration_*.json from alter_ego_calibrate_s31.db."""
import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
os.chdir(REPO_ROOT)
sys.path.insert(0, str(REPO_ROOT))

DB_PATH = REPO_ROOT / "alter_ego_calibrate_s31.db"
ANOMALY_THRESHOLD = 45.0
CONFIG_VERSION = "2.2"
GENERATOR_SEED = 42

os.environ["DATABASE_URL"] = f"sqlite:///{DB_PATH.as_posix()}"

from sqlalchemy import select  # noqa: E402

from core.database import SessionLocal  # noqa: E402
from core.models import DecisionRecordModel, EvalGroundTruthModel  # noqa: E402
from batch.eval.calibrate import generate_pr_curves  # noqa: E402
from batch.eval.runner import calculate_metrics  # noqa: E402


def run_baseline_safe(db) -> dict:
    """Heuristic baseline; tolerates drift-only contribution dicts in S3.1 DB."""
    baseline_anomalies: set = set()
    for eid, contributions in db.execute(
        select(DecisionRecordModel.event_id, DecisionRecordModel.contributions)
    ).all():
        novel_count = 0
        for c in contributions:
            feature_name = c.get("feature_name", "")
            if "novelty" in feature_name or "rarity" in feature_name:
                if c.get("raw_value", 0.0) > 5.0:
                    novel_count += 1
        if novel_count >= 2:
            baseline_anomalies.add(eid)

    malicious_events = {
        row[0]
        for row in db.execute(
            select(EvalGroundTruthModel.event_id).where(
                EvalGroundTruthModel.is_malicious.is_(True)
            )
        ).all()
    }
    tp = len(baseline_anomalies.intersection(malicious_events))
    fp = len(baseline_anomalies - malicious_events)
    fn = len(malicious_events - baseline_anomalies)
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    return {"precision": precision, "recall": recall, "tp": tp, "fp": fp, "fn": fn}


def best_f1_point(curve_data: list[dict]) -> dict:
    best = max(curve_data, key=lambda r: (r["f1"], r["threshold"]))
    return best


def main() -> None:
    if not DB_PATH.exists():
        raise SystemExit(f"Missing S3.1 DB: {DB_PATH}")

    db = SessionLocal()
    try:
        curve_path = REPO_ROOT / "docs" / "calibration_pr_curve.json"
        metrics_path = REPO_ROOT / "docs" / "calibration_final_metrics.json"

        curve_data = generate_pr_curves(db, curve_path)
        baseline = run_baseline_safe(db)
        calibrated = calculate_metrics(db, threshold=ANOMALY_THRESHOLD)
        best = best_f1_point(curve_data)

        payload = {
            "source": "alter_ego_calibrate_s31.db",
            "sweep": "S3.1",
            "config_version": CONFIG_VERSION,
            "generator_seed": GENERATOR_SEED,
            "anomaly_threshold": ANOMALY_THRESHOLD,
            "note": (
                "Post-S1/S2 integrity re-sweep (S3.1 Hybrid C). "
                "Operating point matches current YAML anomaly_threshold; not a CALIBRATED claim."
            ),
            "calibrated": calibrated,
            "baseline": baseline,
        }
        with open(metrics_path, "w") as f:
            json.dump(payload, f, indent=2)

        summary_path = REPO_ROOT / "scratch" / "s32_summary.json"
        with open(summary_path, "w") as f:
            json.dump(
                {
                    "anomaly_threshold": ANOMALY_THRESHOLD,
                    "calibrated": calibrated,
                    "baseline": baseline,
                    "best_f1": best,
                    "curve_points": len(curve_data),
                },
                f,
                indent=2,
            )
        print(json.dumps({"metrics_path": str(metrics_path), "curve_path": str(curve_path), "best_f1": best}, indent=2))
    finally:
        db.close()


if __name__ == "__main__":
    main()
