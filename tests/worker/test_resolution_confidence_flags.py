"""Resolver collision/split fixtures and scorer low_resolution_confidence flag."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.dialects.postgresql import JSONB, ARRAY

from core.database import Base
from worker.resolver import (
    LOW_RESOLUTION_THRESHOLD,
    resolve_entity,
)


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


def test_collision_fixture_maps_distinct_raw_refs_to_same_canonical_with_low_confidence():
    raw_a = "collide::user_123::alias_a"
    raw_b = "collide::user_123::alias_b"

    eid_a, etype_a, conf_a = resolve_entity(raw_a)
    eid_b, etype_b, conf_b = resolve_entity(raw_b)

    assert raw_a != raw_b
    assert eid_a == eid_b == "user_123"
    assert etype_a == etype_b == "human"
    assert conf_a < LOW_RESOLUTION_THRESHOLD
    assert conf_b < LOW_RESOLUTION_THRESHOLD


def test_split_fixture_produces_low_confidence_for_ambiguous_ref():
    raw = "split::user_456"
    eid, etype, conf = resolve_entity(raw)

    assert eid == "user_456"
    assert etype == "human"
    assert conf < LOW_RESOLUTION_THRESHOLD


def test_happy_path_user_svc_remain_high_confidence():
    for raw in ("user_789", "svc_101"):
        _, _, conf = resolve_entity(raw)
        assert conf >= LOW_RESOLUTION_THRESHOLD


def test_scorer_emits_low_resolution_confidence_flag(db_session):
    from datetime import datetime

    from core.schemas.events import ResolvedEvent, AuthEventData
    from core.schemas.profiles import ProfileArtifact
    from worker.scorer import score_event

    ts = datetime(2026, 1, 1, 12, 0)
    event_data = AuthEventData(action="login", ip_address="1.1.1.1", endpoint_id="ep1")
    resolved_event = ResolvedEvent(
        event_id="evt_low_res",
        timestamp=ts,
        event_type="auth",
        raw_entity_id="collide::user_123::alias_a",
        entity_id="user_123",
        entity_type="human",
        resolution_confidence=0.3,
        simulation_partition="production",
        event_data=event_data,
    )
    profile = ProfileArtifact(
        entity_id="user_123",
        entity_type="human",
        profile_version="prof_v1",
        created_at=ts,
        data_window_start=ts,
        data_window_end=ts,
        features={
            "role": "Engineer",
            "cohort_data": {
                "terminus": {"login_hours": {"12": 1}, "endpoints": {"ep1": 1}}
            },
        },
        embedding_model_version="1.0",
        embedding_dimensionality=128,
    )
    config = {"features": {}, "anomaly_threshold": 75.0, "version": "1.0"}

    decision = score_event(db_session, resolved_event, profile, config)

    assert "low_resolution_confidence" in decision.flags


def test_scorer_does_not_emit_low_resolution_confidence_for_high_confidence(db_session):
    from datetime import datetime

    from core.schemas.events import ResolvedEvent, AuthEventData
    from core.schemas.profiles import ProfileArtifact
    from worker.scorer import score_event

    ts = datetime(2026, 1, 1, 12, 0)
    event_data = AuthEventData(action="login", ip_address="1.1.1.1", endpoint_id="ep1")
    resolved_event = ResolvedEvent(
        event_id="evt_high_res",
        timestamp=ts,
        event_type="auth",
        raw_entity_id="user_123",
        entity_id="user_123",
        entity_type="human",
        resolution_confidence=1.0,
        simulation_partition="production",
        event_data=event_data,
    )
    profile = ProfileArtifact(
        entity_id="user_123",
        entity_type="human",
        profile_version="prof_v1",
        created_at=ts,
        data_window_start=ts,
        data_window_end=ts,
        features={
            "role": "Engineer",
            "cohort_data": {
                "terminus": {"login_hours": {"12": 1}, "endpoints": {"ep1": 1}}
            },
        },
        embedding_model_version="1.0",
        embedding_dimensionality=128,
    )
    config = {"features": {}, "anomaly_threshold": 75.0, "version": "1.0"}

    decision = score_event(db_session, resolved_event, profile, config)

    assert "low_resolution_confidence" not in decision.flags
