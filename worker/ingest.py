import json
from pathlib import Path
from sqlalchemy.orm import Session

from core.database import SessionLocal
from core.models import EventModel, EvalGroundTruthModel
from core.schemas.events import Event

def ingest_events(events_path: str | Path, db: Session | None = None) -> int:
    """Reads events from a JSONL file and ingests them into the database."""
    if db is None:
        db_session = SessionLocal()
    else:
        db_session = db
    
    count = 0
    try:
        with open(events_path, "r") as f:
            for line in f:
                if not line.strip():
                    continue
                # Parse with Pydantic first to ensure contract
                event = Event.model_validate_json(line)
                
                # Convert to DB Model
                db_event = EventModel(
                    event_id=event.event_id,
                    timestamp=event.timestamp,
                    event_type=event.event_type,
                    raw_entity_id=event.raw_entity_id,
                    simulation_partition=event.simulation_partition,
                    event_data=event.event_data.model_dump(mode='json')
                )
                db_session.merge(db_event)
                count += 1
                if count % 1000 == 0:
                    db_session.commit()
        db_session.commit()
    finally:
        if db is None:
            db_session.close()
    return count

def ingest_ground_truth(labels_path: str | Path, db: Session | None = None) -> int:
    """Reads ground truth labels from a JSONL file and ingests them into the database."""
    if db is None:
        db_session = SessionLocal()
    else:
        db_session = db
        
    count = 0
    try:
        with open(labels_path, "r") as f:
            for line in f:
                if not line.strip():
                    continue
                data = json.loads(line)
                
                db_label = EvalGroundTruthModel(
                    event_id=data["event_id"],
                    is_malicious=data["is_malicious"],
                    scenario=data["scenario"]
                )
                db_session.merge(db_label)
                count += 1
                if count % 1000 == 0:
                    db_session.commit()
        db_session.commit()
    finally:
        if db is None:
            db_session.close()
    return count

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 3:
        print("Usage: python -m worker.ingest <events.jsonl> <ground_truth.jsonl>")
        sys.exit(1)
        
    events_file = sys.argv[1]
    labels_file = sys.argv[2]
    
    events_ingested = ingest_events(events_file)
    print(f"Ingested {events_ingested} events.")
    
    labels_ingested = ingest_ground_truth(labels_file)
    print(f"Ingested {labels_ingested} ground truth labels.")
