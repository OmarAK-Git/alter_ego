"""S5.9 — embedding/schema metadata mismatch detection at scorer."""

from datetime import datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker

from core.database import Base
from core.models import ProfileArtifactModel
from core.schemas.events import AuthEventData, ResolvedEvent
from core.schemas.profiles import (
    DEFAULT_EMBEDDING_DIMENSIONALITY,
    DEFAULT_EMBEDDING_MODEL_ID,
    DEFAULT_EMBEDDING_MODEL_VERSION,
    ProfileArtifact,
)
from worker.scorer import (
    EMBEDDING_METADATA_MISMATCH_FLAG,
    RUNTIME_EMBEDDING_INPUT_NORMALIZER_VERSION,
    check_profile_embedding_metadata,
    find_active_profiles_with_embedding_mismatch,
    score_event,
)
from worker.vectorizer import NORMALIZER_VERSION


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


def _compatible_profile(**overrides) -> ProfileArtifact:
    ts = datetime(2026, 1, 1, 12, 0)
    base = {
        "entity_id": "u1",
        "entity_type": "human",
        "profile_version": "prof_v1",
        "created_at": ts,
        "data_window_start": ts,
        "data_window_end": ts,
        "features": {
            "role": "Engineer",
            "login_hours": {"12": 50},
            "cohort_data": {},
        },
        "embedding_model_id": DEFAULT_EMBEDDING_MODEL_ID,
        "embedding_model_version": DEFAULT_EMBEDDING_MODEL_VERSION,
        "embedding_dimensionality": DEFAULT_EMBEDDING_DIMENSIONALITY,
        "embedding_input_normalizer_version": RUNTIME_EMBEDDING_INPUT_NORMALIZER_VERSION,
    }
    base.update(overrides)
    return ProfileArtifact(**base)


def _resolved_event() -> ResolvedEvent:
    ts = datetime(2026, 1, 2, 12, 0)
    return ResolvedEvent(
        event_id="evt_embed_check",
        timestamp=ts,
        event_type="auth",
        raw_entity_id="u1",
        entity_id="u1",
        entity_type="human",
        resolution_confidence=1.0,
        simulation_partition="production",
        event_data=AuthEventData(action="login", ip_address="1.1.1.1", endpoint_id="ep1"),
    )


def test_check_profile_embedding_metadata_match():
    profile = _compatible_profile()
    assert check_profile_embedding_metadata(profile) == []


def test_check_profile_embedding_metadata_model_id_mismatch():
    profile = _compatible_profile(embedding_model_id="nomic-embed-text")
    mismatches = check_profile_embedding_metadata(profile)
    assert len(mismatches) == 1
    assert mismatches[0].field == "embedding_model_id"
    assert mismatches[0].profile_value == "nomic-embed-text"
    assert mismatches[0].runtime_value == DEFAULT_EMBEDDING_MODEL_ID


def test_check_profile_embedding_metadata_dimensionality_mismatch():
    profile = _compatible_profile(embedding_dimensionality=768)
    mismatches = check_profile_embedding_metadata(profile)
    assert any(m.field == "embedding_dimensionality" for m in mismatches)


def test_matching_metadata_allows_scoring(db_session):
    profile = _compatible_profile()
    config = {"features": {}, "version": "2.2", "anomaly_threshold": 75.0}
    decision = score_event(db_session, _resolved_event(), profile, config)

    assert EMBEDDING_METADATA_MISMATCH_FLAG not in decision.flags
    assert decision.score >= 0.0


def test_model_id_mismatch_halts_scoring(db_session):
    profile = _compatible_profile(embedding_model_id="nomic-embed-text")
    config = {"features": {}, "version": "2.2"}
    decision = score_event(db_session, _resolved_event(), profile, config)

    assert decision.score == 0.0
    assert decision.is_anomaly is False
    assert decision.contributions == []
    assert EMBEDDING_METADATA_MISMATCH_FLAG in decision.flags
    assert any("embedding_mismatch_embedding_model_id" in f for f in decision.flags)


def test_normalizer_version_mismatch_halts_scoring(db_session):
    profile = _compatible_profile(embedding_input_normalizer_version="1.0")
    config = {"features": {}, "version": "2.2"}
    decision = score_event(db_session, _resolved_event(), profile, config)

    assert decision.score == 0.0
    assert EMBEDDING_METADATA_MISMATCH_FLAG in decision.flags


def test_find_active_profiles_with_embedding_mismatch(db_session):
    ts = datetime(2026, 1, 1, 12, 0)
    db_session.add(
        ProfileArtifactModel(
            profile_version="prof_bad",
            entity_id="u_bad",
            entity_type="human",
            created_at=ts,
            data_window_start=ts,
            data_window_end=ts,
            promoted_at=ts,
            superseded_at=None,
            is_shadow=False,
            features={"role": "Engineer"},
            embedding_model_id="nomic-embed-text",
            embedding_model_version="1.0",
            embedding_dimensionality=128,
            embedding_input_normalizer_version=NORMALIZER_VERSION,
        )
    )
    db_session.add(
        ProfileArtifactModel(
            profile_version="prof_good",
            entity_id="u_good",
            entity_type="human",
            created_at=ts,
            data_window_start=ts,
            data_window_end=ts,
            promoted_at=ts,
            superseded_at=None,
            is_shadow=False,
            features={"role": "Engineer"},
            embedding_model_id=DEFAULT_EMBEDDING_MODEL_ID,
            embedding_model_version=DEFAULT_EMBEDDING_MODEL_VERSION,
            embedding_dimensionality=DEFAULT_EMBEDDING_DIMENSIONALITY,
            embedding_input_normalizer_version=NORMALIZER_VERSION,
        )
    )
    db_session.commit()

    affected = find_active_profiles_with_embedding_mismatch(db_session)
    entity_ids = {entity_id for entity_id, _ in affected}
    assert entity_ids == {"u_bad"}
