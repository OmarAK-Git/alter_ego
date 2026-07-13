import pytest
from fastapi.testclient import TestClient
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from web.api import app, get_db
from core.database import Base
from core.models import DecisionRecordModel, AlertWorkflowStateModel

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


def _make_anomaly(db_session, decision_id, confidence):
    dec = DecisionRecordModel(
        decision_id=decision_id,
        event_id=f"evt_{decision_id}",
        entity_id="user_x",
        timestamp=datetime.utcnow(),
        score=50.0,
        confidence=confidence,
        profile_version="v1",
        scoring_config_version="1",
        contributions=[],
        is_anomaly=True,
        cohort_used="role1",
        cohort_unsupported=False,
        flags=[],
    )
    db_session.add(dec)
    db_session.commit()
    return dec


def test_high_confidence_anomaly_in_triage_not_suppressed(client, db_session):
    _make_anomaly(db_session, "dec_high", confidence=0.9)

    triage = client.get("/api/alerts").json()
    suppressed = client.get("/api/suppressed").json()

    assert any(d["decision_id"] == "dec_high" for d in triage)
    assert not any(d["decision_id"] == "dec_high" for d in suppressed)


def test_low_confidence_anomaly_in_suppressed_not_triage(client, db_session):
    _make_anomaly(db_session, "dec_low", confidence=0.4)

    triage = client.get("/api/alerts").json()
    suppressed = client.get("/api/suppressed").json()

    assert not any(d["decision_id"] == "dec_low" for d in triage)
    assert any(d["decision_id"] == "dec_low" for d in suppressed)


def test_cleared_suppressed_decision_excluded_from_both(client, db_session):
    _make_anomaly(db_session, "dec_cleared_sup", confidence=0.4)
    db_session.add(
        AlertWorkflowStateModel(
            decision_id="dec_cleared_sup",
            entity_id="user_x",
            state="cleared",
            clear_reason="Benign",
        )
    )
    db_session.commit()

    triage = client.get("/api/alerts").json()
    suppressed = client.get("/api/suppressed").json()

    assert not any(d["decision_id"] == "dec_cleared_sup" for d in triage)
    assert not any(d["decision_id"] == "dec_cleared_sup" for d in suppressed)


def test_alert_detail_includes_replay_run_id_when_present(client, db_session):
    dec = DecisionRecordModel(
        decision_id="dec_replay",
        event_id="evt_replay",
        entity_id="user_replay",
        timestamp=datetime.utcnow(),
        score=55.0,
        confidence=0.9,
        profile_version="v1",
        scoring_config_version="2.2",
        contributions=[],
        is_anomaly=True,
        cohort_used="role1",
        cohort_unsupported=False,
        flags=["replay:replay_abc"],
        replay_run_id="replay_abc",
    )
    db_session.add(dec)
    db_session.commit()

    res = client.get("/api/alerts/dec_replay")
    assert res.status_code == 200
    assert res.json()["decision"]["replay_run_id"] == "replay_abc"


def test_alert_detail_replay_run_id_null_for_original(client, db_session):
    dec = DecisionRecordModel(
        decision_id="dec_orig",
        event_id="evt_orig",
        entity_id="user_orig",
        timestamp=datetime.utcnow(),
        score=40.0,
        confidence=0.9,
        profile_version="v1",
        scoring_config_version="2.2",
        contributions=[],
        is_anomaly=True,
        cohort_used="role1",
        cohort_unsupported=False,
        flags=[],
        replay_run_id=None,
    )
    db_session.add(dec)
    db_session.commit()

    res = client.get("/api/alerts/dec_orig")
    assert res.status_code == 200
    assert res.json()["decision"]["replay_run_id"] is None
