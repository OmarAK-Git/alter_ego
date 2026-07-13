import json
import pytest
from datetime import datetime
from unittest.mock import patch

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.dialects.postgresql import JSONB, ARRAY

from core.database import Base
from core.models import DecisionRecordModel, ResolvedEventModel, ProfileArtifactModel
from core.schemas.decisions import DecisionRecord
from batch.replay_runner import run_replay
from worker.recorder import record_decision

sqlite3 = __import__("sqlite3")
sqlite3.register_adapter(list, lambda value: json.dumps(value))
sqlite3.register_adapter(dict, lambda value: json.dumps(value))


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


def test_decision_record_replay_run_id_defaults_null():
    dr = DecisionRecord(
        decision_id="d1",
        event_id="e1",
        entity_id="user_1",
        timestamp=datetime.utcnow(),
        score=10.0,
        confidence=0.8,
        profile_version="v1",
        scoring_config_version="2.2",
        contributions=[],
        is_anomaly=False,
        cohort_used="local",
        cohort_unsupported=False,
        flags=[],
    )
    assert dr.replay_run_id is None


def test_original_decision_persists_null_replay_run_id(db_session):
    dr = DecisionRecord(
        decision_id="orig_1",
        event_id="evt_orig",
        entity_id="user_1",
        timestamp=datetime.utcnow(),
        score=50.0,
        confidence=0.9,
        profile_version="v1",
        scoring_config_version="2.2",
        contributions=[],
        is_anomaly=True,
        cohort_used="local",
        cohort_unsupported=False,
        flags=[],
    )
    record_decision(dr, db_session)

    row = db_session.execute(
        select(DecisionRecordModel).where(DecisionRecordModel.decision_id == "orig_1")
    ).scalar_one()
    assert row.replay_run_id is None


def _seed_replay_fixtures(db_session, ts: datetime):
    db_session.add(
        ResolvedEventModel(
            event_id="evt_replay",
            timestamp=ts,
            event_type="auth",
            raw_entity_id="user_1",
            entity_id="user_1",
            entity_type="human",
            resolution_confidence=1.0,
            simulation_partition="production",
            event_data={
                "action": "login",
                "ip_address": "10.0.0.1",
                "endpoint_id": "ep1",
            },
        )
    )
    db_session.add(
        ProfileArtifactModel(
            profile_version="pv1",
            entity_id="user_1",
            entity_type="human",
            created_at=ts,
            data_window_start=ts,
            data_window_end=ts,
            promoted_at=ts,
            is_shadow=False,
            features={"role": "analyst", "login_hour": {"9": 10}},
        )
    )
    db_session.commit()


def test_run_replay_sets_replay_run_id_on_emitted_decisions(db_session):
    ts = datetime(2026, 6, 1, 12, 0, 0)
    _seed_replay_fixtures(db_session, ts)

    mock_decision = DecisionRecord(
        decision_id="base_dec",
        event_id="evt_replay",
        entity_id="user_1",
        timestamp=ts,
        score=42.0,
        confidence=0.85,
        profile_version="pv1",
        scoring_config_version="2.2",
        contributions=[],
        is_anomaly=True,
        cohort_used="local",
        cohort_unsupported=False,
        flags=[],
    )

    with patch("batch.replay_runner.score_event", return_value=mock_decision):
        summary = run_replay(
            start_time=ts,
            end_time=ts,
            author="analyst",
            change_reason="config bump",
            replay_run_id="replay_test_001",
            db=db_session,
        )

    assert summary["replay_run_id"] == "replay_test_001"
    assert summary["decisions_emitted"] == 1

    row = db_session.execute(
        select(DecisionRecordModel).where(
            DecisionRecordModel.decision_id == "replay_test_001_base_dec"
        )
    ).scalar_one()
    assert row.replay_run_id == "replay_test_001"
    assert "replay:replay_test_001" in row.flags


def test_run_replay_does_not_mutate_original_decision(db_session):
    ts = datetime(2026, 6, 2, 12, 0, 0)
    _seed_replay_fixtures(db_session, ts)

    original = DecisionRecord(
        decision_id="orig_keep",
        event_id="evt_replay",
        entity_id="user_1",
        timestamp=ts,
        score=30.0,
        confidence=0.7,
        profile_version="pv1",
        scoring_config_version="2.2",
        contributions=[],
        is_anomaly=False,
        cohort_used="local",
        cohort_unsupported=False,
        flags=[],
    )
    record_decision(original, db_session)

    replay_decision = original.model_copy(update={"decision_id": "base_replay", "score": 99.0})
    with patch("batch.replay_runner.score_event", return_value=replay_decision):
        run_replay(
            start_time=ts,
            end_time=ts,
            author="analyst",
            change_reason="test",
            replay_run_id="replay_immutable",
            db=db_session,
        )

    orig_row = db_session.execute(
        select(DecisionRecordModel).where(DecisionRecordModel.decision_id == "orig_keep")
    ).scalar_one()
    assert orig_row.score == 30.0
    assert orig_row.replay_run_id is None

    replay_row = db_session.execute(
        select(DecisionRecordModel).where(
            DecisionRecordModel.replay_run_id == "replay_immutable"
        )
    ).scalar_one()
    assert replay_row.decision_id == "replay_immutable_base_replay"
    assert replay_row.score == 99.0
