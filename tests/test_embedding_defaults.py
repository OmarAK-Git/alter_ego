"""S1.4 — profile/schema/ORM defaults align to shipping ngram embedding."""

from datetime import datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import sessionmaker

from batch.profile_builder.builder import build_profiles
from core.database import Base
from core.models import ProfileArtifactModel, ResolvedEventModel
from core.schemas.profiles import ProfileArtifact
from worker.vectorizer import NORMALIZER_VERSION

SHIPPING_MODEL_ID = "alter-ego-ngram-v1"
SHIPPING_DIMENSIONALITY = 128


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


def _minimal_profile_kwargs():
    ts = datetime(2026, 1, 1, 12, 0)
    return {
        "entity_id": "user_eng_alpha",
        "entity_type": "human",
        "profile_version": "prof_v1",
        "created_at": ts,
        "data_window_start": ts,
        "data_window_end": ts,
        "features": {"role": "eng", "total_events": 1, "cohort_data": {}},
    }


def test_profile_artifact_schema_defaults_to_ngram_model():
    profile = ProfileArtifact(**_minimal_profile_kwargs())
    assert profile.embedding_model_id == SHIPPING_MODEL_ID
    assert profile.embedding_dimensionality == SHIPPING_DIMENSIONALITY
    assert profile.embedding_model_version == "1.0"
    assert profile.embedding_input_normalizer_version == NORMALIZER_VERSION


def test_profile_artifact_model_orm_defaults_to_ngram_model(db_session):
    ts = datetime(2026, 1, 1, 12, 0)
    model = ProfileArtifactModel(
        profile_version="orm_default_v1",
        entity_id="user_eng_alpha",
        entity_type="human",
        data_window_start=ts,
        data_window_end=ts,
        features={"role": "eng"},
    )
    db_session.add(model)
    db_session.commit()
    db_session.refresh(model)

    assert model.embedding_model_id == SHIPPING_MODEL_ID
    assert model.embedding_dimensionality == SHIPPING_DIMENSIONALITY
    assert model.embedding_model_version == "1.0"
    assert model.embedding_input_normalizer_version == NORMALIZER_VERSION


def test_builder_promote_writes_ngram_embedding_metadata(db_session):
    entity_id = "user_eng_builder_meta"
    ts = datetime(2026, 1, 1, 10, 0, 0)

    db_session.add(
        ResolvedEventModel(
            event_id="evt_meta_1",
            timestamp=ts,
            event_type="login",
            raw_entity_id=entity_id,
            entity_id=entity_id,
            entity_type="human",
            resolution_confidence=1.0,
            simulation_partition="production",
            event_data={
                "action": "login",
                "endpoint_id": "endpoint_a",
                "process_name": "bash",
                "command_line": "powershell.exe -enc payload",
                "geolocation": "US-East",
            },
        )
    )
    db_session.commit()

    build_profiles(db_session, as_of=ts)

    profile = (
        db_session.query(ProfileArtifactModel)
        .filter(ProfileArtifactModel.entity_id == entity_id)
        .one()
    )
    assert profile.embedding_model_id == SHIPPING_MODEL_ID
    assert profile.embedding_dimensionality == SHIPPING_DIMENSIONALITY
    assert profile.embedding_model_version == "1.0"
    assert profile.embedding_input_normalizer_version == NORMALIZER_VERSION
