import json
import logging
from pathlib import Path
from batch.eval.runner import run_pipeline, calculate_metrics

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

def generate_pr_curves(db, output_path: Path):
    """Sweeps thresholds and saves results to JSON."""
    results = []
    # Sweep from 10 to 150
    for threshold in range(10, 151, 5):
        metrics = calculate_metrics(db, threshold=float(threshold))
        results.append({
            "threshold": threshold,
            "precision": metrics["precision"],
            "recall": metrics["recall"],
            "f1": metrics["f1"],
            "tp": metrics["tp"],
            "fp": metrics["fp"],
            "fn": metrics["fn"]
        })
    
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2)
    logger.info(f"PR curve data saved to {output_path}")
    return results

def run_baseline(db):
    """
    Computes a simple baseline: 
    Any event with at least 2 novel features (raw_value=1.0) is an anomaly.
    """
    from core.models import DecisionRecordModel
    from sqlalchemy import select
    
    malicious_stmt = select(DecisionRecordModel.event_id, DecisionRecordModel.contributions)
    all_decisions = db.execute(malicious_stmt).all()
    
    baseline_anomalies = set()
    for eid, contributions in all_decisions:
        # Simple heuristic: count novelties
        novel_count = 0
        for c in contributions:
            if "novelty" in c["feature_name"] or "rarity" in c["feature_name"]:
                if c["raw_value"] > 5.0: # High rarity/novelty
                    novel_count += 1
        if novel_count >= 2:
            baseline_anomalies.add(eid)
            
    from core.models import EvalGroundTruthModel
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

def calibrate():
    events_path = Path("events.jsonl")
    labels_path = Path("ground_truth.jsonl")
    
    if not events_path.exists():
        logger.error("No events found. Run generator first.")
        return

    db, _has_more, _ = run_pipeline(events_path, labels_path)
    if not db:
        return
    
    try:
        # 1. Generate Curves
        curve_data = generate_pr_curves(db, Path("docs/calibration_pr_curve.json"))
        
        # 2. Baseline Comparison
        baseline = run_baseline(db)
        logger.info(f"Baseline (Heuristic): Precision={baseline['precision']:.2f}, Recall={baseline['recall']:.2f}")
        
        # 3. Select Operating Point
        # We want high recall (1.0) with best possible precision
        best_f1 = -1
        best_threshold = 60
        for r in curve_data:
            if r["f1"] > best_f1:
                best_f1 = r["f1"]
                best_threshold = r["threshold"]
        
        logger.info(f"Optimal Threshold selected: {best_threshold} (F1={best_f1:.2f})")
        
        # 4. Scenario Breakdown at Optimal Threshold
        final_metrics = calculate_metrics(db, threshold=float(best_threshold))
        with open("docs/calibration_final_metrics.json", "w") as f:
            json.dump({"calibrated": final_metrics, "baseline": baseline}, f, indent=2)
            
    finally:
        db.close()

if __name__ == "__main__":
    calibrate()
