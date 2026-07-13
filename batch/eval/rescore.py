import json
import logging
from sqlalchemy import select, delete
from core.database import SessionLocal
from core.models import ResolvedEventModel, DecisionRecordModel
from worker.scorer import score_event, load_scoring_config
from worker.profile_store import ProfileStore
from core.schemas.events import ResolvedEvent

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def rescore():
    db = SessionLocal()
    config = load_scoring_config()
    profile_store = ProfileStore(db)
    
    # 1. Clear old decisions
    db.execute(delete(DecisionRecordModel))
    db.commit()
    
    # 2. Fetch all resolved events
    stmt = select(ResolvedEventModel).order_by(ResolvedEventModel.timestamp)
    events = db.execute(stmt).scalars().all()
    
    count = 0
    for db_event in events:
        profile = profile_store.get_active_profile(db_event.entity_id, db_event.timestamp)
        if not profile:
            continue
        
        event_data_dict = json.loads(db_event.event_data) if isinstance(db_event.event_data, str) else db_event.event_data
        resolved_event = ResolvedEvent(
            event_id=db_event.event_id,
            timestamp=db_event.timestamp,
            event_type=db_event.event_type,
            raw_entity_id=db_event.raw_entity_id,
            entity_id=db_event.entity_id,
            entity_type=db_event.entity_type,
            resolution_confidence=db_event.resolution_confidence,
            simulation_partition=db_event.simulation_partition,
            event_data=event_data_dict
        )
        
        decision = score_event(db, resolved_event, profile, config)
        
        # Manually record to avoid record_decision overhead
        db_decision = DecisionRecordModel(
            decision_id=decision.decision_id,
            event_id=decision.event_id,
            entity_id=decision.entity_id,
            timestamp=decision.timestamp,
            score=decision.score,
            confidence=decision.confidence,
            profile_version=decision.profile_version,
            scoring_config_version=decision.scoring_config_version,
            contributions=[c.model_dump() for c in decision.contributions],
            is_anomaly=decision.is_anomaly,
            cohort_used=decision.cohort_used,
            cohort_unsupported=decision.cohort_unsupported,
            flags=decision.flags
        )
        db.add(db_decision)
        count += 1
        if count % 1000 == 0:
            db.commit()
            logger.info(f"Rescored {count} events...")
            
    db.commit()
    db.close()
    logger.info("Rescoring complete.")

if __name__ == "__main__":
    rescore()
