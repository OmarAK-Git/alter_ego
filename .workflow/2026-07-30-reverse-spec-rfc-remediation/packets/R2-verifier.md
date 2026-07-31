# Packet R2 — skeptic-verifier

- Run: `.workflow/2026-07-30-reverse-spec-rfc-remediation`
- Model: `cursor-grok-4.5-high` (readonly)
- Scope: task (NOT a phase/sprint gate — ignore run-wide gaps)

## Goal under verification (RFC-005)

`build_profiles` in `batch/profile_builder/builder.py` must no longer fully
materialize either event window in Python. Both the historical and the recent
window must stream to their temp JSONL files in bounded chunks, so peak
Python-side memory is a function of `chunk_size`, not of window volume.

## Acceptance criteria

1. `batch/profile_builder/builder.py` contains zero `.scalars().all()` calls for
   the historical/recent event extraction, and zero references to the names
   `events_hist` / `events_recent`.
2. A module-level `_BUILD_EXTRACT_CHUNK_SIZE: int = 5000` exists, and
   `_stream_events_to_jsonl(db_session, stmt, path, chunk_size) -> int` uses
   `stmt.execution_options(yield_per=chunk_size)` and returns the row count.
3. The JSONL row payload is byte-for-byte equivalent to the deleted `write_jsonl`
   closure: same keys, same order, `command_line` default `""`, `timestamp`
   `.isoformat()`, `hour_of_day` from `e.timestamp.hour`, `role` from
   `extract_role(e.entity_id, e.entity_type)`. Compare against the pre-change
   version: `git show 2aaa4e0^:batch/profile_builder/builder.py`.
4. `build_profiles`'s new `chunk_size` is a TRAILING keyword with a default;
   existing call sites that pass `db`/`db_session` positionally and `as_of` by
   keyword still work unchanged. Spot-check real call sites in
   `batch/eval/runner.py` and at least two test modules.
5. Empty-recent-window path: `temp_file_recent` ends as `None` and its file is
   unlinked; the downstream `query_recent` / `recent_features_map` guard reads
   `if temp_file_recent:`. Behavior must match the old "file never created" path.
6. Empty-historical path: the early return unlinks the hist temp file
   (`missing_ok=True`) and preserves the prior
   `_auto_resolve_quiet_attested_alerts` / `_emit_build_block_supervisor_escalations`
   / `db_session.commit()` / `return 0` behavior.
7. RED-before-GREEN evidence is real: `results/R2-regression-red.txt` shows
   `TypeError: build_profiles() got an unexpected keyword argument 'chunk_size'`
   and predates the `builder.py` edit.
8. `test_profile_build_streams_events_across_multiple_chunks` genuinely forces
   multiple chunks (`chunk_size=2` over 5 rows) and would fail if the writer
   dropped rows past the first batch. Prove it — mutate nothing permanently, but
   you may reason about or temporarily probe the failure mode.
9. Full suite green: `pytest -v --tb=short --ignore=tests/live` → 165 passed
   (baseline 164 after packet R1). `ruff check .` clean.
10. No stray `temp_events_hist_*.jsonl` / `temp_events_recent_*.jsonl` in the
    repo root after the suite.
11. `config/scoring_config.yaml` untouched; commits scoped (no unrelated
    untracked root files swept in).

## Paths

- `batch/profile_builder/builder.py`
- `tests/batch/test_profile_build_snapshot.py`
- Commits: `2aaa4e0` (main change), `019487e` (annotation follow-up)
- Implementer result: `results/R2-implementer-result.md`
- Code review: `results/R2-code-review.md`
- Prior evidence: `results/R2-regression-red.txt`, `results/R2-regression-green.txt`

## Commands

```
pytest tests/batch/test_profile_build_snapshot.py -v
pytest -v --tb=short --ignore=tests/live
ruff check .
git show 2aaa4e0 --stat
git show 019487e --stat
git status --short
```

## Known non-blocking notes (do not re-litigate)

- Partial temp files on a mid-stream exception rely on the pre-existing
  `finally` cleanup block; the diff does not worsen this.
- `mypy .` reports 65 pre-existing errors across the repo, none introduced by
  this diff. mypy is not a gate command for this run.

Treat every implementer and reviewer claim as unevidenced until you reproduce it.
