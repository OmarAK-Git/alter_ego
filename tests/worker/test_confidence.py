"""S2.4 — observation-count confidence n/(n+k) from scoring_config."""
import pytest
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.dialects.postgresql import JSONB, ARRAY

from core.database import Base
from core.schemas.events import AuthEventData, ResolvedEvent
from core.schemas.profiles import ProfileArtifact
from tests.worker.conftest import COMPATIBLE_EMBEDDING_PROFILE_FIELDS
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


def _resolved_event() -> ResolvedEvent:
    ts = datetime(2026, 1, 1, 12, 0)
    return ResolvedEvent(
        event_id="evt_conf",
        timestamp=ts,
        event_type="auth",
        raw_entity_id="u1",
        entity_id="u1",
        entity_type="human",
        resolution_confidence=1.0,
        simulation_partition="production",
        event_data=AuthEventData(action="login", ip_address="1.1.1.1", endpoint_id="ep1"),
    )


def _profile(total_events: int | None = None, login_hours: dict | None = None) -> ProfileArtifact:
    ts = datetime(2026, 1, 1, 12, 0)
    features: dict = {"role": "Engineer", "cohort_data": {}}
    if total_events is not None:
        features["total_events"] = total_events
    if login_hours is not None:
        features["login_hours"] = login_hours
    return ProfileArtifact(
        entity_id="u1",
        entity_type="human",
        profile_version="prof_conf",
        created_at=ts,
        data_window_start=ts,
        data_window_end=ts,
        features=features,
        **COMPATIBLE_EMBEDDING_PROFILE_FIELDS,
    )


def _base_config(**overrides):
    config = {
        "features": {},
        "anomaly_threshold": 75.0,
        "version": "test",
    }
    config.update(overrides)
    return config


def test_load_scoring_config_includes_confidence_k():
    """confidence_k must be present in scoring_config.yaml, not only code default."""
    config = load_scoring_config()
    assert "confidence_k" in config
    assert config["confidence_k"] == 10.0


def test_confidence_formula_from_yaml_config(db_session):
    """score_event reads confidence_k from loaded YAML: n/(n+k)."""
    yaml_config = load_scoring_config()
    profile = _profile(total_events=40)
    decision = score_event(db_session, _resolved_event(), profile, yaml_config)
    k = yaml_config["confidence_k"]
    expected = 40 / (40 + k)
    assert abs(decision.confidence - expected) < 1e-9


def test_confidence_k_override_changes_confidence(db_session):
    """Changing confidence_k in config changes confidence for fixed n."""
    profile = _profile(total_events=40)
    config_low_k = _base_config(confidence_k=5.0)
    config_high_k = _base_config(confidence_k=20.0)

    decision_low_k = score_event(db_session, _resolved_event(), profile, config_low_k)
    decision_high_k = score_event(db_session, _resolved_event(), profile, config_high_k)

    assert abs(decision_low_k.confidence - 40 / 45) < 1e-9
    assert abs(decision_high_k.confidence - 40 / 60) < 1e-9
    assert decision_low_k.confidence > decision_high_k.confidence


def test_larger_n_higher_confidence_fixed_k(db_session):
    """Larger observation count n yields higher confidence for fixed k."""
    config = _base_config(confidence_k=10.0)
    decision_small = score_event(db_session, _resolved_event(), _profile(total_events=10), config)
    decision_large = score_event(db_session, _resolved_event(), _profile(total_events=100), config)

    assert abs(decision_small.confidence - 10 / 20) < 1e-9
    assert abs(decision_large.confidence - 100 / 110) < 1e-9
    assert decision_large.confidence > decision_small.confidence


def test_confidence_fallback_to_login_hours_sum(db_session):
    """When total_events is absent, n = sum(login_hours values)."""
    profile = _profile(login_hours={"12": 20, "13": 10})
    config = _base_config(confidence_k=10.0)
    decision = score_event(db_session, _resolved_event(), profile, config)
    assert abs(decision.confidence - 30 / 40) < 1e-9
