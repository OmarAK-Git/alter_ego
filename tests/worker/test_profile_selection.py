import pytest
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.dialects.postgresql import JSONB, ARRAY

from core.database import Base
from core.models import ProfileArtifactModel
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
    # Mock pgvector by making it a standard column for sqlite if needed, 
    # but here we just need to ensure the metadata can be created.
    # The models use pgvector.sqlalchemy.Vector which might cause issues.
    # However, test_audit.py didn't seem to have a special compile for Vector.
    # Let's see if it works.
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()

def test_profile_selection_point_in_time(db_session):
    store = ProfileStore(db_session)
    entity_id = "user_1"
    
    t0 = datetime(2026, 1, 1, 0, 0, 0)
    t1 = t0 + timedelta(days=1)
    
    # Create v1 profile
    p1 = ProfileArtifactModel(
        profile_version="v1",
        entity_id=entity_id,
        entity_type="user",
        created_at=t0,
        data_window_start=t0 - timedelta(days=7),
        data_window_end=t0,
        features={},
        is_shadow=False
    )
    db_session.add(p1)
    db_session.commit()
    
    # Promote v1 at t0
    store.promote_profile("v1", t0)
    
    # Query at t0 + 12h -> should get v1
    profile = store.get_active_profile(entity_id, t0 + timedelta(hours=12))
    assert profile.profile_version == "v1"
    assert profile.superseded_at is None
    
    # Create v2 profile
    p2 = ProfileArtifactModel(
        profile_version="v2",
        entity_id=entity_id,
        entity_type="user",
        created_at=t1,
        data_window_start=t1 - timedelta(days=7),
        data_window_end=t1,
        features={},
        is_shadow=False
    )
    db_session.add(p2)
    db_session.commit()
    
    # Promote v2 at t1
    store.promote_profile("v2", t1)
    
    # Query at t0 + 12h -> should still get v1
    profile = store.get_active_profile(entity_id, t0 + timedelta(hours=12))
    assert profile.profile_version == "v1"
    assert profile.superseded_at == t1
    
    # Query at t1 + 12h -> should get v2
    profile = store.get_active_profile(entity_id, t1 + timedelta(hours=12))
    assert profile.profile_version == "v2"
    assert profile.superseded_at is None
