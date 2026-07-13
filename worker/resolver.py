from sqlalchemy.orm import Session
from sqlalchemy import select

from core.database import SessionLocal
from core.models import EventModel, ResolvedEventModel
from core.schemas.events import Event, ResolvedEvent

# Confidence below this threshold triggers the low_resolution_confidence decision flag.
LOW_RESOLUTION_THRESHOLD = 0.75
COLLISION_SPLIT_CONFIDENCE = 0.3

_COLLISION_PREFIX = "collide::"
_SPLIT_PREFIX = "split::"


def _entity_type_for_canonical(canonical_id: str) -> str:
    if canonical_id.startswith("user_"):
        return "human"
    if canonical_id.startswith("svc_"):
        return "service_account"
    return "unknown"


def resolve_entity(raw_entity_id: str) -> tuple[str, str, float]:
    """
    Returns (entity_id, entity_type, confidence).
    For Phase 1, we use deterministic prefixes.
    user_X -> human
    svc_X -> service_account
    collide::<canonical>::<alias> -> collision fixture (low confidence)
    split::<ref> -> split/ambiguity fixture (low confidence)
    """
    if raw_entity_id.startswith(_COLLISION_PREFIX):
        rest = raw_entity_id[len(_COLLISION_PREFIX) :]
        canonical, _alias = rest.split("::", 1)
        return canonical, _entity_type_for_canonical(canonical), COLLISION_SPLIT_CONFIDENCE

    if raw_entity_id.startswith(_SPLIT_PREFIX):
        ref = raw_entity_id[len(_SPLIT_PREFIX) :]
        return ref, _entity_type_for_canonical(ref), COLLISION_SPLIT_CONFIDENCE

    if raw_entity_id.startswith("user_"):
        return raw_entity_id, "human", 1.0
    if raw_entity_id.startswith("svc_"):
        return raw_entity_id, "service_account", 1.0

    return raw_entity_id, "unknown", 0.5

def process_unresolved_events(db: Session | None = None) -> int:
    """
    Finds all events that have not been resolved and resolves them.
    """
    if db is None:
        db_session = SessionLocal()
    else:
        db_session = db
        
    count = 0
    try:
        # Find events where event_id is not in resolved_events
        stmt = select(EventModel).outerjoin(
            ResolvedEventModel, EventModel.event_id == ResolvedEventModel.event_id
        ).where(ResolvedEventModel.event_id.is_(None))
        
        events_to_resolve = db_session.execute(stmt).scalars().all()
        
        for db_event in events_to_resolve:
            # Construct Event schema
            event = Event(
                event_id=db_event.event_id,
                timestamp=db_event.timestamp,
                event_type=db_event.event_type,
                raw_entity_id=db_event.raw_entity_id,
                simulation_partition=db_event.simulation_partition,
                event_data=db_event.event_data
            )
            
            # Resolve
            entity_id, entity_type, confidence = resolve_entity(event.raw_entity_id)
            
            # Create ResolvedEvent schema
            resolved_event = ResolvedEvent(
                event_id=event.event_id,
                timestamp=event.timestamp,
                event_type=event.event_type,
                raw_entity_id=event.raw_entity_id,
                entity_id=entity_id,
                entity_type=entity_type,
                resolution_confidence=confidence,
                simulation_partition=event.simulation_partition,
                event_data=event.event_data
            )
            
            # Save to DB
            db_resolved = ResolvedEventModel(
                event_id=resolved_event.event_id,
                timestamp=resolved_event.timestamp,
                event_type=resolved_event.event_type,
                raw_entity_id=resolved_event.raw_entity_id,
                entity_id=resolved_event.entity_id,
                entity_type=resolved_event.entity_type,
                resolution_confidence=resolved_event.resolution_confidence,
                simulation_partition=resolved_event.simulation_partition,
                event_data=resolved_event.event_data.model_dump(mode='json')
            )
            
            db_session.add(db_resolved)
            count += 1
            if count % 1000 == 0:
                db_session.commit()
                
        db_session.commit()
    finally:
        if db is None:
            db_session.close()
            
    return count

if __name__ == "__main__":
    resolved_count = process_unresolved_events()
    print(f"Resolved {resolved_count} events.")
