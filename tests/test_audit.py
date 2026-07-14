import json
import sqlite3

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from datetime import datetime
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.dialects.postgresql import JSONB, ARRAY

from core.database import Base
from core.models import AuditLogModel, DecisionRecordModel, log_audit_event, verify_audit_log_chain
from core.schemas.decisions import DecisionRecord
from batch.audit_integrity import AuditIntegrityError, run_integrity_check
from worker.recorder import record_decision

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
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()

def test_decision_record_is_insert_only(db_session):
    dr = DecisionRecord(
        decision_id="test_decision_1",
        event_id="test_event_1",
        entity_id="user_1",
        timestamp=datetime.utcnow(),
        score=50.0,
        confidence=1.0,
        profile_version="v1",
        scoring_config_version="v1",
        contributions=[],
        is_anomaly=False,
        cohort_used="terminus",
        cohort_unsupported=True,
        flags=[]
    )
    
    # First insert should succeed
    record_decision(dr, db_session)
    
    # Second insert with same ID should raise ValueError
    dr.score = 99.0 # Try to update score
    with pytest.raises(ValueError, match="DecisionRecord already exists. Update not allowed."):
        record_decision(dr, db_session)
        
    # Verify score hasn't changed
    stmt = select(DecisionRecordModel).where(DecisionRecordModel.decision_id == "test_decision_1")
    existing_dr = db_session.execute(stmt).scalar_one()
    assert existing_dr.score == 50.0


def test_audit_chain_integrity_healthy_chain_passes(db_session):
    log_audit_event(db_session, action="CREATE_USER", entity_id="user_1", details={"name": "Alice"})
    log_audit_event(db_session, action="UPDATE_USER", entity_id="user_1", details={"name": "Bob"})
    log_audit_event(db_session, action="DELETE_USER", entity_id="user_1", details={})

    logs = db_session.query(AuditLogModel).order_by(AuditLogModel.log_id).all()
    result = verify_audit_log_chain(logs)

    assert result.ok is True
    assert result.log_count == 3
    assert result.breaks == []

    check = run_integrity_check(db_session)
    assert check.ok is True


def test_audit_chain_integrity_broken_chain_fails(db_session):
    log_audit_event(db_session, action="CREATE_USER", entity_id="user_1", details={"name": "Alice"})
    log_audit_event(db_session, action="UPDATE_USER", entity_id="user_1", details={"name": "Bob"})

    broken = db_session.query(AuditLogModel).order_by(AuditLogModel.log_id).offset(1).first()
    broken.previous_log_hash = "tampered_hash"
    db_session.commit()

    logs = db_session.query(AuditLogModel).order_by(AuditLogModel.log_id).all()
    result = verify_audit_log_chain(logs)

    assert result.ok is False
    assert len(result.breaks) == 1
    assert result.breaks[0].log_id == broken.log_id
    assert "previous_log_hash" in result.breaks[0].reason.lower()

    with pytest.raises(AuditIntegrityError) as exc_info:
        run_integrity_check(db_session, raise_on_failure=True)
    assert exc_info.value.result.ok is False


def test_audit_chain_integrity_decision_count_mismatch_fails(db_session):
    log_audit_event(db_session, action="RECORD_DECISION", entity_id="dec_1", details={})

    result = run_integrity_check(db_session)
    assert result.ok is False
    assert result.count_mismatch is True
    assert result.decision_audit_count == 1
    assert result.decision_count == 0
