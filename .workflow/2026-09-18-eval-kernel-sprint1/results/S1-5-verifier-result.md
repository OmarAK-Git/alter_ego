# S1-5 skeptic-verifier result

**Task:** S1-5 / Plan Task 5 — `gov.no_knob_without_sweep`
**Claim:** gov.no_knob_without_sweep evaluate_scenario is complete
**Verdict:** ACCEPT
**Branch:** `gsd/eval-kernel-sprint1` @ `4db2398`
**Date:** 2026-09-18

## Claim restated

Vague “complete” is unverifiable. The load-bearing claim is: `evaluate_scenario("gov.no_knob_without_sweep")` returns two `ScorecardRow`s (`old_build`, `new_build`) with `status=pass` when live `config/scoring_config.yaml` SHA-256 equals `tests/eval/fixtures/scoring_config_baseline.sha256`; `knob_exceptions.yaml` is empty (`exceptions: []`); theater is `series_j_fold` with `staffs_series_j=False`; this ID does not call `run_pipeline`; `ScorecardRow` did not gain a theater field.

## Fresh commands (re-run by verifier)

```
cd C:\Users\oalan\alter_ego
$env:PYTHONPATH = "."
pytest tests/eval/test_gov_no_knob_without_sweep.py -v --tb=short
ruff check batch/eval/e2e_kernel.py tests/eval/test_gov_no_knob_without_sweep.py
```

**pytest:** 2 passed, 0 failed (0.61s), exit 0

```
tests/eval/test_gov_no_knob_without_sweep.py::test_baseline_hash_file_matches_current_yaml PASSED
tests/eval/test_gov_no_knob_without_sweep.py::test_both_arms_pass_when_yaml_matches_baseline PASSED
============================== 2 passed in 0.61s ==============================
```

**ruff (Python files):** All checks passed (exit 0)

HEAD `4db2398b6f7204c53c38383409ab5df7591f130c` (“Pin no-knob-without-sweep as an eval-kernel governance row”). Working tree for the five Task 5 files matches HEAD. `ScorecardRow` fields unchanged vs schema (no theater attribute).

## Files re-read

- Brief: `.workflow/2026-09-18-eval-kernel-sprint1/packets/S1-5-brief.md`
- Plan Task 5: `docs/superpowers/plans/2026-09-08-eval-kernel-sprint1.md:1200-1306`
- `batch/eval/e2e_kernel.py` (`_eval_gov_no_knob_without_sweep` `:186-226`; `evaluate_scenario` `:229-233`)
- `tests/eval/test_gov_no_knob_without_sweep.py`
- `tests/eval/scenarios/gov.no_knob_without_sweep.yaml` (`events: none`, `theater_detector: series_j_fold`)
- `tests/eval/fixtures/scoring_config_baseline.sha256`
- `tests/eval/fixtures/knob_exceptions.yaml` (`exceptions: []`)
- `core/schemas/scorecard.py` (`ScorecardRow` `:54-66`; `PENDING_ALLOWED` `:45-51`)
- `batch/eval/theater.py` (`series_j_fold` flag `:117`)
- `batch/eval/scenario_loader.py` (`extra=forbid`; no `skip`)

## Refutation attempts (named holes)

Independent probes (not the pytest file) imported `evaluate_scenario`, AST-walked the two functions, hashed the live YAML, and patched baseline / theater / exceptions.

| Hole | What would prove it | Evidence | Hole stands? |
|---|---|---|---|
| `evaluate_scenario` calls `run_pipeline` for this ID | AST `Call` to `run_pipeline` / `run_production_call`, or a live call under monkeypatch | AST calls in `_eval_gov_no_knob_without_sweep` + `evaluate_scenario`: `load_scenario`, `_eval_gov_no_knob_without_sweep`, `run_theater_detector`, `_row`, hash/YAML reads. `RUN_PIPELINE_CALLS_IN_TARGETS []`. Monkeypatch of `batch.eval.e2e_kernel.run_pipeline` and `batch.eval.runner.run_pipeline`: `RUN_PIPELINE_CALLS 0`. YAML `setup.events: none`. Notes mention “no run_pipeline”; that is a string, not a call. | no |
| Baseline hash stale | live SHA-256 ≠ pinned file | Independent `hashlib.sha256(config/scoring_config.yaml)` = `26a00c3c17f70d459cf5fff9d2a23f0c230f65ab6e61c5a6ea30c350f39a4701`. Pinned file strip-equals that 64-hex digest. `HASH_MATCH True`. Controller hash test PASSED. Patched stale baseline (`0`*64) → both arms `fail` / `harness` / `knob_diff_unrecorded=True` (kernel actually compares). | no |
| Pending skip flag | `skip:` on YAML/test, `status=pending` rows, or a non-empty silent exception list | `knob_exceptions.yaml` is exactly `exceptions: []`. Scenario YAML and test file have no `skip` / `pytest.mark`. `ScenarioSpec` has no skip field (`extra=forbid`). `PENDING_ALLOWED` has no `gov.*` pair. Constructing `ScorecardRow(..., status="pending")` for this ID raises `pending illegal`. Live rows: `pass` / `none`, not `pending`. | no |
| `ScorecardRow` gained a theater field | new model field / accepted extra `theater_*` | `model_fields` = `schema_version, scenario_id, realm, arm, status, failure_class, expected, observed, fixture, notes`. `HAS_THEATER_FIELD False`. `extra=forbid`. `theater_detector_tripped=False` → `Extra inputs are not permitted`. Row dumps have no theater key. `failure_class` still allows the existing literal `"theater_detector"` (not a new field). Theater result lives in `notes` / optional `observed` only. | no |

Forced `run_theater_detector` trip → both arms `fail` / `theater_detector`. Reviewed exception naming the live digest on a mismatched baseline → both arms `pass` / `knob_diff_unrecorded=False` (allowlist is explicit, not a silent skip). `series_j_fold` + `staffs_series_j=False` → `(False, "")`; `True` → trips.

## Residual nits (not enough to REJECT)

- Controller tests do not assert “no `run_pipeline`”, mismatch-fail, or empty exceptions. Those paths are real; the suite would not catch a later hardcoded-pass kernel if the pin still matched.
- Test theater check is equivalent to `observed.get("theater_detector_tripped", False) is False`; kernel does not write that key.
- Detector name is hardcoded `"series_j_fold"` rather than `spec.theater_detector` (YAML matches today).

## Verdict

**ACCEPT.** The four named holes do not stand: this ID does not call `run_pipeline`, the pinned SHA-256 matches live YAML, there is no pending/skip escape, and `ScorecardRow` has no theater field. Fresh pytest **2/2** + ruff clean on the Python files.
