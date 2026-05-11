from sqlalchemy.orm import Session
from core.database import SessionLocal
from core.models import DecisionRecordModel
from core.schemas.decisions import DecisionRecord

def record_decision(decision: DecisionRecord, db: Session | None = None):
    if db is None:
        db_session = SessionLocal()
    else:
        db_session = db
        
    try:
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
        from sqlalchemy.exc import IntegrityError
        try:
            db_session.add(db_decision)
            db_session.commit()
        except IntegrityError:
            db_session.rollback()
            raise ValueError("DecisionRecord already exists. Update not allowed.")
    finally:
        if db is None:
            db_session.close()
