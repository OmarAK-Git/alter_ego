from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker

from core.database import Base
from core.models import ResolvedEventModel
from batch.profile_builder.builder import compute_build_window_cadence_cov


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


def _resolved_event(entity_id, ts, i):
    return ResolvedEventModel(
        event_id=f"evt_{entity_id}_{i}",
        entity_id=entity_id,
        entity_type="service_account",
        event_type="process",
        raw_entity_id=entity_id,
        timestamp=ts,
        event_data={"process_name": "plc_poll.exe"},
        resolution_confidence=1.0,
        simulation_partition="production",
    )


def test_perfectly_regular_events_score_cov_near_one(db_session):
    entity_id = "svc_ot_poll_test"
    start = datetime(2026, 1, 1, 0, 0, 0)
    for i in range(30):
        db_session.add(_resolved_event(entity_id, start + timedelta(minutes=i), i))
    db_session.commit()

    cov, n = compute_build_window_cadence_cov(db_session, entity_id, start, start + timedelta(hours=1), min_events=20)
    assert n == 30
    assert cov > 0.95


def test_irregular_events_score_lower_cov(db_session):
    import random
    entity_id = "svc_irregular_test"
    rng = random.Random(1)
    start = datetime(2026, 1, 1, 0, 0, 0)
    t = start
    for i in range(30):
        t += timedelta(minutes=rng.uniform(0.5, 20.0))
        db_session.add(_resolved_event(entity_id, t, i))
    db_session.commit()

    cov, n = compute_build_window_cadence_cov(db_session, entity_id, start, t + timedelta(minutes=1), min_events=20)
    assert n == 30
    assert cov < 0.5


def test_below_min_events_returns_zero(db_session):
    entity_id = "svc_sparse_test"
    start = datetime(2026, 1, 1, 0, 0, 0)
    for i in range(5):
        db_session.add(_resolved_event(entity_id, start + timedelta(minutes=i), i))
    db_session.commit()

    cov, n = compute_build_window_cadence_cov(db_session, entity_id, start, start + timedelta(hours=1), min_events=20)
    assert n == 5
    assert cov == 0.0


def test_cadence_disabled_by_default_does_not_change_cumulative_drift(db_session):
    import copy
    import yaml
    from batch.profile_builder.builder import build_profiles
    from core.models import ProfileArtifactModel, ResolvedEventModel

    entity_id = "user_zero_diff_test"
    start = datetime(2026, 1, 1)
    for i in range(20):
        db_session.add(ResolvedEventModel(
            event_id=f"evt_zd_{i}", entity_id=entity_id, entity_type="human",
            event_type="process", raw_entity_id=entity_id,
            timestamp=start + timedelta(minutes=i), event_data={
                "process_name": "chrome.exe", "endpoint_id": "ep-a",
                "geolocation": "US", "command_line": "chrome.exe",
            }, resolution_confidence=1.0, simulation_partition="production",
        ))
    db_session.commit()

    with open("config/scoring_config.yaml") as f:
        base_config = yaml.safe_load(f)
    assert base_config["drift_weights"]["cadence"]["enabled"] is False

    forced_disabled_config = copy.deepcopy(base_config)
    forced_disabled_config["drift_weights"]["cadence"]["enabled"] = False

    build_profiles(db=db_session, as_of=start + timedelta(days=1), config_override=base_config)
    baseline_profile = (
        db_session.query(ProfileArtifactModel).filter_by(entity_id=entity_id).first()
    )
    baseline_drift = baseline_profile.features["cumulative_drift"]

    db_session.query(ProfileArtifactModel).delete()
    db_session.commit()

    build_profiles(db=db_session, as_of=start + timedelta(days=1), config_override=forced_disabled_config)
    override_profile = (
        db_session.query(ProfileArtifactModel).filter_by(entity_id=entity_id).first()
    )
    assert override_profile.features["cumulative_drift"] == baseline_drift
