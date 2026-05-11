import json
import logging
from pathlib import Path
from core.database import SessionLocal
from batch.eval.runner import calculate_metrics
from batch.eval.calibrate import generate_pr_curves, run_baseline

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def report():
    db = SessionLocal()
    try:
        # 1. Generate Curves
        curve_data = generate_pr_curves(db, Path("docs/calibration_pr_curve.json"))
        
        # 2. Baseline Comparison
        baseline = run_baseline(db)
        
        # 3. Select Operating Point
        best_f1 = -1
        best_threshold = 60
        for r in curve_data:
            if r["f1"] >= best_f1: # Favor higher threshold on tie
                best_f1 = r["f1"]
                best_threshold = r["threshold"]
        
        logger.info(f"New Optimal Threshold: {best_threshold} (F1={best_f1:.2f})")
        
        # 4. Final Metrics
        final_metrics = calculate_metrics(db, threshold=float(best_threshold))
        with open("docs/calibration_final_metrics.json", "w") as f:
            json.dump({"calibrated": final_metrics, "baseline": baseline}, f, indent=2)
            
        logger.info(f"Final Report: Precision={final_metrics['precision']:.2f}, Recall={final_metrics['recall']:.2f}")
        for s, m in final_metrics["scenarios"].items():
            logger.info(f"  {s}: Recall={m['recall']:.2f}")
            
    finally:
        db.close()

if __name__ == "__main__":
    report()
