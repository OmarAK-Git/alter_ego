from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker

from core.database import Base
from core.models import ResolvedEventModel
from batch.profile_builder.builder import build_profiles


@compiles(JSONB, "sqlite")
def compile_jsonb_sqlite(type_, compiler, **kw):
    return "JSON"


@compiles(ARRAY, "sqlite")
def compile_array_sqlite(type_, compiler, **kw):
    return "JSON"


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def test_hourly_event_counts_populated_in_profile_features(db_session):
    entity_id = "user_vol_test"
    start = datetime(2026, 1, 1, 9, 0, 0)
    for i in range(25):
        ts = start + timedelta(days=29, minutes=i * 2)
        db_session.add(ResolvedEventModel(
            event_id=f"evt_vol_{i}", entity_id=entity_id, entity_type="human",
            event_type="process", raw_entity_id=entity_id,
            timestamp=ts, event_data={"process_name": "chrome.exe", "endpoint_id": "ep-a",
                                       "geolocation": "US", "command_line": "chrome.exe"},
            resolution_confidence=1.0, simulation_partition="production",
        ))
    db_session.commit()

    build_profiles(db=db_session, as_of=start + timedelta(days=31))

    from core.models import ProfileArtifactModel
    profile = db_session.query(ProfileArtifactModel).filter_by(entity_id=entity_id).first()
    assert profile is not None
    assert "hourly_event_counts" in profile.features
    assert sum(profile.features["hourly_event_counts"].values()) == 25
