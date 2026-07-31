# Packet R2 — implementer

- Run: `.workflow/2026-07-30-reverse-spec-rfc-remediation`
- Model: `composer-2.5`
- Plan ref: `docs/superpowers/plans/2026-07-30-reverse-spec-rfc-remediation.md` — Task 2, Steps 1–7
- Repo: `C:\Users\oalan\alter_ego` (Windows, PowerShell)

## Objective (RFC-005)

`build_profiles` (`batch/profile_builder/builder.py:472-473`) calls
`db_session.execute(stmt).scalars().all()` for both the historical and the
recent window with no LIMIT or chunking, then dumps each full in-memory list to
a temp JSONL file. A volumetric spike in either window is fully materialized in
Python before anything bounds it. Replace both with a chunked streaming write
that goes straight to the temp JSONL files, bounding Python-side memory to one
chunk at a time.

**Read Task 2 of the plan in full before editing.** It contains the exact
helper body, the exact replacement block, and the exact new signature. Use them
verbatim — do not improvise an alternative design.

## Allowed write scope

- `batch/profile_builder/builder.py`
- `tests/batch/test_profile_build_snapshot.py`
- `.workflow/2026-07-30-reverse-spec-rfc-remediation/results/R2-*`

Nothing else. In particular: no `config/scoring_config.yaml` writes (repo rule),
no `pyproject.toml`, no other test module.

## Red-before-green contract (mandatory)

Step 1 writes the new regression test. Step 2 runs it **before** any
`builder.py` edit and you must save that failing output to
`.workflow/2026-07-30-reverse-spec-rfc-remediation/results/R2-regression-red.txt`.
Expected failure: `TypeError: build_profiles() got an unexpected keyword
argument 'chunk_size'`. A green-only evidence trail is a verification failure —
do not skip this.

After the fix, save the passing run to `results/R2-regression-green.txt`.

## Steps

1. Add `test_profile_build_streams_events_across_multiple_chunks` to
   `tests/batch/test_profile_build_snapshot.py` exactly as written in the plan.
   Check the existing imports in that file first and add only what is missing
   (`timedelta`, `ResolvedEventModel`, `ProfileArtifactModel` may already be there).
2. Run it, capture the RED evidence (see contract above).
3. Add `_BUILD_EXTRACT_CHUNK_SIZE = 5000` and the `_stream_events_to_jsonl`
   helper to `batch/profile_builder/builder.py`, after the imports and before
   `build_profiles`, exactly as specified in the plan.
4. Change the `build_profiles` signature (line ~408) to add the trailing
   keyword `chunk_size: int = _BUILD_EXTRACT_CHUNK_SIZE`, then replace the
   block from `import time` / `events_hist = ...` (~line 470) through the end of
   the `write_jsonl` usage (~line 528) with the replacement block in the plan.
   Then fix the remaining `if events_recent:` guard(s) later in the function
   (there is one at ~line 559 guarding the `query_recent` / `recent_features_map`
   block) to test `if temp_file_recent:` instead.
   **Grep `events_recent` and `events_hist` in `builder.py` afterwards — both
   must have zero remaining references.**
   The temp-file cleanup section iterates `[temp_file_hist, temp_file_recent]`
   and needs no change.
5. Re-run the regression test; capture GREEN evidence.
6. Run `pytest -v --tb=short --ignore=tests/live`. All must pass, including
   `test_profile_build_snapshot.py`, `test_shadow_profiles.py`,
   `test_profile_build_block_escalation.py`, `test_profile_builder_geo.py`,
   `test_alert_lifecycle_auto_resolve.py`, and
   `tests/batch/profile_builder/test_builder.py`. None of these pass
   `chunk_size`, so they exercise the new 5000 default and must produce
   identical results to before. Baseline to beat: 164 passed (R1); with your
   new test it should be 165.
7. Also run `ruff check .` (line-length 100) and fix any finding your diff introduced.
8. Confirm no stray `temp_events_hist_*.jsonl` / `temp_events_recent_*.jsonl`
   files are left in the repo root after the suite (the early-return path must
   unlink the hist temp file).
9. Commit with a scoped add:
   `git add batch/profile_builder/builder.py tests/batch/test_profile_build_snapshot.py`
   then commit with the plan's Step 7 message. Never `git add -A` / `git add .`
   — unrelated untracked root files (`AS_BUILT.md`, `DEBT_LEDGER.md`,
   `5638f86d-*`, `scratch/*.log`) must stay out.

## Correctness notes to respect

- Row payload must stay byte-for-byte equivalent to the old `write_jsonl`
  closure: same keys, same order, same `command_line` default of `""`.
- `build_profiles`'s public signature must stay backward compatible — 10+
  existing call sites pass `db`/`db_session` positionally and `as_of` by keyword.
- The early return (no historical events) must `unlink(missing_ok=True)` the
  hist temp file before returning, and must keep the existing
  `_auto_resolve_quiet_attested_alerts` / `_emit_build_block_supervisor_escalations`
  / `db_session.commit()` behavior unchanged.
- When the recent window is empty, `temp_file_recent` must end up `None` and its
  file unlinked, matching the old "never created" behavior for downstream code.

## Constraints

- Do not mark this packet `done`; do not edit `state.json`. The controller owns status.
- Do not run sprint/phase exit verification; this is a task, not a gate.
- Stop for approval before: dependency installs, editing `.codex`/`.claude`,
  cloning, writing outside the allowed scope, destructive git.

## Deliverable

`.workflow/2026-07-30-reverse-spec-rfc-remediation/results/R2-implementer-result.md` with:
header `model: composer-2.5`, packet id, timestamp, exact paths changed, the RED
evidence path and the failure line, the GREEN result, the `events_recent` /
`events_hist` grep output proving zero references, full-suite counts, ruff
result, temp-file check, commit SHA, and anything you could not do.
