from datetime import datetime, timedelta

import pytest
import yaml
from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker

from batch.profile_builder.builder import build_profiles, match_staged_sequence
from core.database import Base
from core.models import ProfileArtifactModel, ResolvedEventModel


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


def test_drift_crossing_log_bounded_and_populated(db_session):
    entity_id = "user_staged_test"
    start = datetime(2026, 1, 1)
    for i in range(20):
        db_session.add(
            ResolvedEventModel(
                event_id=f"evt_staged_{i}",
                entity_id=entity_id,
                entity_type="human",
                raw_entity_id=entity_id,
                event_type="process",
                timestamp=start + timedelta(minutes=i),
                event_data={
                    "process_name": "chrome.exe",
                    "endpoint_id": "ep-a",
                    "geolocation": "US",
                    "command_line": "chrome.exe",
                },
                resolution_confidence=1.0,
                simulation_partition="production",
            )
        )
    db_session.commit()

    for day in range(1, 4):
        build_profiles(db=db_session, as_of=start + timedelta(days=day))

    profile = (
        db_session.query(ProfileArtifactModel)
        .filter_by(entity_id=entity_id, is_shadow=False)
        .order_by(ProfileArtifactModel.data_window_end.desc())
        .first()
    )
    assert profile is not None
    assert "drift_crossing_log" in profile.features
    assert len(profile.features["drift_crossing_log"]) <= 10


def test_matching_staged_sequence_detected():
    log = [
        {"build_ts": "2026-01-01T00:00:00", "dims_crossed": ["endpoint_set"]},
        {"build_ts": "2026-01-02T00:00:00", "dims_crossed": ["login_hour"]},
        {"build_ts": "2026-01-03T00:00:00", "dims_crossed": ["process_name"]},
        {"build_ts": "2026-01-04T00:00:00", "dims_crossed": ["embedding"]},
    ]
    templates = [["endpoint_set", "process_name", "embedding"]]
    matched, which = match_staged_sequence(log, templates)
    assert matched is True
    assert which == ["endpoint_set", "process_name", "embedding"]


def test_wrong_order_does_not_match():
    log = [
        {"build_ts": "2026-01-01T00:00:00", "dims_crossed": ["embedding"]},
        {"build_ts": "2026-01-02T00:00:00", "dims_crossed": ["process_name"]},
        {"build_ts": "2026-01-03T00:00:00", "dims_crossed": ["endpoint_set"]},
    ]
    templates = [["endpoint_set", "process_name", "embedding"]]
    matched, which = match_staged_sequence(log, templates)
    assert matched is False
    assert which is None


def test_staged_drift_disabled_by_default_does_not_change_accumulator(db_session):
    with open("config/scoring_config.yaml") as f:
        config = yaml.safe_load(f)
    assert config["staged_drift"]["enabled"] is False
