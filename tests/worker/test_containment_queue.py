"""S1.3 — auto-write containment queue when threshold + confidence met."""
import pytest
from datetime import datetime
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.dialects.postgresql import JSONB, ARRAY

from core.database import Base
from core.models import ContainmentQueueModel
from core.schemas.decisions import DecisionRecord
from core.schemas.events import ResolvedEvent
from core.schemas.profiles import ProfileArtifact
from worker.recorder import record_decision
from worker.scorer import score_event, load_scoring_config


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


def _base_config(**overrides):
    config = {
        "features": {"drift_alert": {"weight": 100.0}},
        "anomaly_threshold": 45.0,
        "containment_threshold": 85.0,
        "confidence_floor": 0.6,
        "drift_threshold": 5.0,
        "contribution_scale_max": 50.0,
        "confidence_k": 10.0,
        "version": "test",
    }
    config.update(overrides)
    return config


def _drift_profile(entity_id: str, drift_accum: float, total_events: int) -> ProfileArtifact:
    ts = datetime(2026, 1, 10, 12, 0)
    return ProfileArtifact(
        entity_id=entity_id,
        entity_type="human",
        profile_version="prof_v1",
        created_at=ts,
        data_window_start=datetime(2026, 1, 1, 0, 0),
        data_window_end=ts,
        features={
            "role": "Engineer",
            "login_hours": {"12": 50},
            "endpoints": {"ep1": 50},
            "geolocations": {"US": 50},
            "process_names": {"proc.exe": 50},
            "cohort_data": {},
            "cumulative_drift": drift_accum,
            "total_events": total_events,
        },
        embedding_model_id="alter-ego-ngram-v1",
        embedding_model_version="1.0",
        embedding_dimensionality=128,
    )


def _resolved_event(entity_id: str = "u1") -> ResolvedEvent:
    ts = datetime(2026, 1, 12, 12, 0)
    return ResolvedEvent(
        event_id="evt_contain",
        timestamp=ts,
        event_type="auth",
        raw_entity_id=entity_id,
        entity_id=entity_id,
        entity_type="human",
        resolution_confidence=1.0,
        simulation_partition="production",
        event_data={
            "action": "login",
            "ip_address": "1.1.1.1",
            "endpoint_id": "ep1",
            "geolocation": "US",
            "process_name": "proc.exe",
            "command_line": "",
        },
    )


def test_load_scoring_config_includes_containment_threshold():
    config = load_scoring_config()
    assert config.get("containment_threshold") == 85.0


def test_scorer_sets_containment_flag_when_threshold_and_confidence_met(db_session):
    """Score >= containment_threshold and confidence >= floor → flag set."""
    config = _base_config(containment_threshold=50.0)
    profile = _drift_profile("u1", drift_accum=2.5, total_events=100)
    decision = score_event(db_session, _resolved_event(), profile, config)

    assert decision.score >= 50.0
    assert decision.confidence >= 0.6
    assert "simulated_containment_queued" in decision.flags


def test_scorer_no_containment_flag_below_threshold(db_session):
    """Anomaly below containment_threshold must not set containment flag."""
    config = _base_config()
    profile = _drift_profile("u1", drift_accum=2.5, total_events=100)
    decision = score_event(db_session, _resolved_event(), profile, config)

    assert decision.is_anomaly
    assert decision.score < 85.0
    assert "simulated_containment_queued" not in decision.flags


def test_scorer_no_containment_flag_low_confidence(db_session):
    """High raw score with low confidence must not queue containment."""
    config = _base_config(containment_threshold=50.0)
    profile = _drift_profile("u1", drift_accum=2.5, total_events=1)
    decision = score_event(db_session, _resolved_event(), profile, config)

    assert decision.confidence < 0.6
    assert "simulated_containment_queued" not in decision.flags


def test_record_decision_writes_containment_queue_when_flag_set(db_session):
    ts = datetime.utcnow()
    decision = DecisionRecord(
        decision_id="dec_contain_1",
        event_id="evt1",
        entity_id="user_1",
        timestamp=ts,
        score=90.0,
        confidence=0.9,
        profile_version="v1",
        scoring_config_version="v1",
        contributions=[],
        is_anomaly=True,
        cohort_used="local",
        cohort_unsupported=False,
        flags=["simulated_containment_queued"],
    )

    record_decision(decision, db_session)

    rows = db_session.execute(select(ContainmentQueueModel)).scalars().all()
    assert len(rows) == 1
    assert rows[0].decision_id == "dec_contain_1"
    assert rows[0].entity_id == "user_1"
    assert rows[0].action == "simulate_containment"
    assert rows[0].status == "pending"


def test_record_decision_no_queue_without_flag(db_session):
    decision = DecisionRecord(
        decision_id="dec_no_contain",
        event_id="evt2",
        entity_id="user_2",
        timestamp=datetime.utcnow(),
        score=60.0,
        confidence=0.9,
        profile_version="v1",
        scoring_config_version="v1",
        contributions=[],
        is_anomaly=True,
        cohort_used="local",
        cohort_unsupported=False,
        flags=[],
    )

    record_decision(decision, db_session)

    rows = db_session.execute(select(ContainmentQueueModel)).scalars().all()
    assert len(rows) == 0
