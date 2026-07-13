import numpy as np
from pathlib import Path
from core.models import DecisionRecordModel
from batch.eval.runner import run_pipeline, calculate_metrics
from sqlalchemy import select

def analyze_results(db, threshold=45.0, name="DATASET"):
    # Clear caches
    from worker import scorer
    scorer._COHORT_MEMBERS_CACHE = {}
    scorer._NOVELTY_FRACTION_CACHE = {}
    
    stmt = select(DecisionRecordModel.score, DecisionRecordModel.flags)
    results = db.execute(stmt).all()
    
    scores = [r.score for r in results]
    num_alerts = len([r for r in results if r.score >= threshold])
    
    print(f"--- {name} ---")
    print(f"Total Events: {len(results)}")
    print(f"Total Alerts: {num_alerts}")
    if scores:
        print(f"Score Dist: Min={min(scores):.2f}, Max={max(scores):.2f}, Mean={np.mean(scores):.2f}, Std={np.std(scores):.2f}")
        print(f"95th percentile: {np.percentile(scores, 95):.2f}")
        print(f"99th percentile: {np.percentile(scores, 99):.2f}")

    metrics = calculate_metrics(db, threshold=threshold)
    if "scenario_3_coordinated" in metrics["scenarios"]:
        s3 = metrics["scenarios"]["scenario_3_coordinated"]
        print(f"Scenario 3 Recall: {s3['recall']:.4f} ({s3['tp']}/{s3['tp']+s3['fn']})")

if __name__ == "__main__":
    # Threshold held at 45.0
    print("Running Step 3 Analysis (Real Vectorizer)...")
    
    db_benign = run_pipeline(Path("benign_only_events.jsonl"), Path("benign_only_labels.jsonl"))
    analyze_results(db_benign, name="BENIGN ONLY")
    db_benign.close()
    
    db_corr = run_pipeline(Path("correlated_benign_events.jsonl"), Path("correlated_benign_labels.jsonl"))
    analyze_results(db_corr, name="CORRELATED BENIGN")
    db_corr.close()
    
    db_s3 = run_pipeline(Path("scenario3_events.jsonl"), Path("scenario3_labels.jsonl"))
    analyze_results(db_s3, name="SCENARIO 3 MIXED")
    db_s3.close()
