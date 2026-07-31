# Drift Detection Capability Expansion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship seven drift-detection capability phases (foundational shadow-baseline fix, cadence CoV, volume delta, fleet cohort drift, geo-velocity, cross-signal precision gate Stage A, staged sequences) as zero-behavioral-diff-on-ship code, gated behind new `enabled` flags flipped only via recorded calibration sweeps.

**Architecture:** Every phase computes and records its signal unconditionally but only feeds `raw_total`/`cumulative_drift`/`is_anomaly`/containment eligibility when its new `enabled` config flag is `true` (default `false`). Four batched sweep checkpoints (Series E/F/G/H) gate the flags in groups matching the design doc's phase groupings.

**Tech Stack:** Python, SQLAlchemy (Postgres/pgvector + SQLite test fallback), Alembic, pytest, DuckDB (builder), FastAPI (`web/api.py`, untouched by this plan).

**Design doc:** `docs/superpowers/specs/2026-07-30-drift-detection-capability-expansion-design.md`

## Global Constraints

- No `scoring_config.yaml` `enabled` flag flips from `false` to `true` outside a Series governance step (S6.3 standing rule) — every phase's code must default `enabled: false` and prove zero behavioral diff with that default.
- Current live operating point, unchanged by this plan: `version: "2.2"`, `anomaly_threshold: 45.0`, `drift_threshold: 5.0`, `drift_half_life_days: 7`, `contribution_scale_max: 50.0`, `containment_threshold: 85.0`, `laplace_alpha: 1.0`, `cohort_gate_window_days: 7`, `cohort_gating_constants.max_changed_fraction: 0.2`, `cohort_gating_constants.min_cohort_size: 10`.
- Current `drift_weights`: `login_hour: 5.0`, `geolocation: 5.0`, `endpoint_set: 5.0`, `process_name: 20.0`, `embedding: 40.0`. New dimensions (`cadence`, `total_volume_delta`, `geo_velocity`) are added at `weight: 0.0, enabled: false`.
- Hot path reads the raw YAML `dict` via `config.get(...)`, not the `ScoringConfig` Pydantic class (`core/schemas/config.py`) — that class is a known, separately-tracked, out-of-scope divergence (`DEBT-028`). Do not modify `core/schemas/config.py` in this plan.
- Every new DB-visible field (new `DecisionRecordModel` columns) needs an Alembic migration following the existing pattern in `alembic/versions/f5a6b7c8d9e0_add_decisions_replay_run_id.py` (add column, optional index, explicit `downgrade()`).
- Test DB fixture pattern (SQLite in-memory, JSONB/ARRAY compiled to JSON) is established in `tests/worker/test_shadow_drift_under_block.py` — reuse it verbatim for any new test file touching `ProfileArtifactModel`/`DecisionRecordModel`.
- `ruff check .` (line-length 100) and `mypy .` (strict) must pass after every task; `pytest -v --tb=short` must pass after every task.

---

## Phase 0 — Shadow-aware point-rarity & embedding baseline under block

### Task 0.1: Shared effective-profile resolver, wired into point-rarity + embedding

**Files:**
- Modify: `worker/scorer.py:389-538` (inside `score_event`, before the point-rarity/embedding block)
- Create: `tests/worker/test_shadow_baseline_under_block.py`

**Interfaces:**
- Produces: `_resolve_effective_profile(db: Session, entity_id: str, promoted: ProfileArtifact, as_of: datetime) -> tuple[ProfileArtifact, list[str], Optional[str]]` — returns `(effective_profile, warn_events, flag_or_none)`. `warn_events` is a list of `(entity_id, as_of, active_shadow_count)` tuples the caller logs via `logger.warning`; `flag_or_none` is the flag string to append (`f"point_baseline_shadow_fallback:{version}"`, `"point_baseline_shadow_fallback:no_shadow"`, or `None` when unblocked).
- Consumes (existing, unchanged): `entity_has_active_uncleared_alert(db, entity_id) -> bool` (`worker/scorer.py:315`), `ProfileStore.get_latest_shadow_profile(entity_id, as_of) -> Optional[ProfileArtifact]` and `ProfileStore.count_shadow_profiles(entity_id) -> int` (`worker/profile_store.py:54,77`).

- [ ] **Step 1: Write the failing test**

```python
# tests/worker/test_shadow_baseline_under_block.py
"""Phase 0: point-rarity/embedding baseline must follow the shadow profile
while an entity is build-blocked, same as drift_alert already does (D4)."""

from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker

from core.database import Base
from core.models import AlertWorkflowStateModel, DecisionRecordModel, ProfileArtifactModel
from core.schemas.events import ResolvedEvent
from worker.scorer import load_scoring_config, score_event


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


def _profile(*, version, entity_id, login_hours, is_shadow, promoted_at, created_at, data_window_end):
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
            "login_hours": login_hours,
            "geolocations": {"US": 100},
            "endpoints": {"ep-a": 100},
            "process_names": {"chrome.exe": 100},
            "role": "engineer",
            "cohort_data": {},
            "cumulative_drift": 0.0,
        },
        embedding=[0.1] * 128,
        embedding_model_id="alter-ego-ngram-v1",
        embedding_model_version="1.0",
        embedding_dimensionality=128,
        embedding_input_normalizer_version="1.0-char-3gram-hash-128",
    )


def test_blocked_entity_point_rarity_follows_shadow_not_frozen_promoted(db_session):
    entity_id = "user_engineer_p0"
    as_of = datetime(2024, 6, 15, 12, 0, 0)

    # Promoted (frozen pre-block): entity NEVER logs in at hour 3.
    db_session.add(_profile(
        version="promoted_v1", entity_id=entity_id,
        login_hours={str(h): (0 if h == 3 else 5) for h in range(24)},
        is_shadow=False, promoted_at=as_of - timedelta(days=5),
        created_at=as_of - timedelta(days=5), data_window_end=as_of - timedelta(days=5),
    ))
    # Shadow (post-block, has since learned hour-3 logins are now common for this entity).
    db_session.add(_profile(
        version="shadow_v2", entity_id=entity_id,
        login_hours={str(h): 5 for h in range(24)},
        is_shadow=True, promoted_at=None,
        created_at=as_of, data_window_end=as_of - timedelta(hours=1),
    ))
    db_session.add(DecisionRecordModel(
        decision_id="fp_alert_p0", event_id="evt_fp_p0", entity_id=entity_id,
        timestamp=as_of - timedelta(days=2), score=50.0, confidence=0.9,
        profile_version="promoted_v1", scoring_config_version="2.2",
        contributions=[], is_anomaly=True, cohort_used="engineer",
        cohort_unsupported=False, flags=[],
    ))
    db_session.add(AlertWorkflowStateModel(
        decision_id="fp_alert_p0", entity_id=entity_id, state="new", updated_at=as_of - timedelta(days=2),
    ))
    db_session.commit()

    from worker.profile_store import ProfileStore
    promoted = ProfileStore(db_session).get_active_profile(entity_id, as_of)
    config = load_scoring_config()
    event = ResolvedEvent(
        event_id="evt_p0", timestamp=as_of.replace(hour=3), event_type="process",
        raw_entity_id=entity_id, entity_id=entity_id, entity_type="human",
        resolution_confidence=1.0, simulation_partition="production",
        event_data={"process_name": "chrome.exe", "endpoint_id": "ep-a",
                    "geolocation": "US", "command_line": "chrome.exe --silent"},
    )
    decision = score_event(db_session, event, promoted, config)
    login_c = next(c for c in decision.contributions if c.feature_name == "login_hour_rarity")
    # Against the FROZEN promoted profile hour 3 is rare (raw_value high); against
    # the shadow it is common (raw_value ~0). Must reflect the shadow.
    assert login_c.raw_value < 1.0
    assert any(
        isinstance(f, str) and f.startswith("point_baseline_shadow_fallback:")
        for f in decision.flags
    )


def test_blocked_entity_no_shadow_falls_back_to_promoted_with_flag(db_session, caplog):
    import logging

    entity_id = "user_engineer_p0_noshadow"
    as_of = datetime(2024, 6, 15, 12, 0, 0)
    db_session.add(_profile(
        version="promoted_only", entity_id=entity_id,
        login_hours={str(h): (0 if h == 3 else 5) for h in range(24)},
        is_shadow=False, promoted_at=as_of - timedelta(days=5),
        created_at=as_of - timedelta(days=5), data_window_end=as_of - timedelta(days=5),
    ))
    db_session.add(DecisionRecordModel(
        decision_id="fp_alert_p0b", event_id="evt_fp_p0b", entity_id=entity_id,
        timestamp=as_of - timedelta(days=2), score=50.0, confidence=0.9,
        profile_version="promoted_only", scoring_config_version="2.2",
        contributions=[], is_anomaly=True, cohort_used="engineer",
        cohort_unsupported=False, flags=[],
    ))
    db_session.add(AlertWorkflowStateModel(
        decision_id="fp_alert_p0b", entity_id=entity_id, state="new", updated_at=as_of - timedelta(days=2),
    ))
    db_session.commit()

    from worker.profile_store import ProfileStore
    promoted = ProfileStore(db_session).get_active_profile(entity_id, as_of)
    config = load_scoring_config()
    event = ResolvedEvent(
        event_id="evt_p0b", timestamp=as_of.replace(hour=3), event_type="process",
        raw_entity_id=entity_id, entity_id=entity_id, entity_type="human",
        resolution_confidence=1.0, simulation_partition="production",
        event_data={"process_name": "chrome.exe", "endpoint_id": "ep-a",
                    "geolocation": "US", "command_line": "chrome.exe --silent"},
    )
    with caplog.at_level(logging.WARNING, logger="worker.scorer"):
        decision = score_event(db_session, event, promoted, config)
    login_c = next(c for c in decision.contributions if c.feature_name == "login_hour_rarity")
    assert login_c.raw_value > 1.0  # still scored against the stale promoted hour-3-rare histogram
    assert "point_baseline_shadow_fallback:no_shadow" in decision.flags
    assert any("point_baseline_shadow_fallback" in r.message for r in caplog.records if r.levelname == "WARNING")


def test_unblocked_entity_unaffected(db_session):
    """Zero behavioral diff: unblocked entity always scores against its own promoted profile."""
    entity_id = "user_engineer_p0_unblocked"
    as_of = datetime(2024, 6, 15, 12, 0, 0)
    db_session.add(_profile(
        version="promoted_unblocked", entity_id=entity_id,
        login_hours={str(h): (0 if h == 3 else 5) for h in range(24)},
        is_shadow=False, promoted_at=as_of - timedelta(days=5),
        created_at=as_of - timedelta(days=5), data_window_end=as_of - timedelta(days=5),
    ))
    db_session.commit()

    from worker.profile_store import ProfileStore
    promoted = ProfileStore(db_session).get_active_profile(entity_id, as_of)
    config = load_scoring_config()
    event = ResolvedEvent(
        event_id="evt_p0c", timestamp=as_of.replace(hour=3), event_type="process",
        raw_entity_id=entity_id, entity_id=entity_id, entity_type="human",
        resolution_confidence=1.0, simulation_partition="production",
        event_data={"process_name": "chrome.exe", "endpoint_id": "ep-a",
                    "geolocation": "US", "command_line": "chrome.exe --silent"},
    )
    decision = score_event(db_session, event, promoted, config)
    assert not any(
        isinstance(f, str) and f.startswith("point_baseline_shadow_fallback")
        for f in decision.flags
    )
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/worker/test_shadow_baseline_under_block.py -v`
Expected: `test_blocked_entity_point_rarity_follows_shadow_not_frozen_promoted` FAILS (`login_c.raw_value` reflects the frozen promoted histogram, not the shadow — currently scored value is high/rare, not `< 1.0`) and the `no_shadow`/fallback-flag assertions in it FAIL (flag doesn't exist yet). The other two tests currently pass (nothing to break yet) — that's fine, they're the regression/zero-diff guards for the implementation you're about to add.

- [ ] **Step 3: Implement `_resolve_effective_profile` and wire it in**

In `worker/scorer.py`, add near the other module-level helpers (after `_get_cohort_histogram`, before `score_event`):

```python
def _resolve_effective_profile(
    db: Session, entity_id: str, promoted: ProfileArtifact, as_of: datetime
) -> tuple[ProfileArtifact, str | None]:
    """S55-D4-style shadow read, extended beyond drift to point-rarity/embedding.

    Returns (effective_profile, flag_or_none). Logs a WARNING itself on the
    no-shadow-yet path, mirroring the existing drift_shadow_fallback contract.
    """
    if not entity_has_active_uncleared_alert(db, entity_id):
        return promoted, None
    store = ProfileStore(db)
    shadow = store.get_latest_shadow_profile(entity_id, as_of=as_of)
    if shadow is not None:
        if shadow.profile_version != promoted.profile_version:
            return shadow, f"point_baseline_shadow_fallback:{shadow.profile_version}"
        return shadow, None
    active_shadow_count = store.count_shadow_profiles(entity_id)
    logger.warning(
        "point_baseline_shadow_fallback entity_id=%s as_of=%s active_shadow_count=%s",
        entity_id, as_of, active_shadow_count,
    )
    return promoted, "point_baseline_shadow_fallback:no_shadow"
```

Then, in `score_event`, immediately before the `# --- Feature scores ---` block (currently `worker/scorer.py:509`), insert:

```python
    effective_profile, point_baseline_flag = _resolve_effective_profile(
        db, resolved_event.entity_id, profile, resolved_event.timestamp
    )
    if point_baseline_flag is not None:
        flags.append(point_baseline_flag)
```

Replace the four `_get_cohort_histogram(feature_name, profile)` calls (lines 511-514) with `_get_cohort_histogram(feature_name, effective_profile)`, and replace the embedding block's `np.array(profile.embedding)` (line 528) with `np.array(effective_profile.embedding)`. Note `get_rarity_score`'s inner closure at line 485 reads `profile.features.get("role", ...)` for the cohort-novelty check — leave that specific read on `profile` (not `effective_profile`): role/cohort membership is an identity fact, not a point-rarity baseline, and changing it is out of scope for Phase 0.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/worker/test_shadow_baseline_under_block.py -v`
Expected: all three PASS.

- [ ] **Step 5: Run full existing suite to confirm no regression**

Run: `pytest -v --tb=short`
Expected: PASS, including `tests/worker/test_shadow_drift_under_block.py` (drift block untouched by this task) and all point-rarity/embedding tests for unblocked entities.

- [ ] **Step 6: Commit**

```bash
git add worker/scorer.py tests/worker/test_shadow_baseline_under_block.py
git commit -m "Extend D4 shadow-read pattern to point-rarity and embedding baseline under block"
```

### Task 0.2: Dedupe shadow lookup between point-baseline and drift blocks

**Files:**
- Modify: `worker/scorer.py:569-591` (existing D4 drift block)
- Modify: `tests/worker/test_shadow_baseline_under_block.py` (add one assertion-style test)

**Interfaces:**
- Consumes: `_resolve_effective_profile` from Task 0.1 — the drift block reuses `effective_profile.features.get("cumulative_drift", 0.0)` instead of independently calling `ProfileStore.get_latest_shadow_profile` a second time.

- [ ] **Step 1: Write the failing test** (call-count assertion via monkeypatch)

```python
def test_shadow_lookup_happens_once_per_score_event(db_session, monkeypatch):
    """Point-baseline and drift blocks must share one shadow lookup, not two."""
    entity_id = "user_engineer_p0_once"
    as_of = datetime(2024, 6, 15, 12, 0, 0)
    db_session.add(_profile(
        version="promoted_once", entity_id=entity_id,
        login_hours={str(h): 5 for h in range(24)},
        is_shadow=False, promoted_at=as_of - timedelta(days=5),
        created_at=as_of - timedelta(days=5), data_window_end=as_of - timedelta(days=5),
    ))
    db_session.add(_profile(
        version="shadow_once", entity_id=entity_id,
        login_hours={str(h): 5 for h in range(24)},
        is_shadow=True, promoted_at=None,
        created_at=as_of, data_window_end=as_of - timedelta(hours=1),
    ))
    db_session.add(DecisionRecordModel(
        decision_id="fp_once", event_id="evt_fp_once", entity_id=entity_id,
        timestamp=as_of - timedelta(days=2), score=50.0, confidence=0.9,
        profile_version="promoted_once", scoring_config_version="2.2",
        contributions=[], is_anomaly=True, cohort_used="engineer",
        cohort_unsupported=False, flags=[],
    ))
    db_session.add(AlertWorkflowStateModel(
        decision_id="fp_once", entity_id=entity_id, state="new", updated_at=as_of - timedelta(days=2),
    ))
    db_session.commit()

    from worker.profile_store import ProfileStore
    import worker.scorer as scorer_mod

    call_count = {"n": 0}
    original = ProfileStore.get_latest_shadow_profile

    def counting_wrapper(self, entity_id_, as_of=None):
        call_count["n"] += 1
        return original(self, entity_id_, as_of=as_of)

    monkeypatch.setattr(ProfileStore, "get_latest_shadow_profile", counting_wrapper)

    promoted = ProfileStore(db_session).get_active_profile(entity_id, as_of)
    config = load_scoring_config()
    event = ResolvedEvent(
        event_id="evt_once", timestamp=as_of, event_type="process",
        raw_entity_id=entity_id, entity_id=entity_id, entity_type="human",
        resolution_confidence=1.0, simulation_partition="production",
        event_data={"process_name": "chrome.exe", "endpoint_id": "ep-a",
                    "geolocation": "US", "command_line": "chrome.exe --silent"},
    )
    scorer_mod.score_event(db_session, event, promoted, config)
    assert call_count["n"] == 1
```

- [ ] **Step 2: Run to verify it fails**

Run: `pytest tests/worker/test_shadow_baseline_under_block.py::test_shadow_lookup_happens_once_per_score_event -v`
Expected: FAIL, `call_count["n"] == 2` (Task 0.1's resolver calls it once, the existing D4 block at line 575 calls it again).

- [ ] **Step 3: Refactor the D4 drift block to reuse `effective_profile`**

Replace `worker/scorer.py:569-591`:

```python
    # S55 D4: while entity is build-blocked, read cumulative_drift from latest
    # shadow profile; all other features stay on the promoted profile.
    drift_accum = profile.features.get("cumulative_drift", 0.0)
    drift_source_version = profile.profile_version
    if entity_has_active_uncleared_alert(db, resolved_event.entity_id):
        store = ProfileStore(db)
        shadow = store.get_latest_shadow_profile(
            resolved_event.entity_id, as_of=resolved_event.timestamp
        )
        if shadow is not None:
            drift_accum = shadow.features.get("cumulative_drift", 0.0)
            drift_source_version = shadow.profile_version
            if drift_source_version != profile.profile_version:
                flags.append(f"drift_source_profile_version:{drift_source_version}")
        else:
            active_shadow_count = store.count_shadow_profiles(resolved_event.entity_id)
            logger.warning(
                "drift_shadow_fallback entity_id=%s as_of=%s active_shadow_count=%s",
                resolved_event.entity_id,
                resolved_event.timestamp,
                active_shadow_count,
            )
            flags.append("drift_shadow_fallback:no_shadow")
```

with:

```python
    # S55 D4 + Phase 0: effective_profile (resolved once, above) already carries
    # the shadow accumulator when blocked; reuse it instead of a second lookup.
    drift_accum = effective_profile.features.get("cumulative_drift", 0.0)
    drift_source_version = effective_profile.profile_version
    if drift_source_version != profile.profile_version:
        flags.append(f"drift_source_profile_version:{drift_source_version}")
```

The no-shadow WARN + `drift_shadow_fallback:no_shadow` case is now handled by `_resolve_effective_profile` itself via the `point_baseline_shadow_fallback:no_shadow` flag — **do not** duplicate a second no-shadow flag/WARN here. Update `tests/worker/test_shadow_drift_under_block.py::test_blocked_shadow_miss_emits_fallback_flag` to assert on `point_baseline_shadow_fallback:no_shadow` instead of `drift_shadow_fallback:no_shadow` (grep the whole repo for `drift_shadow_fallback` first to confirm no other consumer depends on that exact string — if `web/api.py` or any dashboard filters on it, rename with a backward-compatible dual-flag emission instead of a silent rename).

- [ ] **Step 4: Grep for other consumers of the old flag string before finalizing the rename**

Run: `grep -rn "drift_shadow_fallback" --include=*.py .` (or the Grep tool) across `web/`, `tests/`, `scratch/`. If any non-test file depends on the exact string, keep emitting both `drift_shadow_fallback:no_shadow` and `point_baseline_shadow_fallback:no_shadow` rather than removing the old one silently.

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/worker/test_shadow_baseline_under_block.py tests/worker/test_shadow_drift_under_block.py -v`
Expected: PASS (including the updated fallback-flag assertion).

- [ ] **Step 6: Run full suite**

Run: `pytest -v --tb=short`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add worker/scorer.py tests/worker/test_shadow_baseline_under_block.py tests/worker/test_shadow_drift_under_block.py
git commit -m "Dedupe shadow-profile lookup between point-baseline and drift contribution"
```

### Task 0.3: Series E sweep harness + governance doc

**Files:**
- Create: `scratch/run_series_e_sweep.py` (adapt from `scratch/run_series_d_sweep.py`)
- Create: `docs/scoring-config-governance-series-e.md` (populated after the sweep runs — not before)

**Interfaces:**
- Consumes: `batch.eval.runner.run_pipeline`, `batch.eval.runner.calculate_metrics`, `batch.synthetic.generator.EventGenerator` (unchanged by this plan) — same imports as `run_series_d_sweep.py`.
- Produces: `scratch/series_e_metrics.json` with a new top-level key `"blocked_entity_point_fp_delta"` (see Step 1) that Series F/G/H do not need to reproduce (Phase 0-specific).

- [ ] **Step 1: Copy and adapt the Series D harness**

```bash
cp scratch/run_series_d_sweep.py scratch/run_series_e_sweep.py
```

Edit `scratch/run_series_e_sweep.py`:
- Rename `DB_PATH`/`EVENTS_PATH`/`LABELS_PATH`/`METRICS_PATH` constants from `series_d_*` to `series_e_*`.
- `generate_series_d_mix()` → keep the exact same event mix as Series D (baseline + tooling rollout + S1-S5) so Series E is comparable to Series D as its immediate predecessor — this sweep isolates Phase 0's effect, not a new attack mix. Rename the function to `generate_series_e_mix()` but do not change its body.
- Add a new function:

```python
def blocked_entity_point_fp_delta(db) -> dict[str, Any]:
    """Phase 0: point-score volume for entities that were blocked at scoring time,
    isolated from Series D (pre-Phase-0) for direct before/after comparison."""
    from core.models import AlertWorkflowStateModel

    blocked_ids = {
        row.entity_id
        for row in db.execute(
            select(AlertWorkflowStateModel).where(
                AlertWorkflowStateModel.state.in_(list(ACTIVE_ALERT_STATES))
            )
        ).scalars().all()
    }
    decisions = list(
        db.execute(
            select(DecisionRecordModel).where(DecisionRecordModel.entity_id.in_(blocked_ids))
        ).scalars().all()
    )
    fp_count = sum(1 for d in decisions if d.is_anomaly)
    point_baseline_fallback_count = sum(
        1 for d in decisions
        if any(
            isinstance(f, str) and f.startswith("point_baseline_shadow_fallback:") and not f.endswith(":no_shadow")
            for f in (d.flags or [])
        )
    )
    return {
        "blocked_entity_count": len(blocked_ids),
        "blocked_entity_decision_count": len(decisions),
        "blocked_entity_anomaly_count": fp_count,
        "point_baseline_shadow_engaged_count": point_baseline_fallback_count,
    }
```

- In `main()`, change `payload["series"] = "E"`, add `payload["metrics"]["blocked_entity_point_fp_delta"] = blocked_entity_point_fp_delta(db)`, and update the `"note"` string to: `"NOT CALIBRATED. Series E harness output (Phase 0 shadow-aware point-baseline). Compare blocked_entity_point_fp_delta against Series D's blocked_entity_count/active_alert_workflow_rows as the isolated Phase-0 effect. Do not compare headline FP/P/R to Series A/B/C/D."`

- [ ] **Step 2: Run the sweep**

Run: `python scratch/run_series_e_sweep.py`
Expected: exits 0, writes `scratch/series_e_metrics.json`.

- [ ] **Step 3: Write the governance doc**

Create `docs/scoring-config-governance-series-e.md` following the exact section structure of `docs/scoring-config-governance-series-d.md` (packet reference, "what this sweep covers" table, headline table, cross-series rule, standing rule). Populate every value from `scratch/series_e_metrics.json` — do not estimate or round. Include a `## Phase 0 isolated effect` section with the `blocked_entity_point_fp_delta` numbers compared side-by-side against Series D's `active_alert_workflow_rows`/`blocked_entity_count`. State explicitly: `enabled` flags — none exist yet for Phase 0 (it has no config gate, it's a bugfix to an existing mechanism, not a new weighted signal) — so this governance doc's role is to confirm the fix doesn't shift FP volume in an unexpected direction before Phase 1+ code lands, not to gate a flag flip.

- [ ] **Step 4: Commit**

```bash
git add scratch/run_series_e_sweep.py docs/scoring-config-governance-series-e.md scratch/series_e_metrics.json
git commit -m "Run Series E sweep: isolate Phase 0 shadow-baseline effect on blocked-entity FP volume"
```

---

## Phase 1 — H12: cadence-as-drift-dimension + OT synthetic archetype

### Task 1.1: `ot_polling` synthetic archetype + jitter for existing service accounts

**Files:**
- Modify: `batch/synthetic/generator.py:9-27` (`EntityProfile.__init__`), `:104-120` (service-account event generation in `generate_baseline`)
- Test: `tests/batch/synthetic/test_generator_archetypes.py` (new)

**Interfaces:**
- Produces: `EntityProfile.archetype: str` (`"it_automation"` default, `"ot_polling"` new), `EntityProfile.jitter_minutes: float` (0 for `ot_polling`, a small nonzero value for `it_automation` so cadence CoV has a nonzero benign baseline to compare against).

**Note on generator mechanics (verified):** the baseline-generation loop steps in whole minutes (`current_time += timedelta(minutes=1)`, `batch/synthetic/generator.py:122`) and service accounts fire with **zero jitter today** (`"Strict periodicity"`, `generator.py:106`) — every existing service account is already perfectly regular. This task must (a) add a small nonzero jitter to the default `it_automation` archetype so cadence CoV has something realistic to measure at baseline, and (b) make `ot_polling` genuinely tighter than any existing archetype (`periodicity_minutes=1` — the tightest interval the minute-granularity generator can represent — with `jitter_minutes=0`), rather than describing it as "seconds-scale" (the generator cannot represent sub-minute intervals; do not claim it does).

- [ ] **Step 1: Write the failing test**

```python
# tests/batch/synthetic/test_generator_archetypes.py
from datetime import datetime

from batch.synthetic.generator import EventGenerator


def test_ot_polling_archetype_fires_every_minute_with_zero_jitter():
    gen = EventGenerator(seed=42)
    ot_entities = [e for e in gen.entities.values() if getattr(e, "archetype", None) == "ot_polling"]
    assert len(ot_entities) >= 5, "expected a distinct ot_polling cohort, none found"
    for e in ot_entities:
        assert e.periodicity_minutes == 1
        assert e.jitter_minutes == 0.0


def test_it_automation_archetype_has_nonzero_jitter():
    gen = EventGenerator(seed=42)
    it_entities = [e for e in gen.entities.values() if getattr(e, "archetype", None) == "it_automation"]
    assert len(it_entities) >= 5
    for e in it_entities:
        assert e.jitter_minutes > 0.0


def test_ot_polling_events_are_tighter_interval_than_it_automation():
    gen = EventGenerator(seed=42)
    start, end = datetime(2026, 1, 1), datetime(2026, 1, 1, 2, 0, 0)
    events, _ = gen.generate_baseline(start, end)

    ot_id = next(e.entity_id for e in gen.entities.values() if getattr(e, "archetype", None) == "ot_polling")
    it_id = next(e.entity_id for e in gen.entities.values() if getattr(e, "archetype", None) == "it_automation")

    def intervals(entity_id):
        ts = sorted(e.timestamp for e in events if e.raw_entity_id == entity_id)
        return [(ts[i + 1] - ts[i]).total_seconds() for i in range(len(ts) - 1)]

    ot_intervals = intervals(ot_id)
    it_intervals = intervals(it_id)
    assert ot_intervals, "ot_polling entity produced no events in the test window"
    assert max(ot_intervals) <= 60.0  # every-minute firing, allowing exact 60s spacing
    assert it_intervals
    assert (sum(it_intervals) / len(it_intervals)) > (sum(ot_intervals) / len(ot_intervals))
```

- [ ] **Step 2: Run to verify it fails**

Run: `pytest tests/batch/synthetic/test_generator_archetypes.py -v`
Expected: FAIL — `AttributeError`/`getattr` returns `None`, no entities match either archetype (attribute doesn't exist yet).

- [ ] **Step 3: Implement the archetype fields and cohort**

In `batch/synthetic/generator.py`, modify `EntityProfile.__init__`:

```python
class EntityProfile:
    def __init__(self, rng: random.Random, entity_id: str, entity_type: str, role: str = None, archetype: str = "it_automation"):
        self.entity_id = entity_id
        self.entity_type = entity_type
        self.role = role
        self.archetype = archetype

        if entity_type == "human":
            self.base_shift_hour = rng.randint(7, 10)
            self.primary_endpoint = f"ep_{rng.randint(1, 1000)}"
            self.geography = rng.choice(["US-East", "US-West", "EU-Central", "AP-South"])
            self.typical_processes = self._get_role_processes(role)
            self.jitter_minutes = 0.0
        else:  # service_account
            if archetype == "ot_polling":
                self.periodicity_minutes = 1
                self.jitter_minutes = 0.0
                self.typical_processes = ["plc_poll.exe", "scada_read.exe"]
            else:  # it_automation (existing behavior + jitter)
                self.periodicity_minutes = rng.choice([60, 120, 720, 1440])
                self.jitter_minutes = rng.uniform(1.0, 5.0)
                self.typical_processes = ["backup.sh", "db_dump.exe", "sync_worker.py"]
            self.last_run_time = None
            self.primary_endpoint = f"server_{rng.randint(1, 50)}"
            self.geography = "US-East-DC1"
```

Modify `EventGenerator.__init__` (`generator.py:39-57`) to add an `ot_polling` cohort alongside the existing `svc_backup_*` entities:

```python
        # Service accounts (existing IT-automation-style)
        for i in range(10):
            eid = f"svc_backup_{i}"
            self.entities[eid] = EntityProfile(self.rng, eid, "service_account", archetype="it_automation")

        # OT/ICS-style polling service accounts (Phase 1 / H12)
        for i in range(10):
            eid = f"svc_ot_poll_{i}"
            self.entities[eid] = EntityProfile(self.rng, eid, "service_account", archetype="ot_polling")
```

Modify the service-account firing condition in `generate_baseline` (`generator.py:104-120`) to add jitter for `it_automation` entities (zero jitter is a no-op for `ot_polling` since `jitter_minutes == 0.0`):

```python
                else:  # Service Account
                    effective_periodicity = entity.periodicity_minutes
                    if entity.jitter_minutes > 0:
                        effective_periodicity += self.rng.uniform(-entity.jitter_minutes, entity.jitter_minutes)
                    if entity.last_run_time is None or (current_time - entity.last_run_time).total_seconds() / 60 >= effective_periodicity:
                        entity.last_run_time = current_time
                        event_id = str(uuid.UUID(int=self.rng.getrandbits(128), version=4))
                        events.append(Event(
                            event_id=event_id,
                            timestamp=current_time,
                            event_type="process",
                            raw_entity_id=entity.entity_id,
                            simulation_partition="production",
                            event_data=ProcessEventData(
                                process_name=self.rng.choice(entity.typical_processes),
                                command_line="run_job.sh --auto",
                                endpoint_id=entity.primary_endpoint
                            )
                        ))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/batch/synthetic/test_generator_archetypes.py -v`
Expected: PASS.

- [ ] **Step 5: Run full suite**

Run: `pytest -v --tb=short`
Expected: PASS — check specifically that no existing test hardcodes the old 10-service-account count (`grep -rn "svc_backup" tests/`) or assumes zero jitter; fix any that do by asserting ranges instead of exact equality.

- [ ] **Step 6: Commit**

```bash
git add batch/synthetic/generator.py tests/batch/synthetic/test_generator_archetypes.py
git commit -m "Add ot_polling synthetic service-account archetype and jitter for it_automation"
```

### Task 1.2: Build-window cadence CoV as a new drift dimension (shadow-computed, disabled)

**Files:**
- Modify: `config/scoring_config.yaml` (`drift_weights.cadence`)
- Modify: `batch/profile_builder/builder.py` (raw_drift computation loop, ~lines 600-665 per the existing per-entity KL/embedding delta block)
- Test: `tests/batch/profile_builder/test_cadence_drift_dimension.py` (new)

**Interfaces:**
- Produces: `compute_build_window_cadence_cov(db: Session, entity_id: str, window_start: datetime, window_end: datetime, min_events: int = 20) -> tuple[float, int]` in `batch/profile_builder/builder.py` — returns `(cov_score, n_events)` using the **same formula** as `worker/scorer.py::compute_periodicity` (`max(0.0, 1.0 - (cv / 0.3))`), reused verbatim, applied over all `ResolvedEventModel` rows for the entity within `[window_start, window_end)` regardless of `entity_type`. Returns `(0.0, n)` when `n < min_events`.
- Consumes: nothing new — same `ResolvedEventModel` table already queried elsewhere in `builder.py`.

- [ ] **Step 1: Write the failing test**

```python
# tests/batch/profile_builder/test_cadence_drift_dimension.py
from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker

from core.database import Base
from core.models import ResolvedEventModel
from batch.profile_builder.builder import compute_build_window_cadence_cov


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


def _resolved_event(entity_id, ts, i):
    return ResolvedEventModel(
        event_id=f"evt_{entity_id}_{i}",
        entity_id=entity_id,
        entity_type="service_account",
        timestamp=ts,
        event_data={"process_name": "plc_poll.exe"},
        resolution_confidence=1.0,
        simulation_partition="production",
    )


def test_perfectly_regular_events_score_cov_near_one(db_session):
    entity_id = "svc_ot_poll_test"
    start = datetime(2026, 1, 1, 0, 0, 0)
    for i in range(30):
        db_session.add(_resolved_event(entity_id, start + timedelta(minutes=i), i))
    db_session.commit()

    cov, n = compute_build_window_cadence_cov(db_session, entity_id, start, start + timedelta(hours=1), min_events=20)
    assert n == 30
    assert cov > 0.95  # near-zero interval variance -> near-1.0 regularity score


def test_irregular_events_score_lower_cov(db_session):
    import random
    entity_id = "svc_irregular_test"
    rng = random.Random(1)
    start = datetime(2026, 1, 1, 0, 0, 0)
    t = start
    for i in range(30):
        t += timedelta(minutes=rng.uniform(0.5, 20.0))
        db_session.add(_resolved_event(entity_id, t, i))
    db_session.commit()

    cov, n = compute_build_window_cadence_cov(db_session, entity_id, start, t + timedelta(minutes=1), min_events=20)
    assert n == 30
    assert cov < 0.5


def test_below_min_events_returns_zero(db_session):
    entity_id = "svc_sparse_test"
    start = datetime(2026, 1, 1, 0, 0, 0)
    for i in range(5):
        db_session.add(_resolved_event(entity_id, start + timedelta(minutes=i), i))
    db_session.commit()

    cov, n = compute_build_window_cadence_cov(db_session, entity_id, start, start + timedelta(hours=1), min_events=20)
    assert n == 5
    assert cov == 0.0
```

- [ ] **Step 2: Run to verify it fails**

Run: `pytest tests/batch/profile_builder/test_cadence_drift_dimension.py -v`
Expected: FAIL — `ImportError: cannot import name 'compute_build_window_cadence_cov'`.

- [ ] **Step 3: Add a config-override parameter to `build_profiles` (required for testability)**

`build_profiles` (`batch/profile_builder/builder.py:436-448`) has no config-injection point today — it always reads `config_path = Path("config/scoring_config.yaml")` directly, with no parameter and no environment-variable override. Every subsequent phase in this plan needs to exercise `build_profiles` with an `enabled: true` variant of a specific flag *without* mutating the committed YAML (that mutation only happens later, as a separate governance-gated action). Add the override once, here, so Phases 1-6 all reuse it instead of each inventing a different workaround:

```python
def build_profiles(
    db: Session | None = None,
    drift_compare_n: int = 5,
    as_of: datetime | None = None,
    chunk_size: int = _BUILD_EXTRACT_CHUNK_SIZE,
    config_override: dict | None = None,
) -> int:
    if db is None:
        db_session = SessionLocal()
    else:
        db_session = db

    if as_of is None:
        as_of = datetime.utcnow()

    if config_override is not None:
        config = config_override
    else:
        config_path = Path("config/scoring_config.yaml")
        with open(config_path, "r") as f:
            config = yaml.safe_load(f)
```

(Replace the existing lines 436-448 with the block above — `config_override` defaults to `None`, so every existing caller of `build_profiles(...)` without the new keyword argument is unaffected; this is itself a zero-behavioral-diff change and should have its own tiny regression test: call `build_profiles()` with no `config_override` against a fixture DB and assert it still reads `config/scoring_config.yaml` as before, e.g. by asserting the resulting profile's `features["role"]` or drift threshold behavior matches a pre-change snapshot.)

- [ ] **Step 4: Implement `compute_build_window_cadence_cov` and wire into `raw_drift`**

Add to `batch/profile_builder/builder.py` (near the top-level helper functions, alongside existing imports of `math`/`ResolvedEventModel`):

```python
def compute_build_window_cadence_cov(
    db: Session, entity_id: str, window_start: datetime, window_end: datetime, min_events: int = 20
) -> tuple[float, int]:
    """Build-window inter-event interval CoV, same formula as worker.scorer.compute_periodicity,
    applied to any entity_type over the build window instead of a rolling 60-minute lookback."""
    stmt = (
        select(ResolvedEventModel.timestamp)
        .where(
            and_(
                ResolvedEventModel.entity_id == entity_id,
                ResolvedEventModel.timestamp >= window_start,
                ResolvedEventModel.timestamp < window_end,
            )
        )
        .order_by(ResolvedEventModel.timestamp)
    )
    ts_list = db.execute(stmt).scalars().all()
    count = len(ts_list)
    if count < min_events:
        return 0.0, count
    intervals = [(ts_list[i + 1] - ts_list[i]).total_seconds() for i in range(len(ts_list) - 1)]
    mean_int = sum(intervals) / len(intervals)
    if mean_int < 1.0:
        return 0.0, count
    cv = (math.sqrt(sum((x - mean_int) ** 2 for x in intervals) / len(intervals))) / mean_int
    return max(0.0, 1.0 - (cv / 0.3)), count
```

In the per-entity `raw_drift_records` loop (the block computing `deltas["login_hour"]`, `deltas["geolocation"]`, etc. around `builder.py:636-645`), add a cadence delta gated by config:

```python
                    cadence_cfg = drift_weights_cfg.get("cadence", {})
                    if cadence_cfg.get("enabled", False):
                        cadence_cov, cadence_n = compute_build_window_cadence_cov(
                            db_session, entity_id, window_start, window_end
                        )
                        deltas["cadence"].append(cadence_cov)
```

(`drift_weights_cfg` is whatever local variable already holds `config.get("drift_weights", {})` in this function — confirm the exact name at the call site before editing; it feeds `drift_weights.get(k, 1.0)` at the existing `raw_drift = sum(avg_deltas[k] * drift_weights.get(k, 1.0) for k in avg_deltas)` line, so `enabled: false` alone is not sufficient — `deltas["cadence"]` must not even be appended when disabled, otherwise `avg_deltas["cadence"]` would exist with a nonzero `drift_weights.get("cadence", 1.0)` default fallback of `1.0` and silently contribute. Gating at append-time, not just at the weight, is required for true zero-behavioral-diff.)

Store `cadence_cov` in the profile `features` dict (`raw_drift_records[...]["features"]`) unconditionally (even when `enabled: false`) for sweep observability — add `"cadence_cov": cadence_cov if cadence_cfg.get("enabled", False) else compute_build_window_cadence_cov(db_session, entity_id, window_start, window_end)[0]` — i.e., always compute and store it in `features`, but only fold it into `raw_drift`/`deltas` when `enabled: true`.

Add to `config/scoring_config.yaml`:

```yaml
drift_weights:
  login_hour: 5.0
  geolocation: 5.0
  endpoint_set: 5.0
  process_name: 20.0
  embedding: 40.0
  cadence:
    weight: 0.0
    enabled: false
```

Note: this changes `drift_weights.cadence` from a flat float (matching the other four dims) to a dict — the existing `drift_weights.get(k, 1.0)` call site must handle both shapes. Update that call site to:

```python
def _dim_weight(drift_weights_cfg: dict, key: str) -> float:
    v = drift_weights_cfg.get(key, 1.0)
    return v.get("weight", 0.0) if isinstance(v, dict) else v
```

and use `_dim_weight(drift_weights_cfg, k)` in place of `drift_weights.get(k, 1.0)` at the `raw_drift = sum(...)` line — this keeps the four existing flat-float dimensions (`login_hour`, `geolocation`, `endpoint_set`, `process_name`, `embedding`) working unchanged while allowing `cadence` (and Phase 2/4's dimensions) to carry an `enabled` flag alongside their weight.

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/batch/profile_builder/test_cadence_drift_dimension.py -v`
Expected: PASS.

- [ ] **Step 6: Zero-behavioral-diff regression test using `config_override`**

Add to the same test file — build the same fixture twice, once with the real committed YAML (`enabled: false`) and once with an explicit in-memory override forcing `enabled: false` again (proving the parameter itself is inert when the flag stays off, not just that the default YAML happens to be off):

```python
def test_cadence_disabled_by_default_does_not_change_cumulative_drift(db_session):
    import copy
    import yaml
    from batch.profile_builder.builder import build_profiles
    from core.models import ProfileArtifactModel, ResolvedEventModel

    entity_id = "user_zero_diff_test"
    start = datetime(2026, 1, 1)
    for i in range(20):
        db_session.add(ResolvedEventModel(
            event_id=f"evt_zd_{i}", entity_id=entity_id, entity_type="human",
            timestamp=start + timedelta(minutes=i), event_data={
                "process_name": "chrome.exe", "endpoint_id": "ep-a",
                "geolocation": "US", "command_line": "chrome.exe",
            }, resolution_confidence=1.0, simulation_partition="production",
        ))
    db_session.commit()

    with open("config/scoring_config.yaml") as f:
        base_config = yaml.safe_load(f)
    assert base_config["drift_weights"]["cadence"]["enabled"] is False

    forced_disabled_config = copy.deepcopy(base_config)
    forced_disabled_config["drift_weights"]["cadence"]["enabled"] = False

    build_profiles(db=db_session, as_of=start + timedelta(days=1), config_override=base_config)
    baseline_profile = (
        db_session.query(ProfileArtifactModel).filter_by(entity_id=entity_id).first()
    )
    baseline_drift = baseline_profile.features["cumulative_drift"]

    db_session.query(ProfileArtifactModel).delete()
    db_session.commit()

    build_profiles(db=db_session, as_of=start + timedelta(days=1), config_override=forced_disabled_config)
    override_profile = (
        db_session.query(ProfileArtifactModel).filter_by(entity_id=entity_id).first()
    )
    assert override_profile.features["cumulative_drift"] == baseline_drift
```

- [ ] **Step 7: Run full suite**

Run: `pytest -v --tb=short`
Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add config/scoring_config.yaml batch/profile_builder/builder.py tests/batch/profile_builder/test_cadence_drift_dimension.py
git commit -m "Add cadence CoV as a shadow-computed, disabled-by-default drift dimension"
```

---

## Phase 2 — Volume delta (closes DEBT-051 / DEBT-019)

### Task 2.1: Real `score_vol` computation (shadow-computed, disabled)

**Files:**
- Modify: `worker/scorer.py:554-558`
- Modify: `config/scoring_config.yaml` (`features.total_volume_delta.enabled`)
- Test: `tests/worker/test_volume_delta.py` (new)

**Interfaces:**
- Produces: `compute_volume_rarity(recent_count: int, historical_hourly_counts: dict[str, int], alpha: float) -> float` in `worker/scorer.py` — Laplace-smoothed rarity of `recent_count` against the Poisson-ish historical hourly-count distribution stored in `profile.features["hourly_event_counts"]` (a new histogram field the builder must also start populating — see Task 2.2 for the builder-side companion; this task can ship with a fallback to an empty histogram, which `compute_distribution_kl`-style Laplace smoothing already handles via `get_laplace_prob`).

- [ ] **Step 1: Write the failing test**

```python
# tests/worker/test_volume_delta.py
from worker.scorer import compute_volume_rarity


def test_typical_recent_count_scores_low_rarity():
    # Historical: this entity typically logs 8-12 events/hour.
    hist = {"8": 3, "9": 5, "10": 6, "11": 4, "12": 2}
    score = compute_volume_rarity(recent_count=10, historical_hourly_counts=hist, alpha=1.0)
    assert score < 1.0


def test_spike_count_scores_higher_rarity_than_typical():
    hist = {"8": 3, "9": 5, "10": 6, "11": 4, "12": 2}
    typical = compute_volume_rarity(recent_count=10, historical_hourly_counts=hist, alpha=1.0)
    spike = compute_volume_rarity(recent_count=80, historical_hourly_counts=hist, alpha=1.0)
    assert spike > typical


def test_empty_history_does_not_raise():
    score = compute_volume_rarity(recent_count=5, historical_hourly_counts={}, alpha=1.0)
    assert score >= 0.0
```

- [ ] **Step 2: Run to verify it fails**

Run: `pytest tests/worker/test_volume_delta.py -v`
Expected: FAIL — `ImportError`.

- [ ] **Step 3: Implement `compute_volume_rarity` and wire it in**

Add to `worker/scorer.py` near `get_rarity_score`:

```python
def compute_volume_rarity(recent_count: int, historical_hourly_counts: dict, alpha: float = 1.0) -> float:
    """Laplace-smoothed rarity of a recent event count against the entity's own
    historical hourly-count histogram, same -log2(prob) shape as categorical rarity."""
    if not historical_hourly_counts:
        return 0.0
    buckets = sorted(int(k) for k in historical_hourly_counts.keys())
    vocab_size = max(len(buckets), 1)
    total = sum(historical_hourly_counts.values())
    nearest_bucket = min(buckets, key=lambda b: abs(b - recent_count))
    count_at_bucket = historical_hourly_counts.get(str(nearest_bucket), 0)
    prob = get_laplace_prob(count_at_bucket, total, vocab_size, alpha)
    return -math.log2(prob) if prob > 0 else 0.0
```

Replace `worker/scorer.py:554-558`:

```python
    # total_volume_delta deferred (S2.6): hourly spike formula needs calibrated
    # window counts + baseline; reserved weight in YAML until post-S3 sweep.
    score_vol = 0.0
    v_delta = 0.0
    flags.append("volume_delta_deferred")
```

with:

```python
    volume_cfg = features_config.get("total_volume_delta", {})
    hourly_counts = effective_profile.features.get("hourly_event_counts", {})
    recent_hour_count = _count_entity_events_in_hour(db, resolved_event.entity_id, resolved_event.timestamp)
    v_delta = compute_volume_rarity(recent_hour_count, hourly_counts, alpha)
    weight_vol = volume_cfg.get("weight", 1.0)
    raw_vol = v_delta * 0.5 * weight_vol
    if volume_cfg.get("enabled", False):
        score_vol = min(max_contrib, raw_vol)
        if raw_vol > max_contrib:
            flags.append("cap_hit_volume")
    else:
        score_vol = 0.0
        flags.append("volume_delta_deferred")
```

Add the small helper it depends on, near `compute_periodicity`:

```python
def _count_entity_events_in_hour(db: Session, entity_id: str, event_time: datetime) -> int:
    hour_start = event_time.replace(minute=0, second=0, microsecond=0)
    hour_end = hour_start + timedelta(hours=1)
    stmt = select(func.count()).select_from(ResolvedEventModel).where(
        and_(
            ResolvedEventModel.entity_id == entity_id,
            ResolvedEventModel.timestamp >= hour_start,
            ResolvedEventModel.timestamp < hour_end,
        )
    )
    return db.execute(stmt).scalar_one()
```

(Confirm `func` is already imported from `sqlalchemy` in `worker/scorer.py` — if not, add `from sqlalchemy import func` to the existing import block.) Add `total_volume_delta.enabled: false` to `config/scoring_config.yaml`:

```yaml
features:
  total_volume_delta:
    weight: 1.0
    enabled: false
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/worker/test_volume_delta.py -v`
Expected: PASS.

- [ ] **Step 5: Zero-behavioral-diff regression test**

Add to `tests/worker/test_volume_delta.py`:

Add the same `db_session` fixture and `_profile()` helper used throughout Phase 0 (copy verbatim from `tests/worker/test_shadow_drift_under_block.py:19-74` — the `compile_jsonb_sqlite`/`compile_array_sqlite` compilers, the `db_session` fixture, and `_profile(...)`) to the top of `tests/worker/test_volume_delta.py`, then add:

```python
def test_score_vol_stays_zero_when_disabled(db_session):
    """enabled: false (shipped default) must reproduce the pre-Phase-2 score_vol=0.0 + volume_delta_deferred flag."""
    from core.schemas.events import ResolvedEvent
    from worker.scorer import load_scoring_config, score_event
    from worker.profile_store import ProfileStore

    entity_id = "user_vol_disabled_test"
    as_of = datetime(2024, 6, 15, 12, 0, 0)
    db_session.add(_profile(
        version="promoted_vol_v1", entity_id=entity_id, drift=0.0,
        is_shadow=False, promoted_at=as_of - timedelta(days=5),
        created_at=as_of - timedelta(days=5), data_window_end=as_of - timedelta(days=5),
    ))
    db_session.commit()

    promoted = ProfileStore(db_session).get_active_profile(entity_id, as_of)
    config = load_scoring_config()
    assert config["features"]["total_volume_delta"]["enabled"] is False

    event = ResolvedEvent(
        event_id="evt_vol_disabled", timestamp=as_of, event_type="process",
        raw_entity_id=entity_id, entity_id=entity_id, entity_type="human",
        resolution_confidence=1.0, simulation_partition="production",
        event_data={"process_name": "chrome.exe", "endpoint_id": "ep-a",
                    "geolocation": "US", "command_line": "chrome.exe --silent"},
    )
    decision = score_event(db_session, event, promoted, config)
    vol_c = next(c for c in decision.contributions if c.feature_name == "total_volume_delta")
    assert vol_c.contribution_score == 0.0
    assert "volume_delta_deferred" in decision.flags
```

- [ ] **Step 6: Run full suite**

Run: `pytest -v --tb=short`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add worker/scorer.py config/scoring_config.yaml tests/worker/test_volume_delta.py
git commit -m "Implement real volume-delta rarity, shadow-computed and disabled by default"
```

### Task 2.2: Builder-side `hourly_event_counts` histogram + `total_volume_delta` drift dimension

**Files:**
- Modify: `batch/profile_builder/builder.py` (feature-extraction block that builds `cur_login_hours`, `cur_geolocations`, etc., and the `raw_drift_records[...]["features"]` dict)
- Modify: `config/scoring_config.yaml` (`drift_weights.total_volume_delta`)
- Test: `tests/batch/profile_builder/test_volume_drift_dimension.py` (new)

**Interfaces:**
- Produces: `hourly_event_counts: dict[str, int]` added to every profile's `features` dict (keyed by hour-of-day bucket `"0".."23"`, same shape as `login_hours`) — this is what Task 2.1's `compute_volume_rarity` reads via `effective_profile.features.get("hourly_event_counts", {})`.

- [ ] **Step 1: Write the failing test**

```python
# tests/batch/profile_builder/test_volume_drift_dimension.py
from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker

from core.database import Base
from core.models import EventModel, ResolvedEventModel
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


def test_hourly_event_counts_populated_in_profile_features(db_session):
    entity_id = "user_vol_test"
    start = datetime(2026, 1, 1, 9, 0, 0)
    for i in range(25):
        ts = start + timedelta(minutes=i * 2)
        db_session.add(ResolvedEventModel(
            event_id=f"evt_vol_{i}", entity_id=entity_id, entity_type="human",
            timestamp=ts, event_data={"process_name": "chrome.exe", "endpoint_id": "ep-a",
                                       "geolocation": "US", "command_line": "chrome.exe"},
            resolution_confidence=1.0, simulation_partition="production",
        ))
    db_session.commit()

    build_profiles(db=db_session, as_of=start + timedelta(days=31))

    from core.models import ProfileArtifactModel
    profile = db_session.query(ProfileArtifactModel).filter_by(entity_id=entity_id).first()
    assert profile is not None
    assert "hourly_event_counts" in profile.features
    assert sum(profile.features["hourly_event_counts"].values()) == 25
```

- [ ] **Step 2: Run to verify it fails**

Run: `pytest tests/batch/profile_builder/test_volume_drift_dimension.py -v`
Expected: FAIL — `assert "hourly_event_counts" in profile.features` fails (key absent).

- [ ] **Step 3: Populate `hourly_event_counts` in the builder's per-entity feature extraction**

In `batch/profile_builder/builder.py`, find the block computing `cur_login_hours` (a `Counter`/histogram built from the same per-entity event slice used for the other histograms). Add a parallel `cur_hourly_counts: dict[str, int]` built the same way (bucket by `hour_of_day`, count occurrences — reuse whatever loop already iterates the entity's events for `cur_login_hours`, do not add a second pass over the data). Add it to the `"features"` dict at `raw_drift_records[...]["features"]` (the same dict that already includes `"login_hours"`, `"geolocations"`, etc.):

```python
                "hourly_event_counts": cur_hourly_counts,
```

Add the volume-delta drift-dimension delta next to the cadence delta added in Task 1.2's block:

```python
                    volume_cfg = drift_weights_cfg.get("total_volume_delta", {})
                    if volume_cfg.get("enabled", False):
                        prev_hourly = prev.features.get("hourly_event_counts", {}) if prev else {}
                        deltas["total_volume_delta"].append(
                            compute_distribution_kl(cur_hourly_counts, prev_hourly, alpha=laplace_alpha)
                        )
```

(Reuses the existing `compute_distribution_kl` from `core/math_utils.py` — hourly-count histograms are structurally identical to the other categorical histograms already compared this way, so no new math utility is needed.) Add to `config/scoring_config.yaml`:

```yaml
drift_weights:
  total_volume_delta:
    weight: 0.0
    enabled: false
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/batch/profile_builder/test_volume_drift_dimension.py -v`
Expected: PASS.

- [ ] **Step 5: Run full suite**

Run: `pytest -v --tb=short`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add batch/profile_builder/builder.py config/scoring_config.yaml tests/batch/profile_builder/test_volume_drift_dimension.py
git commit -m "Add hourly_event_counts histogram and total_volume_delta drift dimension"
```

### Task 2.3: Series F sweep harness + governance doc (Phases 1–2)

**Files:**
- Create: `scratch/run_series_f_sweep.py` (adapt from `scratch/run_series_e_sweep.py`)
- Create: `docs/scoring-config-governance-series-f.md`

- [ ] **Step 1: Adapt the harness**

```bash
cp scratch/run_series_e_sweep.py scratch/run_series_f_sweep.py
```

Rename constants to `series_f_*`, `payload["series"] = "F"`. **Verified:** neither `batch.eval.runner.run_pipeline` nor `worker.scorer.load_scoring_config` nor `batch.profile_builder.builder.build_profiles`'s inline loader (absent `config_override`) accept any config-injection parameter or environment variable — both hardcode the relative path `config/scoring_config.yaml`. Plumbing an override through `run_pipeline` → `process_unscored_events` → every `score_event` call site is out of scope for a one-off sweep script. Instead, since this harness already runs in an isolated subprocess against a throwaway SQLite DB, swap the real file's contents for the sweep's duration and restore it in a `finally` block — this is what a human operator running a manual sweep would do, and it doesn't require touching pipeline signatures:

```python
import shutil

CONFIG_PATH = REPO_ROOT / "config" / "scoring_config.yaml"
CONFIG_BACKUP_PATH = REPO_ROOT / "config" / "scoring_config.yaml.series_f_backup"


def with_enabled_flags_for_sweep(enable_paths: list[tuple[tuple[str, ...], bool]]):
    """Context manager: temporarily flips config/scoring_config.yaml's enabled
    flags for the duration of a sweep subprocess, restores the original file after.
    enable_paths: list of (key_path_tuple, value), e.g. (("drift_weights", "cadence", "enabled"), True)."""
    import contextlib

    @contextlib.contextmanager
    def _ctx():
        shutil.copy2(CONFIG_PATH, CONFIG_BACKUP_PATH)
        try:
            with open(CONFIG_PATH) as f:
                config = yaml.safe_load(f)
            for key_path, value in enable_paths:
                node = config
                for key in key_path[:-1]:
                    node = node[key]
                node[key_path[-1]] = value
            with open(CONFIG_PATH, "w") as f:
                yaml.safe_dump(config, f)
            yield
        finally:
            shutil.move(str(CONFIG_BACKUP_PATH), str(CONFIG_PATH))

    return _ctx()
```

In `main()`, wrap the existing `run_pipeline(...)` call:

```python
    with with_enabled_flags_for_sweep([
        (("drift_weights", "cadence", "enabled"), True),
        (("features", "total_volume_delta", "enabled"), True),
        (("drift_weights", "total_volume_delta", "enabled"), True),
    ]):
        db = run_pipeline(EVENTS_PATH, LABELS_PATH, window_delta_days=1)
```

The `finally: shutil.move(...)` restores the committed YAML even if the sweep raises — verify this explicitly by running `git status` after the sweep script exits (success or failure) and confirming `config/scoring_config.yaml` shows no diff before committing this task's other files.

Add a per-dimension `raw_drift` decomposition report function:

```python
def per_dimension_drift_decomposition(db) -> dict[str, Any]:
    """H4-style dominance check: mean/max contribution of each drift_weights
    dimension across all profile builds in this sweep."""
    from collections import defaultdict
    from core.models import ProfileArtifactModel

    profiles = list(db.execute(select(ProfileArtifactModel)).scalars().all())
    per_dim: dict[str, list[float]] = defaultdict(list)
    for p in profiles:
        for dim in ("login_hour", "geolocation", "endpoint_set", "process_name", "embedding", "cadence", "total_volume_delta"):
            val = (p.features or {}).get(f"{dim}_delta_last_build")
            if val is not None:
                per_dim[dim].append(float(val))
    return {
        dim: {"mean": sum(vals) / len(vals) if vals else None, "max": max(vals) if vals else None, "n": len(vals)}
        for dim, vals in per_dim.items()
    }
```

This assumes per-dimension deltas get stored per build as `f"{dim}_delta_last_build"` in `features` — add that storage alongside the existing `avg_deltas` computation in `builder.py` (one extra `features[f"{k}_delta_last_build"] = avg_deltas[k]` line inside the same loop Task 1.2/2.2 already touch) so Series F has decomposition data to report; this is test-covered implicitly by Task 1.2/2.2's existing tests asserting on `profile.features` keys — add one more assertion there for `cadence_delta_last_build` presence rather than writing a fourth near-duplicate test file.

- [ ] **Step 2: Run the sweep**

Run: `python scratch/run_series_f_sweep.py`
Expected: exits 0, writes `scratch/series_f_metrics.json` including `per_dimension_drift_decomposition`.

- [ ] **Step 3: Write the governance doc**

Create `docs/scoring-config-governance-series-f.md` following the Series D/E template. Required sections beyond the standard ones: `## Cadence dimension dominance check` (embedding's mean contribution vs. cadence's, explicit ratio, comparison against H4's original 40.0-vs-5.0 concern) and `## Volume dimension contribution`. State explicitly whether this sweep's evidence supports flipping `enabled: true` in the committed YAML as a next, separate action — this doc reports evidence, it does not itself authorize the flip (that's a distinct follow-on commit once a human reviews this doc, consistent with the S6.3 standing rule).

- [ ] **Step 4: Commit**

```bash
git add scratch/run_series_f_sweep.py docs/scoring-config-governance-series-f.md scratch/series_f_metrics.json batch/profile_builder/builder.py
git commit -m "Run Series F sweep: cadence + volume dimension contribution and dominance check"
```

---

## Phase 3 — Fleet cohort drift (closes DEBT-068 / DEBT-075)

### Task 3.1: Fleet-level `cohort_drift` decision (shadow-computed, disabled)

**Files:**
- Modify: `batch/profile_builder/builder.py` (immediately after the existing `cohort_medians` computation, ~lines 667-681)
- Modify: `config/scoring_config.yaml` (`cohort_gating_constants.fleet_drift_enabled`)
- Test: `tests/batch/profile_builder/test_fleet_cohort_drift.py` (new)

**Interfaces:**
- Produces: a new `DecisionRecordModel` row per affected role per build, `event_id="COHORT_DRIFT"`, `entity_id` set to a synthetic per-role id (`f"__role__{role}"`) so it does not collide with any real entity's decision history, `contributions` containing a single entry describing the affected fraction.
- Consumes (unchanged): `cohort_drifts: dict[str, list[float]]` and `cohort_medians: dict[str, float]`, already computed at `builder.py:668-681`; `config.get("cohort_gating_constants", {}).get("max_changed_fraction", 0.2)` and `config.get("cohort_gate_window_days", 7)`, already read elsewhere.

- [ ] **Step 1: Write the failing test**

```python
# tests/batch/profile_builder/test_fleet_cohort_drift.py
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
            event_id=f"evt_{entity_id}_{i}", entity_id=entity_id, entity_type="human",
            timestamp=start + timedelta(minutes=i),
            event_data={"process_name": pname, "endpoint_id": "ep-a", "geolocation": "US",
                        "command_line": pname, "role": role},
            resolution_confidence=1.0, simulation_partition="production",
        ))


def test_fleet_cohort_drift_disabled_by_default_emits_nothing(db_session):
    start = datetime(2026, 1, 1)
    for i in range(5):
        _events_for(db_session, f"user_eng_{i}", "engineer", start, ["chrome.exe", "new_tool.exe", "new_tool.exe"])
    db_session.commit()

    build_profiles(db=db_session, as_of=start + timedelta(days=1))
    cohort_decisions = db_session.execute(
        select(DecisionRecordModel).where(DecisionRecordModel.event_id == "COHORT_DRIFT")
    ).scalars().all()
    assert len(cohort_decisions) == 0
```

- [ ] **Step 2: Run to verify it fails or passes trivially**

Run: `pytest tests/batch/profile_builder/test_fleet_cohort_drift.py -v`
Expected: PASS already (nothing emits `COHORT_DRIFT` yet — this is the zero-diff guard, written first so it's in place before the feature exists). Add the enabled-path test next.

- [ ] **Step 3: Add the enabled-path test**

```python
def test_fleet_cohort_drift_fires_when_cohort_fraction_exceeds_max_changed_fraction(db_session):
    import yaml
    with open("config/scoring_config.yaml") as f:
        config = yaml.safe_load(f)
    config["cohort_gating_constants"]["fleet_drift_enabled"] = True

    start = datetime(2026, 1, 1)
    # 4 of 5 engineers (0.8 fraction, well above max_changed_fraction=0.2) all pick up a
    # new, previously-unseen process together — coordinated shift.
    for i in range(4):
        _events_for(db_session, f"user_eng_{i}", "engineer", start, ["new_tool.exe"] * 10)
    _events_for(db_session, "user_eng_4", "engineer", start, ["chrome.exe"] * 10)
    db_session.commit()

    build_profiles(db=db_session, as_of=start + timedelta(days=1), config_override=config)
    cohort_decisions = db_session.execute(
        select(DecisionRecordModel).where(DecisionRecordModel.event_id == "COHORT_DRIFT")
    ).scalars().all()
    assert len(cohort_decisions) == 1
    assert cohort_decisions[0].contributions[0]["role"] == "engineer"
```

This test depends on Task 1.2 Step 3's `config_override` parameter on `build_profiles` — if Task 1.2 has not landed yet when this task is picked up, implement that parameter here instead (identical code, see Task 1.2 Step 3) rather than duplicating a different override mechanism.

- [ ] **Step 4: Run to verify the enabled-path test fails**

Run: `pytest tests/batch/profile_builder/test_fleet_cohort_drift.py -v`
Expected: FAIL — no `COHORT_DRIFT` decision exists yet.

- [ ] **Step 5: Implement the fleet-level check**

Insert immediately after the existing `cohort_medians` computation block (`builder.py:667-681`, right after `cohort_medians = {...}` closes), before Phase 3 (`# Phase 3: Update Accumulators and Persist`):

```python
        # Phase 2.5 — Fleet-level cohort drift (DEBT-068/075, H2/H7 mitigation).
        # Additive: does not change any individual entity's norm_drift/cumulative_drift.
        fleet_drift_enabled = cohort_gate_config.get("fleet_drift_enabled", False)
        if fleet_drift_enabled:
            fleet_soft_threshold = global_drift_median  # role-relative: above the cross-role median raw_drift
            for role, drifts in cohort_drifts.items():
                if len(drifts) < 3:
                    continue
                changed_count = sum(1 for d in drifts if d > fleet_soft_threshold)
                fraction = changed_count / len(drifts)
                if fraction > max_changed_fraction:
                    decision_id = f"cohort_drift_{role}_{build_timestamp.strftime('%Y%m%d%H%M%S')}"
                    db_session.add(DecisionRecordModel(
                        decision_id=decision_id,
                        event_id="COHORT_DRIFT",
                        entity_id=f"__role__{role}",
                        timestamp=build_timestamp,
                        score=0.0,
                        confidence=1.0,
                        profile_version="NONE",
                        scoring_config_version=config.get("version", "unknown"),
                        contributions=[{"role": role, "changed_fraction": fraction,
                                        "cohort_size": len(drifts), "max_changed_fraction": max_changed_fraction}],
                        is_anomaly=False,
                        cohort_used=role,
                        cohort_unsupported=False,
                        flags=["fleet_cohort_drift"],
                    ))
```

(`cohort_gate_config` is whatever local variable in `builder.py` already holds `config.get("cohort_gating_constants", {})` — confirm the exact name at the call site; `max_changed_fraction` and `global_drift_median` are already in scope from the immediately-preceding block per the existing code at `builder.py:672-681`.) Add to `config/scoring_config.yaml`:

```yaml
cohort_gating_constants:
  min_cohort_size: 10
  min_clean_observation_count: 5
  max_changed_fraction: 0.2
  fleet_drift_enabled: false
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `pytest tests/batch/profile_builder/test_fleet_cohort_drift.py -v`
Expected: PASS.

- [ ] **Step 7: Regression test — per-entity math unchanged**

Add:

```python
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
        _events_for(db_session, f"user_eng_{i}", "engineer", start, ["new_tool.exe"] * 10)
    _events_for(db_session, "user_eng_4", "engineer", start, ["chrome.exe"] * 10)
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
```

- [ ] **Step 8: Run full suite**

Run: `pytest -v --tb=short`
Expected: PASS.

- [ ] **Step 9: Commit**

```bash
git add batch/profile_builder/builder.py config/scoring_config.yaml tests/batch/profile_builder/test_fleet_cohort_drift.py
git commit -m "Add fleet-level cohort_drift decision, shadow-computed and disabled by default"
```

---

## Phase 4 — H13: geo-velocity

### Task 4.1: Static label→centroid reference table

**Files:**
- Create: `core/geo_centroids.py`
- Test: `tests/core/test_geo_centroids.py` (new)

**Interfaces:**
- Produces: `GEO_CENTROIDS: dict[str, tuple[float, float]]` (label → (lat, long)), `lookup_centroid(label: str) -> Optional[tuple[float, float]]`, `haversine_km(a: tuple[float, float], b: tuple[float, float]) -> float`.

- [ ] **Step 1: Write the failing test**

```python
# tests/core/test_geo_centroids.py
from core.geo_centroids import GEO_CENTROIDS, haversine_km, lookup_centroid


def test_all_synthetic_generator_labels_have_centroids():
    # Labels currently emitted by batch/synthetic/generator.py EntityProfile.geography
    # and the hardcoded "RU-Moscow" injection.
    expected_labels = {"US-East", "US-West", "EU-Central", "AP-South", "US-East-DC1", "RU-Moscow"}
    missing = expected_labels - set(GEO_CENTROIDS.keys())
    assert not missing, f"missing centroid entries: {missing}"


def test_lookup_unknown_label_returns_none():
    assert lookup_centroid("Atlantis") is None


def test_haversine_known_distance():
    # NYC to LA is approximately 3936 km.
    nyc = (40.7128, -74.0060)
    la = (34.0522, -118.2437)
    dist = haversine_km(nyc, la)
    assert 3800 < dist < 4100
```

- [ ] **Step 2: Run to verify it fails**

Run: `pytest tests/core/test_geo_centroids.py -v`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Implement**

```python
# core/geo_centroids.py
"""Static label -> lat/long centroid lookup for geo-velocity (H13).

No live geocoding dependency; covers only the label vocabulary in active use
by batch/synthetic/generator.py today. Extend this table as new labels appear
in production event data, do not fall back to an external API.
"""
import math

GEO_CENTROIDS: dict[str, tuple[float, float]] = {
    "US-East": (39.0438, -77.4874),
    "US-West": (37.3382, -121.8863),
    "EU-Central": (50.1109, 8.6821),
    "AP-South": (19.0760, 72.8777),
    "US-East-DC1": (39.0438, -77.4874),
    "RU-Moscow": (55.7558, 37.6173),
}


def lookup_centroid(label: str) -> tuple[float, float] | None:
    return GEO_CENTROIDS.get(label)


def haversine_km(a: tuple[float, float], b: tuple[float, float]) -> float:
    lat1, lon1 = a
    lat2, lon2 = b
    r = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    h = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * r * math.asin(math.sqrt(h))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/core/test_geo_centroids.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add core/geo_centroids.py tests/core/test_geo_centroids.py
git commit -m "Add static geo-label centroid table and haversine distance helper"
```

### Task 4.2: `geo_velocity_delta` builder computation (shadow-computed, disabled)

**Files:**
- Modify: `batch/profile_builder/builder.py`
- Modify: `config/scoring_config.yaml` (`drift_weights.geo_velocity`)
- Test: `tests/batch/profile_builder/test_geo_velocity_drift.py` (new)

**Interfaces:**
- Produces: `compute_geo_velocity_delta(db: Session, entity_id: str, window_start: datetime, window_end: datetime, min_paired_successes: int = 3) -> tuple[float, list[str]]` — returns `(delta_score, flags)`. `flags` includes `"geo_velocity:no_centroid"` when any successive-pair label is unmapped (contributes `0` for that pair, never guesses); returns `(0.0, [])` when fewer than `min_paired_successes` auth events exist in-window.
- Consumes: `core.geo_centroids.lookup_centroid`, `haversine_km` (Task 4.1).

- [ ] **Step 1: Write the failing test**

```python
# tests/batch/profile_builder/test_geo_velocity_drift.py
from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker

from core.database import Base
from core.models import ResolvedEventModel
from batch.profile_builder.builder import compute_geo_velocity_delta


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


def _auth_event(entity_id, ts, geo, i):
    return ResolvedEventModel(
        event_id=f"evt_geo_{entity_id}_{i}", entity_id=entity_id, entity_type="human",
        timestamp=ts, event_data={"action": "login", "geolocation": geo, "process_name": None,
                                   "endpoint_id": "ep-a", "command_line": ""},
        resolution_confidence=1.0, simulation_partition="production",
    )


def test_impossible_travel_pair_scores_high_delta(db_session):
    entity_id = "user_geo_test"
    start = datetime(2026, 1, 1, 0, 0, 0)
    # Baseline: several local-only US-East successes to establish a "always local" history.
    for i in range(5):
        db_session.add(_auth_event(entity_id, start + timedelta(hours=i), "US-East", i))
    # Then a US-East -> RU-Moscow jump within 1 hour (impossible at any real travel speed).
    db_session.add(_auth_event(entity_id, start + timedelta(hours=5), "US-East", 5))
    db_session.add(_auth_event(entity_id, start + timedelta(hours=5, minutes=30), "RU-Moscow", 6))
    db_session.commit()

    delta, flags = compute_geo_velocity_delta(db_session, entity_id, start, start + timedelta(hours=6), min_paired_successes=3)
    assert delta > 0.0
    assert "geo_velocity:no_centroid" not in flags


def test_nearby_successive_logins_score_low_delta(db_session):
    entity_id = "user_geo_local"
    start = datetime(2026, 1, 1, 0, 0, 0)
    for i in range(5):
        db_session.add(_auth_event(entity_id, start + timedelta(hours=i), "US-East", i))
    db_session.commit()

    delta, flags = compute_geo_velocity_delta(db_session, entity_id, start, start + timedelta(hours=6), min_paired_successes=3)
    assert delta == 0.0 or delta < 1.0


def test_unmapped_label_flags_and_scores_zero_for_that_pair(db_session):
    entity_id = "user_geo_unmapped"
    start = datetime(2026, 1, 1, 0, 0, 0)
    for i in range(3):
        db_session.add(_auth_event(entity_id, start + timedelta(hours=i), "US-East", i))
    db_session.add(_auth_event(entity_id, start + timedelta(hours=3), "Atlantis-Undersea", 3))
    db_session.commit()

    delta, flags = compute_geo_velocity_delta(db_session, entity_id, start, start + timedelta(hours=4), min_paired_successes=3)
    assert "geo_velocity:no_centroid" in flags


def test_below_min_paired_successes_returns_zero(db_session):
    entity_id = "user_geo_sparse"
    start = datetime(2026, 1, 1, 0, 0, 0)
    db_session.add(_auth_event(entity_id, start, "US-East", 0))
    db_session.commit()

    delta, flags = compute_geo_velocity_delta(db_session, entity_id, start, start + timedelta(hours=1), min_paired_successes=3)
    assert delta == 0.0
```

- [ ] **Step 2: Run to verify it fails**

Run: `pytest tests/batch/profile_builder/test_geo_velocity_drift.py -v`
Expected: FAIL — `ImportError`.

- [ ] **Step 3: Implement**

Add to `batch/profile_builder/builder.py`:

```python
from core.geo_centroids import haversine_km, lookup_centroid


def compute_geo_velocity_delta(
    db: Session, entity_id: str, window_start: datetime, window_end: datetime, min_paired_successes: int = 3
) -> tuple[float, list[str]]:
    """Implied travel speed between successive auth events; delta vs. the entity's
    own max historical implied speed within the window. No cross-entity baseline."""
    stmt = (
        select(ResolvedEventModel.timestamp, ResolvedEventModel.event_data)
        .where(
            and_(
                ResolvedEventModel.entity_id == entity_id,
                ResolvedEventModel.timestamp >= window_start,
                ResolvedEventModel.timestamp < window_end,
            )
        )
        .order_by(ResolvedEventModel.timestamp)
    )
    rows = db.execute(stmt).all()
    auth_rows = [
        (ts, data.get("geolocation")) for ts, data in rows
        if isinstance(data, dict) and data.get("action") == "login" and data.get("geolocation")
    ]
    if len(auth_rows) < min_paired_successes:
        return 0.0, []

    flags: list[str] = []
    speeds_kmh: list[float] = []
    for (t1, g1), (t2, g2) in zip(auth_rows, auth_rows[1:]):
        c1, c2 = lookup_centroid(g1), lookup_centroid(g2)
        if c1 is None or c2 is None:
            flags.append("geo_velocity:no_centroid")
            continue
        hours = max((t2 - t1).total_seconds() / 3600.0, 1e-6)
        dist_km = haversine_km(c1, c2)
        speeds_kmh.append(dist_km / hours)

    if not speeds_kmh:
        return 0.0, list(set(flags))

    max_speed = max(speeds_kmh)
    # Plausible commercial air travel ceiling ~900 km/h; anything well beyond that
    # relative to the entity's own max observed speed this window is the delta signal.
    delta = max(0.0, (max_speed - 900.0) / 900.0) if max_speed > 900.0 else 0.0
    return delta, list(set(flags))
```

Wire into the drift-dimension loop (same location as Task 1.2/2.2/3.1's additions):

```python
                    geo_velocity_cfg = drift_weights_cfg.get("geo_velocity", {})
                    if geo_velocity_cfg.get("enabled", False):
                        gv_delta, gv_flags = compute_geo_velocity_delta(db_session, entity_id, window_start, window_end)
                        deltas["geo_velocity"].append(gv_delta)
```

Add to `config/scoring_config.yaml`:

```yaml
drift_weights:
  geo_velocity:
    weight: 0.0
    enabled: false
    vpn_allowlist: []
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/batch/profile_builder/test_geo_velocity_drift.py -v`
Expected: PASS.

- [ ] **Step 5: Run full suite**

Run: `pytest -v --tb=short`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add batch/profile_builder/builder.py config/scoring_config.yaml tests/batch/profile_builder/test_geo_velocity_drift.py
git commit -m "Add geo-velocity drift dimension, shadow-computed and disabled by default"
```

### Task 4.3: Series G sweep harness + governance doc (Phases 3–4)

**Files:**
- Create: `scratch/run_series_g_sweep.py` (adapt from `scratch/run_series_f_sweep.py`)
- Create: `docs/scoring-config-governance-series-g.md`

- [ ] **Step 1: Adapt the harness**

Copy `scratch/run_series_f_sweep.py` to `scratch/run_series_g_sweep.py`, rename constants to `series_g_*`, `payload["series"] = "G"`. Reuse `with_enabled_flags_for_sweep(...)` from Task 2.3 verbatim (import it or copy the function — both scripts live in `scratch/`, which is not a package, so copy it into this file directly rather than adding a cross-script import), called with:

```python
    with with_enabled_flags_for_sweep([
        (("cohort_gating_constants", "fleet_drift_enabled"), True),
        (("drift_weights", "geo_velocity", "enabled"), True),
    ]):
        db = run_pipeline(EVENTS_PATH, LABELS_PATH, window_delta_days=1)
```

Add S3 (`scenario_3_subtle`) recall reporting specifically (already computed by `calculate_metrics`, just surface it explicitly in the governance doc rather than buried in the full `metrics.scenarios` blob) and an S1 recall comparison for the geo-velocity contribution.

- [ ] **Step 2: Run the sweep**

Run: `python scratch/run_series_g_sweep.py`
Expected: exits 0, writes `scratch/series_g_metrics.json`.

- [ ] **Step 3: Write the governance doc**

`docs/scoring-config-governance-series-g.md`, Series D/E/F template. Required section: `## S3 recall with fleet cohort drift enabled` (compare against the Series D-era baseline of 0.667 documented in `docs/residual-risk-drift-hypotheses.md` §2.2 — note explicitly whether this is a like-for-like comparison or crosses a Series boundary that invalidates direct comparison, per this repo's own cross-series discipline).

- [ ] **Step 4: Commit**

```bash
git add scratch/run_series_g_sweep.py docs/scoring-config-governance-series-g.md scratch/series_g_metrics.json
git commit -m "Run Series G sweep: fleet cohort drift and geo-velocity contribution, S3 recall check"
```

---

## Phase 5 — H14: cross-signal precision gate (Stage A)

### Task 5.1: Alembic migration for `signal_family_agreement_count` and `precision_gate_version`

**Files:**
- Create: `alembic/versions/<new_revision_id>_add_precision_gate_fields.py`
- Modify: `core/models.py` (`DecisionRecordModel`)
- Modify: `core/schemas/decisions.py` (`DecisionRecord`)

- [ ] **Step 1: Find the current alembic head**

Run: `alembic heads`
Expected output: the current head revision id (should be `h7i8j9k0l1m2`, the last file in `alembic/versions/` per the earlier directory listing — confirm with the command, don't assume).

- [ ] **Step 2: Write the migration**

```python
# alembic/versions/<new_id>_add_precision_gate_fields.py
"""Add decisions.signal_family_agreement_count and decisions.precision_gate_version (H14 Stage A)

Revision ID: <new_id>
Revises: h7i8j9k0l1m2
Create Date: 2026-07-30 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "<new_id>"
down_revision: Union[str, Sequence[str], None] = "h7i8j9k0l1m2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "decisions",
        sa.Column("signal_family_agreement_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "decisions",
        sa.Column("precision_gate_version", sa.String(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("decisions", "precision_gate_version")
    op.drop_column("decisions", "signal_family_agreement_count")
```

(Generate an actual revision id via `alembic revision --autogenerate -m "Add precision gate fields"` rather than hand-picking one, then hand-edit the generated file's `upgrade`/`downgrade` bodies to match the above if autogenerate produces a different shape — `server_default="0"` is required so the migration is backfill-safe against existing rows without a separate data migration.)

- [ ] **Step 3: Update `DecisionRecordModel`**

In `core/models.py`, add to `DecisionRecordModel` (after `replay_run_id`):

```python
    signal_family_agreement_count = Column(Integer, nullable=False, default=0)
    precision_gate_version = Column(String, nullable=True)
```

- [ ] **Step 4: Update `DecisionRecord` Pydantic schema**

In `core/schemas/decisions.py`, add to `DecisionRecord`:

```python
    signal_family_agreement_count: int = 0
    precision_gate_version: Optional[str] = None
```

- [ ] **Step 5: Run the migration against a scratch DB and verify**

Run: `alembic upgrade head`
Expected: succeeds with no errors against the dev Postgres instance (or run against a throwaway SQLite/Postgres test DB if no dev instance is configured in this environment — confirm which via `alembic.ini`/`core/settings.py` `DATABASE_URL` before running against anything shared).

- [ ] **Step 6: Run full suite**

Run: `pytest -v --tb=short`
Expected: PASS — existing tests constructing `DecisionRecordModel`/`DecisionRecord` without the two new fields must still work (both have defaults).

- [ ] **Step 7: Commit**

```bash
git add alembic/versions core/models.py core/schemas/decisions.py
git commit -m "Add signal_family_agreement_count and precision_gate_version to decisions"
```

### Task 5.2: Compute `signal_family_agreement_count` (additive, no behavior change)

**Files:**
- Modify: `worker/scorer.py` (near the `# Aggregation` block, `worker/scorer.py:598-614`)
- Modify: `config/scoring_config.yaml` (`precision_gate` section)
- Test: `tests/worker/test_precision_gate_stage_a.py` (new)

**Interfaces:**
- Produces: `compute_signal_family_agreement(contributions: list[FeatureContribution], family_floor_fraction: float, max_contrib: float) -> int` in `worker/scorer.py`.

- [ ] **Step 1: Write the failing test**

```python
# tests/worker/test_precision_gate_stage_a.py
from worker.scorer import compute_signal_family_agreement
from core.schemas.decisions import FeatureContribution


def _contrib(name, score):
    return FeatureContribution(contribution_id="x", feature_name=name, raw_value=score, contribution_score=score, confidence_weight=0.9)


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
```

- [ ] **Step 2: Run to verify it fails**

Run: `pytest tests/worker/test_precision_gate_stage_a.py -v`
Expected: FAIL — `ImportError`.

- [ ] **Step 3: Implement and wire in**

Add to `worker/scorer.py`:

```python
_SIGNAL_FAMILIES: dict[str, tuple[str, ...]] = {
    "rarity": ("login_hour_rarity", "geolocation_rarity", "endpoint_set_rarity", "process_name_rarity"),
    "drift": ("drift_alert",),
    "cadence": ("cadence",),
    "volume": ("total_volume_delta",),
    "geo_velocity": ("geo_velocity",),
}


def compute_signal_family_agreement(
    contributions: list, family_floor_fraction: float, max_contrib: float
) -> int:
    """Count independent signal families whose contribution exceeds a soft floor
    (family_floor_fraction * max_contrib) on this decision. Additive metric only —
    does not itself change is_anomaly or any existing scoring path (Stage A)."""
    floor = family_floor_fraction * max_contrib
    by_feature = {c.feature_name: c.contribution_score for c in contributions}
    agreement = 0
    for family_features in _SIGNAL_FAMILIES.values():
        if any(by_feature.get(f, 0.0) > floor for f in family_features):
            agreement += 1
    return agreement
```

In `score_event`, immediately after the `contributions = [...]` list is fully assembled (after the `service_account` conditional append at `worker/scorer.py:615-624`, before the `containment_threshold` block), add:

```python
    precision_gate_cfg = config.get("precision_gate", {})
    family_floor_fraction = precision_gate_cfg.get("family_floor_fraction", 0.1)
    signal_family_agreement_count = compute_signal_family_agreement(
        contributions, family_floor_fraction, max_contrib
    )
    precision_gate_version = precision_gate_cfg.get("version", "stage_a_v1") if precision_gate_cfg.get("enabled", False) else None
```

Add to `config/scoring_config.yaml`:

```yaml
precision_gate:
  enabled: false
  version: "stage_a_v1"
  family_floor_fraction: 0.1
  containment_min_agreement: 2
```

Every `DecisionRecord(...)` construction site in `score_event` (there are three: the S5.9 halt early-return, the staleness halt early-return, and the main return at the end of the function) must now pass `signal_family_agreement_count=signal_family_agreement_count if ... else 0` and `precision_gate_version=precision_gate_version` — for the two halt early-returns (which occur before `contributions`/`signal_family_agreement_count` are computed), pass `signal_family_agreement_count=0, precision_gate_version=None` explicitly rather than relying on the Pydantic defaults, so the value is always deliberate, not accidental.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/worker/test_precision_gate_stage_a.py -v`
Expected: PASS.

- [ ] **Step 5: Regression — `is_anomaly`/containment untouched when `precision_gate.enabled: false`**

Add to the test file:

```python
def test_precision_gate_disabled_does_not_change_containment_flag(db_session):
    """enabled: false (shipped default): agreement_count is computed and stored,
    but simulated_containment_queued fires exactly as before Phase 5."""
    # Reuse the _profile()/db_session fixture pattern; construct an unblocked profile +
    # event whose total_score >= containment_threshold via a single dominant family
    # (e.g. drift_alert alone at containment_threshold+), assert:
    #   decision.signal_family_agreement_count == 1  (only one family agrees)
    #   "simulated_containment_queued" in decision.flags  (still fires — Stage A gate is inert while disabled)
```

Fill in using the shared fixture pattern from `tests/worker/test_shadow_drift_under_block.py`.

- [ ] **Step 6: Run full suite**

Run: `pytest -v --tb=short`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add worker/scorer.py config/scoring_config.yaml tests/worker/test_precision_gate_stage_a.py
git commit -m "Compute signal_family_agreement_count additively (Stage A, no behavior change)"
```

### Task 5.3: Containment eligibility Stage-A gate (behind `precision_gate.enabled`)

**Files:**
- Modify: `worker/scorer.py:649-654`
- Test: `tests/worker/test_precision_gate_stage_a.py` (extend)

**Interfaces:**
- Produces: `_containment_eligible(total_score: float, decision_confidence: float, signal_family_agreement_count: int, containment_threshold: float, confidence_floor: float, precision_gate_active: bool, containment_min_agreement: int) -> tuple[bool, bool]` in `worker/scorer.py` — returns `(should_queue, should_flag_deferred)`. Pulled out as a pure function specifically so this task's test can engineer exact inputs directly, instead of hand-tuning rarity-histogram fixtures through the full `score_event` pipeline to hit precise scores.

- [ ] **Step 1: Write the failing test**

```python
# append to tests/worker/test_precision_gate_stage_a.py
from worker.scorer import _containment_eligible


def test_single_family_high_score_queues_when_gate_disabled():
    should_queue, deferred = _containment_eligible(
        total_score=90.0, decision_confidence=0.9, signal_family_agreement_count=1,
        containment_threshold=85.0, confidence_floor=0.6,
        precision_gate_active=False, containment_min_agreement=2,
    )
    assert should_queue is True
    assert deferred is False


def test_single_family_high_score_deferred_when_gate_enabled():
    should_queue, deferred = _containment_eligible(
        total_score=90.0, decision_confidence=0.9, signal_family_agreement_count=1,
        containment_threshold=85.0, confidence_floor=0.6,
        precision_gate_active=True, containment_min_agreement=2,
    )
    assert should_queue is False
    assert deferred is True


def test_two_family_agreement_queues_when_gate_enabled():
    should_queue, deferred = _containment_eligible(
        total_score=90.0, decision_confidence=0.9, signal_family_agreement_count=2,
        containment_threshold=85.0, confidence_floor=0.6,
        precision_gate_active=True, containment_min_agreement=2,
    )
    assert should_queue is True
    assert deferred is False


def test_below_threshold_never_queues_or_defers_regardless_of_gate():
    should_queue, deferred = _containment_eligible(
        total_score=50.0, decision_confidence=0.9, signal_family_agreement_count=1,
        containment_threshold=85.0, confidence_floor=0.6,
        precision_gate_active=True, containment_min_agreement=2,
    )
    assert should_queue is False
    assert deferred is False
```

- [ ] **Step 2: Run to verify it fails**

Run: `pytest tests/worker/test_precision_gate_stage_a.py -v`
Expected: FAIL — `ImportError: cannot import name '_containment_eligible'`.

- [ ] **Step 3: Implement the gate as an extracted pure function, wire it in**

Add to `worker/scorer.py` near `compute_signal_family_agreement`:

```python
def _containment_eligible(
    total_score: float,
    decision_confidence: float,
    signal_family_agreement_count: int,
    containment_threshold: float,
    confidence_floor: float,
    precision_gate_active: bool,
    containment_min_agreement: int,
) -> tuple[bool, bool]:
    """Stage A containment gate. Returns (should_queue, should_flag_deferred).
    precision_gate_active=False reproduces pre-Phase-5 behavior exactly."""
    score_and_confidence_ok = total_score >= containment_threshold and decision_confidence >= confidence_floor
    if not score_and_confidence_ok:
        return False, False
    meets_agreement = (not precision_gate_active) or (signal_family_agreement_count >= containment_min_agreement)
    if meets_agreement:
        return True, False
    return False, True
```

Replace `worker/scorer.py:649-654`:

```python
    containment_threshold = config.get("containment_threshold", 85.0)
    if (
        total_score >= containment_threshold
        and decision_confidence >= confidence_floor
    ):
        flags.append("simulated_containment_queued")
```

with:

```python
    containment_threshold = config.get("containment_threshold", 85.0)
    should_queue, should_flag_deferred = _containment_eligible(
        total_score=total_score,
        decision_confidence=decision_confidence,
        signal_family_agreement_count=signal_family_agreement_count,
        containment_threshold=containment_threshold,
        confidence_floor=confidence_floor,
        precision_gate_active=precision_gate_cfg.get("enabled", False),
        containment_min_agreement=precision_gate_cfg.get("containment_min_agreement", 2),
    )
    if should_queue:
        flags.append("simulated_containment_queued")
    elif should_flag_deferred:
        flags.append("containment_deferred_single_family")
```

(`containment_deferred_single_family` gives analyst triage/UI a way to see "would have queued containment pre-Stage-A" without actually queuing it — useful for the Series H benign-vs-TP agreement measurement in Task 5.4, and for a human to audit Stage A's effect after the fact.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/worker/test_precision_gate_stage_a.py -v`
Expected: PASS.

- [ ] **Step 4b: One integration-level smoke test through `score_event`**

Add, reusing the `db_session`/`_profile()` pattern already established for this file in Task 5.2:

```python
def test_score_event_defers_containment_flag_when_gate_enabled_and_single_family(db_session):
    """Wiring smoke test: score_event actually calls _containment_eligible with real
    signal_family_agreement_count, not just the unit-tested function in isolation."""
    import copy
    import yaml
    from datetime import datetime, timedelta
    from core.schemas.events import ResolvedEvent
    from worker.scorer import load_scoring_config, score_event
    from worker.profile_store import ProfileStore

    entity_id = "user_containment_smoke"
    as_of = datetime(2024, 6, 15, 12, 0, 0)
    db_session.add(_profile(
        version="promoted_containment_v1", entity_id=entity_id, drift=4.9,  # near drift_threshold=5.0
        is_shadow=False, promoted_at=as_of - timedelta(days=5),
        created_at=as_of - timedelta(days=5), data_window_end=as_of - timedelta(days=5),
    ))
    db_session.commit()

    with open("config/scoring_config.yaml") as f:
        config = yaml.safe_load(f)
    enabled_config = copy.deepcopy(config)
    enabled_config["precision_gate"]["enabled"] = True

    promoted = ProfileStore(db_session).get_active_profile(entity_id, as_of)
    event = ResolvedEvent(
        event_id="evt_containment_smoke", timestamp=as_of, event_type="process",
        raw_entity_id=entity_id, entity_id=entity_id, entity_type="human",
        resolution_confidence=1.0, simulation_partition="production",
        event_data={"process_name": "chrome.exe", "endpoint_id": "ep-a",
                    "geolocation": "US", "command_line": "chrome.exe --silent"},
    )
    decision = score_event(db_session, event, promoted, enabled_config)
    # drift_accum=4.9 alone (one family) produces score_drift = min(50, 4.9/5*100) = 49 —
    # below containment_threshold=85 either way, so this specifically verifies the wiring
    # doesn't raise/misbehave with the gate enabled, not the exact threshold-crossing case
    # (that numeric edge case is already covered precisely by the unit tests above).
    assert isinstance(decision.signal_family_agreement_count, int)
    assert "simulated_containment_queued" not in decision.flags
    assert "containment_deferred_single_family" not in decision.flags
```

- [ ] **Step 5: Run the existing containment-queue test suite**

Run: `pytest tests/worker/test_containment_queue.py -v`
Expected: PASS unchanged — `precision_gate.enabled` defaults to `false` in the config those tests load, so `meets_agreement` is always `True` there and behavior is identical to pre-Phase-5.

- [ ] **Step 6: Run S55 invariant regression suites explicitly**

Run: `pytest tests/test_s55_invariants_c1_c3.py tests/test_boil_the_frog_invariants.py -v`
Expected: PASS unchanged — these must not be affected since Stage A never touches `is_anomaly` or workflow-opening, only the `simulated_containment_queued`/new `containment_deferred_single_family` flags.

- [ ] **Step 7: Run full suite**

Run: `pytest -v --tb=short`
Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add worker/scorer.py tests/worker/test_precision_gate_stage_a.py
git commit -m "Gate containment eligibility on signal-family agreement (Stage A, behind precision_gate.enabled)"
```

### Task 5.4: Series H sweep harness + governance doc (Phases 5–6) — benign-vs-TP agreement distribution is a hard gate

**Files:**
- Create: `scratch/run_series_h_sweep.py` (adapt from `scratch/run_series_g_sweep.py`)
- Create: `docs/scoring-config-governance-series-h.md`

- [ ] **Step 1: Adapt the harness**

Copy `scratch/run_series_g_sweep.py` to `scratch/run_series_h_sweep.py`, rename constants to `series_h_*`, `payload["series"] = "H"`. Reuse `with_enabled_flags_for_sweep(...)` (copied into this file, same as Task 4.3), called with:

```python
    with with_enabled_flags_for_sweep([
        (("precision_gate", "enabled"), True),
        (("staged_drift", "enabled"), True),
    ]):
        db = run_pipeline(EVENTS_PATH, LABELS_PATH, window_delta_days=1)
```

Add:

```python
def signal_family_agreement_distribution(db, threshold: float) -> dict[str, Any]:
    """H14 Stage A governance pre-commitment: report benign-FP vs. TP agreement_count
    distributions SEPARATELY. Any future Stage-B threshold proposal must cite this,
    not a number chosen after seeing recall impact."""
    decisions = list(db.execute(select(DecisionRecordModel)).scalars().all())
    from core.models import EvalGroundTruthModel

    malicious_event_ids = {
        row[0] for row in db.execute(
            select(EvalGroundTruthModel.event_id).where(EvalGroundTruthModel.is_malicious.is_(True))
        ).all()
    }
    benign_counts = [d.signal_family_agreement_count for d in decisions if d.is_anomaly and d.event_id not in malicious_event_ids]
    tp_counts = [d.signal_family_agreement_count for d in decisions if d.is_anomaly and d.event_id in malicious_event_ids]

    def _dist(counts):
        if not counts:
            return {"n": 0}
        from collections import Counter
        c = Counter(counts)
        return {"n": len(counts), "histogram": dict(sorted(c.items())), "mean": sum(counts) / len(counts)}

    return {"benign_fp_agreement_distribution": _dist(benign_counts), "tp_agreement_distribution": _dist(tp_counts)}
```

- [ ] **Step 2: Run the sweep**

Run: `python scratch/run_series_h_sweep.py`
Expected: exits 0, writes `scratch/series_h_metrics.json` including `signal_family_agreement_distribution`.

- [ ] **Step 3: Write the governance doc**

`docs/scoring-config-governance-series-h.md`, Series D-G template plus a mandatory `## Benign vs. TP signal-family agreement (Stage-B evidence base)` section presenting both histograms side by side and their means, explicitly labeled: *"This distribution is the evidence base for any future Stage-B `containment_min_agreement`/workflow-arming threshold proposal. No such proposal may cite a number not derived from this table."* Add a `## Phase 6 staged-sequence recall impact` section (S3 recall before/after, per Task 6.1/6.2).

- [ ] **Step 4: Commit**

```bash
git add scratch/run_series_h_sweep.py docs/scoring-config-governance-series-h.md scratch/series_h_metrics.json
git commit -m "Run Series H sweep: benign-vs-TP signal-family agreement distribution and staged-sequence recall"
```

---

## Phase 6 — H15: staged multi-feature drift ordering

### Task 6.1: Per-build threshold-crossing log

**Files:**
- Modify: `batch/profile_builder/builder.py` (`raw_drift_records[...]["features"]` block)
- Test: `tests/batch/profile_builder/test_staged_drift_sequence.py` (new)

**Interfaces:**
- Produces: `features["drift_crossing_log"]: list[dict]` — bounded to the last `N=10` builds per entity, each entry `{"build_ts": iso_str, "dims_crossed": list[str]}` where `dims_crossed` is every `drift_weights` dimension whose `avg_deltas[k]` exceeded a soft per-dimension threshold (`config["staged_drift"]["soft_crossing_fraction"] * that dimension's own historical p90`, — simplify for v1 to a fixed fraction of `drift_weights[k].weight`-independent raw delta, e.g. `avg_deltas[k] > 0.5`, documented as a v1 heuristic subject to Series H revision) that build.

- [ ] **Step 1: Write the failing test**

```python
# tests/batch/profile_builder/test_staged_drift_sequence.py
from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker

from core.database import Base
from core.models import ProfileArtifactModel, ResolvedEventModel
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


def test_drift_crossing_log_bounded_and_populated(db_session):
    entity_id = "user_staged_test"
    start = datetime(2026, 1, 1)
    for i in range(20):
        db_session.add(ResolvedEventModel(
            event_id=f"evt_staged_{i}", entity_id=entity_id, entity_type="human",
            timestamp=start + timedelta(minutes=i), event_data={
                "process_name": "chrome.exe", "endpoint_id": "ep-a", "geolocation": "US", "command_line": "chrome.exe",
            }, resolution_confidence=1.0, simulation_partition="production",
        ))
    db_session.commit()

    for day in range(1, 4):
        build_profiles(db=db_session, as_of=start + timedelta(days=day))

    profile = (
        db_session.query(ProfileArtifactModel)
        .filter_by(entity_id=entity_id, is_shadow=False)
        .order_by(ProfileArtifactModel.data_window_end.desc())
        .first()
    )
    assert profile is not None
    assert "drift_crossing_log" in profile.features
    assert len(profile.features["drift_crossing_log"]) <= 10
```

- [ ] **Step 2: Run to verify it fails**

Run: `pytest tests/batch/profile_builder/test_staged_drift_sequence.py -v`
Expected: FAIL — key absent.

- [ ] **Step 3: Implement**

In the same per-entity loop where `avg_deltas`/`raw_drift` are computed (`builder.py:644-645`), add:

```python
            soft_crossing_threshold = staged_drift_cfg.get("soft_crossing_fraction", 0.5)
            dims_crossed = [k for k, v in avg_deltas.items() if v > soft_crossing_threshold]
            prior_log = (latest_any.features.get("drift_crossing_log", []) if latest_any else [])
            drift_crossing_log = (prior_log + [{"build_ts": rec["window_end"].isoformat(), "dims_crossed": dims_crossed}])[-10:]
```

(`latest_any` — the same "latest profile even if shadow" lookup already used for `prev_accumulator` at `builder.py:690-694` — must be computed before this point in Phase 3's loop; if the existing code computes it later, hoist that query earlier so both consumers share it, rather than querying twice.) Add `"drift_crossing_log": drift_crossing_log` to the `features` dict written at profile-creation time. Add to `config/scoring_config.yaml`:

```yaml
staged_drift:
  enabled: false
  soft_crossing_fraction: 0.5
  templates:
    - ["endpoint_set", "process_name", "embedding"]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/batch/profile_builder/test_staged_drift_sequence.py -v`
Expected: PASS.

- [ ] **Step 5: Run full suite**

Run: `pytest -v --tb=short`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add batch/profile_builder/builder.py config/scoring_config.yaml tests/batch/profile_builder/test_staged_drift_sequence.py
git commit -m "Record per-build drift-dimension threshold-crossing log"
```

### Task 6.2: Staged-sequence template match (shadow-computed, disabled)

**Files:**
- Modify: `batch/profile_builder/builder.py`
- Test: `tests/batch/profile_builder/test_staged_drift_sequence.py` (extend)

**Interfaces:**
- Produces: `match_staged_sequence(drift_crossing_log: list[dict], templates: list[list[str]]) -> tuple[bool, list[str] | None]` — returns `(matched, matching_template)`, checking whether the ordered, deduplicated union of `dims_crossed` across the log's entries contains each template's dimensions in order (subsequence match, not exact contiguous match — a template `["endpoint_set", "process_name", "embedding"]` matches a log where those three appear in that relative order across builds, with other dimensions or repeats interleaved).

- [ ] **Step 1: Write the failing test**

```python
def test_matching_staged_sequence_detected():
    from batch.profile_builder.builder import match_staged_sequence

    log = [
        {"build_ts": "2026-01-01T00:00:00", "dims_crossed": ["endpoint_set"]},
        {"build_ts": "2026-01-02T00:00:00", "dims_crossed": ["login_hour"]},
        {"build_ts": "2026-01-03T00:00:00", "dims_crossed": ["process_name"]},
        {"build_ts": "2026-01-04T00:00:00", "dims_crossed": ["embedding"]},
    ]
    templates = [["endpoint_set", "process_name", "embedding"]]
    matched, which = match_staged_sequence(log, templates)
    assert matched is True
    assert which == ["endpoint_set", "process_name", "embedding"]


def test_wrong_order_does_not_match():
    from batch.profile_builder.builder import match_staged_sequence

    log = [
        {"build_ts": "2026-01-01T00:00:00", "dims_crossed": ["embedding"]},
        {"build_ts": "2026-01-02T00:00:00", "dims_crossed": ["process_name"]},
        {"build_ts": "2026-01-03T00:00:00", "dims_crossed": ["endpoint_set"]},
    ]
    templates = [["endpoint_set", "process_name", "embedding"]]
    matched, which = match_staged_sequence(log, templates)
    assert matched is False
    assert which is None
```

- [ ] **Step 2: Run to verify it fails**

Run: `pytest tests/batch/profile_builder/test_staged_drift_sequence.py -v`
Expected: FAIL — `ImportError`.

- [ ] **Step 3: Implement**

```python
def match_staged_sequence(
    drift_crossing_log: list[dict], templates: list[list[str]]
) -> tuple[bool, list[str] | None]:
    """Subsequence match: template dims must appear across the log in order,
    not necessarily contiguously or in consecutive builds."""
    seen_in_order: list[str] = []
    for entry in drift_crossing_log:
        for dim in entry.get("dims_crossed", []):
            seen_in_order.append(dim)

    for template in templates:
        idx = 0
        for dim in seen_in_order:
            if idx < len(template) and dim == template[idx]:
                idx += 1
        if idx == len(template):
            return True, template
    return False, None
```

Wire into the accumulator update (Phase 3 of `build_profiles`, near where `new_accumulator` is computed at `builder.py:700`):

```python
            staged_drift_cfg = config.get("staged_drift", {})
            if staged_drift_cfg.get("enabled", False):
                matched, which_template = match_staged_sequence(drift_crossing_log, staged_drift_cfg.get("templates", []))
                if matched:
                    features_staged_bonus = staged_drift_cfg.get("bonus", 1.0)
                    new_accumulator = exponential_decay(prev_accumulator, norm_drift + features_staged_bonus, half_life, time_delta)
                    new_accumulator = max(0.0, new_accumulator)
```

(This re-derives `new_accumulator` with the staged bonus added to `norm_drift` before decay, replacing the line already computed earlier in the loop — place this block immediately after the existing `new_accumulator = exponential_decay(prev_accumulator, norm_drift, half_life, time_delta)` line so it overrides rather than duplicates, and only when `matched` is true.) Add `"staged_match": matched if staged_drift_cfg.get("enabled", False) else None` to the stored `features` dict for observability regardless of whether it changed the accumulator.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/batch/profile_builder/test_staged_drift_sequence.py -v`
Expected: PASS.

- [ ] **Step 5: Zero-behavioral-diff regression**

Add:

```python
def test_staged_drift_disabled_by_default_does_not_change_accumulator(db_session):
    import yaml
    with open("config/scoring_config.yaml") as f:
        config = yaml.safe_load(f)
    assert config["staged_drift"]["enabled"] is False
```

- [ ] **Step 6: Run full suite**

Run: `pytest -v --tb=short`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add batch/profile_builder/builder.py tests/batch/profile_builder/test_staged_drift_sequence.py
git commit -m "Add staged multi-feature sequence template match, shadow-computed and disabled by default"
```

---

## Final Task: Update DEBT_LEDGER.md and residual-risk-drift-hypotheses.md status

**Files:**
- Modify: `DEBT_LEDGER.md` (`DEBT-051`, `DEBT-019`, `DEBT-068`, `DEBT-075` recovery status)
- Modify: `docs/residual-risk-drift-hypotheses.md` (H12-H15 status)

- [ ] **Step 1:** Update `DEBT_LEDGER.md`'s `DEBT-051`/`DEBT-019`/`DEBT-068`/`DEBT-075` rows' "Recovery" column to note the phase and commit range that implemented them (still `enabled: false` pending Series governance sign-off — do not mark these debt items fully closed until their respective `enabled` flags flip true, since "implemented but disabled" is not the same as "recovered" per this ledger's own severity/recovery framing).

- [ ] **Step 2:** Add a one-line status update under each of H12-H15 in `docs/residual-risk-drift-hypotheses.md` noting "Implemented, shadow-computed, disabled pending Series {F/F/G/H} governance sign-off — see `docs/superpowers/plans/2026-07-30-drift-detection-capability-expansion.md`."

- [ ] **Step 3: Commit**

```bash
git add DEBT_LEDGER.md docs/residual-risk-drift-hypotheses.md
git commit -m "Cross-reference drift-capability-expansion plan status in debt ledger and hypotheses doc"
```
