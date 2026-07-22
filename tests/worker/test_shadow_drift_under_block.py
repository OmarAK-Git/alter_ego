"""S55 D4 — drift_alert reads shadow accumulator while entity is build-blocked."""

from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker

from core.database import Base
from core.models import AlertWorkflowStateModel, DecisionRecordModel, ProfileArtifactModel
from core.schemas.events import ResolvedEvent
from core.schemas.profiles import ProfileArtifact
from worker.profile_store import ProfileStore
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


def test_shadow_drift_under_block_equals_unblocked_accumulator(db_session):
    """C2 / D4: block state must not appear in the drift term once shadow exists."""
    entity_id = "user_engineer_s"
    as_of = datetime(2024, 6, 15, 12, 0, 0)  # sim time
    wall_created = datetime(2026, 7, 19, 12, 0, 0)  # wall clock after as_of
    promoted_drift = 0.0
    shadow_drift = 3.0
    promoted_version = "promoted_v1"
    shadow_version = "shadow_v2"

    db_session.add(
        _profile(
            version=promoted_version,
            entity_id=entity_id,
            drift=promoted_drift,
            is_shadow=False,
            promoted_at=as_of - timedelta(days=5),
            created_at=as_of - timedelta(days=5),
            data_window_end=as_of - timedelta(days=5),
        )
    )
    db_session.add(
        _profile(
            version=shadow_version,
            entity_id=entity_id,
            drift=shadow_drift,
            is_shadow=True,
            promoted_at=None,
            created_at=wall_created,
            data_window_end=as_of - timedelta(hours=1),
        )
    )
    db_session.add(
        DecisionRecordModel(
            decision_id="fp_alert",
            event_id="evt_fp",
            entity_id=entity_id,
            timestamp=as_of - timedelta(days=2),
            score=50.0,
            confidence=0.9,
            profile_version=promoted_version,
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
            decision_id="fp_alert",
            entity_id=entity_id,
            state="new",
            updated_at=as_of - timedelta(days=2),
        )
    )
    db_session.commit()

    assert promoted_version != shadow_version

    store = ProfileStore(db_session)
    promoted = store.get_active_profile(entity_id, as_of)
    assert promoted is not None
    assert promoted.features["cumulative_drift"] == promoted_drift

    config = load_scoring_config()
    event = ResolvedEvent(
        event_id="evt_score",
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
    blocked = score_event(db_session, event, promoted, config)
    drift_c = next(c for c in blocked.contributions if c.feature_name == "drift_alert")
    assert abs(drift_c.raw_value - shadow_drift) < 1e-9
    assert any(
        isinstance(f, str) and f.startswith("drift_source_profile_version:")
        for f in blocked.flags
    )

    # Same accumulator without block → identical drift contribution (sanctuary absent).
    db_session.query(AlertWorkflowStateModel).delete()
    db_session.commit()
    # Attach shadow drift onto a synthetic promoted copy for unblocked comparison path
    unblocked_profile = ProfileArtifact(
        entity_id=entity_id,
        entity_type="human",
        profile_version="promoted_with_accum",
        created_at=as_of,
        data_window_start=as_of - timedelta(days=30),
        data_window_end=as_of,
        promoted_at=as_of,
        superseded_at=None,
        is_shadow=False,
        features={**promoted.features, "cumulative_drift": shadow_drift},
        embedding=promoted.embedding,
        embedding_model_id=promoted.embedding_model_id,
        embedding_model_version=promoted.embedding_model_version,
        embedding_dimensionality=promoted.embedding_dimensionality,
        embedding_input_normalizer_version=promoted.embedding_input_normalizer_version,
    )
    unblocked = score_event(db_session, event, unblocked_profile, config)
    drift_u = next(c for c in unblocked.contributions if c.feature_name == "drift_alert")
    assert abs(drift_c.contribution_score - drift_u.contribution_score) < 1e-9


def test_blocked_shadow_miss_emits_fallback_flag(db_session, caplog):
    """Blocked entity with no shadow rows emits WARN + drift_shadow_fallback flag."""
    import logging

    entity_id = "user_no_shadow"
    as_of = datetime(2024, 6, 15, 12, 0, 0)
    promoted_drift = 2.5
    promoted_version = "promoted_only_v1"

    db_session.add(
        _profile(
            version=promoted_version,
            entity_id=entity_id,
            drift=promoted_drift,
            is_shadow=False,
            promoted_at=as_of - timedelta(days=5),
            created_at=as_of - timedelta(days=5),
            data_window_end=as_of - timedelta(days=5),
        )
    )
    db_session.add(
        DecisionRecordModel(
            decision_id="fp_alert_no_shadow",
            event_id="evt_fp_no_shadow",
            entity_id=entity_id,
            timestamp=as_of - timedelta(days=2),
            score=50.0,
            confidence=0.9,
            profile_version=promoted_version,
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
            decision_id="fp_alert_no_shadow",
            entity_id=entity_id,
            state="new",
            updated_at=as_of - timedelta(days=2),
        )
    )
    db_session.commit()

    store = ProfileStore(db_session)
    promoted = store.get_active_profile(entity_id, as_of)
    assert promoted is not None
    assert store.count_shadow_profiles(entity_id) == 0

    config = load_scoring_config()
    event = ResolvedEvent(
        event_id="evt_score_no_shadow",
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

    with caplog.at_level(logging.WARNING, logger="worker.scorer"):
        decision = score_event(db_session, event, promoted, config)

    assert "drift_shadow_fallback:no_shadow" in decision.flags
    assert not any(
        isinstance(f, str) and f.startswith("drift_source_profile_version:")
        for f in decision.flags
    )
    drift_c = next(c for c in decision.contributions if c.feature_name == "drift_alert")
    assert abs(drift_c.raw_value - promoted_drift) < 1e-9

    warning_records = [
        r for r in caplog.records if r.levelname == "WARNING" and "drift_shadow_fallback" in r.message
    ]
    assert len(warning_records) == 1
    record = warning_records[0]
    assert entity_id in record.message
    assert str(as_of) in record.message
    assert "active_shadow_count=0" in record.message


def test_shadow_lookup_uses_data_window_end_not_created_at(db_session):
    """Regression: wall-future created_at must not exclude sim-eligible shadow."""
    entity_id = "user_x"
    as_of = datetime(2024, 6, 15, 12, 0, 0)
    wall_future = datetime(2026, 7, 19, 18, 0, 0)
    shadow_drift = 4.5

    db_session.add(
        _profile(
            version="shadow_future_created",
            entity_id=entity_id,
            drift=shadow_drift,
            is_shadow=True,
            promoted_at=None,
            created_at=wall_future,
            data_window_end=as_of - timedelta(hours=1),
        )
    )
    db_session.commit()

    store = ProfileStore(db_session)
    found = store.get_latest_shadow_profile(entity_id, as_of=as_of)
    assert found is not None
    assert found.features["cumulative_drift"] == shadow_drift
    assert found.profile_version == "shadow_future_created"


def test_shadow_lookup_tiebreak_prefers_later_created_at(db_session):
    """Equal data_window_end → later created_at wins (rebuild tie-break)."""
    entity_id = "user_tiebreak"
    as_of = datetime(2024, 6, 15, 12, 0, 0)
    data_window_end = as_of - timedelta(hours=1)
    earlier_created = datetime(2024, 6, 14, 8, 0, 0)
    later_created = datetime(2024, 6, 14, 20, 0, 0)

    db_session.add(
        _profile(
            version="shadow_older",
            entity_id=entity_id,
            drift=1.0,
            is_shadow=True,
            promoted_at=None,
            created_at=earlier_created,
            data_window_end=data_window_end,
        )
    )
    db_session.add(
        _profile(
            version="shadow_newer",
            entity_id=entity_id,
            drift=9.0,
            is_shadow=True,
            promoted_at=None,
            created_at=later_created,
            data_window_end=data_window_end,
        )
    )
    db_session.commit()

    store = ProfileStore(db_session)
    found = store.get_latest_shadow_profile(entity_id, as_of=as_of)
    assert found is not None
    assert found.profile_version == "shadow_newer"
    assert found.features["cumulative_drift"] == 9.0


def test_shadow_lookup_future_created_at_drives_scorer_d4(db_session):
    """Scorer D4 under block uses shadow found via data_window_end, not created_at."""
    entity_id = "user_scorer_regression"
    as_of = datetime(2024, 6, 15, 12, 0, 0)
    wall_future = datetime(2026, 7, 19, 18, 0, 0)
    promoted_drift = 0.0
    shadow_drift = 4.5
    promoted_version = "promoted_v1"
    shadow_version = "shadow_v2"

    db_session.add(
        _profile(
            version=promoted_version,
            entity_id=entity_id,
            drift=promoted_drift,
            is_shadow=False,
            promoted_at=as_of - timedelta(days=5),
            created_at=as_of - timedelta(days=5),
            data_window_end=as_of - timedelta(days=5),
        )
    )
    db_session.add(
        _profile(
            version=shadow_version,
            entity_id=entity_id,
            drift=shadow_drift,
            is_shadow=True,
            promoted_at=None,
            created_at=wall_future,
            data_window_end=as_of - timedelta(hours=1),
        )
    )
    db_session.add(
        DecisionRecordModel(
            decision_id="fp_alert_regression",
            event_id="evt_fp_regression",
            entity_id=entity_id,
            timestamp=as_of - timedelta(days=2),
            score=50.0,
            confidence=0.9,
            profile_version=promoted_version,
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
            decision_id="fp_alert_regression",
            entity_id=entity_id,
            state="new",
            updated_at=as_of - timedelta(days=2),
        )
    )
    db_session.commit()

    store = ProfileStore(db_session)
    promoted = store.get_active_profile(entity_id, as_of)
    assert promoted is not None

    config = load_scoring_config()
    event = ResolvedEvent(
        event_id="evt_score_regression",
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
    blocked = score_event(db_session, event, promoted, config)
    drift_c = next(c for c in blocked.contributions if c.feature_name == "drift_alert")
    assert abs(drift_c.raw_value - shadow_drift) < 1e-9
    assert any(
        isinstance(f, str) and f.startswith("drift_source_profile_version:")
        for f in blocked.flags
    )
