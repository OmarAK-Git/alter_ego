# S1-EXIT-GATE verdict

**Judge:** skeptic-verifier / `in_session_grok` (`cursor-grok-4.6-high-fast`, never Opus)  
**Branch:** `gsd/eval-kernel-sprint1` @ `e774854ff972755bbb9863573d7ce5b2be5b90d6`  
**Compared to:** `origin/main` @ `e206cde92b5d80beb7350035d7d5a377944e90e6`  
**Date:** 2026-09-18

## Verdict

**ACCEPT-WITH-GAPS**

Official suite is not fully green. The only pytest failure is the documented P0 residual `tests/worker/test_precision_gate_stage_a.py::test_precision_gate_disabled_does_not_change_containment_flag` against shipped Series I `precision_gate.enabled=true`. The eight Sprint 1 kernel checks hold. Ruff is clean. This is not a Sprint 1 kernel regression: the test file and `config/scoring_config.yaml` are byte-identical to `origin/main`.

Do not revert YAML.

## Suite evidence (freshness)

Full official pytest was **not** re-run in this judge session (~8 min). Packet + independent confirms used instead.

| Item | Evidence |
|---|---|
| Packet | `.workflow/2026-09-18-eval-kernel-sprint1/results/S1-EXIT-GATE-packet.txt` started 21:25:39, finished 21:33:55 |
| (a) Packet exit codes | `PYTEST_EXIT=1`, `RUFF_EXIT=0` |
| Packet pytest summary | `1 failed, 252 passed` of 253 collected (`--ignore=tests/live`); single FAILED line in short summary |
| (b) Single failed test | `tests/worker/test_precision_gate_stage_a.py::test_precision_gate_disabled_does_not_change_containment_flag` |
| Judge ruff (re-run) | `ruff check .` → `All checks passed!` `RUFF_EXIT=0` |
| Judge residual spot-check | Same test re-run this session: FAILED in 0.44s; `assert 'simulated_containment_queued' in ['volume_delta_deferred', 'containment_deferred_single_family']`; `precision_gate_version='stage_a_v1'` |
| (c) Residual test vs `origin/main` | blob `ce76e0f8d363f3e0803125455253fb133e2ec481` == HEAD; `git diff origin/main -- tests/worker/test_precision_gate_stage_a.py` empty |
| (d) `scoring_config.yaml` vs `origin/main` | blob `bb25e2040e0a3dd24ab586e4314d47fa74c6dff6` == HEAD; `git diff origin/main -- config/scoring_config.yaml` empty |
| YAML gate state | `config/scoring_config.yaml:62` `precision_gate.enabled: true` (Series I accepted fold). Residual test loads live config and only overrides `containment_threshold` (`tests/worker/test_precision_gate_stage_a.py:196-218`) |

## Eight kernel checks

| # | Check | Result | Independent evidence |
|---|---|---|---|
| 1 | All 15 locked IDs exist as YAML + pytest + 30 scorecard rows | **holds** | `LOCKED_SCENARIO_IDS` is 15 (`core/schemas/scorecard.py:7-25`; `tests/eval/test_scorecard_schema.py:12-50`). `tests/eval/scenarios/` has exactly those 15 YAML stems. Matching `tests/eval/test_<id>.py` modules exist for all 15. Packet: `test_fifteen_scenario_files_exist_and_stems_match` PASSED; `test_evaluate_all_emits_thirty_rows_and_no_illegal_pending` PASSED. Artifact `artifacts/eval-kernel-scorecard.jsonl` is 30 JSONL rows covering 15 IDs × 2 arms. |
| 2 | pending only on the three allowed triples | **holds** | `PENDING_ALLOWED` = `(cap.attributed_s2_s3_s5, new_build)`, `(cap.drift_vs_point_axes, new_build)`, `(thr.fp_block_sanctuary, new_build)` (`core/schemas/scorecard.py:45-51`). Kernel only writes `pending` on those three `new_build` arms (`batch/eval/e2e_kernel.py:916-930`, `979-989`, `1043-1054`). Scorecard artifact pending rows are exactly those three. Packet completeness test PASSED. |
| 3 | `cap.no_n1_headline` and `use.demo_honesty` both arms pass | **holds** | Packet: `test_cap_no_n1_headline_both_arms_pass`, `test_live_docs_pass_demo_honesty_both_arms` PASSED. Completeness test asserts both IDs `status == pass`. Scorecard rows 5–6 and 25–26: both arms `pass`. |
| 4 | Kernel calls `run_pipeline` / five production stages; no DecisionRecord INSERT as E2E; no `/api/ingest`; no Series J | **holds** | `run_production_call` calls `run_pipeline` (`e2e_kernel.py:107`). `run_pipeline` calls `ingest_events` → `process_unresolved_events` → `build_profiles` → `process_unscored_events` (`batch/eval/runner.py:152-161`); scorer then `record_decision` (`worker/scorer.py:862`). Kernel does not construct `DecisionRecordModel(`; `seeded_decision_insert=False`. `web/api.py` has no `/api/ingest` (grep empty); cmdline theater records `introduces_http_ingest: false`. `staffs_series_j=False` on `gov.no_knob_without_sweep`; no Series J YAML flips (`scoring_config.yaml` unchanged vs main). Packet: `test_run_production_call_invokes_all_five_stages_and_does_not_insert_decisions_itself` PASSED; theater `fake_ingest_api` / `series_j_fold` tests PASSED. |
| 5 | GHA runs default pytest and kernel completeness CLI | **holds** | `.github/workflows/ci.yml:29-38` `pytest -v --tb=short` then `python -m batch.eval.e2e_kernel --scorecard-out artifacts/eval-kernel-scorecard.jsonl --assert-complete`. `.github/workflows/eval-kernel.yml:21-32` same default pytest plus `pytest tests/eval` plus the completeness CLI. |
| 6 | ruff clean | **holds** | Packet `RUFF_EXIT=0`. Judge re-run `ruff check .` exit 0. |
| 7 | No usefulness claim; Series I remains `calibrated: false` | **holds** | `docs/eval-kernel.md:12-13` Series I `calibrated: false`; “does not claim usefulness.” Series I `STATUS.md` **Calibrated:** false; “Do not claim CALIBRATED.” README: “Not useful yet.” Memory-bank `activeContext.md` / `progress.md`: `calibrated: false`; “Do not claim usefulness.” Attributed/drift theater uses `f1_treated_as_primary=False`; scorecard records `f1_at_45` on drift but does not pin on it. |
| 8 | No `scoring_config.yaml` knob edits | **holds** | HEAD blob == `origin/main` blob `bb25e204…`. Branch name-only diff vs main does not include `config/scoring_config.yaml`. Baseline pin `tests/eval/fixtures/scoring_config_baseline.sha256` is a harness file, not a knob edit. |

## Attempted refutations that failed

| Hypothesis | Outcome |
|---|---|
| Second pytest failure hidden in packet | No. Short summary has one FAILED line; 253 collected = 252 passed + 1 failed. |
| Residual is a Sprint 1 kernel regression | No. Test and YAML hashes match `origin/main`. Failure mode is Stage A deferral (`containment_deferred_single_family`) under shipped `enabled: true`. |
| Illegal pending or missing ID | No. Schema lock + completeness test + 30-row artifact agree. |
| Usefulness claimed via compact-corpus recall / F1@45 | No. Quality `new_build` remains pending; F1 is recorded-not-primary; docs say not useful / not CALIBRATED. |
| `/api/ingest` or Series J staffed | No. API grep empty; YAML unchanged; theater pin `staffs_series_j=False`. |
| `scoring_config.yaml` edited then reverted to different content | No. Identical blob vs `origin/main`. |

## What remains outside Sprint 1

- **P0 residual (do not revert YAML):** `test_precision_gate_disabled_does_not_change_containment_flag` is stale vs Series I `precision_gate.enabled=true`. Fix is a later test-contract update, not a Sprint 1 kernel change.
- **Stage B / usefulness unearned:** `cap.attributed_s2_s3_s5` `new_build`, `cap.drift_vs_point_axes` `new_build`, and `thr.fp_block_sanctuary` `new_build` stay `pending`. Do not flip them on this sprint.
- **Series I stays `calibrated: false`.** Compact seed-42 cells are a harness baseline, not a usefulness earn and not a CALIBRATED claim.
- **Named UI gap:** `use.ui_sends_api_key` both arms pass because `app.js omits X-API-KEY` is an honest named gap, not a send-key win.
- **Sprint 2+:** full seed-42 Series I corpus, attributed catch + deadlock cut, threshold sweep. F1@45-only is a fail. Honest stop does not authorize Sprint 3.

Sprint 1 may exit with this residual standing.
