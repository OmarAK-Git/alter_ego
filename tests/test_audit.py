import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from datetime import datetime

from core.database import Base
from core.models import DecisionRecordModel
from core.schemas.decisions import DecisionRecord
from worker.recorder import record_decision

from sqlalchemy.ext.compiler import compiles
from sqlalchemy.dialects.postgresql import JSONB, ARRAY

@compiles(JSONB, "sqlite")
def compile_jsonb_sqlite(type_, compiler, **kw):
    return "JSON"

@compiles(ARRAY, "sqlite")
def compile_array_sqlite(type_, compiler, **kw):
    return "JSON"

import sqlite3
import json
sqlite3.register_adapter(list, lambda l: json.dumps(l))
sqlite3.register_adapter(dict, lambda d: json.dumps(d))

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
