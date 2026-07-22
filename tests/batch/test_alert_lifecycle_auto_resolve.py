"""S55 D3/D1 — QUIET∧ATTEST auto-resolve + drift-row refresh hygiene."""

from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker

from batch.profile_builder.builder import (
    ACTIVE_ALERT_STATES,
    AUTO_RESOLVED_AUDIT_ACTION,
    build_profiles,
)
from core.database import Base
from core.models import (
    AlertWorkflowStateModel,
    AuditLogModel,
    DecisionRecordModel,
    ProfileArtifactModel,
    ResolvedEventModel,
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


def _seed_promoted_and_block(
    db,
    *,
    entity_id: str,
    as_of: datetime,
    alert_age_days: int,
    state: str = "new",
    cumulative_drift: float = 0.5,
):
    alert_ts = as_of - timedelta(days=alert_age_days)
    features = {
        "total_events": 10,
        "login_hours": {"9": 10},
        "geolocations": {"US": 10},
        "endpoints": {"ep-a": 10},
        "process_names": {"chrome.exe": 10},
        "role": "engineer",
        "cohort_data": {},
        "cumulative_drift": cumulative_drift,
    }
    db.add(
        ProfileArtifactModel(
            profile_version=f"{entity_id}_promoted",
            entity_id=entity_id,
            entity_type="user",
            created_at=alert_ts - timedelta(days=1),
            data_window_start=alert_ts - timedelta(days=10),
            data_window_end=alert_ts - timedelta(days=1),
            promoted_at=alert_ts - timedelta(days=1),
            superseded_at=None,
            is_shadow=False,
            features=features,
            embedding=[0.0] * 128,
            embedding_model_id="alter-ego-ngram-v1",
            embedding_model_version="1.0",
            embedding_dimensionality=128,
            embedding_input_normalizer_version="1.0-char-3gram-hash-128",
        )
    )
    db.add(
        DecisionRecordModel(
            decision_id=f"alert_{entity_id}",
            event_id=f"evt_alert_{entity_id}",
            entity_id=entity_id,
            timestamp=alert_ts,
            score=50.0,
            confidence=0.9,
            profile_version=f"{entity_id}_promoted",
            scoring_config_version="2.2",
            contributions={},
            is_anomaly=True,
            cohort_used="engineer",
            cohort_unsupported=False,
            flags={},
        )
    )
    db.add(
        AlertWorkflowStateModel(
            decision_id=f"alert_{entity_id}",
            entity_id=entity_id,
            state=state,
            updated_at=alert_ts,
        )
    )
    # Events so builder runs
    for i in range(3):
        ts = as_of - timedelta(days=2) + timedelta(hours=i)
        db.add(
            ResolvedEventModel(
                event_id=f"evt_{entity_id}_{i}",
                timestamp=ts,
                event_type="process",
                raw_entity_id=entity_id,
                entity_id=entity_id,
                entity_type="user",
                resolution_confidence=1.0,
                simulation_partition="production",
                event_data={
                    "process_name": "chrome.exe",
                    "endpoint_id": "ep-a",
                    "geolocation": "US",
                    "command_line": "chrome.exe --silent",
                },
            )
        )
    db.commit()


def test_auto_resolve_new_when_quiet_attest_and_dwell(db_session):
    as_of = datetime(2026, 2, 10, 12, 0, 0)
    entity_id = "user_engineer_fp"
    _seed_promoted_and_block(
        db_session, entity_id=entity_id, as_of=as_of, alert_age_days=5
    )
    # Prior shadow builds satisfy min_dwell=2 with low peak drift
    for i in range(2):
        ts = as_of - timedelta(days=3 - i)
        db_session.add(
            ProfileArtifactModel(
                profile_version=f"{entity_id}_shadow_{i}",
                entity_id=entity_id,
                entity_type="user",
                created_at=ts,
                data_window_start=ts - timedelta(days=30),
                data_window_end=ts,
                promoted_at=None,
                superseded_at=None,
                is_shadow=True,
                features={
                    "process_names": {"chrome.exe": 10},
                    "endpoints": {"ep-a": 10},
                    "geolocations": {"US": 10},
                    "cumulative_drift": 0.4,
                },
                embedding=[0.0] * 128,
                embedding_model_id="alter-ego-ngram-v1",
                embedding_model_version="1.0",
                embedding_dimensionality=128,
                embedding_input_normalizer_version="1.0-char-3gram-hash-128",
            )
        )
    db_session.commit()

    build_profiles(db_session, as_of=as_of)

    row = (
        db_session.query(AlertWorkflowStateModel)
        .filter(AlertWorkflowStateModel.decision_id == f"alert_{entity_id}")
        .one()
    )
    assert row.state == "auto_resolved"
    audits = (
        db_session.query(AuditLogModel)
        .filter(AuditLogModel.action == AUTO_RESOLVED_AUDIT_ACTION)
        .all()
    )
    assert len(audits) >= 1


def test_acknowledged_exempt_from_auto_resolve(db_session):
    as_of = datetime(2026, 2, 10, 12, 0, 0)
    entity_id = "user_engineer_ack"
    _seed_promoted_and_block(
        db_session,
        entity_id=entity_id,
        as_of=as_of,
        alert_age_days=5,
        state="acknowledged",
    )
    for i in range(2):
        ts = as_of - timedelta(days=3 - i)
        db_session.add(
            ProfileArtifactModel(
                profile_version=f"{entity_id}_shadow_{i}",
                entity_id=entity_id,
                entity_type="user",
                created_at=ts,
                data_window_start=ts - timedelta(days=30),
                data_window_end=ts,
                promoted_at=None,
                superseded_at=None,
                is_shadow=True,
                features={
                    "process_names": {"chrome.exe": 10},
                    "endpoints": {"ep-a": 10},
                    "geolocations": {"US": 10},
                    "cumulative_drift": 0.4,
                },
                embedding=[0.0] * 128,
                embedding_model_id="alter-ego-ngram-v1",
                embedding_model_version="1.0",
                embedding_dimensionality=128,
                embedding_input_normalizer_version="1.0-char-3gram-hash-128",
            )
        )
    db_session.commit()

    build_profiles(db_session, as_of=as_of)

    row = (
        db_session.query(AlertWorkflowStateModel)
        .filter(AlertWorkflowStateModel.decision_id == f"alert_{entity_id}")
        .one()
    )
    assert row.state == "acknowledged"


def test_drift_refresh_does_not_stack_workflow_rows(db_session):
    """D1: already-blocked entity refreshes drift row instead of stacking."""
    as_of = datetime(2026, 2, 1, 12, 0, 0)
    entity_id = "user_engineer_drift"
    alert_ts = as_of - timedelta(days=2)
    features = {
        "total_events": 50,
        "login_hours": {"9": 50},
        "geolocations": {"US": 50},
        "endpoints": {"ep-a": 50},
        "process_names": {"chrome.exe": 50},
        "role": "engineer",
        "cohort_data": {},
        "cumulative_drift": 0.0,
    }
    db_session.add(
        ProfileArtifactModel(
            profile_version=f"{entity_id}_p0",
            entity_id=entity_id,
            entity_type="user",
            created_at=alert_ts - timedelta(days=5),
            data_window_start=alert_ts - timedelta(days=30),
            data_window_end=alert_ts - timedelta(days=5),
            promoted_at=alert_ts - timedelta(days=5),
            superseded_at=None,
            is_shadow=False,
            features=features,
            embedding=[0.0] * 128,
            embedding_model_id="alter-ego-ngram-v1",
            embedding_model_version="1.0",
            embedding_dimensionality=128,
            embedding_input_normalizer_version="1.0-char-3gram-hash-128",
        )
    )
    db_session.add(
        DecisionRecordModel(
            decision_id="drift_existing",
            event_id="PROFILE_BUILD",
            entity_id=entity_id,
            timestamp=alert_ts,
            score=6.0,
            confidence=0.8,
            profile_version=f"{entity_id}_p0",
            scoring_config_version="2.2",
            contributions={"cumulative_drift": 6.0},
            is_anomaly=True,
            cohort_used="engineer",
            cohort_unsupported=False,
            flags={"drift_alert": True},
        )
    )
    db_session.add(
        AlertWorkflowStateModel(
            decision_id="drift_existing",
            entity_id=entity_id,
            state="new",
            updated_at=alert_ts,
        )
    )
    # Inject novel recent behavior so builder drift accumulates high
    for i in range(20):
        ts = as_of - timedelta(hours=20 - i)
        db_session.add(
            ResolvedEventModel(
                event_id=f"evt_novel_{i}",
                timestamp=ts,
                event_type="process",
                raw_entity_id=entity_id,
                entity_id=entity_id,
                entity_type="user",
                resolution_confidence=1.0,
                simulation_partition="production",
                event_data={
                    "process_name": f"evil_{i}.exe",
                    "endpoint_id": "ep-evil",
                    "geolocation": "XX",
                    "command_line": f"evil_{i}.exe --run",
                },
            )
        )
    db_session.commit()

    before = db_session.query(AlertWorkflowStateModel).filter(
        AlertWorkflowStateModel.entity_id == entity_id,
        AlertWorkflowStateModel.state.in_(list(ACTIVE_ALERT_STATES)),
    ).count()
    assert before == 1

    build_profiles(db_session, as_of=as_of)

    after = db_session.query(AlertWorkflowStateModel).filter(
        AlertWorkflowStateModel.entity_id == entity_id,
        AlertWorkflowStateModel.state.in_(list(ACTIVE_ALERT_STATES)),
    ).count()
    assert after == 1
    refreshed = db_session.get(DecisionRecordModel, "drift_existing")
    assert refreshed is not None
    flags = refreshed.flags or {}
    assert flags.get("drift_alert") is True
