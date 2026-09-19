# S1-3 skeptic-verifier result

**Task:** S1-3 / Plan Task 3 — Scenario YAML loader + first `des.production_call_shape.yaml`
**Claim:** scenario YAML loader + `des.production_call_shape.yaml` is complete
**Verdict:** ACCEPT
**Branch:** `gsd/eval-kernel-sprint1` @ `c39f75c`
**Date:** 2026-09-18

## Claim restated

`batch/eval/scenario_loader.py` ships a frozen `ScenarioSpec` contract (`load_scenario` / `load_all_scenarios` / local `ALLOWED_THEATER`), the four plan tests lock stem match, `runner: e2e_kernel`, no skip flags, and tree load, and `tests/eval/scenarios/des.production_call_shape.yaml` is the first real scenario file.

Vague “complete” without those four behaviors would be unverifiable. Those are the load-bearing checks.

## Fresh commands (re-run by verifier)

```
cd C:\Users\oalan\alter_ego
$env:PYTHONPATH = "."
pytest tests/eval/test_scenario_loader.py -v --tb=short
ruff check batch/eval/scenario_loader.py tests/eval/test_scenario_loader.py
```

**pytest:** 4 passed, 0 failed (0.19s), exit 0

```
tests/eval/test_scenario_loader.py::test_filename_stem_must_equal_scenario_id PASSED
tests/eval/test_scenario_loader.py::test_runner_must_be_e2e_kernel PASSED
tests/eval/test_scenario_loader.py::test_skip_flag_field_is_rejected PASSED
tests/eval/test_scenario_loader.py::test_load_des_production_call_shape_from_tree PASSED
============================== 4 passed in 0.19s ==============================
```

**ruff:** All checks passed (exit 0)

Commit `c39f75cb1f92fc8e7fff1fe56bd5216f0a70eae0` (“Add eval scenario YAML contract and production-call-shape spec”) contains only:

- `batch/eval/scenario_loader.py`
- `tests/eval/test_scenario_loader.py`
- `tests/eval/scenarios/des.production_call_shape.yaml`

Working tree for those three files matches HEAD. `e2e_kernel.py` and `scoring_config.yaml` were not touched.

## Files re-read

- Plan Task 3 only: `docs/superpowers/plans/2026-09-08-eval-kernel-sprint1.md:680-926`
- Design spec §8 theater names: `docs/superpowers/specs/2026-09-08-eval-kernel-usefulness-canary-design.md:365-378`
- `batch/eval/scenario_loader.py` (stem wrap at `:80-96`; `extra="forbid"` / `frozen=True` at `:41`)
- `tests/eval/test_scenario_loader.py` (plan’s four tests; imports trimmed to `load_scenario`)
- `tests/eval/scenarios/des.production_call_shape.yaml` (stem == `des.production_call_shape`)

## Refutation attempts (named holes)

Independent probes (not the pytest file) wrote the plan fixtures into a temp dir and called `load_scenario` directly. A matching-stem control used the same YAML bytes as the stem-mismatch case.

| Hole | What would prove it | Evidence | Hole stands? |
|---|---|---|---|
| skip flag accepted | `skip: true` loads, or is dropped silently (`extra="ignore"`) | `SKIP_LOAD: ValidationError` `loc=('skip',) type=extra_forbidden`. Direct `ScenarioSpec.model_validate(..., skip=True)` also `extra_forbidden`. First YAML has no `skip:` key. | no |
| stem mismatch not rejected | same-content file named `des.no_llm_in_score.yaml` loads, or fails for a *different* reason so the test is a false positive | Mismatch: `ValidationError` `loc=('scenario_id',)` message `filename stem 'des.no_llm_in_score' != scenario_id 'des.production_call_shape'`. Same bytes under `des.production_call_shape.yaml`: `ACCEPTED ScenarioSpec`. | no |
| runner `demo_path` accepted | `runner: demo_path` validates | `RUNNER_DEMO_PATH: ValidationError` `loc=('runner',) type=literal_error` `Input should be 'e2e_kernel'`. First YAML runner is `e2e_kernel`. | no |
| missing first YAML | file absent, empty, or unloadable | `tests/eval/scenarios/des.production_call_shape.yaml` exists (546 bytes). `load_scenario` returns `ScenarioSpec` with `scenario_id=des.production_call_shape`, `runner=e2e_kernel`, `theater_detector=unit_as_e2e`, arms `{old_build, new_build}`, pins `[stages_complete, seeded_decision_insert]`. Only `*.yaml` in that dir. `load_all_scenarios` returns that one id. | no |

`pytest.raises(ValidationError)` is broad, but the independent errors are the *right* types/locs, and the stem control proves the mismatch fixture is otherwise valid.

## Other checks (not named holes)

- `ALLOWED_THEATER` is the exact 10 design-spec §8 names (`THEATER_EQ_SPEC8 True`).
- `ScenarioSpec` is frozen: assigning `spec.runner = "demo_path"` raises `ValidationError`.
- Unknown theater `not_a_theater` is rejected (`loc=('theater_detector',)`).
- Brief-required stem wrap is `ValidationError.from_exception_data`, not a bare `ValueError`.
- No extra scenario YAMLs; Task 4 theater registry not implemented (local `ALLOWED_THEATER` remains, as planned).

## Residual nits (not enough to REJECT)

- Tests do not assert error `loc` / `type` (only `ValidationError`). Independent probe closed that gap for this pass.
- `load_all_scenarios` and `ScenarioSpec` are not imported by the test module (ruff F401). Function exists and loaded the tree in the probe.
- Tree test does not pin `scorecard_pins` or `seeded_decision_insert`; the YAML still matches the plan bytes besides the unicode arrow in `description`.
- `SCENARIO_DIR = Path("tests/eval/scenarios")` is cwd-relative (same as the plan).

## Verdict

**ACCEPT.** The four named holes do not stand: skip is `extra_forbidden`, stem mismatch is a `ValidationError` (and the same YAML loads when the stem matches), `demo_path` is a runner literal error, and the first YAML is on disk and loadable. Fresh pytest 4/4 + ruff clean.
