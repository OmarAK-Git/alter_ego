import sys
import json
import logging
import sqlite3
from pathlib import Path
from datetime import datetime, timedelta
from sqlalchemy import select, update, delete, func

from core.database import SessionLocal, Base, engine
from core.models import (
    DecisionRecordModel, EventModel, EvalGroundTruthModel, 
    ResolvedEventModel, ProfileArtifactModel, ContainmentQueueModel
)
from worker.ingest import ingest_events, ingest_ground_truth
from worker.resolver import process_unresolved_events
from batch.profile_builder.builder import build_profiles
from worker.scorer import process_unscored_events

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

def clear_db(db):
    """Clears all tables to ensure a clean evaluation run."""
    logger.info("Clearing database tables...")
    db.execute(delete(DecisionRecordModel))
    db.execute(delete(ResolvedEventModel))
    db.execute(delete(EventModel))
    db.execute(delete(EvalGroundTruthModel))
    db.execute(delete(ProfileArtifactModel))
    db.execute(delete(ContainmentQueueModel))
    db.commit()

def calculate_metrics(db, threshold=None):
    """Calculates precision, recall, and F1 at a specific threshold."""
    # 1. Fetch all malicious events from ground truth
    malicious_stmt = select(EvalGroundTruthModel.event_id, EvalGroundTruthModel.scenario).where(EvalGroundTruthModel.is_malicious == True)
    malicious_events = {row[0]: row[1] for row in db.execute(malicious_stmt).all()}
    
    # 2. Fetch all scores from decisions
    score_stmt = select(DecisionRecordModel.event_id, DecisionRecordModel.score)
    all_scores = {row[0]: row[1] for row in db.execute(score_stmt).all()}
    
    if threshold is None:
        # Use whatever is in the DB (the is_anomaly flag)
        anomaly_stmt = select(DecisionRecordModel.event_id).where(DecisionRecordModel.is_anomaly == True)
        detected_anomalies = {row[0] for row in db.execute(anomaly_stmt).all()}
    else:
        # Re-apply threshold
        detected_anomalies = {eid for eid, score in all_scores.items() if score >= threshold}
    
    # 3. Calculate metrics
    scenarios = db.execute(select(EvalGroundTruthModel.scenario).distinct()).scalars().all()
    
    tp = len(detected_anomalies.intersection(malicious_events.keys()))
    fp = len(detected_anomalies - malicious_events.keys())
    fn = len(malicious_events.keys() - detected_anomalies)
    tn = len(all_scores) - (tp + fp + fn)
    
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
    
    results = {
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": tn,
        "drift_alerts": len([r for r in db.execute(select(DecisionRecordModel).where(func.json_extract(DecisionRecordModel.flags, '$.drift_alert') == True)).all()]),
        "scenarios": {}
    }
    
    for scenario in scenarios:
        scenario_malicious = {eid for eid, s in malicious_events.items() if s == scenario}
        if not scenario_malicious: continue
        s_tp = len(detected_anomalies.intersection(scenario_malicious))
        s_fn = len(scenario_malicious - detected_anomalies)
        s_recall = s_tp / (s_tp + s_fn) if (s_tp + s_fn) > 0 else 0.0
        results["scenarios"][scenario] = {"recall": s_recall, "tp": s_tp, "fn": s_fn}
        
    return results

def run_pipeline(events_path: Path, labels_path: Path, window_delta_days: int = 1):
    Base.metadata.create_all(engine)
    db = SessionLocal()
    try:
        clear_db(db)
        
        events = []
        with open(events_path, "r") as f:
            for line in f:
                if line.strip():
                    events.append(json.loads(line))
        events.sort(key=lambda x: x["timestamp"])
        
        if not events: return
        start_time = datetime.fromisoformat(events[0]["timestamp"])
        end_time = datetime.fromisoformat(events[-1]["timestamp"])
        
        ingest_ground_truth(labels_path, db)
        
        current_window_start = start_time
        window_delta = timedelta(days=window_delta_days)
        
        while current_window_start <= end_time:
            current_window_end = current_window_start + window_delta
            window_events = [e for e in events if current_window_start <= datetime.fromisoformat(e["timestamp"]) < current_window_end]
            
            if window_events:
                temp_events = Path(f"temp_window_{current_window_start.strftime('%Y%m%d')}.jsonl")
                with open(temp_events, "w") as f:
                    for e in window_events: f.write(json.dumps(e) + "\n")
                
                ingest_events(temp_events, db)
                if temp_events.exists(): temp_events.unlink()
                process_unresolved_events(db)
                build_profiles(db, as_of=current_window_end)
                process_unscored_events(db)
                logger.info(f"Processed window ending {current_window_end.date()}")

            current_window_start = current_window_end

        # Return the DB session for further calibration if needed
        return db
    except Exception as e:
        db.close()
        raise e

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python -m batch.eval.runner <events.jsonl> <ground_truth.jsonl>")
        sys.exit(1)
        
    db = run_pipeline(Path(sys.argv[1]), Path(sys.argv[2]))
    if db:
        metrics = calculate_metrics(db)
        logger.info(f"Final Metrics: {json.dumps(metrics, indent=2)}")
        db.close()
