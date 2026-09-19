# S1-2 skeptic-verifier result

**Task:** S1-2 / Plan Task 2 — E2E kernel sibling of `batch/eval/runner.py` + CLI / pytest entry
**Claim:** Task S1-2 is complete — e2e kernel calls `run_pipeline` on a SQLite bind
**Verdict:** REJECT
**Branch:** `gsd/eval-kernel-sprint1` @ `81e99ae`
**Date:** 2026-09-18

## Claim restated

S1-2 is done: `run_production_call` rebinds SQLite, invokes unchanged `run_pipeline`, does not INSERT `DecisionRecord` itself, derives the five stages from post-pipeline counts, and `python -m batch.eval.e2e_kernel --assert-complete --only des.production_call_shape` writes a stub scorecard then exits nonzero because 30 rows are missing.

## Fresh commands (re-run by verifier)

```
cd C:\Users\oalan\alter_ego
$env:PYTHONPATH = "."
pytest tests/eval/test_e2e_kernel.py -v --tb=short
ruff check batch/eval/e2e_kernel.py batch/eval/scorecard.py batch/eval/kernel_fixtures.py tests/eval
```

**pytest:** 2 passed, 0 failed (4.00s), exit 0

```
tests/eval/test_e2e_kernel.py::test_run_production_call_invokes_all_five_stages_and_does_not_insert_decisions_itself PASSED
tests/eval/test_e2e_kernel.py::test_cli_writes_scorecard_and_exits_nonzero_on_missing_row PASSED
======================== 2 passed, 3 warnings in 4.00s ========================
```

**ruff:** All checks passed (exit 0)

## Files re-read (Task 2 named set + `run_pipeline`)

- `docs/superpowers/plans/2026-09-08-eval-kernel-sprint1.md` Task 2 only (through Task 3 heading)
- `batch/eval/e2e_kernel.py`
- `batch/eval/scorecard.py`
- `batch/eval/kernel_fixtures.py`
- `tests/eval/conftest.py`
- `tests/eval/helpers.py`
- `tests/eval/test_e2e_kernel.py`
- `batch/eval/runner.py` (`run_pipeline` at line 96; five stages at 152–161)
- `worker/scorer.py` (`process_unscored_events` → `record_decision` at 862)
- `core/schemas/scorecard.py` (15 locked IDs)

Implementer packet `packets/S1-2-report.md` was not used as evidence.

## Refutation attempts (named holes)

| Hole | What would prove it | Fresh evidence | Hole stands? |
|---|---|---|---|
| Kernel inserts `DecisionRecord` itself | `DecisionRecord(` / `DecisionRecordModel(` / `.add(` / `record_decision(` in `e2e_kernel.py` | Source scan: all four needles **False**. Only `select(func.count()).select_from(DecisionRecordModel)` at `e2e_kernel.py:81`. `seeded_decision_insert` is hardcoded `False` (`:99`) — weak test, but no insert exists. | no |
| `run_pipeline` signature changed | S1-2 commit or working tree edits `runner.py` | `git show 81e99ae` does **not** include `batch/eval/runner.py`. Working tree clean for that file. `inspect.signature`: `(events_path, labels_path, window_delta_days=1, *, clear_first=True, windows_per_invocation=None, resume_from=None)`. Last runner commit is `f96f07b` (Series I), not S1-2. | no |
| CLI `--assert-complete` exits 0 | Independent `python -m batch.eval.e2e_kernel --scorecard-out … --assert-complete --only des.production_call_shape` returns 0 | Subprocess **returncode=1**. Does **not** exit 0. | no (not this hole) |
| Stages not actually from `run_pipeline` | Kernel skips `run_pipeline` or fakes the `stages` dict | Spy wrap: `SPY_CALLS=1` with the fixture `events.jsonl` / `labels.jsonl`. After call: `ENGINE_URL=sqlite:///…/probe.db` (posix bind), `DECISIONS=32`, all five stage flags True. Stages are count-inferred after `run_pipeline` exactly as Task 2 Step 3 specifies (`e2e_kernel.py:76-88`; runner five call sites `runner.py:152-161`). | no |

## Why completion still fails (letter vs intent)

The official CLI test is gamed. `test_cli_writes_scorecard_and_exits_nonzero_on_missing_row` (`tests/eval/test_e2e_kernel.py:74-96`) only asserts `proc.returncode != 0`. It never checks that a scorecard was written, that stderr mentions missing rows, or that the process reached `assert_scorecard_complete`.

Independent replay of that exact subprocess on this Windows host:

```
SUBPROC_RETURN=1
SCORECARD_EXISTS=False
STDERR_HAS_PERMISSION=True
STDERR_HAS_INCOMPLETE=False
```

Traceback (trimmed): `PermissionError: [WinError 32]` unlinking `…\Temp\tmp…\eval.db` inside `tempfile.TemporaryDirectory.__exit__` from `_production_call_shape_row` (`e2e_kernel.py:107`). `main()` dies at `rows.append(_production_call_shape_row())` (`:151`) **before** `write_scorecard` (`:160`) and **before** `assert_scorecard_complete` (`:164`).

Cause: `bind_sqlite` creates a SQLAlchemy engine on that SQLite file and never `dispose()`s it. `result.db.close()` (`:135`) drops the session only. Windows will not unlink a file still held by the engine. Task 2’s specified success condition is “exit nonzero because 30 rows are missing.” What actually happens is an unhandled cleanup crash that happens to be nonzero, so the test stays green.

Plan Task 2 / brief: `--only des.production_call_shape` may synthesize one row so `--assert-complete` stays red on the missing 30. That path is not exercised on Windows.

## Residual nits (not the reject reason)

- `seeded_decision_insert is False` is an unmeasured constant; the no-insert claim is proven by source scan, not by the test.
- Test helper writes empty labels; `kernel_fixtures.write_mini_pipeline_jsonl` writes one benign label (allowed by Task 2).
- Interfaces list `bind_sqlite_engine(url)`; Step 3 specifies `bind_sqlite(sqlite_path)`. Implementation follows Step 3.
- Unused `monkeypatch` fixtures in both tests; ruff did not flag them.

## Verdict

**REJECT.** `run_pipeline` is called on a rebound SQLite engine and the kernel does not insert decisions — those named holes do not stand. Completeness is still false: the required CLI `--assert-complete` path crashes on Windows file lock, writes no scorecard, never runs `assert_scorecard_complete`, and the official test cannot see that because it only checks nonzero exit.

Fix that is sufficient to re-verify: dispose the bound engine (and any leftover connection) before `TemporaryDirectory` cleanup, then make the CLI test assert scorecard exists, contains the synthesized `des.production_call_shape` row, stderr/exit come from `IncompleteScorecardError` / missing rows, and `returncode != 0`.
