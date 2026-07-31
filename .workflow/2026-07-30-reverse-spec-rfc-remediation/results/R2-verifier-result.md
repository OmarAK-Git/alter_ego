# R2 skeptic-verifier result

**Verdict:** `survives`

**Scope:** packet R2 / RFC-005 (`build_profiles` chunked streaming), task-scoped.
**Commits under review:** `2aaa4e0`, `019487e`
**Verifier:** fresh-context skeptic-verifier (readonly; AC8 probe reverted)

---

## Claim restated

`build_profiles` no longer fully materializes historical or recent event windows via
`.scalars().all()` into `events_hist` / `events_recent`. Both windows stream to temp
JSONL via `_stream_events_to_jsonl(..., yield_per=chunk_size)` with payload parity to
the deleted `write_jsonl` closure; `chunk_size` is a trailing kwarg defaulting to 5000;
empty-recent ends as `temp_file_recent is None`; suite is 165 green; ruff clean;
red-before-green evidence is authentic; commit scope excludes scoring config and
unrelated root artifacts.

---

## Acceptance criteria

| AC | Result | Evidence |
|---|---|---|
| 1 | PASS | `\bevents_hist\b` / `\bevents_recent\b` → 0 idents in current `builder.py`. Hist/recent use `_stream_events_to_jsonl(db_session, stmt_hist/stmt_recent, ...)`. Remaining `.scalars().all()` are alerts / prev profiles only. |
| 2 | PASS | `_BUILD_EXTRACT_CHUNK_SIZE: int = 5000` at L408; helper L411–433 uses `stmt.execution_options(yield_per=chunk_size)` and returns `count`. |
| 3 | PASS | Normalized `data = {...}` key lines from `git show 2aaa4e0^:...` `write_jsonl` vs current helper: **EQUAL** (11 keys, same order, `command_line` default `""`, `.isoformat()`, `.hour`, `extract_role`). |
| 4 | PASS | Signature ends with `chunk_size: int = _BUILD_EXTRACT_CHUNK_SIZE`. Call sites: `batch/eval/runner.py:132` `build_profiles(db, as_of=...)`; `tests/batch/test_shadow_profiles.py`, `tests/batch/test_profile_build_block_escalation.py` (positional db + keyword `as_of`). |
| 5 | PASS | On `count_recent == 0`: `unlink(missing_ok=True)` then `temp_file_recent = None` (L536–538). Downstream `if temp_file_recent:` before `query_recent` (L568). Equivalent to old never-created path for DuckDB. |
| 6 | PASS | On `count_hist == 0`: hist unlink + `_auto_resolve_quiet_attested_alerts` + `_emit_build_block_supervisor_escalations` + `db_session.commit()` + `return 0` (L505–530). |
| 7 | PASS | `R2-regression-red.txt` contains `TypeError: build_profiles() got an unexpected keyword argument 'chunk_size'`. File LastWrite `2026-07-30T18:37:55-04:00` < green `18:38:09` < commit `2aaa4e0` `18:38:47`. |
| 8 | PASS | Independent probe: temporarily `break` after first `chunk_size` rows → test failed `assert 2 == 5`. Reverted via backup restore; `git diff HEAD -- batch/profile_builder/builder.py` empty; probe string absent. |
| 9 | PASS | Fresh post-revert: `pytest -v --tb=short --ignore=tests/live` → **165 passed**. `ruff check .` → **All checks passed!** |
| 10 | PASS | No `temp_events_*.jsonl` in repo root (or recurse) after suite. |
| 11 | PASS | `git show 2aaa4e0 --name-only` → only `builder.py` + `test_profile_build_snapshot.py`. `019487e` → only `builder.py`. `git diff 2aaa4e0^..019487e -- config/scoring_config.yaml` empty. Unrelated untracked roots not in commits. |

---

## AC8 probe (strongest failure-mode check)

Applied temporary mutation inside `_stream_events_to_jsonl`:

```python
if count >= chunk_size:  # AC8 probe: drop rows past first batch
    break
```

Command:

```
pytest tests/batch/test_profile_build_snapshot.py::test_profile_build_streams_events_across_multiple_chunks -v --tb=short
```

Output relied on:

```
E   assert 2 == 5
FAILED ...test_profile_build_streams_events_across_multiple_chunks
======================== 1 failed, 1 warning in 0.79s =========================
```

Revert: restored from pre-probe backup. Confirmed:

- `AC8 probe: False` / `early break: False` in file text
- `git diff HEAD -- batch/profile_builder/builder.py` empty
- Targeted re-run: **2 passed**
- Full suite re-run (clean): **165 passed**

Note: an earlier full-suite run that executed **in parallel with the probe** reported 2 failures (contaminated; discarded). Clean re-run is authoritative.

---

## Commands and outputs relied on

### Payload parity

```
OLD: ['"event_id": e.event_id', ... '"hour_of_day": e.timestamp.hour']
NEW: ['"event_id": e.event_id', ... '"hour_of_day": e.timestamp.hour']
EQUAL: True
events_hist idents: 0
events_recent idents: 0
yield_per=chunk_size: True
```

### Red evidence timestamps

```
RED LastWrite:  2026-07-30T18:37:55.7313041-04:00
GREEN LastWrite: 2026-07-30T18:38:09.3153580-04:00
Commit 2aaa4e0: 2026-07-30 18:38:47 -0400
```

### Full suite (clean, post-revert)

```
===================== 165 passed, 381 warnings in 22.70s ======================
```

### Ruff

```
All checks passed!
```

### Commit scope

```
2aaa4e0: batch/profile_builder/builder.py, tests/batch/test_profile_build_snapshot.py
019487e: batch/profile_builder/builder.py
```

### Final `git status --short` (no probe leftovers on source)

```
 M docs/residual-risk-drift-hypotheses.md
?? .workflow/2026-07-30-reverse-spec-rfc-remediation/
?? 5638f86d-29ea-4156-b6b6-f65ff9f28f83-rfcs.md
?? 5638f86d-29ea-4156-b6b6-f65ff9f28f83-run_log.md
?? AS_BUILT.md
?? DEBT_LEDGER.md
?? alter-ego-drift-gap-evaluation.md
?? docs/superpowers/plans/2026-07-30-reverse-spec-rfc-remediation.md
?? scratch/series_c_d4_engagement_run.log
```

No modifications under `batch/`, `tests/`, or `config/` from verifier probing.

---

## Strongest reason the claim survives

AC8 was independently falsified-then-restored: dropping rows past the first batch made `total_events` assert `2 == 5`, proving the regression test is not vacuous; a clean full suite then reproduced **165 passed** with ruff clean and payload/empty-path/commit-scope checks holding against `2aaa4e0^`.

## Known non-blocking notes

Not re-litigated per packet: mid-stream temp cleanup via pre-existing `finally`; pre-existing mypy noise.
