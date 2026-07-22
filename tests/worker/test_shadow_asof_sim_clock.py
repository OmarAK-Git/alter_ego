"""Regression: D4 shadow lookup must use sim-time window, not wall created_at."""

from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker

from core.database import Base
from core.models import ProfileArtifactModel
from worker.profile_store import ProfileStore


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


def test_get_latest_shadow_profile_as_of_uses_data_window_not_wall_created_at(db_session):
    """Sim event times must see shadows whose data_window_end <= as_of.

    Series C replay builds profiles with wall-clock created_at (host now) while
    events carry 2026-01-* timestamps. Filtering created_at <= as_of always
    misses shadows and defeats D4.
    """
    entity = "user_engineer_d4"
    sim_end = datetime(2026, 1, 12, 23, 0, 0)
    wall_created = datetime(2026, 7, 19, 5, 0, 0)
    event_as_of = datetime(2026, 1, 13, 10, 0, 0)

    db_session.add(
        ProfileArtifactModel(
            profile_version=f"{entity}_shadow",
            entity_id=entity,
            entity_type="user",
            created_at=wall_created,
            data_window_start=sim_end - timedelta(days=30),
            data_window_end=sim_end,
            promoted_at=None,
            superseded_at=None,
            is_shadow=True,
            features={"cumulative_drift": 24.3, "process_names": {"chrome.exe": 10}},
            embedding=[0.0] * 128,
            embedding_model_id="alter-ego-ngram-v1",
            embedding_model_version="1.0",
            embedding_dimensionality=128,
            embedding_input_normalizer_version="1.0-char-3gram-hash-128",
        )
    )
    db_session.commit()

    shadow = ProfileStore(db_session).get_latest_shadow_profile(entity, as_of=event_as_of)
    assert shadow is not None, (
        "D4 as_of must resolve sim-time shadows; created_at wall-clock filter is wrong"
    )
    assert float(shadow.features["cumulative_drift"]) == pytest.approx(24.3)
