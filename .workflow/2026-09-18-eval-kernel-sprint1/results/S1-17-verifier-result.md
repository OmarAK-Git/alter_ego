# S1-17 skeptic-verifier result

**Task:** S1-17 / Plan Task 17 — `cap.attributed_s2_s3_s5`
**Claim:** `old_build` records attributed S2/S3/S5 B3a cells on compact seed-42 fixture (corpus `ci_compact_seed42_shaped`, each cell n>=1, not vacuous R=1.0); `new_build` is pending with `failure_class` none. ID is not `cap.attributed_s3`. Quality is recorded, not claimed useful. Series I TP=54 is not the comparison. `scoring_config.yaml` was not edited.
**Verdict:** ACCEPT
**Branch:** `gsd/eval-kernel-sprint1` @ `aed7b3d43f4794a0bc7b5a3fc8cb65eea8efe2f2`
**Date:** 2026-09-18

## Claim restated

Load-bearing claim: `evaluate_scenario("cap.attributed_s2_s3_s5")` emits two `ScorecardRow`s; `old_build.status=="pass"` with `observed.corpus=="ci_compact_seed42_shaped"` and B3a cells for `scenario_2_slow_roll`, `scenario_3_subtle`, `scenario_5_patient_cycle` each having `n>=1`, `attributed_tp`, `recall`, and `vacuous_r1 is False`; `old.observed.f1_treated_as_primary is False`; `new_build.status=="pending"` and `new.failure_class=="none"` without a second pipeline; fixture writer keeps ≤12 engineer + ≤12 finance, `seed=42`, injects S2/S3/S5; theater detector is `f1_only_usefulness`; `config/scoring_config.yaml` unchanged; no DecisionRecord INSERT as E2E substitute. ID is `cap.attributed_s2_s3_s5`, not `cap.attributed_s3`. Quality recorded, not usefulness. Not compared to Series I TP=54.

Vague “test passed” without those behaviors would be unverifiable; this verdict is from independent re-runs and a live `evaluate_scenario` dump, not the implementer transcript.

## Fresh commands (re-run by verifier)

```
cd C:\Users\oalan\alter_ego
$env:PYTHONPATH="."
pytest tests/eval/test_cap_attributed_s2_s3_s5.py -v --tb=short
ruff check batch/eval/e2e_kernel.py batch/eval/kernel_fixtures.py tests/eval/test_cap_attributed_s2_s3_s5.py
git diff HEAD -- config/scoring_config.yaml
```

**pytest:** 1 passed, 0 failed (50.40s), exit 0

```
tests/eval/test_cap_attributed_s2_s3_s5.py::test_attributed_s2_s3_s5_old_recorded_new_pending PASSED
====================== 1 passed, 274 warnings in 50.40s =======================
```

**ruff:** All checks passed (exit 0)

**git diff HEAD -- config/scoring_config.yaml:** empty (no output)

HEAD `aed7b3d43f4794a0bc7b5a3fc8cb65eea8efe2f2` (“Record attributed S2/S3/S5 B3a baseline; leave quality new_build pending”). Commit name-only: `batch/eval/e2e_kernel.py`, `batch/eval/kernel_fixtures.py`, `tests/eval/scenarios/cap.attributed_s2_s3_s5.yaml`, `tests/eval/test_cap_attributed_s2_s3_s5.py`. `git diff aed7b3d^..aed7b3d -- config/scoring_config.yaml` also empty.

Working tree at verify time: `M .workflow/2026-09-18-eval-kernel-sprint1/state.json`, `?? .workflow/2026-09-18-eval-kernel-sprint1/packets/S1-17-brief.md` — workflow packets only; not scoring config.

## Files re-read

- Plan Task 17: `docs/superpowers/plans/2026-09-08-eval-kernel-sprint1.md:2462-2610`
- `tests/eval/test_cap_attributed_s2_s3_s5.py` (controller asserts cells + pending)
- `tests/eval/scenarios/cap.attributed_s2_s3_s5.yaml` (`theater_detector: f1_only_usefulness`, `events: seed42_s2_s3_s5`)
- `batch/eval/e2e_kernel.py` (`attributed_tp` `:706-732`; `scenario_cell` `:749-754`; `_eval_cap_attributed_s2_s3_s5` `:757-822`; dispatch `:1108-1110`; `run_production_call` `:100-131` with `seeded_decision_insert=False`)
- `batch/eval/kernel_fixtures.py` (`write_compact_seed42_s2_s3_s5_jsonl` `:174-222`)
- `batch/eval/theater.py` (`f1_only_usefulness` `:115`)
- `batch/synthetic/generator.py` (`inject_scenario_2_slow_roll`, `inject_scenario_3_coordinated` labels `scenario_3_subtle`, `inject_scenario_5_patient_cycle(..., exclude_entity_ids=...)`)
- `core/schemas/scorecard.py` (`LOCKED_SCENARIO_IDS` includes `cap.attributed_s2_s3_s5`; `PENDING_ALLOWED` includes `(cap.attributed_s2_s3_s5, new_build)`)
- `scratch/run_series_i_sweep.py` `_is_drift_necessary` `:242-246` matches B3a (`score>=thr` ∧ `score-contrib_drift < thr` on `drift_alert`)

No `tests/eval/scenarios/cap.attributed_s3.yaml`. Test file has no `54` / `Series I` / `TP=54` strings.

## Independent probes (not the pytest file)

Imported `evaluate_scenario` + `write_compact_seed42_s2_s3_s5_jsonl` into a fresh tmp dir (second live run, ~37s). Dumped both rows and a fixture census.

Live `evaluate_scenario("cap.attributed_s2_s3_s5")`:

| arm | status | failure_class | observed (abridged) |
|---|---|---|---|
| old_build | pass | none | corpus=`ci_compact_seed42_shaped`; S2 `{n:35, attributed_tp:30, recall:0.857, vacuous_r1:False}`; S3 `{n:45, attributed_tp:30, recall:0.667, vacuous_r1:False}`; S5 `{n:35, attributed_tp:25, recall:0.714, vacuous_r1:False}`; `f1_treated_as_primary:False` |
| new_build | pending | none | `{quality: pending, corpus: ci_compact_seed42_shaped}`; notes=`Stage B unbuilt` |

`N_ROWS 2`. Both `scenario_id == cap.attributed_s2_s3_s5`. Pipeline log `Clearing database tables` occurred **once** (old_build only).

Fixture census from `write_compact_seed42_s2_s3_s5_jsonl`:

- engineers: **12** (`user_engineer_0`..`11`); finance: **12** (`user_finance_0`..`11`); other entity ids: **empty**
- `EventGenerator(seed=42)` keep filter matches; generator total entities 65 before keep
- malicious labels: S2=35, S3=45, S5=35 (matches live `n`)
- injects used: `inject_scenario_2_slow_roll`, `inject_scenario_3_coordinated` (label `scenario_3_subtle`), `inject_scenario_5_patient_cycle(..., exclude_entity_ids={s2 victim})`

B3a helper `attributed_tp` matches Series I `_is_drift_necessary` (threshold 45, feature `drift_alert`). `old_build` goes through `run_production_call` → `run_pipeline`. `new_build` `continue`s before `write_*` / `run_production_call`. No `DecisionRecordModel(` constructor in the cap path or `kernel_fixtures.py`.

## Refutation attempts (named holes)

| # | Hole | What would prove it | Evidence | Hole stands? |
|---|---|---|---|---|
| 1 | Not two rows / old not pass / new not pending | live row count ≠2, or statuses wrong | Live `N_ROWS 2`; old `pass`; new `pending`. Pytest asserts both arms. | no |
| 2 | corpus not `ci_compact_seed42_shaped` | observed.corpus other string, or fixture is Series I | Live old+new corpus string exact. Writer is compact seed-42, not Series I mix. | no |
| 3 | vacuous / missing S2/S3/S5 cells | n=0, missing keys, or R=1.0 with n=0 | Live n=35/45/35; `attributed_tp` 30/30/25; recall 0.857/0.667/0.714; `vacuous_r1` False on all three. None is R=1.0. | no |
| 4 | F1 treated as primary | `f1_treated_as_primary True` or theater `f1_only_usefulness` trips | Live False. YAML+`run_theater_detector("f1_only_usefulness", TheaterContext(f1_treated_as_primary=False))`. | no |
| 5 | new_build ran a second pipeline or is not pending | two `run_pipeline` / two DB clears, or new status pass | One DB clear. `new_build` branch `continue`s before fixture write/pipeline. `failure_class=="none"`. | no |
| 6 | fixture too large / wrong seed / missing inject | >12 eng or fin, seed≠42, missing S2/S3/S5 labels | 12+12, seed=42, all three injects, malicious n matches cells. | no |
| 7 | wrong theater detector | YAML/runtime not `f1_only_usefulness` | YAML line 18; evaluator uses `spec.theater_detector`. | no |
| 8 | `scoring_config.yaml` edited | git diff nonempty for that file on HEAD or in `aed7b3d` | Both diffs empty. Commit touches 4 eval files only. | no |
| 9 | DecisionRecord INSERT as E2E substitute | seeded insert / `DecisionRecordModel(` in fixture or cap eval | `run_production_call` sets `seeded_decision_insert=False`. No model INSERT in fixture writer. new_build does not insert rows. | no |
| ID | still `cap.attributed_s3` | locked id or yaml stem | `LOCKED_SCENARIO_IDS` has `cap.attributed_s2_s3_s5`; no `cap.attributed_s3.yaml`. Live `scenario_id` is the three-scenario id. | no |
| Series I | TP=54 comparison | test/eval compares to 54 | Grep of test file: no matches. Cells are 30/30/25 on compact n, not 54. | no |

## Residual nits (not enough to REJECT)

- Controller test does not assert `len(rows)==2` or `new.observed["quality"]=="pending"`. Independent dump saw both.
- `vacuous = n == 0 or (tp == 0 and recall == 1.0)` second clause is dead under `recall = tp/n if n else 0.0`. Vacuous-empty is still rejected via `n>=1`. Live recalls are not 1.0 anyway.
- `TheaterContext(f1_treated_as_primary=False)` is hardcoded; the detector cannot trip on this path. That matches “recorded, not claimed useful,” not a silent usefulness win.
- Post-inject event span is 17 calendar days / 12 weekdays (baseline loop is 10 calendar days). Plan “≤10 weekdays” is the compact baseline bound; injects are required to extend past it. Entity caps still hold.
- Compact-fixture attributed TP (30/30/25) is high; claim explicitly does not treat that as usefulness or as Series I TP=54.

## Verdict

**ACCEPT.** All nine load-bearing checks survived independent re-run: two rows, old pass / new pending, compact corpus, three non-vacuous B3a cells with n>=1, F1 not primary, no second pipeline, fixture caps+seed+injects, `f1_only_usefulness`, untouched `scoring_config.yaml`, pipeline-sourced decisions. Residual nits are test thinness and a dead vacuous clause, not missing behaviors.
