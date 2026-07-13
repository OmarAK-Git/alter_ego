"""S1.2 — geolocation histograms in profiles and drift KL."""

import pytest
from datetime import datetime, timedelta
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
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def _login_event(event_id: str, entity_id: str, ts: datetime, geolocation: str) -> ResolvedEventModel:
    return ResolvedEventModel(
        event_id=event_id,
        timestamp=ts,
        event_type="login",
        raw_entity_id=entity_id,
        entity_id=entity_id,
        entity_type="human",
        resolution_confidence=1.0,
        simulation_partition="production",
        event_data={
            "action": "login",
            "endpoint_id": "endpoint_a",
            "process_name": "bash",
            "geolocation": geolocation,
        },
    )


def test_profile_builder_populates_geolocation_histogram(db_session):
    entity_id = "user_test_geo"
    t0 = datetime(2026, 1, 1, 10, 0, 0)

    db_session.add(_login_event("evt_1", entity_id, t0, "US-East"))
    db_session.commit()

    build_profiles(db_session, as_of=t0)

    profile = (
        db_session.query(ProfileArtifactModel)
        .filter(ProfileArtifactModel.entity_id == entity_id)
        .one()
    )
    assert profile.features["geolocations"]["US-East"] == 1
    cohort = profile.features["cohort_data"]
    assert cohort["terminus"]["geolocations"]["US-East"] == 1


def test_drift_includes_geolocation_when_distributions_differ(db_session):
    base = datetime(2026, 1, 1, 9, 0, 0)
    stable_ids = ["user_eng_alpha", "user_eng_beta", "user_eng_gamma"]
    drift_id = "user_eng_delta"

    for entity_id in stable_ids + [drift_id]:
        for day in range(20):
            geo = "US-East" if entity_id != drift_id or day < 18 else "US-East"
            db_session.add(
                _login_event(f"{entity_id}_{day}", entity_id, base + timedelta(days=day), geo)
            )
    db_session.commit()

    as_of_baseline = base + timedelta(days=19)
    build_profiles(db_session, as_of=as_of_baseline)

    baseline = (
        db_session.query(ProfileArtifactModel)
        .filter(ProfileArtifactModel.entity_id == drift_id)
        .one()
    )
    assert baseline.features["geolocations"]["US-East"] == 20

    for day in range(3):
        db_session.add(
            _login_event(
                f"recent_{day}",
                drift_id,
                base + timedelta(days=20 + day),
                "RU-Moscow",
            )
        )
    db_session.commit()

    as_of_drift = base + timedelta(days=22)
    build_profiles(db_session, as_of=as_of_drift)

    updated = (
        db_session.query(ProfileArtifactModel)
        .filter(ProfileArtifactModel.entity_id == drift_id)
        .order_by(ProfileArtifactModel.created_at.desc())
        .first()
    )
    assert updated.features["geolocations"]["US-East"] == 20
    assert updated.features["geolocations"]["RU-Moscow"] == 3
    assert updated.features["normalized_drift"] > 0
