"""S4.4 — automated demo path: seed → triage → explain → contain."""

import importlib.util
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from core.database import Base
from core.models import ContainmentQueueModel
from web.api import app, get_db

_demo_spec = importlib.util.spec_from_file_location(
    "demo_path",
    Path(__file__).resolve().parents[2] / "scripts" / "demo_path.py",
)
assert _demo_spec is not None and _demo_spec.loader is not None
demo_path = importlib.util.module_from_spec(_demo_spec)
_demo_spec.loader.exec_module(demo_path)

DEMO_DECISION_ID = demo_path.DEMO_DECISION_ID
seed_demo_alert = demo_path.seed_demo_alert
cleanup_demo_alert = demo_path.cleanup_demo_alert
run_demo_path = demo_path.run_demo_path


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


def test_demo_path_api_chain(client, db_session):
    """Seed → triage visible → acknowledge → explain → contain."""
    seed_demo_alert(db_session)

    result = run_demo_path(client, decision_id=DEMO_DECISION_ID)

    assert result["decision_id"] == DEMO_DECISION_ID
    assert result["workflow_state"] == "acknowledged"
    assert result["validation_status"] in ("passed", "template_fallback")

    rows = db_session.execute(select(ContainmentQueueModel)).scalars().all()
    assert any(r.decision_id == DEMO_DECISION_ID and r.action == "simulate_containment" for r in rows)

    cleanup_demo_alert(db_session)
    triage = client.get("/api/alerts").json()
    assert not any(a["decision_id"] == DEMO_DECISION_ID for a in triage)
