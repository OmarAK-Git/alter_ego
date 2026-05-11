import pytest
from datetime import datetime, timedelta
from sqlalchemy import create_engine, select, and_
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.dialects.postgresql import JSONB, ARRAY

from core.database import Base
from core.models import ResolvedEventModel, ProfileArtifactModel
from batch.profile_builder.builder import build_profiles

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

def test_profile_build_is_repeatable(db_session):
    entity_id = "user_1"
    t0 = datetime(2026, 1, 1, 0, 0, 0)
    
    e1 = ResolvedEventModel(
        event_id="e1", timestamp=t0, event_type="login", raw_entity_id=entity_id,
        entity_id=entity_id, entity_type="user", resolution_confidence=1.0,
        simulation_partition="production", event_data={"action": "login"}
    )
    db_session.add(e1)
    db_session.commit()
    
    build_profiles(db_session, as_of=t0)
    
    e2 = ResolvedEventModel(
        event_id="e2", timestamp=t0 + timedelta(days=1), event_type="login", raw_entity_id=entity_id,
        entity_id=entity_id, entity_type="user", resolution_confidence=1.0,
        simulation_partition="production", event_data={"action": "login"}
    )
    db_session.add(e2)
    db_session.commit()
    
    # Manually check the query that builder.py uses
    stmt = select(ResolvedEventModel).where(
        and_(
            ResolvedEventModel.simulation_partition == "production",
            ResolvedEventModel.timestamp <= t0
        )
    )
    events = db_session.execute(stmt).scalars().all()
    print(f"MANUAL CHECK: found {len(events)} events for as_of {t0}")
    for e in events:
        print(f"  Event: {e.event_id} {e.timestamp}")
    
    assert len(events) == 1, f"Sqlite/SQLAlchemy query failed to filter by timestamp correctly. Found {len(events)} events but expected 1."
    
    build_profiles(db_session, as_of=t0)
    
    all_profiles = db_session.query(ProfileArtifactModel).filter(ProfileArtifactModel.entity_id == entity_id).order_by(ProfileArtifactModel.created_at).all()
    assert len(all_profiles) == 2
    assert all_profiles[1].features["total_events"] == 1
