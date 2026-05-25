import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from datetime import datetime
from core.database import Base
from core.models import AuditLogModel, log_audit_event
from worker.scorer import score_event
from core.schemas.events import ResolvedEvent
from core.schemas.profiles import ProfileArtifact

@pytest.fixture
def db_session():
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()

def test_new_confidence_calculation(db_session):
    # Test confidence calculation formula: n / (n + k)
    from core.schemas.events import ResolvedEvent, AuthEventData
    from core.schemas.profiles import ProfileArtifact
    from worker.scorer import score_event
    
    ts = datetime(2026, 1, 1, 12, 0)
    event_data = AuthEventData(action="login", ip_address="1.1.1.1", endpoint_id="ep1")
    resolved_event = ResolvedEvent(
        event_id="evt_123",
        timestamp=ts,
        event_type="auth",
        raw_entity_id="u1",
        entity_id="u1",
        entity_type="human",
        resolution_confidence=1.0,
        simulation_partition="production",
        event_data=event_data
    )

    # 1. Profile with total_events = 40, and config confidence_k = 10.0
    # Expected confidence = 40 / (40 + 10) = 40 / 50 = 0.8
    profile = ProfileArtifact(
        entity_id="u1",
        entity_type="human",
        profile_version="prof_v1",
        created_at=ts,
        data_window_start=ts,
        data_window_end=ts,
        features={"role": "Engineer", "total_events": 40, "cohort_data": {}},
        embedding_model_id="nomic-embed-text",
        embedding_model_version="1.0",
        embedding_dimensionality=128
    )
    
    config = {"features": {}, "anomaly_threshold": 75.0, "version": "1.0", "confidence_k": 10.0}
    decision = score_event(db_session, resolved_event, profile, config)
    assert abs(decision.confidence - 0.8) < 1e-6

    # 2. Profile with total_events missing, fallback to sum of login_hours values = 30, confidence_k missing (defaults to 10.0)
    # Expected confidence = 30 / (30 + 10) = 0.75
    profile_fallback = ProfileArtifact(
        entity_id="u1",
        entity_type="human",
        profile_version="prof_v2",
        created_at=ts,
        data_window_start=ts,
        data_window_end=ts,
        features={"role": "Engineer", "login_hours": {"12": 20, "13": 10}, "cohort_data": {}},
        embedding_model_id="nomic-embed-text",
        embedding_model_version="1.0",
        embedding_dimensionality=128
    )
    
    config_default_k = {"features": {}, "anomaly_threshold": 75.0, "version": "1.0"}
    decision_fallback = score_event(db_session, resolved_event, profile_fallback, config_default_k)
    assert abs(decision_fallback.confidence - 0.75) < 1e-6

def test_audit_log_hash_chaining(db_session):
    # Log first event
    log1 = log_audit_event(db_session, action="CREATE_USER", entity_id="user_1", details={"name": "Alice"})
    assert log1.previous_log_hash is None
    hash1 = log1.compute_hash()
    
    # Log second event
    log2 = log_audit_event(db_session, action="UPDATE_USER", entity_id="user_1", details={"name": "Alice Cooper"})
    assert log2.previous_log_hash == hash1
    hash2 = log2.compute_hash()
    
    # Log third event
    log3 = log_audit_event(db_session, action="DELETE_USER", entity_id="user_1", details={})
    assert log3.previous_log_hash == hash2
    
    # Verify the database records chain correctly
    all_logs = db_session.query(AuditLogModel).order_by(AuditLogModel.log_id).all()
    assert len(all_logs) == 3
    assert all_logs[0].previous_log_hash is None
    assert all_logs[1].previous_log_hash == all_logs[0].compute_hash()
    assert all_logs[2].previous_log_hash == all_logs[1].compute_hash()
