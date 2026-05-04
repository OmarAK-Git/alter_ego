import sys
import json
import logging
from pathlib import Path
from datetime import datetime, timedelta
from sqlalchemy import select, update

from core.database import SessionLocal
from core.models import DecisionRecordModel, EventModel, EvalGroundTruthModel
from worker.ingest import ingest_events, ingest_ground_truth
from worker.resolver import process_unresolved_events
from batch.profile_builder.builder import build_profiles
from worker.scorer import process_unscored_events

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

def run_pipeline(events_path: Path, labels_path: Path, window_delta_days: int = 1, auto_clear_days: int = 0):
    db = SessionLocal()
    try:
        # Load all events into memory to chunk by time
        events = []
        with open(events_path, "r") as f:
            for line in f:
                if line.strip():
                    events.append(json.loads(line))
                    
        events.sort(key=lambda x: x["timestamp"])
        
        if not events:
            logger.info("No events found.")
            return
            
        start_time = datetime.fromisoformat(events[0]["timestamp"])
        end_time = datetime.fromisoformat(events[-1]["timestamp"])
        
        # Write ground truth immediately
        n_labels = ingest_ground_truth(labels_path, db)
        logger.info(f"Ingested {n_labels} ground truth labels.")
        
        current_window_start = start_time
        window_delta = timedelta(days=window_delta_days)
        
        total_resolved = 0
        total_profiles = 0
        total_scored = 0
        
        while current_window_start <= end_time:
            current_window_end = current_window_start + window_delta
            
            # Find events in this window
            window_events = [e for e in events if current_window_start <= datetime.fromisoformat(e["timestamp"]) < current_window_end]
            
            if window_events:
                # 0. Clear previous active alerts to allow drift to accumulate across cycles
                # If auto_clear_days is 0, we NEVER auto-clear, properly testing Scenario 2 blocking.
                if auto_clear_days > 0:
                    clear_threshold = current_window_start - timedelta(days=auto_clear_days)
                    stmt = update(DecisionRecordModel).where(
                        DecisionRecordModel.is_anomaly == True,
                        DecisionRecordModel.timestamp < clear_threshold
                    ).values(is_anomaly=False)
                    db.execute(stmt)
                    db.commit()
                
                # 1. Ingest Window
                temp_events = Path("temp_window.jsonl")
                with open(temp_events, "w") as f:
                    for e in window_events:
                        f.write(json.dumps(e) + "\n")
                
                ingest_events(temp_events, db)
                if temp_events.exists(): temp_events.unlink()
                
                # 2. Resolve
                n_resolved = process_unresolved_events(db)
                total_resolved += n_resolved
                
                # 3. Build Profiles
                n_profiles = build_profiles(db)
                total_profiles += n_profiles
                
                # 4. Score
                n_scored = process_unscored_events(db)
                total_scored += n_scored
                
                logger.info(f"Window {current_window_start.date()}: Ingested {len(window_events)} | Resolved {n_resolved} | Profiles Built {n_profiles} | Scored {n_scored}")

            current_window_start = current_window_end

        logger.info("--- Final Stats ---")
        logger.info(f"Total Resolved: {total_resolved}")
        logger.info(f"Total Profiles Built: {total_profiles}")
        logger.info(f"Total Scored: {total_scored}")
        
        decisions = db.execute(select(DecisionRecordModel)).scalars().all()
        anomalies = [d for d in decisions if d.is_anomaly]
        logger.info(f"Generated {len(decisions)} decision artifacts. Found {len(anomalies)} anomalies.")
        logger.info("Precision/Recall/F1 reporting is deferred to Phase 2 calibration per SPEC v2 §10.1.")
        
    finally:
        db.close()

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python -m batch.eval.runner <events.jsonl> <ground_truth.jsonl>")
        sys.exit(1)
        
    run_pipeline(Path(sys.argv[1]), Path(sys.argv[2]))
