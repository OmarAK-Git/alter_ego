"""Phase 0: point-rarity/embedding baseline must follow the shadow profile
while an entity is build-blocked, same as drift_alert already does (D4)."""

from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker

from core.database import Base
from core.models import AlertWorkflowStateModel, DecisionRecordModel, ProfileArtifactModel
from core.schemas.events import ResolvedEvent
from worker.scorer import load_scoring_config, score_event


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
    login_hours,
    is_shadow,
    promoted_at,
    created_at,
    data_window_end,
    cumulative_drift=0.0,
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
            "login_hours": login_hours,
            "geolocations": {"US": 100},
            "endpoints": {"ep-a": 100},
            "process_names": {"chrome.exe": 100},
            "role": "engineer",
            "cohort_data": {},
            "cumulative_drift": cumulative_drift,
        },
        embedding=[0.1] * 128,
        embedding_model_id="alter-ego-ngram-v1",
        embedding_model_version="1.0",
        embedding_dimensionality=128,
        embedding_input_normalizer_version="1.0-char-3gram-hash-128",
    )


def test_blocked_entity_point_rarity_follows_shadow_not_frozen_promoted(db_session):
    entity_id = "user_engineer_p0"
    as_of = datetime(2024, 6, 15, 12, 0, 0)

    db_session.add(
        _profile(
            version="promoted_v1",
            entity_id=entity_id,
            login_hours={str(h): (0 if h == 3 else 5) for h in range(24)},
            is_shadow=False,
            promoted_at=as_of - timedelta(days=5),
            created_at=as_of - timedelta(days=5),
            data_window_end=as_of - timedelta(days=5),
        )
    )
    db_session.add(
        _profile(
            version="shadow_v2",
            entity_id=entity_id,
            login_hours={str(h): 5 for h in range(24)},
            is_shadow=True,
            promoted_at=None,
            created_at=as_of,
            data_window_end=as_of - timedelta(hours=1),
        )
    )
    db_session.add(
        DecisionRecordModel(
            decision_id="fp_alert_p0",
            event_id="evt_fp_p0",
            entity_id=entity_id,
            timestamp=as_of - timedelta(days=2),
            score=50.0,
            confidence=0.9,
            profile_version="promoted_v1",
            scoring_config_version="2.2",
            contributions=[],
            is_anomaly=True,
            cohort_used="engineer",
            cohort_unsupported=False,
            flags=[],
        )
    )
    db_session.add(
        AlertWorkflowStateModel(
            decision_id="fp_alert_p0",
            entity_id=entity_id,
            state="new",
            updated_at=as_of - timedelta(days=2),
        )
    )
    db_session.commit()

    from worker.profile_store import ProfileStore

    promoted = ProfileStore(db_session).get_active_profile(entity_id, as_of)
    config = load_scoring_config()
    event = ResolvedEvent(
        event_id="evt_p0",
        timestamp=as_of.replace(hour=3),
        event_type="process",
        raw_entity_id=entity_id,
        entity_id=entity_id,
        entity_type="human",
        resolution_confidence=1.0,
        simulation_partition="production",
        event_data={
            "process_name": "chrome.exe",
            "endpoint_id": "ep-a",
            "geolocation": "US",
            "command_line": "chrome.exe --silent",
        },
    )
    decision = score_event(db_session, event, promoted, config)
    login_c = next(c for c in decision.contributions if c.feature_name == "login_hour_rarity")
    assert login_c.raw_value < 1.0
    assert any(
        isinstance(f, str) and f.startswith("point_baseline_shadow_fallback:")
        for f in decision.flags
    )


def test_blocked_entity_no_shadow_falls_back_to_promoted_with_flag(db_session, caplog):
    import logging

    entity_id = "user_engineer_p0_noshadow"
    as_of = datetime(2024, 6, 15, 12, 0, 0)
    db_session.add(
        _profile(
            version="promoted_only",
            entity_id=entity_id,
            login_hours={str(h): (0 if h == 3 else 500) for h in range(24)},
            is_shadow=False,
            promoted_at=as_of - timedelta(days=5),
            created_at=as_of - timedelta(days=5),
            data_window_end=as_of - timedelta(days=5),
        )
    )
    db_session.add(
        DecisionRecordModel(
            decision_id="fp_alert_p0b",
            event_id="evt_fp_p0b",
            entity_id=entity_id,
            timestamp=as_of - timedelta(days=2),
            score=50.0,
            confidence=0.9,
            profile_version="promoted_only",
            scoring_config_version="2.2",
            contributions=[],
            is_anomaly=True,
            cohort_used="engineer",
            cohort_unsupported=False,
            flags=[],
        )
    )
    db_session.add(
        AlertWorkflowStateModel(
            decision_id="fp_alert_p0b",
            entity_id=entity_id,
            state="new",
            updated_at=as_of - timedelta(days=2),
        )
    )
    db_session.commit()

    from worker.profile_store import ProfileStore

    promoted = ProfileStore(db_session).get_active_profile(entity_id, as_of)
    config = load_scoring_config()
    event = ResolvedEvent(
        event_id="evt_p0b",
        timestamp=as_of.replace(hour=3),
        event_type="process",
        raw_entity_id=entity_id,
        entity_id=entity_id,
        entity_type="human",
        resolution_confidence=1.0,
        simulation_partition="production",
        event_data={
            "process_name": "chrome.exe",
            "endpoint_id": "ep-a",
            "geolocation": "US",
            "command_line": "chrome.exe --silent",
        },
    )
    with caplog.at_level(logging.WARNING, logger="worker.scorer"):
        decision = score_event(db_session, event, promoted, config)
    login_c = next(c for c in decision.contributions if c.feature_name == "login_hour_rarity")
    assert login_c.raw_value > 1.0
    assert "point_baseline_shadow_fallback:no_shadow" in decision.flags
    assert any(
        "point_baseline_shadow_fallback" in r.message
        for r in caplog.records
        if r.levelname == "WARNING"
    )


def test_unblocked_entity_unaffected(db_session):
    """Zero behavioral diff: unblocked entity always scores against its own promoted profile."""
    entity_id = "user_engineer_p0_unblocked"
    as_of = datetime(2024, 6, 15, 12, 0, 0)
    db_session.add(
        _profile(
            version="promoted_only",
            entity_id=entity_id,
            login_hours={str(h): 5 for h in range(24)},
            is_shadow=False,
            promoted_at=as_of - timedelta(days=5),
            created_at=as_of - timedelta(days=5),
            data_window_end=as_of - timedelta(days=5),
        )
    )
    db_session.commit()

    from worker.profile_store import ProfileStore

    promoted = ProfileStore(db_session).get_active_profile(entity_id, as_of)
    config = load_scoring_config()
    event = ResolvedEvent(
        event_id="evt_unblocked",
        timestamp=as_of.replace(hour=3),
        event_type="process",
        raw_entity_id=entity_id,
        entity_id=entity_id,
        entity_type="human",
        resolution_confidence=1.0,
        simulation_partition="production",
        event_data={
            "process_name": "chrome.exe",
            "endpoint_id": "ep-a",
            "geolocation": "US",
            "command_line": "chrome.exe --silent",
        },
    )
    decision = score_event(db_session, event, promoted, config)
    assert not any(
        isinstance(f, str) and f.startswith("point_baseline_shadow_fallback:")
        for f in decision.flags
    )


def test_shadow_lookup_happens_once_per_score_event(db_session, monkeypatch):
    """Point-baseline and drift blocks must share one shadow lookup, not two."""
    entity_id = "user_engineer_p0_once"
    as_of = datetime(2024, 6, 15, 12, 0, 0)
    db_session.add(
        _profile(
            version="promoted_once",
            entity_id=entity_id,
            login_hours={str(h): 5 for h in range(24)},
            is_shadow=False,
            promoted_at=as_of - timedelta(days=5),
            created_at=as_of - timedelta(days=5),
            data_window_end=as_of - timedelta(days=5),
            cumulative_drift=1.0,
        )
    )
    db_session.add(
        _profile(
            version="shadow_once",
            entity_id=entity_id,
            login_hours={str(h): 5 for h in range(24)},
            is_shadow=True,
            promoted_at=None,
            created_at=as_of,
            data_window_end=as_of - timedelta(hours=1),
            cumulative_drift=3.0,
        )
    )
    db_session.add(
        DecisionRecordModel(
            decision_id="fp_once",
            event_id="evt_fp_once",
            entity_id=entity_id,
            timestamp=as_of - timedelta(days=2),
            score=50.0,
            confidence=0.9,
            profile_version="promoted_once",
            scoring_config_version="2.2",
            contributions=[],
            is_anomaly=True,
            cohort_used="engineer",
            cohort_unsupported=False,
            flags=[],
        )
    )
    db_session.add(
        AlertWorkflowStateModel(
            decision_id="fp_once",
            entity_id=entity_id,
            state="new",
            updated_at=as_of - timedelta(days=2),
        )
    )
    db_session.commit()

    from worker.profile_store import ProfileStore
    import worker.scorer as scorer_mod

    call_count = {"n": 0}
    original = ProfileStore.get_latest_shadow_profile

    def counting_wrapper(self, entity_id_, as_of=None):
        call_count["n"] += 1
        return original(self, entity_id_, as_of=as_of)

    monkeypatch.setattr(ProfileStore, "get_latest_shadow_profile", counting_wrapper)

    promoted = ProfileStore(db_session).get_active_profile(entity_id, as_of)
    config = load_scoring_config()
    event = ResolvedEvent(
        event_id="evt_once",
        timestamp=as_of,
        event_type="process",
        raw_entity_id=entity_id,
        entity_id=entity_id,
        entity_type="human",
        resolution_confidence=1.0,
        simulation_partition="production",
        event_data={
            "process_name": "chrome.exe",
            "endpoint_id": "ep-a",
            "geolocation": "US",
            "command_line": "chrome.exe --silent",
        },
    )
    scorer_mod.score_event(db_session, event, promoted, config)
    assert call_count["n"] == 1
