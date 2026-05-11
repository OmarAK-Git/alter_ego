import pytest
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.dialects.postgresql import JSONB, ARRAY

from core.database import Base
from core.models import ResolvedEventModel, ProfileArtifactModel, ContainmentQueueModel
from batch.profile_builder.builder import build_profiles
from worker.profile_store import ProfileStore

@compiles(JSONB, "sqlite")
def compile_jsonb_sqlite(type_, compiler, **kw):
    return "JSON"

@compiles(ARRAY, "sqlite")
def compile_array_sqlite(type_, compiler, **kw):
    return "JSON"

@pytest.fixture
def db_session():
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()

def test_shadow_profile_logic(db_session):
    store = ProfileStore(db_session)
    entity_id = "user_1"
    t0 = datetime(2026, 1, 1, 0, 0, 0)
    
    db_session.add(ResolvedEventModel(
        event_id="e1", timestamp=t0, event_type="login", raw_entity_id=entity_id,
        entity_id=entity_id, entity_type="user", resolution_confidence=1.0,
        simulation_partition="production", event_data={"action": "login"}
    ))
    db_session.commit()
    
    # 1. Normal build
    build_profiles(db_session, as_of=t0)
    p1 = db_session.query(ProfileArtifactModel).filter(ProfileArtifactModel.entity_id == entity_id).one()
    
    print(f"P1: version={p1.profile_version}, promoted_at={p1.promoted_at}, is_shadow={p1.is_shadow}")
    
    # 2. Block entity
    db_session.add(ContainmentQueueModel(
        decision_id="d1", entity_id=entity_id, action="block", status="pending"
    ))
    db_session.commit()
    
    # Add another event
    t1 = t0 + timedelta(days=1)
    db_session.add(ResolvedEventModel(
        event_id="e2", timestamp=t1, event_type="login", raw_entity_id=entity_id,
        entity_id=entity_id, entity_type="user", resolution_confidence=1.0,
        simulation_partition="production", event_data={"action": "login"}
    ))
    db_session.commit()
    
    # 3. Build again
    build_profiles(db_session, as_of=t1)
    p2 = db_session.query(ProfileArtifactModel).filter(
        ProfileArtifactModel.entity_id == entity_id
    ).order_by(ProfileArtifactModel.created_at.desc()).first()
    
    print(f"P2: version={p2.profile_version}, promoted_at={p2.promoted_at}, is_shadow={p2.is_shadow}")
    
    # Verify p1 is still the active one for t1
    active = store.get_active_profile(entity_id, t1)
    if active is None:
        print("ACTIVE IS NONE")
        # Check why
        all_p = db_session.query(ProfileArtifactModel).filter(ProfileArtifactModel.entity_id == entity_id).all()
        for p in all_p:
             print(f"  P: version={p.profile_version}, promoted_at={p.promoted_at}, is_shadow={p.is_shadow}, superseded={p.superseded_at}")
    
    assert active is not None
    assert active.profile_version == p1.profile_version
