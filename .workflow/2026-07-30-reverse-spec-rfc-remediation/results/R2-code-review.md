# R2 Code Review — RFC-005 streaming extraction (`2aaa4e0`)

**Reviewer:** code-reviewer subagent  
**Commit:** `2aaa4e0bff559a231b54adfb84501f6ea95d5f1a`  
**Spec:** Task 2, `docs/superpowers/plans/2026-07-30-reverse-spec-rfc-remediation.md`  
**Scope:** `batch/profile_builder/builder.py`, `tests/batch/test_profile_build_snapshot.py`

## Summary

The diff implements Task 2 as specified: replaces dual `.scalars().all()` materialization with `_stream_events_to_jsonl` using `yield_per`, adds `_BUILD_EXTRACT_CHUNK_SIZE = 5000`, adds trailing `chunk_size` kwarg, switches the recent-window guard to `if temp_file_recent:`, and adds the chunked regression test. Commit touches only the two allowed files; `config/scoring_config.yaml` and unrelated untracked root artifacts are not in the commit.

**Blocking findings: 0**  
**Non-blocking notes: 3**

Verification evidence on disk: RED (`R2-regression-red.txt`), GREEN (`R2-regression-green.txt`), full suite 165 passed (`R2-pytest-full.txt`).

---

## 1. Spec compliance

| Requirement | Status |
|---|---|
| `_BUILD_EXTRACT_CHUNK_SIZE = 5000` | Present (`builder.py:408`) |
| `_stream_events_to_jsonl(db_session, stmt, path, chunk_size) -> int` | Present (`builder.py:411-433`) |
| Trailing `chunk_size` kwarg with default | Present (`builder.py:436`) |
| Stream hist → early return + unlink on `count_hist == 0` | Present (`builder.py:500-530`) |
| Stream recent → unlink + `temp_file_recent = None` on `count_recent == 0` | Present (`builder.py:532-538`) |
| Replace `if events_recent:` with `if temp_file_recent:` | Done (`builder.py:568`); `grep events_recent` → zero references |
| Regression test per plan | Matches plan verbatim (`test_profile_build_snapshot.py:72-95`) |
| Commit scope (2 files only) | Confirmed via `git show 2aaa4e0 --name-only` |

Minor spec nits (non-blocking): plan Interfaces section types the constant as `_BUILD_EXTRACT_CHUNK_SIZE: int = 5000` (annotation omitted in code); plan Step 3 says "near the top" but implementation places the constant/helper immediately before `build_profiles` (line 408), which matches the implementer packet.

---

## 2. Risk-focused review

### 2.1 Row payload equivalence — PASS

Compared the deleted `write_jsonl` closure (commit parent) to `_stream_events_to_jsonl` (`builder.py:418-431`). The `data` dict is byte-for-byte equivalent in structure:

- Same 11 keys in the same insertion order (`event_id` … `hour_of_day`)
- `command_line`: `e.event_data.get("command_line", "")`
- `timestamp`: `e.timestamp.isoformat()`
- `hour_of_day`: `e.timestamp.hour`
- `role`: `extract_role(e.entity_id, e.entity_type)`
- Same `json.dumps(data) + "\n"` write path

No drift detected that would corrupt downstream DuckDB `read_json_auto` aggregation.

### 2.2 Empty-window semantics — PASS

**Recent window empty (hist non-empty):** New code always allocates `temp_file_recent`, streams zero rows (creates empty file), then `unlink(missing_ok=True)` and sets `temp_file_recent = None` (`builder.py:536-538`). Matches old behavior where `temp_file_recent` stayed `None` and `if events_recent:` was false.

**Hist window empty:** New code streams first, hits `count_hist == 0`, `temp_file_hist.unlink(missing_ok=True)`, then early-returns (`builder.py:505-530`). Old code never created temp files on this path. Semantically equivalent; new code also avoids streaming the recent window when hist is empty (spec-intended improvement over old dual-fetch).

**Downstream guard:** The only `events_recent` truthiness guard (`query_recent` / `recent_features_map`, formerly ~line 559) now reads `if temp_file_recent:` (`builder.py:568-573`). Truthiness is equivalent: `Path` object when recent rows exist, `None` when empty. Temp-file cleanup loops (`builder.py:575-577`, `801-805`) iterate `[temp_file_hist, temp_file_recent]` and skip falsy/`None` entries — unchanged and correct.

### 2.3 Temp file leaks — PASS (note: pre-existing finally pattern)

| Path | Behavior |
|---|---|
| `count_hist == 0` early return | Explicit `temp_file_hist.unlink(missing_ok=True)` before `return 0` (`builder.py:506`) |
| Happy path after DuckDB read | Inline cleanup `575-577` unlinks both files |
| Exception before inline cleanup | `finally` (`801-805`) unlinks any assigned path where `p.exists()` |
| `_stream_events_to_jsonl` raises mid-write | Partial file exists on disk; inline cleanup has not run yet, but `finally` removes it because `temp_file_hist` / `temp_file_recent` were assigned before the call |

**Note (NON-BLOCKING):** Partial-file cleanup on exception relies on the pre-existing Fix #7 `finally` block, not on new logic in this diff. The diff does not worsen leak behavior; it adds one more early path that correctly unlinks an empty hist file before return.

### 2.4 `yield_per` correctness — PASS

- `stmt_hist` / `stmt_recent` are plain `select(ResolvedEventModel).where(...)` with no `joinedload`, `selectinload`, or `subqueryload` (`builder.py:481-496`).
- `ResolvedEventModel` has no ORM `relationship()` loaders; `event_data` is an inline JSONB column (`core/models.py`).
- Helper consumes via `for e in result` on `ScalarResult` — correct SQLAlchemy 2.0 streaming pattern.
- Each statement is executed once; `execution_options(yield_per=...)` does not create reuse hazards.

Suite passes on SQLite in-memory fixtures including the `chunk_size=2` test; production Postgres is the intended `yield_per` target and has no eager-loader conflict in these statements.

### 2.5 Backward compatibility — PASS

Signature adds `chunk_size` as the fourth, trailing keyword with default `_BUILD_EXTRACT_CHUNK_SIZE` (`builder.py:436`). Grep of `build_profiles(` across the repo shows 10+ call sites (`batch/eval/runner.py`, multiple test modules, scratch scripts) — none pass `chunk_size`; all remain valid. `docs/deployment.md` references `build_profiles` without positional fourth args — unaffected.

### 2.6 Test quality — PASS (one non-blocking gap)

`test_profile_build_streams_events_across_multiple_chunks`:

- Inserts 5 events, calls `build_profiles(..., chunk_size=2)`.
- Asserts `profile.features["total_events"] == 5`.

This **would fail** if the writer dropped rows after the first batch (expected count would be 2). It exercises the full hist aggregation path through DuckDB, not just the helper in isolation.

**NON-BLOCKING:** The test does not assert DB round-trip count (e.g. via query logging); on SQLite, `yield_per` may not enforce the same server-side chunking as Postgres. The test therefore proves iterator completeness, not that `yield_per` is honored at the driver level in CI. Acceptable per plan Step 1, which only requires the aggregate assertion.

---

## 3. Out-of-scope checks

- `config/scoring_config.yaml`: **not modified** in `2aaa4e0`.
- Unrelated untracked root files (`AS_BUILT.md`, `DEBT_LEDGER.md`, `5638f86d-*`, etc.): **not swept into commit** (scoped add of two files only).

---

## Findings

### BLOCKING

None.

### NON-BLOCKING

1. **`builder.py:408`** — Plan Interfaces section annotates `_BUILD_EXTRACT_CHUNK_SIZE: int`; implementation omits the `: int` annotation. Cosmetic only.

2. **`test_profile_build_snapshot.py:72-95`** — Regression test validates end-to-end row count but cannot prove multi-chunk DB fetch on SQLite; would not catch a future change that removes `yield_per` but still iterates all rows via a single fetch.

3. **`builder.py:801-805`** — Mid-stream exception cleanup depends on the pre-existing `finally` block (not introduced by this diff). Documented for audit; not a regression.

---

## Verdict

**Approve for packet R2 completion.** Implementation matches Task 2, preserves JSONL row shape and empty-window semantics, does not introduce temp-file regressions beyond the existing finally safety net, and maintains backward compatibility at all call sites.
