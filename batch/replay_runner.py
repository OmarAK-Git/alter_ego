"""
Replay Runner — Phase 3
Rescores all events in a time window using the currently active scorer and
emits new DecisionRecords tagged with a replay_run_id so original audit
records are never mutated.
"""
import json
import uuid
import logging
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import select, and_

from core.database import SessionLocal
from core.models import ResolvedEventModel, DecisionRecordModel, ProfileArtifactModel
from core.schemas.events import ResolvedEvent
from core.schemas.profiles import ProfileArtifact
from core.schemas.decisions import DecisionRecord
from worker.scorer import score_event, load_scoring_config

logger = logging.getLogger(__name__)


def _orm_to_resolved_event(event: ResolvedEventModel) -> ResolvedEvent:
    event_data = event.event_data
    if isinstance(event_data, str):
        event_data = json.loads(event_data)
    return ResolvedEvent(
        event_id=event.event_id,
        timestamp=event.timestamp,
        event_type=event.event_type,
        raw_entity_id=event.raw_entity_id,
        entity_id=event.entity_id,
        entity_type=event.entity_type,
        resolution_confidence=event.resolution_confidence,
        simulation_partition=event.simulation_partition,
        event_data=event_data,
    )


def _orm_to_profile(profile: ProfileArtifactModel) -> ProfileArtifact:
    return ProfileArtifact(
        entity_id=profile.entity_id,
        entity_type=profile.entity_type,
        profile_version=profile.profile_version,
        created_at=profile.created_at,
        data_window_start=profile.data_window_start,
        data_window_end=profile.data_window_end,
        promoted_at=profile.promoted_at,
        superseded_at=profile.superseded_at,
        is_shadow=profile.is_shadow,
        features=profile.features,
        embedding=profile.embedding,
        embedding_model_id=profile.embedding_model_id,
        embedding_model_version=profile.embedding_model_version,
        embedding_dimensionality=profile.embedding_dimensionality,
        embedding_input_normalizer_version=profile.embedding_input_normalizer_version,
    )


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
    config = load_scoring_config()

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
                            ProfileArtifactModel.is_shadow.is_(False),
                        )
                    )
                    .order_by(ProfileArtifactModel.promoted_at.desc())
                    .limit(1)
                )
                profile_row = db.execute(profile_stmt).scalars().first()

                if profile_row is None:
                    logger.debug(
                        f"[{replay_run_id}] No profile for {event.entity_id} "
                        f"at {event.timestamp} — skipping"
                    )
                    continue

                resolved_event = _orm_to_resolved_event(event)
                profile = _orm_to_profile(profile_row)
                decision: DecisionRecord = score_event(db, resolved_event, profile, config)
                decision = decision.model_copy(update={"replay_run_id": replay_run_id})

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
                    embedding_model_version=decision.embedding_model_version,
                    flags=list(decision.flags) + [f"replay:{replay_run_id}"],
                    replay_run_id=replay_run_id,
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
