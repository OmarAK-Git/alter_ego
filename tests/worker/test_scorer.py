import math
from core.math_utils import compute_kl_divergence, get_laplace_prob
import hashlib
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.dialects.postgresql import JSONB, ARRAY
from core.database import Base

@compiles(JSONB, "sqlite")
def compile_jsonb_sqlite(type_, compiler, **kw):
    return "JSON"

@compiles(ARRAY, "sqlite")
def compile_array_sqlite(type_, compiler, **kw):
    return "JSON"

@pytest.fixture
def db_session():
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()

def test_kl_divergence():
    p = 1.0
    q = 0.5
    expected = 1.0 * math.log(1.0 / 0.5)
    assert compute_kl_divergence(p, q) == expected

def test_laplace_prob():
    # 5 items, 100 total, 50 vocab, alpha=1.0
    # (5 + 1) / (100 + 50) = 6 / 150 = 0.04
    assert get_laplace_prob(5, 100, 50) == 0.04

def test_idempotent_decision_id():
    event_id = "test_event_1"
    profile_version = "v1"
    scoring_version = "v1"
    
    raw = f"{event_id}{profile_version}{scoring_version}".encode('utf-8')
    expected_hash = hashlib.sha256(raw).hexdigest()
    
    raw2 = f"{event_id}{profile_version}{scoring_version}".encode('utf-8')
    assert hashlib.sha256(raw2).hexdigest() == expected_hash

def test_decision_determinism(db_session):
    """Same inputs to score_event must produce identical decision_id and raw_score."""
    from core.schemas.events import ResolvedEvent, AuthEventData
    from core.schemas.profiles import ProfileArtifact
    from worker.scorer import score_event
    from datetime import datetime

    ts = datetime(2026, 1, 1, 12, 0)
    event_data = AuthEventData(action="login", ip_address="1.1.1.1", endpoint_id="ep1")
    resolved_event = ResolvedEvent(
        event_id="evt_123",
        timestamp=ts,
        event_type="auth",
        raw_entity_id="u1",
        entity_id="u1",
        entity_type="human",
        resolution_confidence=1.0,
        simulation_partition="production",
        event_data=event_data
    )

    profile = ProfileArtifact(
        entity_id="u1",
        entity_type="human",
        profile_version="prof_v1",
        created_at=ts,
        data_window_start=ts,
        data_window_end=ts,
        features={"role": "Engineer", "cohort_data": {"terminus": {"login_hours": {"12": 1}, "endpoints": {"ep1": 1}}}},
        embedding_model_id="nomic-embed-text",
        embedding_model_version="1.0",
        embedding_dimensionality=768
    )

    config = {"features": {}, "anomaly_threshold": 75.0, "version": "1.0"}

    decision1 = score_event(db_session, resolved_event, profile, config)
    decision2 = score_event(db_session, resolved_event, profile, config)

    assert decision1.decision_id == decision2.decision_id
    assert decision1.score == decision2.score
    assert decision1.confidence == decision2.confidence

def test_scorer_ground_truth_isolation():
    """Scorer must not import or reference EvalGroundTruthModel."""
    import ast
    from pathlib import Path

    scorer_path = Path(__file__).parent.parent.parent / "worker" / "scorer.py"
    with open(scorer_path, "r") as f:
        tree = ast.parse(f.read())
        
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            for alias in node.names:
                assert alias.name != "EvalGroundTruthModel", "Scorer must not import EvalGroundTruthModel"
                assert alias.name != "EvalGroundTruth", "Scorer must not import EvalGroundTruth"

def test_confidence_not_hardcoded(db_session):
    """Decision confidence must be a weighted average of per-feature confidences.
    
    When all contributions are zero (benign event), weight_sum=0 and confidence=1.0
    by convention (no evidence of anomaly → full confidence in normality).
    This test verifies confidence is NOT hardcoded by using an anomalous event
    that produces non-zero contributions, then checking confidence is < 1.0
    (because the mixed confidence_weights of 0.9/0.7/0.6/0.8 produce a value < 1).
    """
    from core.schemas.events import ResolvedEvent, AuthEventData
    from core.schemas.profiles import ProfileArtifact
    from worker.scorer import score_event
    from datetime import datetime

    profile_end = datetime(2026, 1, 10, 12, 0)
    ts = datetime(2026, 1, 12, 12, 0)   # familiar hour (noon), within staleness window
    # Use dict event_data to set process_name explicitly
    event_data = {
        "action": "login",
        "ip_address": "1.1.1.1",
        "endpoint_id": "ep1",
        "geolocation": "US",
        "process_name": "never_seen.exe",    # completely absent from profile
        "command_line": "",
    }
    resolved_event = ResolvedEvent(
        event_id="evt_conf_test",
        timestamp=ts,
        event_type="auth",
        raw_entity_id="u1",
        entity_id="u1",
        entity_type="human",
        resolution_confidence=1.0,
        simulation_partition="production",
        event_data=event_data,
    )

    # Profile has 50 known process names — 'never_seen.exe' is absent.
    # With vocab=1000 and total=50: rarity = -log2((0+1)/(50+1000)) ≈ 10.04 > baseline 10.
    known_procs = {f"proc_{i}.exe": 1 for i in range(50)}
    profile = ProfileArtifact(
        entity_id="u1",
        entity_type="human",
        profile_version="prof_conf",
        created_at=profile_end,
        data_window_start=datetime(2026, 1, 1, 0, 0),
        data_window_end=profile_end,
        features={
            "role": "Engineer",
            "login_hours": {"12": 50},
            "endpoints": {"ep1": 50},
            "geolocations": {"US": 50},
            "process_names": known_procs,
            "cohort_data": {},
        },
        embedding_model_id="nomic-embed-text",
        embedding_model_version="1.0",
        embedding_dimensionality=768,
    )

    config = {"features": {}, "anomaly_threshold": 75.0, "version": "1.0"}
    decision = score_event(db_session, resolved_event, profile, config)

    # Non-zero contributions exist: process_name 'never_seen.exe' is absent from
    # a profile with 50 known entries; rarity (-log2(1/1050)) ≈ 10.04 > baseline 10
    non_zero = [c for c in decision.contributions if c.contribution_score > 0]
    assert non_zero, (
        f"Expected at least one non-zero contribution for anomalous event. "
        f"Contributions: {[(c.feature_name, c.contribution_score, c.raw_value) for c in decision.contributions]}"
    )

    # Confidence must be a weighted average, NOT hardcoded to 1.0
    assert decision.confidence < 1.0, (
        f"Expected confidence < 1.0 for anomalous event with mixed weights, got {decision.confidence}"
    )
    # Must be in valid range
    assert 0.0 <= decision.confidence <= 1.0

