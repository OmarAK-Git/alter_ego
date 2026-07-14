"""Evidence-binding: reconstruct decision score from feature contributions.

Invariant (worker/scorer.py):
    raw_total = Σ contribution_score_i

Each contribution_score already folds in feature weight, Laplace rarity
centering, capping (contribution_scale_max), and cohort-novelty suppression.
confidence_weight on FeatureContribution is metadata for decision confidence,
NOT multiplied into the score sum.

Decision score semantics:
    - Undamped: decision.score == raw_total == Σ contribution_score_i
    - Damped (decision.confidence < confidence_floor):
        decision.score == min(anomaly_threshold - 5, raw_total)
        flag "low_confidence_damping_applied" is set
"""

import pytest
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.dialects.postgresql import JSONB, ARRAY

from core.database import Base
from core.schemas.events import ResolvedEvent
from core.schemas.profiles import ProfileArtifact
from worker.scorer import score_event
from tests.worker.conftest import COMPATIBLE_EMBEDDING_PROFILE_FIELDS

TOLERANCE = 1e-6


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


def _reconstruct_raw_total(decision) -> float:
    return sum(c.contribution_score for c in decision.contributions)


def _base_config(*, anomaly_threshold: float) -> dict:
    return {
        "laplace_alpha": 0.0001,
        "features": {
            "login_hour_rarity": {"weight": 10.0},
            "geolocation_rarity": {"weight": 10.0},
            "endpoint_set_rarity": {"weight": 10.0},
            "process_name_rarity": {"weight": 10.0},
            "drift_alert": {"weight": 100.0},
        },
        "drift_threshold": 5.0,
        "anomaly_threshold": anomaly_threshold,
        "confidence_floor": 0.6,
        "confidence_k": 10.0,
        "version": "2.2",
    }


def _anomalous_profile_and_event(*, total_events: int):
    """Profile + event that produce multiple clearly non-zero rarity contributions."""
    profile_end = datetime(2026, 1, 10, 12, 0)
    ts = datetime(2026, 1, 12, 3, 0)  # hour absent from profile (only noon seen)
    known_procs = {f"proc_{i}.exe": 1 for i in range(50)}
    profile = ProfileArtifact(
        entity_id="u1",
        entity_type="human",
        profile_version="prof_evidence",
        created_at=profile_end,
        data_window_start=datetime(2026, 1, 1, 0, 0),
        data_window_end=profile_end,
        features={
            "role": "Engineer",
            "login_hours": {"12": 50},
            "endpoints": {"ep1": 50},
            "geolocations": {"US": 50},
            "process_names": known_procs,
            "total_events": total_events,
            "cumulative_drift": 3.0,
            "cohort_data": {},
        },
        **COMPATIBLE_EMBEDDING_PROFILE_FIELDS,
    )
    resolved_event = ResolvedEvent(
        event_id="evt_evidence_binding",
        timestamp=ts,
        event_type="auth",
        raw_entity_id="u1",
        entity_id="u1",
        entity_type="human",
        resolution_confidence=1.0,
        simulation_partition="production",
        event_data={
            "action": "login",
            "ip_address": "1.1.1.1",
            "endpoint_id": "ep_UNKNOWN",
            "geolocation": "XX",
            "process_name": "never_seen.exe",
            "command_line": "",
        },
    )
    return profile, resolved_event


def test_evidence_binding_reconstructs_raw_score_from_contributions(db_session):
    """Σ contribution_score_i must equal decision.score on the undamped path."""
    profile, resolved_event = _anomalous_profile_and_event(total_events=200)
    config = _base_config(anomaly_threshold=75.0)
    decision = score_event(db_session, resolved_event, profile, config)

    non_zero = [c for c in decision.contributions if c.contribution_score > 0]
    firing = {c.feature_name for c in non_zero}
    assert len(non_zero) >= 2
    assert {"login_hour_rarity", "geolocation_rarity", "endpoint_set_rarity"} <= firing, (
        f"Expected hour/geo/endpoint to contribute; got {[(c.feature_name, c.contribution_score) for c in decision.contributions]}"
    )

    reconstructed = _reconstruct_raw_total(decision)
    assert abs(reconstructed - decision.score) <= TOLERANCE, (
        f"reconstructed={reconstructed}, decision.score={decision.score}"
    )
    assert "low_confidence_damping_applied" not in decision.flags


def test_evidence_binding_damped_score_differs_from_contribution_sum(db_session):
    """When damping applies, score is capped below the contribution sum."""
    profile, resolved_event = _anomalous_profile_and_event(total_events=5)
    config = _base_config(anomaly_threshold=45.0)

    decision = score_event(db_session, resolved_event, profile, config)

    reconstructed = _reconstruct_raw_total(decision)
    cap = config["anomaly_threshold"] - 5.0

    assert reconstructed > cap, (
        f"Fixture must push raw_total above cap; sum={reconstructed}, cap={cap}"
    )
    assert "low_confidence_damping_applied" in decision.flags
    assert abs(decision.score - cap) <= TOLERANCE, (
        f"score={decision.score}, expected cap={cap}, raw_sum={reconstructed}"
    )
    assert abs(decision.score - reconstructed) > TOLERANCE, (
        f"Damping must reduce score below sum; score={decision.score}, sum={reconstructed}"
    )
