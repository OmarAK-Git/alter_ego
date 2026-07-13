import numpy as np
from pathlib import Path
from core.models import DecisionRecordModel
from batch.eval.runner import run_pipeline
from sqlalchemy import select

def analyze_results(db, threshold=45.0):
    stmt = select(DecisionRecordModel.score, DecisionRecordModel.flags, DecisionRecordModel.entity_id, DecisionRecordModel.timestamp)
    results = db.execute(stmt).all()
    
    scores = [r.score for r in results]
    flags = [r.flags for r in results]
    entities = {r.entity_id for r in results}
    
    # Alert rate
    alerts = [r for r in results if r.score >= threshold]
    num_alerts = len(alerts)
    num_entities = len(entities)
    num_days = 14 # 2 weeks baseline
    alert_rate = num_alerts / (num_entities * num_days) if num_entities > 0 else 0
    
    # Confidence floor saves
    # A "save" is when low_confidence_damping_applied is present AND 
    # the un-dampened score would have been >= threshold.
    # Actually, the dampening logic in scorer.py is:
    # if decision_confidence < config.get("confidence_floor", 0.6):
    #     total_score = min(threshold - 5.0, raw_total)
    # So if "low_confidence_damping_applied" is in flags, we check if raw_total (which isn't stored directly, but we can infer or just check if score is threshold-5)
    # Wait, the scorer doesn't store raw_total. 
    # But if it's dampened, it's capped at 40.0.
    # We can count how many hit exactly 40.0 with the flag.
    saves = [r for r in results if "low_confidence_damping_applied" in r.flags and r.score == (threshold - 5.0)]
    num_saves = len(saves)
    
    print(f"Total Events: {len(results)}")
    print(f"Total Alerts: {num_alerts}")
    print(f"Alert Rate (alerts/entity/day): {alert_rate:.4f}")
    print(f"Score Dist: Min={min(scores):.2f}, Max={max(scores):.2f}, Mean={np.mean(scores):.2f}, Std={np.std(scores):.2f}")
    print(f"Confidence Floor Saves: {num_saves}")
    
    # Percentiles
    p95 = np.percentile(scores, 95)
    p99 = np.percentile(scores, 99)
    print(f"95th percentile: {p95:.2f}")
    print(f"99th percentile: {p99:.2f}")

if __name__ == "__main__":
    print("--- BENIGN ONLY ---")
    db_benign = run_pipeline(Path("benign_only_events.jsonl"), Path("benign_only_labels.jsonl"))
    analyze_results(db_benign)
    db_benign.close()
    
    print("\n--- CORRELATED BENIGN ---")
    db_corr = run_pipeline(Path("correlated_benign_events.jsonl"), Path("correlated_benign_labels.jsonl"))
    analyze_results(db_corr)
    db_corr.close()
