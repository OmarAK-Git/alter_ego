"""S5.5 — staleness halt + active-alert mandatory escalation flags."""

from datetime import datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker
from sqlalchemy.dialects.postgresql import ARRAY, JSONB

from core.database import Base
from core.models import AlertWorkflowStateModel, DecisionRecordModel
from core.schemas.events import AuthEventData, ResolvedEvent
from core.schemas.profiles import ProfileArtifact
from worker.scorer import (
    SENSOR_HEALTH_STALENESS_FLAG,
    STALENESS_ESCALATION_FLAG,
    entity_has_active_uncleared_alert,
    score_event,
)
from tests.worker.conftest import COMPATIBLE_EMBEDDING_PROFILE_FIELDS


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


def _stale_profile_fixture():
    profile_end = datetime(2026, 1, 1, 12, 0)
    event_ts = datetime(2026, 1, 20, 12, 0)  # 19 days later — past default 14-day window
    resolved_event = ResolvedEvent(
        event_id="evt_stale",
        timestamp=event_ts,
        event_type="auth",
        raw_entity_id="u1",
        entity_id="u1",
        entity_type="human",
        resolution_confidence=1.0,
        simulation_partition="production",
        event_data=AuthEventData(action="login", ip_address="1.1.1.1", endpoint_id="ep1"),
    )
    profile = ProfileArtifact(
        entity_id="u1",
        entity_type="human",
        profile_version="prof_stale",
        created_at=profile_end,
        data_window_start=datetime(2026, 1, 1, 0, 0),
        data_window_end=profile_end,
        features={"role": "Engineer", "login_hours": {"12": 50}, "cohort_data": {}},
        **COMPATIBLE_EMBEDDING_PROFILE_FIELDS,
    )
    config = {
        "features": {},
        "version": "2.2",
        "max_profile_staleness_days": 14,
    }
    return resolved_event, profile, config


def _add_active_alert(db_session, entity_id: str, decision_id: str, state: str = "new"):
    db_session.add(
        DecisionRecordModel(
            decision_id=decision_id,
            event_id=f"evt_{decision_id}",
            entity_id=entity_id,
            timestamp=datetime(2026, 1, 5, 12, 0),
            score=55.0,
            confidence=0.9,
            profile_version="v1",
            scoring_config_version="2.2",
            contributions=[],
            is_anomaly=True,
            cohort_used="local",
            cohort_unsupported=False,
            flags=[],
            embedding_model_version="1.0",
        )
    )
    if state != "new":
        db_session.add(
            AlertWorkflowStateModel(
                decision_id=decision_id,
                entity_id=entity_id,
                state=state,
            )
        )
    db_session.commit()


def test_staleness_halt_preserves_score_zero(db_session):
    resolved_event, profile, config = _stale_profile_fixture()
    decision = score_event(db_session, resolved_event, profile, config)

    assert decision.score == 0.0
    assert "staleness_halt" in decision.flags
    assert decision.is_anomaly is False


def test_staleness_halt_without_active_alert_no_escalation_flag(db_session):
    resolved_event, profile, config = _stale_profile_fixture()
    decision = score_event(db_session, resolved_event, profile, config)

    assert STALENESS_ESCALATION_FLAG not in decision.flags
    assert SENSOR_HEALTH_STALENESS_FLAG in decision.flags


@pytest.mark.parametrize("alert_state", ["new", "acknowledged", "investigating"])
def test_staleness_halt_with_active_alert_adds_escalation_flags(db_session, alert_state):
    _add_active_alert(db_session, "u1", "dec_alert", state=alert_state)
    resolved_event, profile, config = _stale_profile_fixture()
    decision = score_event(db_session, resolved_event, profile, config)

    assert "staleness_halt" in decision.flags
    assert STALENESS_ESCALATION_FLAG in decision.flags
    assert SENSOR_HEALTH_STALENESS_FLAG in decision.flags


def test_cleared_alert_does_not_trigger_escalation_flag(db_session):
    _add_active_alert(db_session, "u1", "dec_cleared", state="cleared")

    resolved_event, profile, config = _stale_profile_fixture()
    decision = score_event(db_session, resolved_event, profile, config)

    assert STALENESS_ESCALATION_FLAG not in decision.flags


def test_entity_has_active_uncleared_alert_helper(db_session):
    assert entity_has_active_uncleared_alert(db_session, "u1") is False
    _add_active_alert(db_session, "u1", "dec_a", state="acknowledged")
    assert entity_has_active_uncleared_alert(db_session, "u1") is True
