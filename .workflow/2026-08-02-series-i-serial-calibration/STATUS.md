# Series I — STATUS (T2 restructure)

**Updated:** 2026-08-02T22:30Z
**Branch:** `series-i-serial-calibration` (pushed to `origin`)
**Calibrated:** false

## Step 1 — Hygiene

| Item | Status |
|---|---|
| Defender exclusions | **Pending operator (admin)** — run commands in `state.json` → `av_exclusions.commands` |
| Resume | **Partial yes** — `batch/eval/runner.py` supports chunked resume; `run_series_i_sweep.py --chunked` added; campaign orchestrator does not resume |
| Local fanout | **2 writers** — precision_gate + feat_volume (cadence killed) |

## Step 2 — Cadence inertness (cohort-constant)

**Decision: ABORT cadence lanes** — dimension cohort-constant as implemented.

| Metric | Value |
|---|---:|
| n (Series I cadence_2 partial DB) | 1365 profiles / 65 entities |
| `cadence_cov` SA median | 1.000 (~95% saturate at ≈1.0) |
| `cadence_cov` humans (hr/engineer/finance) | 0.0 (n=315 each) |
| standalone precision / recall | 0.050 / 0.143 (base rate 0.108) |
| w=2/5/10 equivalence | arithmetically equivalent to control arm |

**Abort reason:** dimension cohort-constant as implemented; absolute CoV saturates per role (SA≈1, humans=0); cohort_median norm cancels contribution for any weight; sweep uninformative; requires code fix: `compute_build_window_cadence_cov` must become CoV(recent)−CoV(baseline) per entity (delta vs baseline profile), not absolute regularity computed once outside prev_profiles loop. Related: DEBT-012.

Code facts:
- `builder.py:489` — `max(0.0, 1.0 - cv/0.3)` floors at 0 when cv≥0.3 (DEBT-012)
- `builder.py:748–777` — `cadence_cov` computed once; appended as absolute value per prev profile (not Δ vs baseline)
- `builder.py:868` — `norm_drift = raw_drift - cohort_median(role)` cancels cohort-constant dimension
- `builder.py:810,914` — `cadence_cov` persisted unconditionally

DEBT-078 updated (cohort-constant evidence + code-fix requirement; cross-ref DEBT-012). No weight decision owed. `drift_weights.cadence.enabled: false`, weight `0.0`.

## Step 3 — Lane split

### Local (running)

| Lane | Progress |
|---|---|
| `ws_precision_gate` | ~day 10/21 |
| `ws_feat_volume` | ~day 10/21 |

### Cloud (running — dispatched 2026-08-02T20:54Z)

See [`CLOUD-I-LAUNCH.md`](CLOUD-I-LAUNCH.md). Partial progress through sim-day 2026-01-10; checkpoints at 2026-01-11.

| Lane | Cloud agent | Status |
|---|---|---|
| `ws_volume_1` | [bc-6d94a41a](bc-6d94a41a-4ffe-46f0-9e8f-870b10ca4e04) | running |
| `ws_volume_5` | [bc-78440d47](bc-78440d47-1af6-4161-91cf-e6f8d4ab0122) | running |
| `ws_volume_15` | [bc-32e5935d](bc-32e5935d-b0eb-4aa1-a3f6-cc5f838361e5) | running |
| `ws_staged_drift` | [bc-bbc337d7](bc-bbc337d7-bcac-45aa-a3a3-c331df1ce76b) | running |
| `ws_fleet` | [bc-edff5f1d](bc-edff5f1d-62e3-467b-9d87-9c09db060039) | running |

### Aborted / skipped

| Lane | Reason |
|---|---|
| `ws_geo_5` | `geo_velocity_delta_last_build` 100% zero in partial DB (n=585); Series G mean=0 |
| `ws_cadence_2` | cohort-constant dimension; sweep uninformative; PID 77784 killed; see Step 2 |
| `ws_cadence_5` | skipped — same inertness as cadence_2; DEBT-078 |
| `ws_cadence_10` | skipped — same inertness as cadence_2; DEBT-078 |

## Next

1. Operator: run Defender exclusions (admin PowerShell).
2. ~~Dispatch 5 cloud probes per `CLOUD-I-LAUNCH.md`.~~ **Done** — 5 cloud agents running.
3. Let local precision_gate + feat_volume finish; collect metrics JSON before marking done.
4. Cloud agents: await metrics JSON in `results/series_i_<step>_metrics.json` before marking lanes done.
5. Cadence: **no re-sweep until DEBT-078 code fix** (delta CoV vs baseline per entity).
