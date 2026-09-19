# S1-18 skeptic-verifier result

**Task:** S1-18 / Plan Task 18 — `cap.drift_vs_point_axes`
**Claim:** `old_build` records `drift_alerts` and `point_anomaly_fp` as separate fields plus `f1_at_45` that is not the decision pin; `f1_treated_as_primary` is False; `axes_split` is True; `new_build` is pending. Drift alerts counted via B3a `drift_necessary` or `"drift_alert"` in flags list — not `json_extract($.drift_alert)`. Reuses compact seed-42 fixture. `scoring_config.yaml` untouched. No usefulness claim.
**Verdict:** ACCEPT
**Branch:** `gsd/eval-kernel-sprint1` @ `63752bc184648be9daf530469aaf6ed86e355946`
**Date:** 2026-09-18

## Claim restated

Load-bearing claim: `evaluate_scenario("cap.drift_vs_point_axes")` emits two `ScorecardRow`s; `old_build.status=="pass"` with `observed` containing separate integer keys `drift_alerts` and `point_anomaly_fp` plus recorded `f1_at_45` that is not used as the pass/fail pin; `f1_treated_as_primary is False`; `axes_split is True`; `new_build.status=="pending"`. Drift-alert count is B3a `drift_necessary` or `"drift_alert"` in `flags` (`list[str]`), not SQL `json_extract($.drift_alert)`. Point-anomaly FP is `is_anomaly ∧ not malicious ∧ not drift_necessary`. `PROFILE_BUILD` / `COHORT_DRIFT` skipped on those counters. Fixture is Task 17 `write_compact_seed42_s2_s3_s5_jsonl`. `config/scoring_config.yaml` unchanged. No usefulness claim.

Vague “test passed” without those behaviors would be unverifiable; this verdict is from independent re-runs and a live `evaluate_scenario` dump, not the implementer transcript.

## Fresh commands (re-run by verifier)

```
cd C:\Users\oalan\alter_ego
$env:PYTHONPATH="."
pytest tests/eval/test_cap_drift_vs_point_axes.py -v --tb=short
ruff check batch/eval/e2e_kernel.py tests/eval/test_cap_drift_vs_point_axes.py
git diff HEAD -- config/scoring_config.yaml
```

**pytest:** 1 passed, 0 failed (48.18s), exit 0

```
tests/eval/test_cap_drift_vs_point_axes.py::test_axes_split_old_recorded_new_pending PASSED
====================== 1 passed, 274 warnings in 48.18s =======================
```

**ruff:** All checks passed (exit 0)

**git diff HEAD -- config/scoring_config.yaml:** empty (no output)

HEAD `63752bc184648be9daf530469aaf6ed86e355946` (“Split drift vs point-anomaly axes on the eval scorecard; F1@45 not the pin”). Commit name-only: `batch/eval/e2e_kernel.py`, `tests/eval/scenarios/cap.drift_vs_point_axes.yaml`, `tests/eval/test_cap_drift_vs_point_axes.py`. `git diff 63752bc^..63752bc -- config/scoring_config.yaml` also empty.

Working tree at verify time: `M .workflow/2026-09-18-eval-kernel-sprint1/state.json`, `M .workflow/autopilot-queue.json`, untracked S1-17/S1-18 packets — workflow files only; not scoring config.

## Files re-read

- Plan Task 18: `docs/superpowers/plans/2026-09-08-eval-kernel-sprint1.md:2614-2705`
- Packet: `.workflow/2026-09-18-eval-kernel-sprint1/packets/S1-18-brief.md`
- `tests/eval/test_cap_drift_vs_point_axes.py` (key presence + pending)
- `tests/eval/scenarios/cap.drift_vs_point_axes.yaml` (`theater_detector: f1_only_usefulness`, `events: seed42_s2_s3_s5`, pins `[drift_alerts, point_anomaly_fp, f1_at_45]`)
- `batch/eval/e2e_kernel.py` (`drift_necessary` `:708-718`; `_has_drift_alert_flag` `:721-728`; `_count_drift_alerts` `:740-747`; `_count_point_anomaly_fp` `:750-757`; `_f1_at_45` `:760-773`; `_eval_cap_drift_vs_point_axes` `:895-955`; dispatch `:1244-1246`; `run_production_call` `:100-131` with `seeded_decision_insert=False`)
- `batch/eval/kernel_fixtures.py` (`write_compact_seed42_s2_s3_s5_jsonl` `:174-222`)
- `batch/eval/theater.py` (`f1_only_usefulness` `:115`)
- `core/schemas/scorecard.py` (`LOCKED_SCENARIO_IDS` / `PENDING_ALLOWED` include this id + `(cap.drift_vs_point_axes, new_build)`)
- `tests/test_boil_the_frog_invariants.py` B3a (`:392-420`) and Series I `_is_drift_necessary` (`scratch/run_series_i_sweep.py:242-246`)
- `worker/scorer.py` writes `flags = []` then string appends (no `"drift_alert"` string); `batch/profile_builder/builder.py:247-248` writes PROFILE_BUILD `flags={"drift_alert": True, ...}`
- `batch/eval/runner.py:75-78` still uses `json_extract($.drift_alert)` — kernel path does not

No `json_extract` / `func.json` anywhere in `batch/eval/e2e_kernel.py`.

## Independent probes (not the pytest file)

Imported `evaluate_scenario`, `drift_necessary`, counters, and `write_compact_seed42_s2_s3_s5_jsonl` into a fresh tmp dir (second live run after pytest, plus a third census `run_production_call`).

B3a helper (synthetic namespaces):

| case | score | drift contrib | `drift_necessary` |
|---|---|---|---|
| below threshold | 44.9 | 100.0 | False |
| point-only | 50.0 | 0.0 | False |
| drift necessary | 50.0 | 10.0 | True |

`_has_drift_alert_flag(['drift_alert'])` True; `['staleness_halt']` False; dict `{'drift_alert': True}` True (fallback; not SQL extract).

Live `evaluate_scenario("cap.drift_vs_point_axes")`:

| arm | status | failure_class | observed |
|---|---|---|---|
| old_build | pass | none | `drift_alerts`: **125** (int); `point_anomaly_fp`: **128** (int); `f1_at_45`: **0.4607…** (float); `f1_treated_as_primary`: False; `axes_split`: True |
| new_build | pending | none | `{quality: pending}`; notes=`Stage B unbuilt` |

`N_ROWS 2`. Both `scenario_id == cap.drift_vs_point_axes`. Pass predicate is `axes_split and f1_treated_as_primary is False` (`e2e_kernel.py:938`) — `f1_at_45` is recorded and not consulted.

Census on the same compact fixture + `run_pipeline`:

- decisions 1312; `PROFILE_BUILD` hits **5**; `COHORT_DRIFT` hits **0**
- flag types: 1307 `list`, 5 `dict` (the PROFILE_BUILD rows)
- `"drift_alert"` string-in-list hits on scored events: 0 (list flags have `drift_shadow_fallback:…`, not `"drift_alert"`)
- `DRIFT_FLAG_HITS` 5 = excluded PROFILE_BUILD dict flags
- live recount: `drift_alerts=125`, `point_anomaly_fp=128` (matches scorecard)
- overlap of the two axis predicates after exclusion: **0**
- without exclusion those 5 PROFILE_BUILD rows would have entered **both** counters (`excl_would_da=5`, `excl_would_pfp=5`)
- malicious n=115
- pipeline log `Clearing database tables` twice in the probe process = evaluate_scenario old_build + census call; `new_build` `continue`s before fixture write / `run_production_call`

## Refutation attempts (named holes)

| # | Hole | What would prove it | Evidence | Hole stands? |
|---|---|---|---|---|
| 1 | evaluate_scenario does not emit old pass + new pending | live statuses wrong or ≠2 rows | Live `N_ROWS 2`; old `pass` / `failure_class=none`; new `pending` / `none`. Pytest asserts both. | no |
| 2 | old.observed missing separate axis ints or `f1_at_45` | keys absent, nested, or not ints | Live keys present; types int/int/float; values 125 / 128 / 0.4607 not stubs. | no |
| 3 | `f1_treated_as_primary` True or `axes_split` False | live flags wrong | Live False / True. YAML expected matches. Theater `f1_only_usefulness` with hardcoded False does not trip. | no |
| 4 | e2e_kernel uses `json_extract` on flags for this pin | `json_extract` / `func.json` in kernel | Grep of `e2e_kernel.py`: no matches. Counts iterate loaded `DecisionRecordModel` rows + Python `drift_necessary` / `_has_drift_alert_flag`. | no |
| 5 | `drift_necessary` is not B3a | formula ≠ `(score>=45) ∧ (score-contrib_drift<45)` on `drift_alert` | `e2e_kernel.py:708-718` matches B3a / Series I `_is_drift_necessary`. Synthetic: below-thr False, point-only False, drift-needed True. | no |
| 6 | point_anomaly_fp includes `drift_necessary` True | counter omits `not drift_necessary` or live overlap | `e2e_kernel.py:755`: `is_anomaly and event_id not in malicious and not drift_necessary`. Live overlap after exclusion = 0. | no |
| 7 | PROFILE_BUILD / COHORT_DRIFT counted on the pins | skip missing or live excluded rows in 125/128 | `_KERNEL_EXCLUDED_EVENT_IDS` applied in both counters. Live 5 PROFILE_BUILD skipped; without skip they would add 5 to each axis. `COHORT_DRIFT` skip is in code; 0 such rows in this fixture. | no |
| 8 | `scoring_config.yaml` edited | git diff nonempty vs HEAD or in `63752bc` | Both diffs empty. Commit touches 3 eval files only. | no |

## Residual nits (not enough to REJECT)

- Controller test only asserts key presence, not types or live values. Independent dump saw real ints/float and matching census recount.
- `axes_split` is `isinstance(drift_alerts, int) and isinstance(point_anomaly_fp, int)` — tautological once counters return ints. The split that matters is two separate keys; those exist and are disjoint on this fixture.
- `_has_drift_alert_flag` also accepts dict `flags.get("drift_alert")`. That is not `json_extract`. Live dict flags are the 5 excluded PROFILE_BUILD rows; scored events are `list[str]` and do not contain the token `"drift_alert"`. Live `drift_alerts=125` is therefore B3a-only.
- `_f1_at_45` does **not** skip PROFILE_BUILD. F1 is recorded-only, not the pin. Axis counters do skip.
- `COHORT_DRIFT` exclusion is unexercised on this compact corpus (0 rows). Code path is present.
- `TheaterContext(f1_treated_as_primary=False)` is hardcoded; the detector cannot trip on this path. That matches “no usefulness claim,” not a silent F1 win.
- Compact-fixture axis magnitudes (125 / 128, F1≈0.46) are recorded, not asserted useful.

## Verdict

**ACCEPT.** All eight load-bearing checks survived independent re-run: old pass / new pending, separate axis ints plus recorded non-pin `f1_at_45`, `f1_treated_as_primary=False` / `axes_split=True`, no `json_extract` on this pin, B3a `drift_necessary`, point-FP excludes drift-necessary, PROFILE_BUILD skipped on the axis counters, untouched `scoring_config.yaml`. Residual nits are test thinness, tautological `axes_split`, and F1 not excluding PROFILE_BUILD — not missing pin behaviors.
