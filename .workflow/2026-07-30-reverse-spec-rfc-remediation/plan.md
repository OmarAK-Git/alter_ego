# Reverse-Spec RFC Remediation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the two RFCs from the `5638f86d…-rfcs.md` reverse-spec review that were independently verified against the actual code — bounded/streamed extraction in `build_profiles` (RFC-005) and pytest discovery for the profile-builder test file (RFC-006). RFC-001 is rejected (fabricated premise); RFC-002/003 KILL dispositions are affirmed and out of scope; RFC-004 was already dropped by the citation breaker.

**Architecture:** No new subsystems. Task 1 is a file rename (zero behavior change other than making an existing, already-passing test executable in CI). Task 2 replaces the two `Session.execute(stmt).scalars().all()` full-materialization calls in `batch/profile_builder/builder.py::build_profiles` with a chunked streaming write straight to the temp JSONL files, bounding Python-side memory to one chunk at a time regardless of window size.

**Tech Stack:** `batch/profile_builder/builder.py`, SQLAlchemy 2.0 (`execution_options(yield_per=...)`), pytest, sqlite in-memory test fixtures (existing pattern in `tests/batch/*.py`).

## Global Constraints

- No scoring weight or threshold in `config/scoring_config.yaml` changes as part of this work (evaluation-first discipline — this is a memory/IO bounding change, not a detection-logic change).
- `build_profiles()` public signature must stay backward compatible — all existing callers (`batch/eval/runner.py`, 6+ test modules, `docs/deployment.md` one-liners) call it positionally for `db`/`db_session` and by keyword for `as_of`; any new parameter must be a trailing keyword with a default.
- Streamed extraction must produce byte-for-byte equivalent JSONL rows to the current `write_jsonl` closure (same field set, same ordering per entity is not guaranteed today either — do not add an ordering guarantee that didn't exist).
- Do not touch `evidence/` or other unrelated pre-existing artifacts in the repo root — out of scope for this plan.

---

## Verification summary (why these two tasks and not the others)

| RFC | Disposition in review | Independent verification | Action |
|-----|---|---|---|
| RFC-001 (ScenarioType enum bounds) | CONCEDE (S2) | **Rejected.** `batch/synthetic/scenarios.py::ScenarioType` holds semantic attack labels (`SHARP_CREDENTIAL_MISUSE`, …) and is never read by `builder.py`. The partition filter actually used is a hardcoded string tuple, `builder_partitions = ("production", "eval_scenario_2", "eval_scenario_3", "eval_scenario_5")` (`batch/profile_builder/builder.py:450`), which already includes `eval_scenario_5` and is used only in a SQL `.in_()` filter — an unrecognized partition string is silently excluded from the query, not a crash. The RFC conflates two unrelated data structures; there is no code path where an enum/partition mismatch is fatal. **Do not implement.** |
| RFC-002 (staleness DoS → safe harbor) | KILL | Affirmed. `staleness_halt` (`worker/scorer.py:446`) is a documented fail-closed invariant; alerting on prolonged builder unavailability is an ops/monitoring concern outside this codebase, not an application bug. No action. |
| RFC-003 (revoke worker UPDATE grant) | KILL | Affirmed. `alembic/versions/g6h7i8j9k0l1_add_app_db_roles.py:76` grants `UPDATE (promoted_at, superseded_at)` only — already column-scoped, and is how the builder itself promotes/supersedes profiles. Revoking it would break the builder's own promotion path for a threat that requires the worker credential to already be compromised. No action. |
| RFC-004 | Dropped (citation breaker: missing evidence file `worker/resolver.py`) | N/A — never reached review. |
| RFC-005 (paginate DuckDB extraction) | WEAKEN (S1→ downgraded) | **Confirmed real.** `build_profiles` (`batch/profile_builder/builder.py:472-473`) calls `db_session.execute(stmt).scalars().all()` for both the historical and recent windows with no `LIMIT`/chunking, then dumps the full in-memory list to one JSONL file (`write_jsonl`, lines 508-528). A volumetric spike in either window is fully materialized in Python before anything is bounded. **Implement (Task 2).** |
| RFC-006 (rename test file for discovery) | WEAKEN (S1→downgraded) | **Confirmed real.** `tests/batch/profile_builder/builder.py` exists and contains a real, currently-passing test (`test_profile_builder_aggregates_correctly`), but `pyproject.toml`'s `[tool.pytest.ini_options]` only sets `testpaths = ["tests"]` with no `python_files` override, so pytest's default `test_*.py`/`*_test.py` discovery pattern applies and this file is silently skipped — zero CI execution for the module the ledger flags as the highest complexity hotspot (DEBT-032, cc≈34). **Implement (Task 1).** |

---

## Task 1: Fix pytest discovery for profile-builder tests (RFC-006)

**Files:**
- Rename: `tests/batch/profile_builder/builder.py` → `tests/batch/profile_builder/test_builder.py`

**Interfaces:**
- Consumes: nothing new — same imports as today (`batch.profile_builder.builder.build_profiles`, `core.models.ResolvedEventModel`/`ProfileArtifactModel`, `core.database.Base`).
- Produces: nothing consumed by later tasks; this is a standalone fix.

- [ ] **Step 1: Confirm the test is currently invisible to pytest**

Run: `pytest tests/batch/profile_builder/ -v --collect-only`
Expected: `no tests ran` / zero items collected from `builder.py` (it is not matched by the default `test_*.py` pattern and there is no `python_files` override in `pyproject.toml`).

- [ ] **Step 2: Rename the file**

```bash
git mv tests/batch/profile_builder/builder.py tests/batch/profile_builder/test_builder.py
```

- [ ] **Step 3: Verify pytest now discovers and passes it**

Run: `pytest tests/batch/profile_builder/test_builder.py -v`
Expected: `test_profile_builder_aggregates_correctly` collected and `PASSED`.

- [ ] **Step 4: Run full suite to confirm no name collision or regression**

Run: `pytest -v --tb=short`
Expected: same pass count as before plus the newly-discovered test; no `import file mismatch` errors (no other `test_builder.py` exists elsewhere under `tests/`).

- [ ] **Step 5: Commit**

```bash
git add tests/batch/profile_builder/test_builder.py
git commit -m "test: fix pytest discovery for profile builder aggregation test"
```

---

## Task 2: Bound memory/disk usage of Postgres→JSONL extraction in `build_profiles` (RFC-005)

**Files:**
- Modify: `batch/profile_builder/builder.py:408-529` (`build_profiles`, plus a new module-level helper)
- Test: `tests/batch/test_profile_build_snapshot.py` (add a chunked-extraction regression test)

**Interfaces:**
- Consumes: existing `stmt_hist`/`stmt_recent` `Select` objects built earlier in `build_profiles` (unchanged); `core.models.ResolvedEventModel`; `extract_role` (already imported/defined in `builder.py`).
- Produces: new module-level constant `_BUILD_EXTRACT_CHUNK_SIZE: int = 5000` and helper `_stream_events_to_jsonl(db_session: Session, stmt, path: Path, chunk_size: int) -> int` (returns row count written). `build_profiles` gains a trailing keyword parameter `chunk_size: int = _BUILD_EXTRACT_CHUNK_SIZE`. Downstream code must branch on `temp_file_recent` (`Path | None`) instead of the old `events_recent` list truthiness.

- [ ] **Step 1: Write the failing regression test**

Add to `tests/batch/test_profile_build_snapshot.py`:

```python
def test_profile_build_streams_events_across_multiple_chunks(db_session):
    entity_id = "user_chunked"
    t0 = datetime(2026, 1, 1, 0, 0, 0)

    for i in range(5):
        db_session.add(ResolvedEventModel(
            event_id=f"chunk_evt_{i}", timestamp=t0 + timedelta(hours=i),
            event_type="login", raw_entity_id=entity_id, entity_id=entity_id,
            entity_type="user", resolution_confidence=1.0,
            simulation_partition="production",
            event_data={"action": "login", "endpoint_id": "ep_a", "process_name": "bash", "geolocation": "US"},
        ))
    db_session.commit()

    # chunk_size=2 forces 3 DB round-trips (2+2+1) for 5 rows; every row must
    # still land in the aggregate — a broken chunked writer would silently
    # drop rows past the first batch.
    build_profiles(db_session, as_of=t0 + timedelta(hours=4), chunk_size=2)

    profile = db_session.query(ProfileArtifactModel).filter(
        ProfileArtifactModel.entity_id == entity_id
    ).order_by(ProfileArtifactModel.created_at).first()
    assert profile is not None
    assert profile.features["total_events"] == 5
```

- [ ] **Step 2: Run it to verify it fails**

Run: `pytest tests/batch/test_profile_build_snapshot.py::test_profile_build_streams_events_across_multiple_chunks -v`
Expected: `FAILED` with `TypeError: build_profiles() got an unexpected keyword argument 'chunk_size'` (the parameter doesn't exist yet).

- [ ] **Step 3: Add the streaming helper and constant**

In `batch/profile_builder/builder.py`, add near the top of the file (after existing imports, before `build_profiles`):

```python
_BUILD_EXTRACT_CHUNK_SIZE = 5000  # rows per DB round-trip when streaming to temp JSONL (bounds build_profiles memory/disk under volume spikes)


def _stream_events_to_jsonl(db_session: Session, stmt, path: Path, chunk_size: int) -> int:
    """Stream ResolvedEventModel rows straight to a JSONL file in bounded
    chunks instead of materializing the full result set in Python first."""
    count = 0
    result = db_session.execute(stmt.execution_options(yield_per=chunk_size)).scalars()
    with open(path, "w") as f:
        for e in result:
            data = {
                "event_id": e.event_id,
                "timestamp": e.timestamp.isoformat(),
                "entity_id": e.entity_id,
                "entity_type": e.entity_type,
                "role": extract_role(e.entity_id, e.entity_type),
                "action": e.event_data.get("action"),
                "endpoint_id": e.event_data.get("endpoint_id"),
                "process_name": e.event_data.get("process_name"),
                "command_line": e.event_data.get("command_line", ""),
                "geolocation": e.event_data.get("geolocation"),
                "hour_of_day": e.timestamp.hour,
            }
            f.write(json.dumps(data) + "\n")
            count += 1
    return count
```

- [ ] **Step 4: Wire the helper into `build_profiles` and drop full materialization**

Change the signature (`batch/profile_builder/builder.py:408`) from:

```python
def build_profiles(db: Session | None = None, drift_compare_n: int = 5, as_of: datetime | None = None) -> int:
```

to:

```python
def build_profiles(db: Session | None = None, drift_compare_n: int = 5, as_of: datetime | None = None, chunk_size: int = _BUILD_EXTRACT_CHUNK_SIZE) -> int:
```

Replace the block from `import time` / `events_hist = db_session.execute(stmt_hist)...` (around line 470) through the end of `write_jsonl` usage (around line 529) — currently:

```python
        import time
        t0 = time.time()
        events_hist = db_session.execute(stmt_hist).scalars().all()
        events_recent = db_session.execute(stmt_recent).scalars().all()
        logger.info(f"Fetched {len(events_hist)} hist and {len(events_recent)} recent events in {time.time()-t0:.2f}s")

        if not events_hist:
            build_timestamp = datetime.utcnow()
            _auto_resolve_quiet_attested_alerts(
                db_session,
                blocked_alert_rows,
                as_of,
                drift_threshold,
            )
            blocked_alert_rows = list(
                db_session.execute(
                    select(AlertWorkflowStateModel).where(
                        AlertWorkflowStateModel.state.in_(list(ACTIVE_ALERT_STATES))
                    )
                ).scalars().all()
            )
            _emit_build_block_supervisor_escalations(
                db_session,
                blocked_alert_rows,
                as_of,
                max_profile_build_block_days,
                config,
                build_timestamp,
            )
            db_session.commit()
            return 0

        temp_file_hist = Path(f"temp_events_hist_{uuid.uuid4().hex}.jsonl")
        temp_file_recent = None
        if events_recent:
            temp_file_recent = Path(f"temp_events_recent_{uuid.uuid4().hex}.jsonl")

        t1 = time.time()
        def write_jsonl(path, evts):
            with open(path, "w") as f:
                for e in evts:
                    data = {
                        "event_id": e.event_id,
                        "timestamp": e.timestamp.isoformat(),
                        "entity_id": e.entity_id,
                        "entity_type": e.entity_type,
                        "role": extract_role(e.entity_id, e.entity_type),
                        "action": e.event_data.get("action"),
                        "endpoint_id": e.event_data.get("endpoint_id"),
                        "process_name": e.event_data.get("process_name"),
                        "command_line": e.event_data.get("command_line", ""),
                        "geolocation": e.event_data.get("geolocation"),
                        "hour_of_day": e.timestamp.hour
                    }
                    f.write(json.dumps(data) + "\n")

        write_jsonl(temp_file_hist, events_hist)
        if events_recent:
            write_jsonl(temp_file_recent, events_recent)
        logger.info(f"Wrote temp JSONLs in {time.time()-t1:.2f}s")
```

with:

```python
        import time

        temp_file_hist = Path(f"temp_events_hist_{uuid.uuid4().hex}.jsonl")
        t0 = time.time()
        count_hist = _stream_events_to_jsonl(db_session, stmt_hist, temp_file_hist, chunk_size)
        logger.info(f"Streamed {count_hist} hist events to JSONL in {time.time()-t0:.2f}s")

        if count_hist == 0:
            temp_file_hist.unlink(missing_ok=True)
            build_timestamp = datetime.utcnow()
            _auto_resolve_quiet_attested_alerts(
                db_session,
                blocked_alert_rows,
                as_of,
                drift_threshold,
            )
            blocked_alert_rows = list(
                db_session.execute(
                    select(AlertWorkflowStateModel).where(
                        AlertWorkflowStateModel.state.in_(list(ACTIVE_ALERT_STATES))
                    )
                ).scalars().all()
            )
            _emit_build_block_supervisor_escalations(
                db_session,
                blocked_alert_rows,
                as_of,
                max_profile_build_block_days,
                config,
                build_timestamp,
            )
            db_session.commit()
            return 0

        temp_file_recent = Path(f"temp_events_recent_{uuid.uuid4().hex}.jsonl")
        t1 = time.time()
        count_recent = _stream_events_to_jsonl(db_session, stmt_recent, temp_file_recent, chunk_size)
        logger.info(f"Streamed {count_recent} recent events to JSONL in {time.time()-t1:.2f}s")
        if count_recent == 0:
            temp_file_recent.unlink(missing_ok=True)
            temp_file_recent = None
```

Then update every remaining `if events_recent:` guard later in the same function (there are two more: one guarding the `query_recent`/`recent_features_map` block, one in the temp-file cleanup section is already list-based and fine since it iterates `[temp_file_hist, temp_file_recent]` — no change needed there) to check `if temp_file_recent:` instead. Search for `events_recent` after this edit — it must have zero remaining references in `builder.py`.

- [ ] **Step 5: Run the regression test to verify it passes**

Run: `pytest tests/batch/test_profile_build_snapshot.py::test_profile_build_streams_events_across_multiple_chunks -v`
Expected: `PASSED`.

- [ ] **Step 6: Run the full test suite**

Run: `pytest -v --tb=short`
Expected: all tests pass, including the pre-existing `test_profile_build_snapshot.py`, `test_shadow_profiles.py`, `test_profile_build_block_escalation.py`, `test_profile_builder_geo.py`, `test_alert_lifecycle_auto_resolve.py`, and `tests/batch/profile_builder/test_builder.py` (from Task 1) — none of these pass `chunk_size` explicitly, so they exercise the new default (`5000`) and must produce identical results to before.

- [ ] **Step 7: Commit**

```bash
git add batch/profile_builder/builder.py tests/batch/test_profile_build_snapshot.py
git commit -m "fix: stream Postgres extraction to temp JSONL in bounded chunks

Prevents unbounded Python-side memory growth in build_profiles during
volumetric event spikes by replacing full .scalars().all() materialization
with chunked yield_per streaming straight to the JSONL temp files."
```

---

## Self-review notes

- **Spec coverage:** Both surviving, verified RFCs (005, 006) have a task each. RFC-001 has no task (rejected as fabricated — documented in the verification table, not silently dropped). RFC-002/003 have no task (KILL affirmed). RFC-004 never reached review.
- **Placeholder scan:** No TBD/"handle edge cases"/"similar to Task N" — all code is inline and copy-pasteable.
- **Type consistency:** `_stream_events_to_jsonl` signature (`db_session, stmt, path, chunk_size`) matches its two call sites in Task 2 Step 4. `build_profiles`'s new `chunk_size` kwarg is trailing with a default, so all 10+ existing call sites across `batch/eval/runner.py` and `tests/**` remain valid unchanged.
