# S1-2 skeptic-verifier result (re-verify)

**Task:** S1-2 / Plan Task 2 — E2E kernel sibling of `batch/eval/runner.py` + CLI / pytest entry
**Claim:** complete after `dispose_eval_bind` + strengthened CLI test
**Verdict:** ACCEPT
**Branch:** `gsd/eval-kernel-sprint1` @ `c61eda0`
**Date:** 2026-09-18

## Claim restated

The prior REJECT hole is closed: `dispose_eval_bind` releases the rebound SQLite engine before `TemporaryDirectory` cleanup, and `test_cli_writes_scorecard_and_exits_nonzero_on_missing_row` now requires a written scorecard plus a missing-rows completeness failure (not WinError 32).

## Fresh commands (re-run by verifier)

```
cd C:\Users\oalan\alter_ego
$env:PYTHONPATH = "."
pytest tests/eval/test_e2e_kernel.py -v --tb=short
```

**pytest:** 2 passed, 0 failed (3.64s), exit 0

```
tests/eval/test_e2e_kernel.py::test_run_production_call_invokes_all_five_stages_and_does_not_insert_decisions_itself PASSED
tests/eval/test_e2e_kernel.py::test_cli_writes_scorecard_and_exits_nonzero_on_missing_row PASSED
======================== 2 passed, 3 warnings in 3.64s ========================
```

## Files re-read this pass

- `batch/eval/e2e_kernel.py` (`dispose_eval_bind` at `:69-78`; called on pipeline exception `:114` and in `_production_call_shape_row` finally `:147`)
- `tests/eval/test_e2e_kernel.py` (CLI test now asserts no `PermissionError`, `"missing scorecard rows"` in stderr, file exists, and contains `des.production_call_shape` / `old_build` — `:96-102`)

## Independent CLI replay (not the pytest subprocess)

Same argv as the test: `python -m batch.eval.e2e_kernel --scorecard-out <tmp>/scorecard.jsonl --assert-complete --only des.production_call_shape`

```
SUBPROC_RETURN=1
SCORECARD_EXISTS=True
STDERR_HAS_PERMISSION=False
STDERR_HAS_INCOMPLETE=True
SCORECARD_ROWS=1
ROW_ID=des.production_call_shape
ROW_ARM=old_build
ROW_STATUS=pass
```

Stderr ends with `missing scorecard rows:` and 29 `(scenario_id, arm)` pairs (15×2 expected minus the synthesized `des.production_call_shape`/`old_build`). No `PermissionError` / `WinError 32`. Scorecard JSON includes `observed.stages` all true, `event_count=48`, `decision_count=32`.

Returncode is 1 because `assert_scorecard_complete` raised `IncompleteScorecardError` after `write_scorecard` (`e2e_kernel.py:172-179`), not because tempfile cleanup crashed.

## Prior REJECT holes (re-checked)

| Prior hole | This pass | Stands? |
|---|---|---|
| CLI crashes on WinError 32; no scorecard | Independent replay: file written, no PermissionError | no |
| Test only checked `returncode != 0` | Test now checks scorecard + missing-rows stderr + no PermissionError (`test_e2e_kernel.py:96-102`) | no |
| `assert_scorecard_complete` never reached | Stderr lists 29 missing pairs from that function | no |

Named Task 2 holes from the first pass (kernel insert, `run_pipeline` signature, stages not from `run_pipeline`) were already closed and were not reopened by `c61eda0`.

## Residual nits (not enough to REJECT)

- `seeded_decision_insert` is still a hardcoded `False`; no-insert is proven by source scan, not measurement.
- Stage test still does not call `dispose_eval_bind` (CLI path does). pytest `tmp_path` cleanup did not fail this run.
- CLI test matches substrings rather than `ScorecardRow.model_validate`; independent replay parsed one valid row.

## Verdict

**ACCEPT.** The Windows dispose fix and the strengthened CLI test hold under an independent subprocess replay: scorecard exists, exit is nonzero because 29 scorecard rows are missing, and WinError 32 is gone.
