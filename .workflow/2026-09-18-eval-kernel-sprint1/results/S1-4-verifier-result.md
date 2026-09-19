# S1-4 skeptic-verifier result

**Task:** S1-4 / Plan Task 4 — Theater detector registry
**Claim:** Task S1-4 theater registry is complete
**Verdict:** ACCEPT
**Branch:** `gsd/eval-kernel-sprint1` @ `78caae2`
**Date:** 2026-09-18

## Claim restated

`batch/eval/theater.py` is the single source for the ten spec §8 names (`THEATER_DETECTOR_NAMES` + `REGISTRY` + `run_theater_detector`), `scenario_loader.py` imports that set and no longer defines `ALLOWED_THEATER`, `n1_headline` trips on an S1/S4-only headline, and an unknown detector name raises `KeyError` (not a silent ignore). Vague “complete” without those four behaviors is unverifiable. Those are the load-bearing checks.

## Fresh commands (re-run by verifier)

```
cd C:\Users\oalan\alter_ego
$env:PYTHONPATH = "."
pytest tests/eval/test_theater.py tests/eval/test_scenario_loader.py -v --tb=short
ruff check batch/eval/theater.py batch/eval/scenario_loader.py tests/eval/test_theater.py
```

**pytest:** 16 passed, 0 failed (0.20s), exit 0

```
tests/eval/test_theater.py::test_registry_has_exactly_the_ten_named_checks PASSED
tests/eval/test_theater.py::test_n1_headline_trips_on_s1_s4_only_decision_criterion PASSED
tests/eval/test_theater.py::test_n1_headline_passes_when_s2_s3_s5_present_with_n PASSED
tests/eval/test_theater.py::test_seeded_decision_e2e_trips_when_demo_insert_counted_as_win PASSED
tests/eval/test_theater.py::test_unit_as_e2e_trips_without_run_pipeline PASSED
tests/eval/test_theater.py::test_gt_in_scorer_trips_on_label_import PASSED
tests/eval/test_theater.py::test_fake_ingest_api_trips_on_http_ingest_route PASSED
tests/eval/test_theater.py::test_unearned_demo_claim_trips_on_series_a_as_current PASSED
tests/eval/test_theater.py::test_f1_only_usefulness_trips_when_flagged PASSED
tests/eval/test_theater.py::test_stage_a_as_fp_win_trips_when_flagged PASSED
tests/eval/test_theater.py::test_series_j_fold_trips_when_flagged PASSED
tests/eval/test_theater.py::test_auto_resolved_as_precision_trips_when_flagged PASSED
tests/eval/test_scenario_loader.py::test_filename_stem_must_equal_scenario_id PASSED
tests/eval/test_scenario_loader.py::test_runner_must_be_e2e_kernel PASSED
tests/eval/test_scenario_loader.py::test_skip_flag_field_is_rejected PASSED
tests/eval/test_scenario_loader.py::test_load_des_production_call_shape_from_tree PASSED
============================= 16 passed in 0.20s ==============================
```

**ruff:** All checks passed (exit 0)

HEAD `78caae27283622a4f912c751c0027241e6b27f17` (“Add named theater-detector registry for the eval kernel”). Working tree for `theater.py`, `scenario_loader.py`, and `test_theater.py` matches HEAD. `config/scoring_config.yaml` was not touched. `/api/ingest` appears only as the `fake_ingest_api` detail string.

## Files re-read

- Brief: `.workflow/2026-09-18-eval-kernel-sprint1/packets/S1-4-brief.md`
- Plan Task 4: `docs/superpowers/plans/2026-09-08-eval-kernel-sprint1.md:930-1196`
- Design spec §8 names: `docs/superpowers/specs/2026-09-08-eval-kernel-usefulness-canary-design.md:365-378`
- `batch/eval/theater.py` (`THEATER_DETECTOR_NAMES` `:6-19`; `_n1_headline` `:36-45`; `REGISTRY` `:108-121`; `run_theater_detector` KeyError `:124-127`)
- `batch/eval/scenario_loader.py` (import `:9`; validator uses `THEATER_DETECTOR_NAMES` `:47-50`; no `ALLOWED_THEATER`)
- `tests/eval/test_theater.py` (plan’s twelve tests; no unknown-name case)
- `tests/eval/test_scenario_loader.py` + `tests/eval/scenarios/des.production_call_shape.yaml`

## Refutation attempts (named holes)

Independent probes (not the pytest file) imported `run_theater_detector` / `REGISTRY` / `ScenarioSpec` directly and compared names to spec §8.

| Hole | What would prove it | Evidence | Hole stands? |
|---|---|---|---|
| `ALLOWED_THEATER` still defined locally in `scenario_loader` | assignment, module attr, or source string still present | AST assigns exclude it. `'ALLOWED_THEATER' in src` is False. `hasattr(scenario_loader, 'ALLOWED_THEATER')` is False. File imports `from batch.eval.theater import THEATER_DETECTOR_NAMES` and validates against that set. Repo-wide `*.py` grep: no `ALLOWED_THEATER`. | no |
| Missing one of the 10 spec §8 names | `THEATER_DETECTOR_NAMES` or `REGISTRY` missing/extra vs spec table | `THEATER_DETECTOR_NAMES == SPEC8` True. Missing `[]`, extra `[]`. `set(REGISTRY) == set(THEATER_DETECTOR_NAMES)` True. Count 10/10/10. All ten names are invoked by `test_theater.py` (not names-only). | no |
| `n1_headline` does not trip S1/S4-only headline | S1/S4-only text returns `tripped is False` | Plan fixture: `True` / `'headline reports S1/S4 without S2+S3+S5 n-attributed catch'`. Distinct alt `'Decision criterion: S1 and S4 only'`: also `True`. S1-only and S4-only: `True`. S2+S3+S5 fixture and all-five: `False`. Empty: `False`. | no |
| Unknown detector name silently ignored | `run_theater_detector` returns a tuple / no exception | `'not_a_detector'`, `'N1_HEADLINE'`, `'n1_headlines'`, `''`, `'seeded'` all raise `KeyError` with that name. Loader unknown `not_a_theater` is `ValidationError` `loc=('theater_detector',)` `value_error` (not silent). Tree YAML still loads `theater_detector=unit_as_e2e`. | no |

`test_theater.py` has **no** `KeyError` case (grep: no `KeyError` / `unknown` / `not_a_detector`). That gap is closed by the independent probe, not by the suite.

## Residual nits (not enough to REJECT)

- Unknown-name `KeyError` is untested in `test_theater.py`. Behavior is real; the suite would not catch a later silent `.get()`.
- `test_registry_has_exactly_the_ten_named_checks` asserts only `THEATER_DETECTOR_NAMES`, not `REGISTRY` equality. Probe confirmed they match.
- `_n1_headline` is substring (`"S1" in text`); `"S10"` would trip. Same as the plan snippet.
- `_seeded` does not trip when `decision_insert_path` is set **and** `used_run_pipeline` is True (plan copy). Flag detectors are boolean stubs (plan copy).

## Verdict

**ACCEPT.** The four named holes do not stand: local `ALLOWED_THEATER` is gone, the ten spec §8 names are the registry, S1/S4-only headlines trip `n1_headline` (plan string and an independent alt), and unknown names raise `KeyError`. Fresh pytest **16/16** + ruff clean.
