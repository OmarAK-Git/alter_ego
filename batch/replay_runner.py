"""
Replay Runner — Phase 3
Rescores all events in a time window using the currently active scorer and
emits new DecisionRecords tagged with a replay_run_id so original audit
records are never mutated.
"""
import uuid
import logging
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import select, and_

from core.database import SessionLocal
from core.models import ResolvedEventModel, DecisionRecordModel, ProfileArtifactModel
from core.schemas.decisions import DecisionRecord
from worker.scorer import score_event

logger = logging.getLogger(__name__)


def run_replay(
    start_time: datetime,
    end_time: datetime,
    author: str,
    change_reason: str,
    replay_run_id: str | None = None,
    db: Session | None = None,
) -> dict:
    """
    Replay all resolved events in [start_time, end_time] under the current scorer.

    Returns a summary dict: {replay_run_id, events_replayed, decisions_emitted,
                              errors, started_at, finished_at}
    """
    if replay_run_id is None:
        replay_run_id = f"replay_{uuid.uuid4().hex[:12]}"

    close_db = db is None
    if db is None:
        db = SessionLocal()

    started_at = datetime.utcnow()
    events_replayed = 0
    decisions_emitted = 0
    errors = []

    try:
        stmt = (
            select(ResolvedEventModel)
            .where(
                and_(
                    ResolvedEventModel.timestamp >= start_time,
                    ResolvedEventModel.timestamp <= end_time,
                    ResolvedEventModel.simulation_partition == "production",
                )
            )
            .order_by(ResolvedEventModel.timestamp)
        )
        events = db.execute(stmt).scalars().all()
        logger.info(
            f"[{replay_run_id}] Replaying {len(events)} events "
            f"from {start_time.isoformat()} to {end_time.isoformat()}"
        )

        for event in events:
            events_replayed += 1
            try:
                # Fetch the profile that was active *at the time of the event*
                profile_stmt = (
                    select(ProfileArtifactModel)
                    .where(
                        and_(
                            ProfileArtifactModel.entity_id == event.entity_id,
                            ProfileArtifactModel.promoted_at <= event.timestamp,
                            ProfileArtifactModel.is_shadow == False,
                        )
                    )
                    .order_by(ProfileArtifactModel.promoted_at.desc())
                    .limit(1)
                )
                profile = db.execute(profile_stmt).scalars().first()

                if profile is None:
                    logger.debug(
                        f"[{replay_run_id}] No profile for {event.entity_id} "
                        f"at {event.timestamp} — skipping"
                    )
                    continue

                decision: DecisionRecord = score_event(event, profile)

                # Tag decision with replay metadata so it's distinguishable
                replay_decision_id = f"{replay_run_id}_{decision.decision_id}"

                db_decision = DecisionRecordModel(
                    decision_id=replay_decision_id,
                    event_id=event.event_id,
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
                    flags=list(decision.flags) + [f"replay:{replay_run_id}"],
                )
                db.add(db_decision)
                decisions_emitted += 1

            except Exception as e:
                errors.append({"event_id": event.event_id, "error": str(e)})
                logger.warning(f"[{replay_run_id}] Error on event {event.event_id}: {e}")

        db.commit()

    finally:
        if close_db:
            db.close()

    finished_at = datetime.utcnow()
    summary = {
        "replay_run_id": replay_run_id,
        "author": author,
        "change_reason": change_reason,
        "events_replayed": events_replayed,
        "decisions_emitted": decisions_emitted,
        "errors": errors,
        "started_at": started_at.isoformat(),
        "finished_at": finished_at.isoformat(),
    }
    logger.info(f"[{replay_run_id}] Replay complete: {summary}")
    return summary
