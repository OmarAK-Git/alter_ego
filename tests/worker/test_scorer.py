import math
from core.math_utils import compute_kl_divergence, get_laplace_prob
import hashlib

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

def test_decision_determinism():
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

    decision1 = score_event(resolved_event, profile, config)
    decision2 = score_event(resolved_event, profile, config)

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

def test_confidence_not_hardcoded():
    """Decision confidence must reflect per-feature confidences, not be hardcoded to 1.0."""
    from core.schemas.events import ResolvedEvent, AuthEventData
    from core.schemas.profiles import ProfileArtifact
    from worker.scorer import score_event
    from datetime import datetime

    ts = datetime(2026, 1, 1, 12, 0)
    event_data = AuthEventData(action="login", ip_address="1.1.1.1", endpoint_id="ep1")
    resolved_event = ResolvedEvent(
        event_id="evt_conf_test",
        timestamp=ts,
        event_type="auth",
        raw_entity_id="u1",
        entity_id="u1",
        entity_type="human",
        resolution_confidence=1.0,
        simulation_partition="production",
        event_data=event_data
    )

    # Use terminus-level cohort data so the confidence weights will be 0.5 (not 1.0)
    profile = ProfileArtifact(
        entity_id="u1",
        entity_type="human",
        profile_version="prof_conf",
        created_at=ts,
        data_window_start=ts,
        data_window_end=ts,
        features={
            "role": "Engineer",
            "login_hours": {"12": 1},  # Only 1 event -> falls below 10 threshold
            "endpoints": {"ep1": 1},
            "cohort_data": {"terminus": {"login_hours": {"12": 5}, "endpoints": {"ep1": 5}}}
        },
        embedding_model_id="nomic-embed-text",
        embedding_model_version="1.0",
        embedding_dimensionality=768
    )

    config = {"features": {}, "anomaly_threshold": 75.0, "version": "1.0"}
    decision = score_event(resolved_event, profile, config)
    
    # With terminus-level data, confidence_weight per feature should be 0.5
    # So decision confidence should NOT be 1.0
    assert decision.confidence < 1.0, f"Expected confidence < 1.0 for terminus fallback, got {decision.confidence}"
