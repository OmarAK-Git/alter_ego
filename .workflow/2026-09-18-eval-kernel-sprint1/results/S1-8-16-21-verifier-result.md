# S1-8..S1-16 + S1-21 skeptic-verifier result

**Tasks:** S1-8..S1-16 (des/thr/use rows) and S1-21 (Series I SoT docs)
**Claim:** `evaluate_scenario` for those IDs returns both arms as specified (`thr.fp_block_sanctuary` `new_build` pending; others pass). Packet pytest listed in S1-P1-GATE commands all pass. `scoring_config.yaml` untouched (`anomaly_threshold` 45.0). No `/api/ingest`. Series I SoT: README and `docs/SPEC.md` name Series I and mark Series A archival. `SPEC.md` == `docs/SPEC.md` bytes. `use.demo_honesty` both arms pass on live files.
**Verdict:** ACCEPT
**Branch:** `gsd/eval-kernel-sprint1` @ `e11019d`
**Date:** 2026-09-18

## Claim restated

Load-bearing claim, five parts:

1. Fresh `evaluate_scenario` for S1-8..S1-16 IDs emits two `ScorecardRow`s; `thr.fp_block_sanctuary` `new_build` is `pending` / `failure_class=none`; every other arm on those IDs is `pass`.
2. The exact S1-P1-GATE pytest list in `.workflow/autopilot-queue.json` is 16/16 pass.
3. `config/scoring_config.yaml` is unchanged vs baseline SHA; `anomaly_threshold` is 45.0.
4. `web/api.py` has no `/api/ingest`. README and `docs/SPEC.md` name Series I and mark Series A archival. Root `SPEC.md` is byte-identical to `docs/SPEC.md`.
5. Live-file `use.demo_honesty` both arms `pass` (`unearned_demo_claim` False). Named refutes (illegal `pending`, seeded `DecisionRecord` INSERT, lowered threshold, SPEC mismatch, demo honesty still trips) do not stand.

## Fresh commands (re-run by verifier)

```
cd C:\Users\oalan\alter_ego
$env:PYTHONPATH = "."
pytest tests/eval/test_gov_no_knob_without_sweep.py tests/eval/test_gov_anomaly_opens_workflow.py tests/eval/test_gov_integrity_job_sees_decisions.py tests/eval/test_des_production_call_shape.py tests/eval/test_des_no_llm_in_score.py tests/eval/test_des_ngram_mismatch_halts.py tests/eval/test_thr_cmdline_injection_survives.py tests/eval/test_thr_api_key_required.py tests/eval/test_thr_fp_block_sanctuary.py tests/eval/test_use_pipeline_to_triage.py tests/eval/test_use_ui_sends_api_key.py tests/eval/test_use_demo_honesty.py -v --tb=short
ruff check batch/eval core/schemas/scorecard.py tests/eval
ruff check .
```

**pytest:** 16 passed, 0 failed (49.48s), exit 0

```
tests/eval/test_gov_no_knob_without_sweep.py::test_baseline_hash_file_matches_current_yaml PASSED
tests/eval/test_gov_no_knob_without_sweep.py::test_both_arms_pass_when_yaml_matches_baseline PASSED
tests/eval/test_gov_anomaly_opens_workflow.py::test_pipeline_anomaly_opens_new_workflow_both_arms PASSED
tests/eval/test_gov_integrity_job_sees_decisions.py::test_integrity_skip_is_named_after_pipeline_decisions PASSED
tests/eval/test_des_production_call_shape.py::test_production_call_shape_both_arms PASSED
tests/eval/test_des_no_llm_in_score.py::test_scorer_import_guard_on_live_source PASSED
tests/eval/test_des_no_llm_in_score.py::test_des_no_llm_in_score_both_arms PASSED
tests/eval/test_des_ngram_mismatch_halts.py::test_nomic_metadata_halts_both_arms PASSED
tests/eval/test_thr_cmdline_injection_survives.py::test_cmdline_injection_survives_ingest_both_arms PASSED
tests/eval/test_thr_api_key_required.py::test_api_key_required_without_pytest_bypass PASSED
tests/eval/test_thr_fp_block_sanctuary.py::test_sanctuary_old_build_recorded_new_build_pending PASSED
tests/eval/test_use_pipeline_to_triage.py::test_pipeline_anomaly_reaches_alerts_api PASSED
tests/eval/test_use_ui_sends_api_key.py::test_kernel_names_missing_ui_api_key PASSED
tests/eval/test_use_demo_honesty.py::test_detector_trips_on_series_a_current_fixture PASSED
tests/eval/test_use_demo_honesty.py::test_live_docs_pass_demo_honesty_both_arms PASSED
tests/eval/test_use_demo_honesty.py::test_readme_and_spec_mark_series_a_archival PASSED
====================== 16 passed, 174 warnings in 49.48s ======================
```

**ruff (narrow + `ruff check .` as listed on S1-P1-GATE):** All checks passed (exit 0 both).

HEAD `e11019dd83830d10875f471dfc3b6647d86c8f5a` (“Point docs at Series I SoT and the Sprint 1 eval kernel.”). Working tree clean at verify time.

## Files re-read

- Queue S1-P1-GATE commands: `.workflow/autopilot-queue.json:39`
- Plan Tasks 8–16, 21: `docs/superpowers/plans/2026-09-08-eval-kernel-sprint1.md:1494-3076`
- `batch/eval/e2e_kernel.py` (`run_production_call` `:96-131`; sanctuary `:731-802`; demo honesty `:893-932`; `evaluate_scenario` `:977-1017`; `ANOMALY_THRESHOLD = 45.0` `:699`)
- `batch/eval/kernel_fixtures.py` (`write_sanctuary_jsonl` `:123-170` — JSONL only)
- `batch/eval/theater.py` (`_unearned` `:76-97`; `_seeded` `:48-54`)
- Packet tests under `tests/eval/test_{des,thr,use}_*.py`
- `config/scoring_config.yaml:2` (`anomaly_threshold: 45.0`)
- `tests/eval/fixtures/scoring_config_baseline.sha256`
- `README.md:22`, `docs/SPEC.md:8`, root `SPEC.md:8`
- `web/api.py` routes (alerts / workflow / contain / explain / replay; no ingest)
- `docs/eval-kernel.md:12`

## Independent probes (not the pytest file)

SHA256 of live `config/scoring_config.yaml` == baseline file: `26a00c3c17f70d459cf5fff9d2a23f0c230f65ab6e61c5a6ea30c350f39a4701`. `git diff` merge-base `e206cde`..`HEAD` on that YAML is empty. Last YAML commit is `b4a511f` (pre-sprint).

`SPEC.md` and `docs/SPEC.md` are 69207 bytes and `a == b`.

Imported `evaluate_scenario` in a fresh tempdir (not pytest). Live rows:

| scenario_id | n | old_build | new_build | observed highlights |
|---|---|---|---|---|
| des.production_call_shape | 2 | pass/none | pass/none | stages all True; `seeded_decision_insert` False |
| des.no_llm_in_score | 2 | pass/none | pass/none | `import_llm` False; `import_explainer` False |
| des.ngram_mismatch_halts | 2 | pass/none | pass/none | `halt_score` 0.0; flag `embedding_metadata_mismatch_halt` |
| thr.cmdline_injection_survives | 2 | pass/none | pass/none | ingested/scored/persisted/escaped; no HTTP ingest |
| thr.api_key_required | 2 | pass/none | pass/none | missing/wrong 401; `pytest_loaded` False |
| thr.fp_block_sanctuary | 2 | pass/none | **pending**/none | old: `fp_opened_before_ladder` True, `attributed_ladder_tp` 5; new: `stage_b=pending` |
| use.pipeline_to_triage | 2 | pass/none | pass/none | alert visible; reconstruct True; seeded insert False |
| use.ui_sends_api_key | 2 | pass/none | pass/none | names `app.js omits X-API-KEY` |
| use.demo_honesty | 2 | pass/none | pass/none | `unearned_demo_claim` False |

AST of `e2e_kernel.py`: `DecisionRecordModel(` / `DecisionRecord(` constructors: none. `run_pipeline` once (`:103`); other arms go through `run_production_call`. Literal `"pending"` only at `:745` and `:748` (`thr.fp_block_sanctuary` `new_build`). `kernel_fixtures.py` has zero decision constructors.

`git grep` on `web/api.py` for `/api/ingest`: no match. Routes are `/api/alerts*`, escalations, replay, `/`.

## Refutation attempts (named holes)

| Hole | What would prove it | Evidence | Hole stands? |
|---|---|---|---|
| Pending on illegal IDs | any S1-8..16 arm other than sanctuary `new_build` is `pending` | Live dump: only sanctuary `new_build` pending. AST pending literals only in that branch. | no |
| Seeded DecisionRecord INSERT | kernel/fixture constructs `DecisionRecordModel` and counts it as E2E | No ctors in `e2e_kernel.py` or `kernel_fixtures.py`. Sanctuary writes JSONL only (`kernel_fixtures.py:123-170`) then `run_production_call`. `run_production_call` calls `run_pipeline` (`e2e_kernel.py:103`). | no |
| Lowered threshold | YAML `anomaly_threshold` ≠ 45.0, SHA drift, or `ANOMALY_THRESHOLD` ≠ 45 | Live YAML `45.0`. SHA match. No branch diff. Kernel `ANOMALY_THRESHOLD = 45.0`. | no |
| SPEC mismatch | root ≠ `docs/SPEC.md`, or Series I / archival missing | 69207 == 69207 bytes. README `:22` and SPEC `:8` name Series I and mark Series A **archival**. | no |
| Demo honesty still trips | live `use.demo_honesty` fail / `unearned_demo_claim` True | Live both arms `pass`, observed False. Fixture-only trip test still red on Series A-as-current (`test_detector_trips_on_series_a_current_fixture`). | no |

## Residual nits (not enough to REJECT)

- `seeded_decision_insert` is hardcoded `False` on a successful `run_production_call` (`e2e_kernel.py:126`). Theater `_seeded` is a no-op when `used_run_pipeline=True`. Path still is `run_pipeline`, not an INSERT.
- Most packet tests do not assert `len(rows)==2`; an empty list would vacuous-pass the `for` loop. Independent probe saw two arms on every ID.
- README / SPEC still print Series A P≈0.019 / FP=3448 below the SoT banner. Plan allows that if Series I is named and Series A is marked archival. Joined-text detector therefore does not trip.
- Queue item statuses for S1-8..16 / S1-21 are still `pending` in `autopilot-queue.json`. That is bookkeeping, not a scorecard arm.

## Verdict

**ACCEPT.** The five named holes do not stand. Fresh packet pytest **16/16**, both ruff commands clean, live `evaluate_scenario` matches the specified arms, YAML SHA equals baseline at thr=45.0, SPEC files are byte-identical, and live demo-honesty does not trip.
