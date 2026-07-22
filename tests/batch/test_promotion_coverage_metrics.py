"""Unit tests for Series D dual promotion_coverage metrics (SD4)."""
from __future__ import annotations

from datetime import date, datetime, time, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker

from core.database import Base
from core.models import DecisionRecordModel, ProfileArtifactModel
from scratch.run_series_d_sweep import (
    IN_WINDOW_STALENESS_DAYS,
    promotion_coverage_ever,
    promotion_coverage_in_window,
)
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


def _add_profile(
    db,
    *,
    entity_id: str,
    version: str,
    data_window_end: datetime,
    promoted_at: datetime | None = None,
    is_shadow: bool = False,
    superseded_at: datetime | None = None,
    created_at: datetime | None = None,
) -> ProfileArtifactModel:
    profile = ProfileArtifactModel(
        profile_version=version,
        entity_id=entity_id,
        entity_type="user",
        created_at=created_at or datetime(2026, 1, 1, 12, 0, 0),
        data_window_start=data_window_end - timedelta(days=7),
        data_window_end=data_window_end,
        promoted_at=promoted_at,
        superseded_at=superseded_at,
        is_shadow=is_shadow,
        features={},
    )
    db.add(profile)
    db.commit()
    return profile


def _add_decision(db, *, entity_id: str, score_day: date, suffix: str = "") -> None:
    ts = datetime.combine(score_day, time(12, 0, 0))
    decision_id = f"d-{entity_id}-{score_day.isoformat()}{suffix}"
    db.add(
        DecisionRecordModel(
            decision_id=decision_id,
            event_id=f"e-{decision_id}",
            entity_id=entity_id,
            timestamp=ts,
            score=10.0,
            confidence=0.9,
            profile_version="v1",
            scoring_config_version="2.2",
            contributions=[],
            is_anomaly=False,
            cohort_used="global",
            cohort_unsupported=False,
            embedding_model_version="v1",
            flags={},
        )
    )
    db.commit()


def test_ever_one_while_in_window_below_one_frozen_profile(db_session):
    """Series C counterexample shape: ever-promoted but stale through attack window."""
    entity_id = "user_frozen"
    promoted_at = datetime(2026, 1, 1, 0, 0, 0)
    _add_profile(
        db_session,
        entity_id=entity_id,
        version="v1",
        data_window_end=promoted_at,
        promoted_at=promoted_at,
    )
    for day in (date(2026, 1, 10), date(2026, 1, 11), date(2026, 1, 12)):
        _add_decision(db_session, entity_id=entity_id, score_day=day)

    ever = promotion_coverage_ever(db_session)
    in_window = promotion_coverage_in_window(db_session)

    assert ever["fraction"] == 1.0
    assert ever["entities_with_active_promoted_profile"] == 1
    assert in_window["fraction"] == 0.0
    assert in_window["stale_entity_days"] == 3
    assert in_window["serving_profile_missing_days"] == 0


def test_in_window_n5_boundary_day_five_fresh_day_six_stale(db_session):
    """N=5: day exactly 5 stale → fresh; day 6 → stale."""
    entity_id = "user_boundary"
    anchor = datetime(2026, 1, 1, 0, 0, 0)
    _add_profile(
        db_session,
        entity_id=entity_id,
        version="v1",
        data_window_end=anchor,
        promoted_at=anchor,
    )
    _add_decision(db_session, entity_id=entity_id, score_day=date(2026, 1, 6))
    _add_decision(db_session, entity_id=entity_id, score_day=date(2026, 1, 7))

    in_window = promotion_coverage_in_window(db_session, n_days=IN_WINDOW_STALENESS_DAYS)

    assert in_window["in_window_entity_days"] == 1
    assert in_window["stale_entity_days"] == 1
    assert in_window["fraction"] == 0.5


def test_sim_promoted_at_axis_smoke(db_session):
    """Sim ``promoted_at`` + sim score day → serving profile found (not missing)."""
    entity_id = "user_sim_axis"
    sim_day = datetime(2026, 1, 5, 0, 0, 0)
    _add_profile(
        db_session,
        entity_id=entity_id,
        version="v1",
        data_window_end=sim_day,
        promoted_at=sim_day,
        created_at=datetime(2030, 6, 1, 12, 0, 0),
    )
    _add_decision(db_session, entity_id=entity_id, score_day=sim_day.date())

    store = ProfileStore(db_session)
    assert store.get_active_profile(entity_id, sim_day + timedelta(hours=12)) is not None

    in_window = promotion_coverage_in_window(db_session)
    assert in_window["serving_profile_missing_days"] == 0
    assert in_window["fraction"] == 1.0


def test_wall_promoted_at_trap_counts_missing_not_stale(db_session):
    """Wall-only ``promoted_at`` with sim score days → missing, not silent stale."""
    entity_id = "user_wall_trap"
    sim_data_end = datetime(2026, 1, 1, 0, 0, 0)
    wall_promoted = datetime(2030, 1, 1, 0, 0, 0)
    _add_profile(
        db_session,
        entity_id=entity_id,
        version="v1",
        data_window_end=sim_data_end,
        promoted_at=wall_promoted,
    )
    _add_decision(db_session, entity_id=entity_id, score_day=date(2026, 1, 5))

    in_window = promotion_coverage_in_window(db_session)

    assert in_window["serving_profile_missing_days"] == 1
    assert in_window["stale_entity_days"] == 0
    assert in_window["fraction"] == 0.0
