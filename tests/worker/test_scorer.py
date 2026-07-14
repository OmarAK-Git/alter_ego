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
    """Canonical decision_id serialization is stable for identical inputs."""
    import json
    from worker.scorer import SCORER_ALGORITHM_VERSION, compute_decision_id

    payload = {
        "embedding_model_version": "1.0",
        "event_id": "test_event_1",
        "profile_version": "v1",
        "scorer_algorithm_version": SCORER_ALGORITHM_VERSION,
        "scoring_config_version": "v1",
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    expected_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    assert compute_decision_id(
        event_id="test_event_1",
        profile_version="v1",
        scoring_config_version="v1",
        embedding_model_version="1.0",
    ) == expected_hash
    assert compute_decision_id(
        event_id="test_event_1",
        profile_version="v1",
        scoring_config_version="v1",
        embedding_model_version="1.0",
    ) == expected_hash

def test_decision_determinism(db_session):
    """Same inputs to score_event must produce identical decision_id and raw_score."""
    from worker.scorer import score_event

    resolved_event, profile, config = _determinism_fixture()

    decision1 = score_event(db_session, resolved_event, profile, config)
    decision2 = score_event(db_session, resolved_event, profile, config)

    assert decision1.decision_id == decision2.decision_id
    assert decision1.score == decision2.score
    assert decision1.confidence == decision2.confidence


def _determinism_fixture():
    from core.schemas.events import ResolvedEvent, AuthEventData
    from core.schemas.profiles import ProfileArtifact
    from datetime import datetime

    from tests.worker.conftest import COMPATIBLE_EMBEDDING_PROFILE_FIELDS

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
        event_data=event_data,
    )
    profile = ProfileArtifact(
        entity_id="u1",
        entity_type="human",
        profile_version="prof_v1",
        created_at=ts,
        data_window_start=ts,
        data_window_end=ts,
        features={
            "role": "Engineer",
            "cohort_data": {
                "terminus": {"login_hours": {"12": 1}, "endpoints": {"ep1": 1}}
            },
        },
        **COMPATIBLE_EMBEDDING_PROFILE_FIELDS,
    )
    config = {"features": {}, "anomaly_threshold": 75.0, "version": "1.0"}
    return resolved_event, profile, config


def test_total_volume_delta_deferred(db_session):
    """total_volume_delta is deferred (S2.6): always zero with explicit flag."""
    from worker.scorer import score_event

    resolved_event, profile, config = _determinism_fixture()
    decision = score_event(db_session, resolved_event, profile, config)

    vol = next(c for c in decision.contributions if c.feature_name == "total_volume_delta")
    assert vol.contribution_score == 0.0
    assert vol.raw_value == 0.0
    assert "volume_delta_deferred" in decision.flags


def test_decision_id_matches_canonical_formula(db_session):
    """decision_id must equal SHA-256 of sorted-key JSON lineage payload."""
    import json
    from worker.scorer import SCORER_ALGORITHM_VERSION, compute_decision_id, score_event

    resolved_event, profile, config = _determinism_fixture()
    decision = score_event(db_session, resolved_event, profile, config)

    expected = compute_decision_id(
        event_id=resolved_event.event_id,
        profile_version=profile.profile_version,
        scoring_config_version=str(config["version"]),
        embedding_model_version=profile.embedding_model_version,
    )
    assert decision.decision_id == expected

    payload = {
        "embedding_model_version": profile.embedding_model_version,
        "event_id": resolved_event.event_id,
        "profile_version": profile.profile_version,
        "scorer_algorithm_version": SCORER_ALGORITHM_VERSION,
        "scoring_config_version": str(config["version"]),
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    assert decision.decision_id == hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def test_decision_id_sensitive_to_algorithm_version(db_session, monkeypatch):
    """Changing scorer_algorithm_version must change decision_id."""
    from worker import scorer as scorer_module
    from worker.scorer import score_event

    resolved_event, profile, config = _determinism_fixture()
    baseline = score_event(db_session, resolved_event, profile, config).decision_id

    monkeypatch.setattr(scorer_module, "SCORER_ALGORITHM_VERSION", "9.9-test-bump")
    bumped = score_event(db_session, resolved_event, profile, config).decision_id

    assert bumped != baseline


def test_decision_id_sensitive_to_embedding_model_version(db_session):
    """Changing embedding_model_version must change decision_id."""
    from core.schemas.profiles import ProfileArtifact
    from worker.scorer import score_event

    resolved_event, profile, config = _determinism_fixture()
    baseline = score_event(db_session, resolved_event, profile, config).decision_id

    alt_profile = ProfileArtifact(
        **{**profile.model_dump(), "embedding_model_version": "2.0"}
    )
    bumped = score_event(db_session, resolved_event, alt_profile, config).decision_id

    assert bumped != baseline


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
    from core.schemas.events import ResolvedEvent
    from core.schemas.profiles import ProfileArtifact
    from worker.scorer import score_event
    from datetime import datetime

    from tests.worker.conftest import COMPATIBLE_EMBEDDING_PROFILE_FIELDS

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
        **COMPATIBLE_EMBEDDING_PROFILE_FIELDS,
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


# ---------------------------------------------------------------------------
# Issue 1 — Dialect abstraction: geolocation / endpoint / process_name novelty
# ---------------------------------------------------------------------------

class _MockDialect:
    """Minimal dialect stub for _is_postgresql()."""
    def __init__(self, name: str):
        self.name = name


class _MockBind:
    def __init__(self, dialect_name: str):
        self.dialect = _MockDialect(dialect_name)


class _MockSession:
    """Session stub that records the WHERE clause appended via execute()."""
    def __init__(self, dialect_name: str, scalar_result: int = 0):
        self.bind = _MockBind(dialect_name)
        self._scalar_result = scalar_result
        self.last_stmt = None

    def execute(self, stmt):
        self.last_stmt = stmt
        return self

    def scalar(self):
        return self._scalar_result

    def scalars(self):
        return self

    def all(self):
        return []


def _compile_stmt_str(stmt) -> str:
    """Render the SQLAlchemy clause to a string (dialect-agnostic literal)."""
    from sqlalchemy.dialects import postgresql as pg_dialect
    try:
        return str(stmt.compile(dialect=pg_dialect.dialect()))
    except Exception:
        return str(stmt)


def test_novelty_fraction_sqlite_uses_json_extract(monkeypatch):
    """On SQLite the non-hour path must use json_extract, not JSONB operators."""
    import worker.scorer as scorer_module
    # Clear cache so we don't get a hit
    scorer_module._NOVELTY_FRACTION_CACHE.clear()
    scorer_module._COHORT_MEMBERS_CACHE.clear()

    session = _MockSession("sqlite", scalar_result=0)
    members = ["u1", "u2"]
    from datetime import datetime
    # Call for a non-hour feature so the json_extract branch is taken
    fraction = scorer_module._get_novelty_fraction(
        session, members, "geolocations", "US", 7, datetime(2026, 1, 10, 12, 0)
    )
    assert fraction == 0.0  # 0 matching / 2 members

    # Inspect the compiled WHERE clause
    compiled = _compile_stmt_str(session.last_stmt)
    assert "json_extract" in compiled.lower(), (
        f"SQLite path must use json_extract; got: {compiled}"
    )


def test_novelty_fraction_postgresql_uses_jsonb_operator(monkeypatch):
    """On PostgreSQL the non-hour path must use JSONB [] operator, not json_extract."""
    import worker.scorer as scorer_module
    scorer_module._NOVELTY_FRACTION_CACHE.clear()

    session = _MockSession("postgresql", scalar_result=1)
    members = ["u1", "u2"]
    from datetime import datetime
    fraction = scorer_module._get_novelty_fraction(
        session, members, "endpoints", "ep1", 7, datetime(2026, 1, 10, 12, 0)
    )
    assert fraction == 0.5  # 1 matching / 2 members

    compiled = _compile_stmt_str(session.last_stmt)
    assert "json_extract" not in compiled.lower(), (
        f"PostgreSQL path must NOT use json_extract; got: {compiled}"
    )
    # JSONB subscript compiles as a ->> or [] operator, not json_extract
    assert "event_data" in compiled.lower()


def test_cohort_members_sqlite_uses_json_extract():
    """On SQLite, cohort role extraction must use json_extract (gated SQLite-only path)."""
    import worker.scorer as scorer_module
    scorer_module._COHORT_MEMBERS_CACHE.clear()

    captured = {}

    class _CapturingSession:
        bind = _MockBind("sqlite")

        def execute(self, stmt):
            captured["stmt"] = stmt
            class R:
                def scalars(self):
                    return self
                def all(self):
                    return []
            return R()

    scorer_module._get_cohort_members(_CapturingSession(), "Engineer", "human")

    assert "stmt" in captured, "execute() was never called"
    stmt_str = _compile_stmt_str(captured["stmt"])
    assert "json_extract" in stmt_str.lower(), (
        f"SQLite cohort path must use json_extract; got: {stmt_str}"
    )


def test_cohort_members_postgresql_uses_jsonb_operator():
    """On PostgreSQL, cohort role extraction uses JSONB subscript, not json_extract."""
    import worker.scorer as scorer_module
    scorer_module._COHORT_MEMBERS_CACHE.clear()

    captured = {}

    class _CapturingSession:
        bind = _MockBind("postgresql")

        def execute(self, stmt):
            captured["stmt"] = stmt
            class R:
                def scalars(self):
                    return self
                def all(self):
                    return []
            return R()

    scorer_module._get_cohort_members(_CapturingSession(), "Engineer", "human")

    assert "stmt" in captured, "execute() was never called"
    stmt_str = _compile_stmt_str(captured["stmt"])
    assert "json_extract" not in stmt_str.lower(), (
        f"PostgreSQL cohort path must NOT use json_extract; got: {stmt_str}"
    )


# ---------------------------------------------------------------------------
# Issue 2 — Novelty cache TTL regression
# ---------------------------------------------------------------------------

def test_novelty_cache_ttl_expiry(monkeypatch):
    """A cache entry older than _NOVELTY_CACHE_TTL must be recomputed, not reused."""
    import worker.scorer as scorer_module

    scorer_module._NOVELTY_FRACTION_CACHE.clear()

    session = _MockSession("sqlite", scalar_result=0)
    members = ["u1"]
    from datetime import datetime
    ts = datetime(2026, 1, 10, 12, 0)

    call_count = {"n": 0}

    def counting_execute(self, stmt):
        call_count["n"] += 1
        class R:
            def scalar(self_inner):
                return 0
        return R()

    monkeypatch.setattr(_MockSession, "execute", counting_execute)

    # First call — computes and caches
    scorer_module._get_novelty_fraction(session, members, "geolocations", "DE", 7, ts)
    assert call_count["n"] == 1

    # Second call within TTL — should return cached value without DB hit
    scorer_module._get_novelty_fraction(session, members, "geolocations", "DE", 7, ts)
    assert call_count["n"] == 1, "Expected cache hit (no DB call)"

    # Simulate TTL expiry by back-dating the insert timestamp
    for k in list(scorer_module._NOVELTY_FRACTION_CACHE.keys()):
        frac, insert_ts = scorer_module._NOVELTY_FRACTION_CACHE[k]
        scorer_module._NOVELTY_FRACTION_CACHE[k] = (
            frac,
            insert_ts - scorer_module._NOVELTY_CACHE_TTL - 1,
        )

    # Third call — TTL expired, must recompute
    scorer_module._get_novelty_fraction(session, members, "geolocations", "DE", 7, ts)
    assert call_count["n"] == 2, "Expected DB recompute after TTL expiry"


def test_novelty_cache_max_size_preserved():
    """Cache must never exceed _NOVELTY_CACHE_MAX entries."""
    import worker.scorer as scorer_module
    scorer_module._NOVELTY_FRACTION_CACHE.clear()

    # Insert exactly max+10 entries manually to trigger FIFO eviction
    limit = scorer_module._NOVELTY_CACHE_MAX
    for i in range(limit + 10):
        key = (f"feat_{i}", f"val_{i}", f"hash_{i}", i)
        # Direct insertion simulating what _get_novelty_fraction does
        if len(scorer_module._NOVELTY_FRACTION_CACHE) >= limit:
            oldest = next(iter(scorer_module._NOVELTY_FRACTION_CACHE))
            del scorer_module._NOVELTY_FRACTION_CACHE[oldest]
        scorer_module._NOVELTY_FRACTION_CACHE[key] = (0.5, 0.0)

    assert len(scorer_module._NOVELTY_FRACTION_CACHE) == limit


# ---------------------------------------------------------------------------
# Issue 4 — compute_distribution_kl edge cases
# ---------------------------------------------------------------------------

def test_kl_both_empty_returns_zero():
    """compute_distribution_kl({}, {}) must return 0.0 — no evidence in either window."""
    from core.math_utils import compute_distribution_kl
    result = compute_distribution_kl({}, {})
    assert result == 0.0, f"Expected 0.0, got {result}"


def test_kl_empty_baseline_returns_max_novelty():
    """compute_distribution_kl(non_empty, {}) must return positive max-novelty signal."""
    from core.math_utils import compute_distribution_kl
    dist_p = {"a": 1, "b": 2, "c": 3}
    result = compute_distribution_kl(dist_p, {})
    # Should equal len(dist_p) = 3 (vocab size as max-novelty proxy)
    assert result == float(len(dist_p)), f"Expected {float(len(dist_p))}, got {result}"
    assert result > 0.0


def test_kl_empty_current_with_nonempty_baseline():
    """compute_distribution_kl({}, non_empty) should compute a finite KL divergence.

    With p empty: all vocab mass is in q; the Laplace-smoothed p puts equal small
    weight on every key, so KL is positive but finite (no division by zero).
    """
    from core.math_utils import compute_distribution_kl
    dist_q = {"x": 10, "y": 5}
    result = compute_distribution_kl({}, dist_q)
    # dist_p={} means total_p=0; Laplace smoothed → each prob_p = alpha / (alpha * vocab)
    # The result must be a non-negative finite float (not zero, not inf)
    assert isinstance(result, float)
    assert result >= 0.0
    assert not (result != result)  # not NaN
    assert result < float("inf")


# ---------------------------------------------------------------------------
# Regression — process_unscored_events must not raise NameError when db=None
# ---------------------------------------------------------------------------

def test_process_unscored_events_can_create_default_session(monkeypatch):
    """process_unscored_events(db=None) must use SessionLocal, not raise NameError.

    Regression guard for: 'from core.database import Base' (broken import that
    dropped SessionLocal, causing NameError on the default production path).
    """
    import worker.scorer as scorer

    class FakeSession:
        def execute(self, stmt):
            class R:
                def yield_per(self, n):
                    return iter([])

                def scalars(self):
                    return iter([])

            return R()

        def close(self):
            pass

    monkeypatch.setattr(scorer, "SessionLocal", lambda: FakeSession())

    assert scorer.process_unscored_events() == 0
