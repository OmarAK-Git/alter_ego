# S1-7 skeptic-verifier result

**Task:** S1-7 / Plan Task 7 — `gov.integrity_job_sees_decisions`
**Claim:** `evaluate_scenario("gov.integrity_job_sees_decisions")` returns two pass rows; `observed.integrity_skip=="decision_audit_count==0"`; `decision_count_gt_0` True; `count_check_skipped` True. Skip is named, not hidden. `run_pipeline` is used.
**Verdict:** ACCEPT
**Branch:** `gsd/eval-kernel-sprint1` @ `71e9284`
**Date:** 2026-09-18

## Claim restated

Load-bearing claim: `evaluate_scenario("gov.integrity_job_sees_decisions")` emits two `ScorecardRow`s (`old_build`, `new_build`) with `status=pass`; each `observed` has `integrity_skip == "decision_audit_count==0"`, `decision_count_gt_0 is True`, `count_check_skipped is True`; the skip is an explicit named field (not a silent/omitted pass); the path actually calls `run_pipeline` (via `run_production_call`).

## Fresh commands (re-run by verifier)

```
cd C:\Users\oalan\alter_ego
$env:PYTHONPATH = "."
pytest tests/eval/test_gov_integrity_job_sees_decisions.py -v --tb=short
ruff check batch/eval/e2e_kernel.py tests/eval/test_gov_integrity_job_sees_decisions.py
```

**pytest:** 1 passed, 0 failed (2.81s), exit 0

```
tests/eval/test_gov_integrity_job_sees_decisions.py::test_integrity_skip_is_named_after_pipeline_decisions PASSED
======================== 1 passed, 6 warnings in 2.81s ========================
```

**ruff:** All checks passed (exit 0)

HEAD `71e928475d255b5bf7f0089f29e8976acfe7ef0a` (“Name the audit-integrity decision skip as an eval-kernel row”). Working tree clean at verify time.

## Files re-read

- Plan Task 7: `docs/superpowers/plans/2026-09-08-eval-kernel-sprint1.md:1398-1475`
- `batch/eval/e2e_kernel.py` (`run_production_call` `:87-121`; `_eval_gov_integrity_job_sees_decisions` `:294-339`; `evaluate_scenario` `:342-350`)
- `tests/eval/test_gov_integrity_job_sees_decisions.py`
- `tests/eval/scenarios/gov.integrity_job_sees_decisions.yaml` (`setup.call: run_pipeline`, `theater_detector: unit_as_e2e`)
- `batch/audit_integrity.py` (`run_integrity_check` `:35-53`)
- `core/models.py` (`verify_audit_log_chain` `:164-200`; `count_check_skipped` when `decision_audit_count == 0`)
- `worker/recorder.py` (`record_decision` `:45-86` — no `log_audit_event` / `AuditLogModel`)
- `batch/eval/theater.py` (`unit_as_e2e` `:57-60`)

## Independent probes (not the pytest file)

Imported `evaluate_scenario` and `run_integrity_check` directly. Monkeypatched `batch.eval.e2e_kernel.run_pipeline` and `run_integrity_check` to count live calls. AST-walked `_eval_gov_integrity_job_sees_decisions`. Ran a separate `run_production_call` + `run_integrity_check` and queried `DecisionRecordModel` / `AuditLogModel`. Forced unnamed-skip via fake `AuditIntegrityResult(count_check_skipped=False, decision_audit_count=5)`.

Live `evaluate_scenario` (fresh tmp):

| arm | status | failure_class | integrity_skip | decision_count_gt_0 | count_check_skipped | decision_audit_count |
|---|---|---|---|---|---|---|
| old_build | pass | none | `decision_audit_count==0` | True | True | None |
| new_build | pass | none | `decision_audit_count==0` | True | True | None |

`ROW_COUNT 2`. `PIPELINE_CALLS 2`. `INTEGRITY_CALLS 2`.

Direct DB after `run_production_call` + `run_integrity_check`: `DIRECT_DECISION_COUNT 32`, `DIRECT_AUDIT_LOG_COUNT 0`, `count_check_skipped True`, `decision_audit_count None` (chain maps `0` → `None`), `ok True`.

## Refutation attempts (named holes)

| Hole | What would prove it | Evidence | Hole stands? |
|---|---|---|---|
| Silent skip | pass with missing/None `integrity_skip`, or no skip field | Live observed `integrity_skip == "decision_audit_count==0"` on both arms. Kernel sets that string only when `count_check_skipped` and `decision_audit_count in {0, None}` (`e2e_kernel.py:311-323`). | no |
| No pipeline | AST/live with zero `run_pipeline` / `run_production_call` | Function AST calls `run_production_call` (not `run_pipeline` directly). `run_production_call` calls imported `run_pipeline` (`e2e_kernel.py:94`). Live wrap of `batch.eval.e2e_kernel.run_pipeline`: **2 calls** (one per arm). YAML `setup.call: run_pipeline`. | no |
| `decision_count==0` | live `DecisionRecord` count 0, or `decision_count_gt_0` hardcoded True while DB empty | Direct count **32**. Both arms `decision_count_gt_0 True`. Pass requires `call.decision_count > 0` (`e2e_kernel.py:322`). | no |
| Hardcoded pass without named skip | still `pass` when skip unnamed | Fake integrity (`count_check_skipped=False`, `decision_audit_count=5`): both arms **`fail` / `harness`**, `integrity_skip None`. Single `pass` literal is behind `skip == "decision_audit_count==0" and call.decision_count > 0`. | no |

`record_decision` writes `DecisionRecordModel` only — no audit row — which is why `decision_audit_count` is 0/None and the skip exists. That is the named skip, not a hidden one.

## Residual nits (not enough to REJECT)

- Controller test does not assert `len(rows)==2`; an empty list would vacuous-pass the `for` loop. Independent probe saw two arms.
- `TheaterContext(used_run_pipeline=True)` is hardcoded; `unit_as_e2e` does not independently observe the call. Live monkeypatch does.
- Observed `decision_audit_count` is `None` (ORM maps 0 → None), not the integer `0`. The skip **name** is still `decision_audit_count==0`.

## Verdict

**ACCEPT.** The four named holes do not stand: skip is named, `run_pipeline` ran twice, decision count is 32 (not 0), and unnamed skip fails closed. Fresh pytest **1/1** + ruff clean on the Python files.
