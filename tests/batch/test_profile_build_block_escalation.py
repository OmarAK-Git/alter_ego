"""S5.6 — max_profile_build_block_days supervisor escalation in profile builder."""

from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker

from batch.profile_builder.builder import (
    BUILD_BLOCK_SUPERVISOR_ESCALATION_FLAG,
    build_profiles,
)
from core.database import Base
from core.models import (
    AlertWorkflowStateModel,
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


def _seed_blocked_entity(
    db_session,
    *,
    entity_id: str,
    as_of: datetime,
    alert_age_days: int,
    event_ts: datetime | None = None,
):
    if event_ts is None:
        event_ts = as_of - timedelta(days=5)
    alert_ts = as_of - timedelta(days=alert_age_days)

    db_session.add(
        ResolvedEventModel(
            event_id=f"evt_{entity_id}",
            timestamp=event_ts,
            event_type="login",
            raw_entity_id=entity_id,
            entity_id=entity_id,
            entity_type="user",
            resolution_confidence=1.0,
            simulation_partition="production",
            event_data={"action": "login"},
        )
    )
    db_session.add(
        DecisionRecordModel(
            decision_id=f"alert_{entity_id}",
            event_id=f"evt_alert_{entity_id}",
            entity_id=entity_id,
            timestamp=alert_ts,
            score=50.0,
            confidence=0.9,
            profile_version="prof_v0",
            scoring_config_version="2.2",
            contributions={},
            is_anomaly=True,
            cohort_used="engineer",
            cohort_unsupported=False,
            flags={"drift_alert": True},
        )
    )
    db_session.add(
        AlertWorkflowStateModel(
            decision_id=f"alert_{entity_id}",
            entity_id=entity_id,
            state="investigating",
            updated_at=alert_ts,
        )
    )
    db_session.commit()


def _escalation_decisions(db_session, entity_id: str):
    return (
        db_session.query(DecisionRecordModel)
        .filter(
            DecisionRecordModel.entity_id == entity_id,
            DecisionRecordModel.event_id == "PROFILE_BUILD",
        )
        .all()
    )


def test_build_block_under_threshold_no_supervisor_escalation(db_session):
    as_of = datetime(2026, 2, 1, 12, 0, 0)
    entity_id = "user_under"
    _seed_blocked_entity(db_session, entity_id=entity_id, as_of=as_of, alert_age_days=15)

    build_profiles(db_session, as_of=as_of)

    escalations = [
        d
        for d in _escalation_decisions(db_session, entity_id)
        if (d.flags or {}).get(BUILD_BLOCK_SUPERVISOR_ESCALATION_FLAG)
    ]
    assert escalations == []
    assert (
        db_session.query(ProfileArtifactModel)
        .filter(ProfileArtifactModel.entity_id == entity_id)
        .order_by(ProfileArtifactModel.created_at.desc())
        .first()
        .is_shadow
        is True
    )


def test_build_block_over_threshold_emits_supervisor_escalation(db_session):
    as_of = datetime(2026, 2, 1, 12, 0, 0)
    entity_id = "user_over"
    _seed_blocked_entity(db_session, entity_id=entity_id, as_of=as_of, alert_age_days=35)

    build_profiles(db_session, as_of=as_of)

    escalations = [
        d
        for d in _escalation_decisions(db_session, entity_id)
        if (d.flags or {}).get(BUILD_BLOCK_SUPERVISOR_ESCALATION_FLAG)
    ]
    assert len(escalations) == 1
    flags = escalations[0].flags
    assert flags[BUILD_BLOCK_SUPERVISOR_ESCALATION_FLAG] is True
    assert flags["block_days"] > 30
    assert flags["max_profile_build_block_days"] == 30
    assert flags["sla_hours"] == 24
    assert escalations[0].is_anomaly is False


def test_build_block_escalation_without_events_when_over_threshold(db_session):
    as_of = datetime(2026, 2, 1, 12, 0, 0)
    entity_id = "user_no_events"
    alert_ts = as_of - timedelta(days=40)
    db_session.add(
        DecisionRecordModel(
            decision_id="alert_no_evt",
            event_id="evt_x",
            entity_id=entity_id,
            timestamp=alert_ts,
            score=50.0,
            confidence=0.9,
            profile_version="prof_v0",
            scoring_config_version="2.2",
            contributions={},
            is_anomaly=True,
            cohort_used="engineer",
            cohort_unsupported=False,
            flags={},
        )
    )
    db_session.add(
        AlertWorkflowStateModel(
            decision_id="alert_no_evt",
            entity_id=entity_id,
            state="new",
            updated_at=alert_ts,
        )
    )
    db_session.commit()

    count = build_profiles(db_session, as_of=as_of)

    assert count == 0
    escalations = [
        d
        for d in _escalation_decisions(db_session, entity_id)
        if (d.flags or {}).get(BUILD_BLOCK_SUPERVISOR_ESCALATION_FLAG)
    ]
    assert len(escalations) == 1
