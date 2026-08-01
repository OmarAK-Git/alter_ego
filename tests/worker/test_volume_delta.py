from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker

from core.database import Base
from core.models import ProfileArtifactModel
from core.schemas.events import ResolvedEvent
from worker.profile_store import ProfileStore
from worker.scorer import compute_volume_rarity, load_scoring_config, score_event


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


def _profile(
    *,
    version,
    entity_id,
    drift,
    is_shadow,
    promoted_at,
    created_at,
    data_window_end,
):
    return ProfileArtifactModel(
        profile_version=version,
        entity_id=entity_id,
        entity_type="human",
        created_at=created_at,
        data_window_start=data_window_end - timedelta(days=30),
        data_window_end=data_window_end,
        promoted_at=promoted_at,
        superseded_at=None,
        is_shadow=is_shadow,
        features={
            "total_events": 100,
            "login_hours": {str(h): 4 for h in range(24)},
            "geolocations": {"US": 100},
            "endpoints": {"ep-a": 100},
            "process_names": {"chrome.exe": 100},
            "role": "engineer",
            "cohort_data": {},
            "cumulative_drift": drift,
        },
        embedding=[0.1] * 128,
        embedding_model_id="alter-ego-ngram-v1",
        embedding_model_version="1.0",
        embedding_dimensionality=128,
        embedding_input_normalizer_version="1.0-char-3gram-hash-128",
    )


def test_typical_recent_count_scores_low_rarity():
    hist = {"8": 3, "9": 5, "10": 6, "11": 4, "12": 2}
    score = compute_volume_rarity(recent_count=10, historical_hourly_counts=hist, alpha=1.0)
    assert score < 2.0


def test_spike_count_scores_higher_rarity_than_typical():
    hist = {"8": 3, "9": 5, "10": 6, "11": 4, "12": 2}
    typical = compute_volume_rarity(recent_count=10, historical_hourly_counts=hist, alpha=1.0)
    spike = compute_volume_rarity(recent_count=80, historical_hourly_counts=hist, alpha=1.0)
    assert spike > typical


def test_empty_history_does_not_raise():
    score = compute_volume_rarity(recent_count=5, historical_hourly_counts={}, alpha=1.0)
    assert score >= 0.0


def test_score_vol_stays_zero_when_disabled(db_session):
    """enabled: false (shipped default) must reproduce the pre-Phase-2 score_vol=0.0 + volume_delta_deferred flag."""
    entity_id = "user_vol_disabled_test"
    as_of = datetime(2024, 6, 15, 12, 0, 0)
    db_session.add(_profile(
        version="promoted_vol_v1", entity_id=entity_id, drift=0.0,
        is_shadow=False, promoted_at=as_of - timedelta(days=5),
        created_at=as_of - timedelta(days=5), data_window_end=as_of - timedelta(days=5),
    ))
    db_session.commit()

    promoted = ProfileStore(db_session).get_active_profile(entity_id, as_of)
    config = load_scoring_config()
    assert config["features"]["total_volume_delta"]["enabled"] is False

    event = ResolvedEvent(
        event_id="evt_vol_disabled", timestamp=as_of, event_type="process",
        raw_entity_id=entity_id, entity_id=entity_id, entity_type="human",
        resolution_confidence=1.0, simulation_partition="production",
        event_data={"process_name": "chrome.exe", "endpoint_id": "ep-a",
                    "geolocation": "US", "command_line": "chrome.exe --silent"},
    )
    decision = score_event(db_session, event, promoted, config)
    vol_c = next(c for c in decision.contributions if c.feature_name == "total_volume_delta")
    assert vol_c.contribution_score == 0.0
    assert "volume_delta_deferred" in decision.flags
