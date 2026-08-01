"""H14 Stage A — signal-family agreement count and containment gate."""

from datetime import datetime, timedelta

import pytest
import yaml
from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker

from core.database import Base
from core.models import ProfileArtifactModel
from core.schemas.decisions import FeatureContribution
from core.schemas.events import ResolvedEvent
from worker.profile_store import ProfileStore
from worker.scorer import (
    _containment_eligible,
    compute_signal_family_agreement,
    load_scoring_config,
    score_event,
)


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


def _contrib(name, score):
    return FeatureContribution(
        contribution_id="x",
        feature_name=name,
        raw_value=score,
        contribution_score=score,
        confidence_weight=0.9,
    )


def _profile(
    *,
    version,
    entity_id,
    drift,
    is_shadow,
    promoted_at,
    created_at,
    data_window_end,
):
    return ProfileArtifactModel(
        profile_version=version,
        entity_id=entity_id,
        entity_type="human",
        created_at=created_at,
        data_window_start=data_window_end - timedelta(days=30),
        data_window_end=data_window_end,
        promoted_at=promoted_at,
        superseded_at=None,
        is_shadow=is_shadow,
        features={
            "total_events": 100,
            "login_hours": {str(h): 4 for h in range(24)},
            "geolocations": {"US": 100},
            "endpoints": {"ep-a": 100},
            "process_names": {"chrome.exe": 100},
            "role": "engineer",
            "cohort_data": {},
            "cumulative_drift": drift,
        },
        embedding=[0.1] * 128,
        embedding_model_id="alter-ego-ngram-v1",
        embedding_model_version="1.0",
        embedding_dimensionality=128,
        embedding_input_normalizer_version="1.0-char-3gram-hash-128",
    )


def test_single_family_agreement_counts_one():
    contribs = [
        _contrib("login_hour_rarity", 20.0),
        _contrib("geolocation_rarity", 0.0),
        _contrib("endpoint_set_rarity", 0.0),
        _contrib("process_name_rarity", 0.0),
        _contrib("drift_alert", 0.0),
        _contrib("total_volume_delta", 0.0),
    ]
    count = compute_signal_family_agreement(contribs, family_floor_fraction=0.1, max_contrib=50.0)
    assert count == 1


def test_two_families_agreement_counts_two():
    contribs = [
        _contrib("login_hour_rarity", 20.0),
        _contrib("drift_alert", 30.0),
        _contrib("total_volume_delta", 0.0),
    ]
    count = compute_signal_family_agreement(contribs, family_floor_fraction=0.1, max_contrib=50.0)
    assert count == 2


def test_below_floor_does_not_count():
    contribs = [_contrib("login_hour_rarity", 1.0), _contrib("drift_alert", 1.0)]
    count = compute_signal_family_agreement(contribs, family_floor_fraction=0.5, max_contrib=50.0)
    assert count == 0


def test_single_family_high_score_queues_when_gate_disabled():
    should_queue, deferred = _containment_eligible(
        total_score=90.0,
        decision_confidence=0.9,
        signal_family_agreement_count=1,
        containment_threshold=85.0,
        confidence_floor=0.6,
        precision_gate_active=False,
        containment_min_agreement=2,
    )
    assert should_queue is True
    assert deferred is False


def test_single_family_high_score_deferred_when_gate_enabled():
    should_queue, deferred = _containment_eligible(
        total_score=90.0,
        decision_confidence=0.9,
        signal_family_agreement_count=1,
        containment_threshold=85.0,
        confidence_floor=0.6,
        precision_gate_active=True,
        containment_min_agreement=2,
    )
    assert should_queue is False
    assert deferred is True


def test_two_family_agreement_queues_when_gate_enabled():
    should_queue, deferred = _containment_eligible(
        total_score=90.0,
        decision_confidence=0.9,
        signal_family_agreement_count=2,
        containment_threshold=85.0,
        confidence_floor=0.6,
        precision_gate_active=True,
        containment_min_agreement=2,
    )
    assert should_queue is True
    assert deferred is False


def test_below_threshold_never_queues_or_defers_regardless_of_gate():
    should_queue, deferred = _containment_eligible(
        total_score=50.0,
        decision_confidence=0.9,
        signal_family_agreement_count=1,
        containment_threshold=85.0,
        confidence_floor=0.6,
        precision_gate_active=True,
        containment_min_agreement=2,
    )
    assert should_queue is False
    assert deferred is False


def test_precision_gate_disabled_does_not_change_containment_flag(db_session):
    """enabled: false (shipped default): agreement_count is computed and stored,
    but simulated_containment_queued fires exactly as before Phase 5."""
    entity_id = "user_containment_default"
    as_of = datetime(2024, 6, 15, 12, 0, 0)
    db_session.add(
        _profile(
            version="promoted_containment_v1",
            entity_id=entity_id,
            drift=2.5,
            is_shadow=False,
            promoted_at=as_of - timedelta(days=5),
            created_at=as_of - timedelta(days=5),
            data_window_end=as_of - timedelta(days=5),
        )
    )
    db_session.commit()

    config = load_scoring_config()
    config = {**config, "containment_threshold": 50.0}

    promoted = ProfileStore(db_session).get_active_profile(entity_id, as_of)
    event = ResolvedEvent(
        event_id="evt_containment_default",
        timestamp=as_of,
        event_type="process",
        raw_entity_id=entity_id,
        entity_id=entity_id,
        entity_type="human",
        resolution_confidence=1.0,
        simulation_partition="production",
        event_data={
            "process_name": "chrome.exe",
            "endpoint_id": "ep-a",
            "geolocation": "US",
            "command_line": "chrome.exe --silent",
        },
    )
    decision = score_event(db_session, event, promoted, config)
    assert decision.signal_family_agreement_count == 1
    assert "simulated_containment_queued" in decision.flags


def test_score_event_defers_containment_flag_when_gate_enabled_and_single_family(db_session):
    """Wiring smoke test: score_event actually calls _containment_eligible with real
    signal_family_agreement_count, not just the unit-tested function in isolation."""
    import copy

    entity_id = "user_containment_smoke"
    as_of = datetime(2024, 6, 15, 12, 0, 0)
    db_session.add(
        _profile(
            version="promoted_containment_v1",
            entity_id=entity_id,
            drift=4.9,
            is_shadow=False,
            promoted_at=as_of - timedelta(days=5),
            created_at=as_of - timedelta(days=5),
            data_window_end=as_of - timedelta(days=5),
        )
    )
    db_session.commit()

    with open("config/scoring_config.yaml") as f:
        config = yaml.safe_load(f)
    enabled_config = copy.deepcopy(config)
    enabled_config["precision_gate"]["enabled"] = True

    promoted = ProfileStore(db_session).get_active_profile(entity_id, as_of)
    event = ResolvedEvent(
        event_id="evt_containment_smoke",
        timestamp=as_of,
        event_type="process",
        raw_entity_id=entity_id,
        entity_id=entity_id,
        entity_type="human",
        resolution_confidence=1.0,
        simulation_partition="production",
        event_data={
            "process_name": "chrome.exe",
            "endpoint_id": "ep-a",
            "geolocation": "US",
            "command_line": "chrome.exe --silent",
        },
    )
    decision = score_event(db_session, event, promoted, enabled_config)
    assert isinstance(decision.signal_family_agreement_count, int)
    assert "simulated_containment_queued" not in decision.flags
    assert "containment_deferred_single_family" not in decision.flags
