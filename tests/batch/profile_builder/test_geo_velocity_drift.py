from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker

from core.database import Base
from core.models import ResolvedEventModel
from batch.profile_builder.builder import compute_geo_velocity_delta


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


def _auth_event(entity_id, ts, geo, i):
    return ResolvedEventModel(
        event_id=f"evt_geo_{entity_id}_{i}", entity_id=entity_id, entity_type="human",
        event_type="login", raw_entity_id=entity_id,
        timestamp=ts, event_data={"action": "login", "geolocation": geo, "process_name": None,
                                   "endpoint_id": "ep-a", "command_line": ""},
        resolution_confidence=1.0, simulation_partition="production",
    )


def test_impossible_travel_pair_scores_high_delta(db_session):
    entity_id = "user_geo_test"
    start = datetime(2026, 1, 1, 0, 0, 0)
    # Baseline: several local-only US-East successes to establish a "always local" history.
    for i in range(5):
        db_session.add(_auth_event(entity_id, start + timedelta(hours=i), "US-East", i))
    # Then a US-East -> RU-Moscow jump within 1 hour (impossible at any real travel speed).
    db_session.add(_auth_event(entity_id, start + timedelta(hours=5), "US-East", 5))
    db_session.add(_auth_event(entity_id, start + timedelta(hours=5, minutes=30), "RU-Moscow", 6))
    db_session.commit()

    delta, flags = compute_geo_velocity_delta(db_session, entity_id, start, start + timedelta(hours=6), min_paired_successes=3)
    assert delta > 0.0
    assert "geo_velocity:no_centroid" not in flags


def test_nearby_successive_logins_score_low_delta(db_session):
    entity_id = "user_geo_local"
    start = datetime(2026, 1, 1, 0, 0, 0)
    for i in range(5):
        db_session.add(_auth_event(entity_id, start + timedelta(hours=i), "US-East", i))
    db_session.commit()

    delta, flags = compute_geo_velocity_delta(db_session, entity_id, start, start + timedelta(hours=6), min_paired_successes=3)
    assert delta == 0.0 or delta < 1.0


def test_unmapped_label_flags_and_scores_zero_for_that_pair(db_session):
    entity_id = "user_geo_unmapped"
    start = datetime(2026, 1, 1, 0, 0, 0)
    for i in range(3):
        db_session.add(_auth_event(entity_id, start + timedelta(hours=i), "US-East", i))
    db_session.add(_auth_event(entity_id, start + timedelta(hours=3), "Atlantis-Undersea", 3))
    db_session.commit()

    delta, flags = compute_geo_velocity_delta(db_session, entity_id, start, start + timedelta(hours=4), min_paired_successes=3)
    assert "geo_velocity:no_centroid" in flags


def test_below_min_paired_successes_returns_zero(db_session):
    entity_id = "user_geo_sparse"
    start = datetime(2026, 1, 1, 0, 0, 0)
    db_session.add(_auth_event(entity_id, start, "US-East", 0))
    db_session.commit()

    delta, flags = compute_geo_velocity_delta(db_session, entity_id, start, start + timedelta(hours=1), min_paired_successes=3)
    assert delta == 0.0
