from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker

from core.database import Base
from core.models import DecisionRecordModel, ResolvedEventModel
from batch.profile_builder.builder import build_profiles


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


def _events_for(db, entity_id, role, start, process_names):
    for i, pname in enumerate(process_names):
        db.add(ResolvedEventModel(
            event_id=f"evt_{entity_id}_{int(start.timestamp())}_{i}", entity_id=entity_id, entity_type="human",
            event_type="process", raw_entity_id=entity_id,
            timestamp=start + timedelta(minutes=i),
            event_data={"process_name": pname, "endpoint_id": "ep-a", "geolocation": "US",
                        "command_line": pname, "role": role},
            resolution_confidence=1.0, simulation_partition="production",
        ))


def test_fleet_cohort_drift_disabled_by_default_emits_nothing(db_session):
    start = datetime(2026, 1, 1)
    for i in range(5):
        _events_for(db_session, f"user_engineer_{i}", "engineer", start, ["chrome.exe", "new_tool.exe", "new_tool.exe"])
    db_session.commit()

    build_profiles(db=db_session, as_of=start + timedelta(days=1))
    cohort_decisions = db_session.execute(
        select(DecisionRecordModel).where(DecisionRecordModel.event_id == "COHORT_DRIFT")
    ).scalars().all()
    assert len(cohort_decisions) == 0


def test_fleet_cohort_drift_fires_when_cohort_fraction_exceeds_max_changed_fraction(db_session):
    import yaml
    with open("config/scoring_config.yaml") as f:
        config = yaml.safe_load(f)
    config["cohort_gating_constants"]["fleet_drift_enabled"] = True

    start = datetime(2026, 1, 1)
    # Pad cohort: stable finance users keep the global raw-drift median low.
    for i in range(10):
        for day in range(20):
            _events_for(
                db_session, f"user_finance_{i}", "finance",
                start + timedelta(days=day), ["excel.exe"],
            )
    # Baseline: all engineers use chrome.exe for 20 days to establish promoted profiles.
    for i in range(5):
        for day in range(20):
            _events_for(
                db_session, f"user_engineer_{i}", "engineer",
                start + timedelta(days=day), ["chrome.exe"],
            )
    db_session.commit()
    build_profiles(db=db_session, as_of=start + timedelta(days=19), config_override=config)

    # Coordinated shift: 4 of 5 engineers pick up new_tool.exe in the recent window.
    for i in range(4):
        for day in range(3):
            _events_for(
                db_session, f"user_engineer_{i}", "engineer",
                start + timedelta(days=20 + day), ["new_tool.exe"] * 5,
            )
    # user_engineer_4 stays on chrome.exe only
    db_session.commit()

    build_profiles(db=db_session, as_of=start + timedelta(days=22), config_override=config)
    cohort_decisions = db_session.execute(
        select(DecisionRecordModel).where(DecisionRecordModel.event_id == "COHORT_DRIFT")
    ).scalars().all()
    assert len(cohort_decisions) == 1
    assert cohort_decisions[0].contributions[0]["role"] == "engineer"


def test_fleet_cohort_drift_does_not_change_per_entity_cumulative_drift(db_session):
    """Identical accumulator values with fleet_drift_enabled on vs off for a fixed fixture."""
    import copy
    import yaml
    from core.models import ProfileArtifactModel

    with open("config/scoring_config.yaml") as f:
        base_config = yaml.safe_load(f)
    assert base_config["cohort_gating_constants"]["fleet_drift_enabled"] is False
    enabled_config = copy.deepcopy(base_config)
    enabled_config["cohort_gating_constants"]["fleet_drift_enabled"] = True

    start = datetime(2026, 1, 1)
    for i in range(4):
        _events_for(db_session, f"user_engineer_{i}", "engineer", start, ["new_tool.exe"] * 10)
    _events_for(db_session, "user_engineer_4", "engineer", start, ["chrome.exe"] * 10)
    db_session.commit()

    build_profiles(db=db_session, as_of=start + timedelta(days=1), config_override=base_config)
    baseline_drifts = {
        p.entity_id: p.features["cumulative_drift"]
        for p in db_session.query(ProfileArtifactModel).all()
    }

    db_session.query(ProfileArtifactModel).delete()
    db_session.commit()

    build_profiles(db=db_session, as_of=start + timedelta(days=1), config_override=enabled_config)
    enabled_drifts = {
        p.entity_id: p.features["cumulative_drift"]
        for p in db_session.query(ProfileArtifactModel).all()
    }

    assert baseline_drifts == enabled_drifts
