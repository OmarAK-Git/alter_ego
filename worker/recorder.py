from sqlalchemy.orm import Session
from core.database import SessionLocal
from core.models import DecisionRecordModel, ContainmentQueueModel, AlertWorkflowStateModel
from core.schemas.decisions import DecisionRecord


def queue_simulated_containment(
    db: Session, decision_id: str, entity_id: str
) -> ContainmentQueueModel:
    """Enqueue simulated containment — same semantics as manual API contain path."""
    cq = ContainmentQueueModel(
        decision_id=decision_id,
        entity_id=entity_id,
        action="simulate_containment",
        status="pending",
    )
    db.add(cq)
    return cq


def open_active_alert_if_needed(
    db: Session, decision_id: str, entity_id: str
) -> AlertWorkflowStateModel | None:
    """SPEC §5.5: anomaly → active workflow state so profile builds block.

    Without this, DecisionRecord.is_anomaly alone never arms build-blocking
    (builder keys only on AlertWorkflowState in {new, acknowledged, investigating}).
    """
    existing = (
        db.query(AlertWorkflowStateModel)
        .filter(AlertWorkflowStateModel.decision_id == decision_id)
        .first()
    )
    if existing:
        return existing
    state = AlertWorkflowStateModel(
        decision_id=decision_id,
        entity_id=entity_id,
        state="new",
    )
    db.add(state)
    return state


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
            if decision.is_anomaly:
                open_active_alert_if_needed(
                    db_session, decision.decision_id, decision.entity_id
                )
            if "simulated_containment_queued" in decision.flags:
                queue_simulated_containment(
                    db_session, decision.decision_id, decision.entity_id
                )
            db_session.commit()
        except IntegrityError:
            db_session.rollback()
            raise ValueError("DecisionRecord already exists. Update not allowed.")
    finally:
        if db is None:
            db_session.close()
