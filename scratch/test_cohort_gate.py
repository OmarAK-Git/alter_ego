import uuid
from datetime import datetime, timedelta
from sqlalchemy import select
from core.database import SessionLocal, Base, engine
from core.models import ResolvedEventModel, ProfileArtifactModel
from worker.scorer import score_event
from core.schemas.events import ResolvedEvent

def setup_test_db():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    return SessionLocal()

def create_profile(db, entity_id, role, cohort_size=15):
    # Create a profile for the entity
    features = {
        "role": role,
        "login_hours": {"9": 100},
        "geolocations": {"US": 100},
        "endpoints": {"EP1": 100},
        "process_names": {"explorer.exe": 100},
        "cohort_data": {
            "primary": {
                role: {
                    "process_names": {"explorer.exe": 1000}
                }
            }
        }
    }
    profile = ProfileArtifactModel(
        profile_version=f"v1_{entity_id}",
        entity_id=entity_id,
        entity_type="human",
        data_window_start=datetime.utcnow() - timedelta(days=30),
        data_window_end=datetime.utcnow(),
        promoted_at=datetime.utcnow(),
        features=features
    )
    db.add(profile)
    db.commit()
    
    # Create members to satisfy min_cohort_size (10)
    for i in range(cohort_size - 1):
        m_id = f"member_{role}_{i}"
        m_profile = ProfileArtifactModel(
            profile_version=f"v1_{m_id}",
            entity_id=m_id,
            entity_type="human",
            data_window_start=datetime.utcnow() - timedelta(days=30),
            data_window_end=datetime.utcnow(),
            promoted_at=datetime.utcnow(),
            features=features
        )
        db.add(m_profile)
    db.commit()

def add_event(db, entity_id, process_name, timestamp=None):
    if timestamp is None: timestamp = datetime.utcnow()
    event = ResolvedEventModel(
        event_id=str(uuid.uuid4()),
        timestamp=timestamp,
        event_type="process",
        raw_entity_id=entity_id,
        entity_id=entity_id,
        entity_type="human",
        resolution_confidence=1.0,
        event_data={
            "process_name": process_name, 
            "endpoint_id": "EP1", 
            "geolocation": "US",
            "command_line": f"{process_name} --args"
        }
    )
    db.add(event)
    db.commit()
    return event

def test_gate():
    db = setup_test_db()
    config = {
        "anomaly_threshold": 45.0,
        "cohort_gating_constants": {
            "max_changed_fraction": 0.2,
            "min_cohort_size": 10,
            "min_clean_observation_count": 5
        },
        "cohort_gate_window_days": 7,
        "features": {"process_name_rarity": {"weight": 2.0}}
    }
    
    from core.schemas.profiles import ProfileArtifact
    
    # Case 1: One entity novelty (preserved)
    print("--- Case 1: Individual Novelty ---")
    create_profile(db, "user1", "Engineer")
    add_event(db, "user1", "mimikatz.exe")
    
    p1_db = db.execute(select(ProfileArtifactModel).where(ProfileArtifactModel.entity_id == "user1")).scalar()
    p1 = ProfileArtifact(**{c.name: getattr(p1_db, c.name) for c in p1_db.__table__.columns})
    
    e1 = add_event(db, "user1", "mimikatz.exe")
    res1 = score_event(db, ResolvedEvent(
        event_id=e1.event_id, timestamp=e1.timestamp, event_type=e1.event_type,
        raw_entity_id=e1.raw_entity_id, entity_id=e1.entity_id,
        entity_type=e1.entity_type, resolution_confidence=e1.resolution_confidence,
        event_data=e1.event_data
    ), p1, config)
    
    proc_contrib = next(c for c in res1.contributions if c.feature_name == "process_name_rarity")
    print(f"Score: {proc_contrib.contribution_score}, Flags: {res1.flags}")
    assert proc_contrib.contribution_score > 0
    assert "novelty_suppressed_process_name_rarity" not in res1.flags

    # Case 2: Whole cohort novelty (suppressed)
    print("\n--- Case 2: Cohort-wide Novelty (Suppressed) ---")
    # Fraction: 4/15 = 0.266 > 0.2
    for i in range(4):
        add_event(db, f"member_Engineer_{i}", "mimikatz.exe")
    
    e2 = add_event(db, "user1", "mimikatz.exe")
    res2 = score_event(db, ResolvedEvent(
        event_id=e2.event_id, timestamp=e2.timestamp, event_type=e2.event_type,
        raw_entity_id=e2.raw_entity_id, entity_id=e2.entity_id,
        entity_type=e2.entity_type, resolution_confidence=e2.resolution_confidence,
        event_data=e2.event_data
    ), p1, config)
    
    proc_contrib2 = next(c for c in res2.contributions if c.feature_name == "process_name_rarity")
    print(f"Score: {proc_contrib2.contribution_score}, Flags: {res2.flags}")
    assert proc_contrib2.contribution_score == 0
    assert "novelty_suppressed_process_name_rarity" in res2.flags

    # Case 3: Small cohort (flagged, preserved)
    print("\n--- Case 3: Small Cohort ---")
    create_profile(db, "user_small", "SmallTeam", cohort_size=5)
    p_small_db = db.execute(select(ProfileArtifactModel).where(ProfileArtifactModel.entity_id == "user_small")).scalar()
    p_small = ProfileArtifact(**{c.name: getattr(p_small_db, c.name) for c in p_small_db.__table__.columns})
    
    # Even if everyone does it, cohort too small to suppress
    for i in range(4):
        add_event(db, f"member_SmallTeam_{i}", "evil.exe")
    
    e3 = add_event(db, "user_small", "evil.exe")
    res3 = score_event(db, ResolvedEvent(
        event_id=e3.event_id, timestamp=e3.timestamp, event_type=e3.event_type,
        raw_entity_id=e3.raw_entity_id, entity_id=e3.entity_id,
        entity_type=e3.entity_type, resolution_confidence=e3.resolution_confidence,
        event_data=e3.event_data
    ), p_small, config)
    
    proc_contrib3 = next(c for c in res3.contributions if c.feature_name == "process_name_rarity")
    print(f"Score: {proc_contrib3.contribution_score}, Flags: {res3.flags}")
    assert proc_contrib3.contribution_score > 0
    assert "cohort_too_small_process_name_rarity" in res3.flags
    assert "novelty_suppressed_process_name_rarity" not in res3.flags

    print("\nTests Passed!")

if __name__ == "__main__":
    test_gate()
