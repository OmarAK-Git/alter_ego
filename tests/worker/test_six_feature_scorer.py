import pytest
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.dialects.postgresql import JSONB, ARRAY

from core.database import Base
from core.models import ResolvedEventModel
from core.schemas.events import ResolvedEvent
from core.schemas.profiles import ProfileArtifact
from worker.scorer import score_event, load_scoring_config

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

def test_six_feature_scorer_basic(db_session):
    config = load_scoring_config()
    
    t0 = datetime(2026, 1, 1, 12, 0, 0)
    
    profile = ProfileArtifact(
        entity_id="user_1",
        entity_type="human",
        profile_version="v1",
        created_at=t0,
        data_window_start=t0 - timedelta(days=7),
        data_window_end=t0,
        features={
            "login_hours": {"12": 100},
            "endpoints": {"ep1": 50},
            "process_names": {"bash": 50},
            "total_events": 200,
            "cohort_data": {}
        }
    )
    
    # 1. Normal event
    e1 = ResolvedEvent(
        event_id="e1", timestamp=t0 + timedelta(minutes=5), event_type="process",
        raw_entity_id="user_1", entity_id="user_1", entity_type="human",
        resolution_confidence=1.0, simulation_partition="production",
        event_data={
            "endpoint_id": "ep1", 
            "process_name": "bash",
            "command_line": "/bin/bash"
        }
    )
    
    decision1 = score_event(db_session, e1, profile, config)
    assert decision1.score < config["anomaly_threshold"]
    
    # 2. Anomaly: New endpoint + New process + Weird hour
    e2 = ResolvedEvent(
        event_id="e2", timestamp=t0 + timedelta(hours=15), # 3 AM next day
        event_type="process",
        raw_entity_id="user_1", entity_id="user_1", entity_type="human",
        resolution_confidence=1.0, simulation_partition="production",
        event_data={
            "endpoint_id": "ep_UNKNOWN", 
            "process_name": "malware.exe",
            "command_line": "malware.exe --attack"
        }
    )
    
    decision2 = score_event(db_session, e2, profile, config)
    assert decision2.score > decision1.score
    # login_hour_rarity (~10+) + endpoint_novelty (15) + process_novelty (15) 
    # With weights: hour (2x) + endp (1.5x) + proc (1.0x)
    # total_score should be high
    assert decision2.score > 40.0
