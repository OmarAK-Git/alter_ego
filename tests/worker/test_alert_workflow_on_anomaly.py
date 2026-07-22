"""SPEC §5.5 — anomaly DecisionRecords must open AlertWorkflowState so builds block."""

from datetime import datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker

from core.database import Base
from core.models import AlertWorkflowStateModel, DecisionRecordModel
from core.schemas.decisions import DecisionRecord, FeatureContribution
from worker.recorder import record_decision


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


def test_anomaly_decision_opens_active_alert_workflow(db_session):
    ts = datetime(2026, 1, 10, 12, 0, 0)
    dr = DecisionRecord(
        decision_id="dec_anomaly_1",
        event_id="evt_1",
        entity_id="user_engineer_x",
        timestamp=ts,
        score=50.0,
        confidence=0.9,
        profile_version="p1",
        scoring_config_version="2.2",
        contributions=[
            FeatureContribution(
                contribution_id="c1",
                feature_name="drift_alert",
                raw_value=2.5,
                contribution_score=50.0,
                confidence_weight=0.8,
            )
        ],
        is_anomaly=True,
        cohort_used="engineer",
        cohort_unsupported=False,
        flags=[],
        embedding_model_version="1.0",
    )
    record_decision(dr, db_session)

    state = (
        db_session.query(AlertWorkflowStateModel)
        .filter(AlertWorkflowStateModel.decision_id == "dec_anomaly_1")
        .one()
    )
    assert state.entity_id == "user_engineer_x"
    assert state.state == "new"


def test_non_anomaly_does_not_open_workflow(db_session):
    ts = datetime(2026, 1, 10, 12, 0, 0)
    dr = DecisionRecord(
        decision_id="dec_ok_1",
        event_id="evt_2",
        entity_id="user_engineer_y",
        timestamp=ts,
        score=10.0,
        confidence=0.9,
        profile_version="p1",
        scoring_config_version="2.2",
        contributions=[],
        is_anomaly=False,
        cohort_used="engineer",
        cohort_unsupported=False,
        flags=[],
        embedding_model_version="1.0",
    )
    record_decision(dr, db_session)
    assert (
        db_session.query(AlertWorkflowStateModel)
        .filter(AlertWorkflowStateModel.decision_id == "dec_ok_1")
        .count()
        == 0
    )
    assert db_session.query(DecisionRecordModel).count() == 1
