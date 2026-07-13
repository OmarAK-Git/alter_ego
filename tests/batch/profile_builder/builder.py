import pytest
from datetime import datetime
from sqlalchemy import create_engine
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

def test_profile_builder_aggregates_correctly(db_session):
    entity_id = "user_test"
    t0 = datetime(2026, 1, 1, 15, 30, 0)
    
    e1 = ResolvedEventModel(
        event_id="test_evt_1", timestamp=t0, event_type="login", raw_entity_id=entity_id,
        entity_id=entity_id, entity_type="human", resolution_confidence=1.0,
        simulation_partition="production", event_data={
            "action": "login",
            "endpoint_id": "endpoint_a",
            "process_name": "bash",
            "geolocation": "US"
        }
    )
    db_session.add(e1)
    db_session.commit()
    
    # Run the profile builder
    build_profiles(db_session, as_of=t0)
    
    # Retrieve the built profile
    profile = db_session.query(ProfileArtifactModel).filter(ProfileArtifactModel.entity_id == entity_id).first()
    assert profile is not None, "Profile was not built"
    assert profile.features["total_events"] == 1
    assert profile.features["login_hours"]["15"] == 1
    assert profile.features["geolocations"]["US"] == 1
    assert profile.features["endpoints"]["endpoint_a"] == 1
    assert profile.features["process_names"]["bash"] == 1
