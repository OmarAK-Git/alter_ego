import pytest
from fastapi.testclient import TestClient
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from web.api import app, get_db
from core.database import Base
from core.models import DecisionRecordModel, AlertWorkflowStateModel, ProfileArtifactModel

from sqlalchemy.pool import StaticPool

@pytest.fixture
def db_session():
    engine = create_engine('sqlite:///:memory:', connect_args={'check_same_thread': False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()

@pytest.fixture
def client(db_session):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass
    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()

def test_get_triage_alerts(client, db_session):
    dec = DecisionRecordModel(
        decision_id="dec1",
        event_id="evt1",
        entity_id="user_1",
        timestamp=datetime.utcnow(),
        score=50.0,
        confidence=0.9,
        profile_version="v1",
        scoring_config_version="1",
        contributions=[],
        is_anomaly=True,
        cohort_used="role1",
        cohort_unsupported=False,
        flags=[]
    )
    db_session.add(dec)
    db_session.commit()
    
    res = client.get("/api/alerts")
    assert res.status_code == 200
    data = res.json()
    assert len(data) == 1
    assert data[0]["decision_id"] == "dec1"
    assert data[0]["state"] == "new"
    
def test_workflow_state_transition(client, db_session):
    dec = DecisionRecordModel(
        decision_id="dec2",
        event_id="evt2",
        entity_id="user_2",
        timestamp=datetime.utcnow(),
        score=60.0,
        confidence=0.9,
        profile_version="v1",
        scoring_config_version="1",
        contributions=[],
        is_anomaly=True,
        cohort_used="role1",
        cohort_unsupported=False,
        flags=[]
    )
    db_session.add(dec)
    db_session.commit()
    
    # Update to acknowledged
    res = client.put("/api/alerts/dec2/workflow", json={"state": "acknowledged"})
    assert res.status_code == 200
    assert res.json()["state"] == "acknowledged"
    
    # Check DB
    state = db_session.query(AlertWorkflowStateModel).filter(AlertWorkflowStateModel.decision_id == "dec2").first()
    assert state.state == "acknowledged"
    
def test_clear_alert_hides_from_triage(client, db_session):
    dec = DecisionRecordModel(
        decision_id="dec3",
        event_id="evt3",
        entity_id="user_3",
        timestamp=datetime.utcnow(),
        score=70.0,
        confidence=0.9,
        profile_version="v1",
        scoring_config_version="1",
        contributions=[],
        is_anomaly=True,
        cohort_used="role1",
        cohort_unsupported=False,
        flags=[]
    )
    db_session.add(dec)
    db_session.commit()
    
    res = client.put("/api/alerts/dec3/workflow", json={"state": "cleared", "clear_reason": "False positive"})
    assert res.status_code == 200
    
    res2 = client.get("/api/alerts")
    data = res2.json()
    # dec3 should not be in the triage queue
    assert not any(d["decision_id"] == "dec3" for d in data)
