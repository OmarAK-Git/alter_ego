"""S5.5 — mandatory escalation queue API."""

from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from core.database import Base
from core.models import (
    AlertWorkflowStateModel,
    DecisionRecordModel,
    StalenessHaltExtensionModel,
)
from web.api import app, get_db
from worker.scorer import STALENESS_ESCALATION_FLAG


@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
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


def _add_decision(
    db_session,
    *,
    decision_id: str,
    entity_id: str,
    is_anomaly: bool,
    flags: list[str],
):
    db_session.add(
        DecisionRecordModel(
            decision_id=decision_id,
            event_id=f"evt_{decision_id}",
            entity_id=entity_id,
            timestamp=datetime.utcnow(),
            score=0.0 if not is_anomaly else 55.0,
            confidence=0.9,
            profile_version="v1",
            scoring_config_version="2.2",
            contributions=[],
            is_anomaly=is_anomaly,
            cohort_used="local",
            cohort_unsupported=True,
            flags=flags,
            embedding_model_version="1.0",
        )
    )
    db_session.commit()


def test_mandatory_escalations_lists_staleness_with_active_alert(client, db_session):
    _add_decision(
        db_session,
        decision_id="dec_alert",
        entity_id="ent_1",
        is_anomaly=True,
        flags=[],
    )
    _add_decision(
        db_session,
        decision_id="dec_halt",
        entity_id="ent_1",
        is_anomaly=False,
        flags=["staleness_halt", STALENESS_ESCALATION_FLAG, "sensor_health_staleness"],
    )

    res = client.get("/api/mandatory-escalations")
    assert res.status_code == 200
    data = res.json()
    assert len(data) == 1
    assert data[0]["entity_id"] == "ent_1"
    assert "dec_alert" in data[0]["alert_decision_ids"]
    assert data[0]["staleness_decision_id"] == "dec_halt"


def test_mandatory_escalations_no_anomaly_required_for_halt_decision(client, db_session):
    _add_decision(
        db_session,
        decision_id="dec_alert2",
        entity_id="ent_2",
        is_anomaly=True,
        flags=[],
    )
    _add_decision(
        db_session,
        decision_id="dec_halt2",
        entity_id="ent_2",
        is_anomaly=False,
        flags=["staleness_halt", STALENESS_ESCALATION_FLAG],
    )

    res = client.get("/api/mandatory-escalations")
    assert res.status_code == 200
    assert any(item["entity_id"] == "ent_2" for item in res.json())


def test_cleared_alert_removes_from_mandatory_queue(client, db_session):
    _add_decision(
        db_session,
        decision_id="dec_alert3",
        entity_id="ent_3",
        is_anomaly=True,
        flags=[],
    )
    _add_decision(
        db_session,
        decision_id="dec_halt3",
        entity_id="ent_3",
        is_anomaly=False,
        flags=["staleness_halt", STALENESS_ESCALATION_FLAG],
    )
    db_session.add(
        AlertWorkflowStateModel(
            decision_id="dec_alert3",
            entity_id="ent_3",
            state="cleared",
            clear_reason="Resolved",
        )
    )
    db_session.commit()

    res = client.get("/api/mandatory-escalations")
    assert res.status_code == 200
    assert not any(item["entity_id"] == "ent_3" for item in res.json())


def test_extend_halt_requires_justification(client, db_session):
    res = client.post("/api/mandatory-escalations/ent_x/extend-halt", json={})
    assert res.status_code == 422


def test_extend_halt_persists_and_removes_from_queue(client, db_session):
    _add_decision(
        db_session,
        decision_id="dec_alert4",
        entity_id="ent_4",
        is_anomaly=True,
        flags=[],
    )
    _add_decision(
        db_session,
        decision_id="dec_halt4",
        entity_id="ent_4",
        is_anomaly=False,
        flags=["staleness_halt", STALENESS_ESCALATION_FLAG],
    )

    before = client.get("/api/mandatory-escalations").json()
    assert any(item["entity_id"] == "ent_4" for item in before)

    res = client.post(
        "/api/mandatory-escalations/ent_4/extend-halt",
        json={"justification": "Profile rebuild blocked pending vendor patch"},
    )
    assert res.status_code == 200
    assert res.json()["status"] == "success"

    ext = (
        db_session.query(StalenessHaltExtensionModel)
        .filter(StalenessHaltExtensionModel.entity_id == "ent_4")
        .first()
    )
    assert ext is not None
    assert ext.justification == "Profile rebuild blocked pending vendor patch"
    assert ext.expires_at > datetime.utcnow()

    after = client.get("/api/mandatory-escalations").json()
    assert not any(item["entity_id"] == "ent_4" for item in after)


def test_expired_extend_halt_returns_entity_to_queue(client, db_session):
    _add_decision(
        db_session,
        decision_id="dec_alert5",
        entity_id="ent_5",
        is_anomaly=True,
        flags=[],
    )
    _add_decision(
        db_session,
        decision_id="dec_halt5",
        entity_id="ent_5",
        is_anomaly=False,
        flags=["staleness_halt", STALENESS_ESCALATION_FLAG],
    )
    db_session.add(
        StalenessHaltExtensionModel(
            entity_id="ent_5",
            justification="Temporary",
            extended_at=datetime.utcnow() - timedelta(hours=48),
            expires_at=datetime.utcnow() - timedelta(hours=1),
        )
    )
    db_session.commit()

    res = client.get("/api/mandatory-escalations")
    assert any(item["entity_id"] == "ent_5" for item in res.json())


def test_mandatory_escalations_lists_build_block_sla(client, db_session):
    """S55 D5 — build-block supervisor escalation appears on mandatory queue."""
    from batch.profile_builder.builder import BUILD_BLOCK_SUPERVISOR_ESCALATION_FLAG

    _add_decision(
        db_session,
        decision_id="dec_alert_bb",
        entity_id="ent_bb",
        is_anomaly=True,
        flags=[],
    )
    db_session.add(
        AlertWorkflowStateModel(
            decision_id="dec_alert_bb",
            entity_id="ent_bb",
            state="new",
        )
    )
    db_session.add(
        DecisionRecordModel(
            decision_id="dec_bb_esc",
            event_id="PROFILE_BUILD",
            entity_id="ent_bb",
            timestamp=datetime.utcnow(),
            score=0.0,
            confidence=1.0,
            profile_version="v1",
            scoring_config_version="2.2",
            contributions={"build_block_days": 35.0},
            is_anomaly=False,
            cohort_used="unknown",
            cohort_unsupported=False,
            flags={
                BUILD_BLOCK_SUPERVISOR_ESCALATION_FLAG: True,
                "mandatory_review": True,
                "block_days": 35.0,
            },
            embedding_model_version="1.0",
        )
    )
    db_session.commit()

    res = client.get("/api/mandatory-escalations")
    assert res.status_code == 200
    data = res.json()
    match = [item for item in data if item["entity_id"] == "ent_bb"]
    assert len(match) == 1
    assert match[0]["escalation_type"] == "build_block"
    assert match[0]["escalation_decision_id"] == "dec_bb_esc"
