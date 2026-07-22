"""S55.6 — invariants C1–C3 + Design 1F (FP-storm deadlock companion).

Series C full sweep is deferred; these are focused fixture proofs.
C2 (no sanctuary) lives in tests/worker/test_shadow_drift_under_block.py.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker

from batch.profile_builder.builder import ACTIVE_ALERT_STATES, build_profiles
from core.attestation import ALPHA_ANCHOR, ALPHA_PROD, ANCHOR_HISTORY_COUNT, novel_mass
from core.database import Base
from core.models import (
    AlertWorkflowStateModel,
    DecisionRecordModel,
    ProfileArtifactModel,
    ResolvedEventModel,
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


def _features(
    *,
    drift: float = 0.2,
    process_names: dict | None = None,
    endpoints: dict | None = None,
    geolocations: dict | None = None,
) -> dict:
    return {
        "total_events": 20,
        "login_hours": {"9": 20},
        "geolocations": geolocations or {"US": 20},
        "endpoints": endpoints or {"ep-a": 20},
        "process_names": process_names or {"chrome.exe": 20},
        "role": "engineer",
        "cohort_data": {},
        "cumulative_drift": drift,
    }


def _add_profile(
    db,
    *,
    version: str,
    entity_id: str,
    ts: datetime,
    is_shadow: bool,
    drift: float = 0.2,
    promoted_at: datetime | None = None,
    process_names: dict | None = None,
    endpoints: dict | None = None,
    geolocations: dict | None = None,
    superseded_at: datetime | None = None,
):
    db.add(
        ProfileArtifactModel(
            profile_version=version,
            entity_id=entity_id,
            entity_type="user",
            created_at=ts,
            data_window_start=ts - timedelta(days=30),
            data_window_end=ts,
            promoted_at=None if is_shadow else (promoted_at or ts),
            superseded_at=superseded_at,
            is_shadow=is_shadow,
            features=_features(
                drift=drift,
                process_names=process_names,
                endpoints=endpoints,
                geolocations=geolocations,
            ),
            embedding=[0.0] * 128,
            embedding_model_id="alter-ego-ngram-v1",
            embedding_model_version="1.0",
            embedding_dimensionality=128,
            embedding_input_normalizer_version="1.0-char-3gram-hash-128",
        )
    )


def _add_event(
    db,
    *,
    event_id: str,
    entity_id: str,
    ts: datetime,
    process_name: str = "chrome.exe",
    endpoint_id: str = "ep-a",
    geolocation: str = "US",
    partition: str = "production",
):
    db.add(
        ResolvedEventModel(
            event_id=event_id,
            timestamp=ts,
            event_type="process",
            raw_entity_id=entity_id,
            entity_id=entity_id,
            entity_type="user",
            resolution_confidence=1.0,
            simulation_partition=partition,
            event_data={
                "process_name": process_name,
                "endpoint_id": endpoint_id,
                "geolocation": geolocation,
                "command_line": f"{process_name} --silent",
            },
        )
    )


def _active_count(db, entity_id: str) -> int:
    return (
        db.query(AlertWorkflowStateModel)
        .filter(
            AlertWorkflowStateModel.entity_id == entity_id,
            AlertWorkflowStateModel.state.in_(list(ACTIVE_ALERT_STATES)),
        )
        .count()
    )


def _latest_unsuperseded_promoted(db, entity_id: str) -> ProfileArtifactModel | None:
    return (
        db.query(ProfileArtifactModel)
        .filter(
            ProfileArtifactModel.entity_id == entity_id,
            ProfileArtifactModel.is_shadow.is_(False),
            ProfileArtifactModel.superseded_at.is_(None),
        )
        .order_by(ProfileArtifactModel.created_at.desc())
        .first()
    )


def _anchor_features(db, entity_id: str) -> dict:
    rows = (
        db.query(ProfileArtifactModel)
        .filter(
            ProfileArtifactModel.entity_id == entity_id,
            ProfileArtifactModel.is_shadow.is_(False),
            ProfileArtifactModel.promoted_at.isnot(None),
        )
        .order_by(ProfileArtifactModel.promoted_at.desc())
        .limit(ANCHOR_HISTORY_COUNT)
        .all()
    )
    if not rows:
        return {}
    return rows[-1].features or {}


def test_c1_benign_fp_block_auto_resolves_without_analyst(db_session):
    """C1: GT-benign-only active alerts re-enter promote path without analyst."""
    as_of = datetime(2026, 3, 1, 12, 0, 0)
    entity_id = "user_engineer_c1"
    alert_ts = as_of - timedelta(days=6)
    _add_profile(
        db_session,
        version=f"{entity_id}_p0",
        entity_id=entity_id,
        ts=alert_ts - timedelta(days=2),
        is_shadow=False,
        drift=0.1,
    )
    db_session.add(
        DecisionRecordModel(
            decision_id="benign_fp",
            event_id="evt_fp",
            entity_id=entity_id,
            timestamp=alert_ts,
            score=50.0,
            confidence=0.9,
            profile_version=f"{entity_id}_p0",
            scoring_config_version="2.2",
            contributions=[],
            is_anomaly=True,
            cohort_used="engineer",
            cohort_unsupported=False,
            flags={"ground_truth": "benign_fp"},
        )
    )
    db_session.add(
        AlertWorkflowStateModel(
            decision_id="benign_fp",
            entity_id=entity_id,
            state="new",
            updated_at=alert_ts,
        )
    )
    for i in range(2):
        _add_profile(
            db_session,
            version=f"{entity_id}_sh_{i}",
            entity_id=entity_id,
            ts=alert_ts + timedelta(days=i + 1),
            is_shadow=True,
            drift=0.3,
        )
    for i in range(4):
        _add_event(
            db_session,
            event_id=f"evt_{i}",
            entity_id=entity_id,
            ts=as_of - timedelta(days=1, hours=i),
        )
    db_session.commit()

    build_profiles(db_session, as_of=as_of)
    row = db_session.get(AlertWorkflowStateModel, "benign_fp")
    assert row is not None
    assert row.state == "auto_resolved"

    next_as_of = as_of + timedelta(days=1)
    _add_event(
        db_session,
        event_id="evt_next",
        entity_id=entity_id,
        ts=next_as_of - timedelta(hours=1),
    )
    db_session.commit()
    build_profiles(db_session, as_of=next_as_of)
    promoted = _latest_unsuperseded_promoted(db_session, entity_id)
    assert promoted is not None
    assert promoted.promoted_at is not None
    assert _active_count(db_session, entity_id) == 0


def test_c3_bounded_laundering_after_auto_resolve(db_session):
    """C3: after auto-resolution, M_novel(next_promoted, P₋ₙ) < alpha_anchor."""
    as_of = datetime(2026, 4, 1, 12, 0, 0)
    entity_id = "user_engineer_c3"
    alert_ts = as_of - timedelta(days=6)

    # Anchor history: several prior promotions (P_{-n} is earliest in window).
    for i in range(ANCHOR_HISTORY_COUNT):
        ts = alert_ts - timedelta(days=ANCHOR_HISTORY_COUNT - i + 1)
        _add_profile(
            db_session,
            version=f"{entity_id}_hist_{i}",
            entity_id=entity_id,
            ts=ts,
            is_shadow=False,
            drift=0.1,
            promoted_at=ts,
            superseded_at=None if i == ANCHOR_HISTORY_COUNT - 1 else ts + timedelta(days=1),
            process_names={"chrome.exe": 100},
        )

    db_session.add(
        DecisionRecordModel(
            decision_id="c3_fp",
            event_id="evt_c3_fp",
            entity_id=entity_id,
            timestamp=alert_ts,
            score=50.0,
            confidence=0.9,
            profile_version=f"{entity_id}_hist_{ANCHOR_HISTORY_COUNT - 1}",
            scoring_config_version="2.2",
            contributions=[],
            is_anomaly=True,
            cohort_used="engineer",
            cohort_unsupported=False,
            flags={"ground_truth": "benign_fp"},
        )
    )
    db_session.add(
        AlertWorkflowStateModel(
            decision_id="c3_fp",
            entity_id=entity_id,
            state="new",
            updated_at=alert_ts,
        )
    )
    # Block-era shadows: tiny novel mass (below alpha_prod/alpha_anchor) so ATTEST passes.
    for i in range(2):
        _add_profile(
            db_session,
            version=f"{entity_id}_sh_{i}",
            entity_id=entity_id,
            ts=alert_ts + timedelta(days=i + 1),
            is_shadow=True,
            drift=0.4,
            process_names={"chrome.exe": 99, "notepad.exe": 1},
        )
    for i in range(4):
        _add_event(
            db_session,
            event_id=f"c3_evt_{i}",
            entity_id=entity_id,
            ts=as_of - timedelta(days=1, hours=i),
            process_name="chrome.exe",
        )
    db_session.commit()

    build_profiles(db_session, as_of=as_of)
    assert db_session.get(AlertWorkflowStateModel, "c3_fp").state == "auto_resolved"

    next_as_of = as_of + timedelta(days=1)
    # Stress the bound: ~3% novel mass in the post-resolve window (< alpha_anchor=0.05).
    for i in range(97):
        _add_event(
            db_session,
            event_id=f"c3_post_chrome_{i}",
            entity_id=entity_id,
            ts=next_as_of - timedelta(hours=1, minutes=i % 50),
            process_name="chrome.exe",
        )
    for i in range(3):
        _add_event(
            db_session,
            event_id=f"c3_post_novel_{i}",
            entity_id=entity_id,
            ts=next_as_of - timedelta(minutes=i + 1),
            process_name="newtool.exe",
        )
    db_session.commit()
    build_profiles(db_session, as_of=next_as_of)

    next_promoted = _latest_unsuperseded_promoted(db_session, entity_id)
    assert next_promoted is not None
    assert next_promoted.promoted_at is not None
    assert next_promoted.created_at >= as_of  # post-resolution promote

    anchor = _anchor_features(db_session, entity_id)
    assert anchor, "expected P₋ₙ from promotion history"
    m = novel_mass(next_promoted.features or {}, anchor)
    assert 0.0 < m < ALPHA_ANCHOR, (
        f"C3 FAIL: expected 0 < M_novel(next_promoted, P₋ₙ) < alpha_anchor; "
        f"got m={m:.4f}, alpha_anchor={ALPHA_ANCHOR}"
    )


def test_c3_high_novel_mass_blocks_auto_resolve(db_session):
    """C3 gate: ATTEST fails when built shadow novel mass exceeds alpha_prod — no auto-resolve.

    Hand-seeded shadow features alone are insufficient: build_profiles rebuilds the
    latest shadow from live events before attesting. Inject out-of-family events so
    the constructed shadow retains high novel mass.
    """
    as_of = datetime(2026, 4, 15, 12, 0, 0)
    entity_id = "user_engineer_c3_fail"
    alert_ts = as_of - timedelta(days=6)

    _add_profile(
        db_session,
        version=f"{entity_id}_p0",
        entity_id=entity_id,
        ts=alert_ts - timedelta(days=2),
        is_shadow=False,
        drift=0.1,
        process_names={"chrome.exe": 100},
    )
    db_session.add(
        DecisionRecordModel(
            decision_id="c3_fail_fp",
            event_id="evt_c3_fail",
            entity_id=entity_id,
            timestamp=alert_ts,
            score=50.0,
            confidence=0.9,
            profile_version=f"{entity_id}_p0",
            scoring_config_version="2.2",
            contributions=[],
            is_anomaly=True,
            cohort_used="engineer",
            cohort_unsupported=False,
            flags={},
        )
    )
    db_session.add(
        AlertWorkflowStateModel(
            decision_id="c3_fail_fp",
            entity_id=entity_id,
            state="new",
            updated_at=alert_ts,
        )
    )
    # Prior shadow builds for min_dwell (≥2) during the block.
    for i in range(2):
        _add_profile(
            db_session,
            version=f"{entity_id}_sh_{i}",
            entity_id=entity_id,
            ts=alert_ts + timedelta(days=i + 1),
            is_shadow=True,
            drift=0.5,
            process_names={"chrome.exe": 80, "evil.exe": 20},
        )
    # Window events: majority out-of-family so rebuilt shadow fails novel-mass gate.
    for i in range(10):
        _add_event(
            db_session,
            event_id=f"c3f_chrome_{i}",
            entity_id=entity_id,
            ts=as_of - timedelta(days=2, hours=i),
            process_name="chrome.exe",
        )
    for i in range(10):
        _add_event(
            db_session,
            event_id=f"c3f_evil_{i}",
            entity_id=entity_id,
            ts=as_of - timedelta(days=1, hours=i),
            process_name="evil.exe",
        )
    db_session.commit()

    build_profiles(db_session, as_of=as_of)
    row = db_session.get(AlertWorkflowStateModel, "c3_fail_fp")
    assert row.state == "new", (
        f"expected ATTEST failure to keep block active, got {row.state}"
    )
    assert _active_count(db_session, entity_id) == 1

    # Lock the failure reason: latest shadow (built this cycle) must exceed alpha_prod.
    latest_shadow = (
        db_session.query(ProfileArtifactModel)
        .filter(
            ProfileArtifactModel.entity_id == entity_id,
            ProfileArtifactModel.is_shadow.is_(True),
        )
        .order_by(ProfileArtifactModel.created_at.desc())
        .first()
    )
    assert latest_shadow is not None
    promoted = _latest_unsuperseded_promoted(db_session, entity_id)
    assert promoted is not None
    m_prod = novel_mass(latest_shadow.features or {}, promoted.features or {})
    assert m_prod >= ALPHA_PROD, (
        f"negative C3 must fail for novel-mass; got m_prod={m_prod:.4f} < alpha_prod={ALPHA_PROD}"
    )


def test_design_1f_fp_injection_deadlock_resolves(db_session):
    """Design 1F: Design-1-shaped baseline + synthetic benign FP — no absorbing deadlock.

    Design 1 fixture is FP-storm-free by construction; 1F injects an early benign FP
    that would freeze promotion under Series B semantics, then asserts QUIET∧ATTEST
    clears the block and the next build promotes again.
    """
    t0 = datetime(2026, 1, 1, 9, 0, 0)
    target = "user_engineer_1f"
    pads = [f"user_engineer_pad{i}" for i in range(3)]
    all_ids = [target, *pads]
    family = ["chrome.exe", "outlook.exe", "teams.exe", "code.exe"]

    # Design-1-shaped multi-day baseline with padding cohort (MIN_NORM_COHORT path).
    for day in range(5):
        for entity in all_ids:
            for burst in range(4):
                proc = family[(day + burst) % len(family)]
                _add_event(
                    db_session,
                    event_id=f"1f_ben_{entity}_{day}_{burst}",
                    entity_id=entity,
                    ts=t0 + timedelta(days=day, hours=burst),
                    process_name=proc,
                )
        db_session.commit()
        build_profiles(db_session, as_of=t0 + timedelta(days=day, hours=23))

    promoted_before = _latest_unsuperseded_promoted(db_session, target)
    assert promoted_before is not None and promoted_before.promoted_at is not None

    # Synthetic benign FP injection — arms §5.5 block (Series B deadlock seed).
    fp_ts = t0 + timedelta(days=5, hours=8)
    db_session.add(
        DecisionRecordModel(
            decision_id="1f_benign_fp",
            event_id="1f_fp_evt",
            entity_id=target,
            timestamp=fp_ts,
            score=50.1,
            confidence=0.9,
            profile_version=promoted_before.profile_version,
            scoring_config_version="2.2",
            contributions=[],
            is_anomaly=True,
            cohort_used="engineer",
            cohort_unsupported=False,
            flags={"ground_truth": "benign_fp", "design_1f": True},
        )
    )
    db_session.add(
        AlertWorkflowStateModel(
            decision_id="1f_benign_fp",
            entity_id=target,
            state="new",
            updated_at=fp_ts,
        )
    )
    db_session.commit()

    # Blocked era: benign-only traffic continues; builds emit shadows (promotion frozen).
    for day in range(6, 10):
        for entity in all_ids:
            for burst in range(3):
                proc = family[(day + burst) % len(family)]
                _add_event(
                    db_session,
                    event_id=f"1f_quiet_{entity}_{day}_{burst}",
                    entity_id=entity,
                    ts=t0 + timedelta(days=day, hours=burst),
                    process_name=proc,
                )
        db_session.commit()
        build_profiles(db_session, as_of=t0 + timedelta(days=day, hours=23))

    # Mid-block: still active after first quiet day(s) if dwell/quiet not yet satisfied;
    # by day 9 the entity must either auto-resolve or stay blocked — resolve path required.
    row = db_session.get(AlertWorkflowStateModel, "1f_benign_fp")
    assert row is not None
    # QUIET window is 3 days; FP at day-5 morning; by as_of day-9 quiet is satisfied
    # and ≥2 shadow builds exist → expect auto_resolved.
    assert row.state == "auto_resolved", (
        f"Design 1F FAIL: expected auto_resolved after quiet+dwell, got {row.state}"
    )

    # Post-resolution build must promote (not absorbing deadlock).
    next_day = 10
    for entity in all_ids:
        for burst in range(3):
            proc = family[(next_day + burst) % len(family)]
            _add_event(
                db_session,
                event_id=f"1f_post_{entity}_{burst}",
                entity_id=entity,
                ts=t0 + timedelta(days=next_day, hours=burst),
                process_name=proc,
            )
    db_session.commit()
    build_profiles(db_session, as_of=t0 + timedelta(days=next_day, hours=23))

    promoted_after = _latest_unsuperseded_promoted(db_session, target)
    assert promoted_after is not None
    assert promoted_after.promoted_at is not None
    assert promoted_after.profile_version != promoted_before.profile_version, (
        "Design 1F FAIL: no new promotion after FP auto-resolve (absorbing deadlock survives)"
    )
    assert _active_count(db_session, target) == 0
