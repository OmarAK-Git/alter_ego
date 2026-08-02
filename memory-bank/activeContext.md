# Active Context

**Updated:** 2026-08-02T22:30Z — cadence lanes aborted

## Current focus

**T2:** Finish Series I campaign via cloud/local split (not individual dimension proofs)
**Workflow:** `.workflow/2026-08-02-series-i-serial-calibration/`
**Branch:** `series-i-serial-calibration` (pushed to origin)
**Calibrated:** false

## Phase

`A_weight_search_split` — recall-side weight probes on cloud; flag-only solos local (max 2 writers).

## Cadence Step 2 decision

**ABORTED** — dimension cohort-constant as implemented. `cadence_cov` saturates per role (SA≈1, humans=0); cohort_median norm cancels contribution for any weight; sweep uninformative. PID 77784 killed. `ws_cadence_5/10` skipped. Code fix required (DEBT-078, cross-ref DEBT-012). No weight decision owed. YAML: `enabled: false`, weight `0.0`.

## Local lanes (max 2)

| Lane | Status |
|---|---|
| `ws_precision_gate` | running (~day 10/21) |
| `ws_feat_volume` | running (~day 10/21) |

## Cloud lanes (running — dispatched 2026-08-02T20:54Z)

| Lane | Cloud agent |
|---|---|
| `ws_volume_1` | bc-6d94a41a-4ffe-46f0-9e8f-870b10ca4e04 |
| `ws_volume_5` | bc-78440d47-1af6-4161-91cf-e6f8d4ab0122 |
| `ws_volume_15` | bc-32e5935d-b0eb-4aa1-a3f6-cc5f838361e5 |
| `ws_staged_drift` | bc-bbc337d7-bcac-45aa-a3a3-c331df1ce76b |
| `ws_fleet` | bc-edff5f1d-62e3-467b-9d87-9c09db060039 |

See `CLOUD-I-LAUNCH.md`; partial DBs + checkpoints at sim-day 2026-01-11.

## Aborted / skipped

| Lane | Reason |
|---|---|
| `ws_geo_5` | `geo_velocity_delta_last_build` 100% zero in partial DB (n=585); Series G mean=0 |
| `ws_cadence_2` | cohort-constant dimension; sweep uninformative; PID 77784 killed |
| `ws_cadence_5` | skipped — same inertness; DEBT-078 |
| `ws_cadence_10` | skipped — same inertness; DEBT-078 |

## Standing order

All gates on Grok Fast; do **not** merge Series I to main. Never claim CALIBRATED.
