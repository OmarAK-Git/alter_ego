# Tasks

**Updated:** 2026-08-02 — Series I T2 campaign

## Active: Series I serial calibration

| Item | Status |
|---|---|
| T2 restructure (hygiene + cadence query + lane split) | **in progress** |
| Phase A weight search | in progress |
| Phase B serial folds | pending weight decisions |
| Cloud probe dispatch (5 lanes) | **running** — dispatched 2026-08-02T20:54Z |
| `ws_cadence_2` | **aborted** — cohort-constant dimension; PID 77784 killed |
| `ws_cadence_5/10` | **skipped** — same inertness; DEBT-078 two-part code fix required |

### Lane table (authoritative snapshot)

| Lane | Host | Status | Notes |
|---|---|---|---|
| `ws_cadence_2` | local | **aborted** | PID 77784 killed; cohort-constant; DEBT-078 |
| `ws_cadence_5` | — | **skipped** | same inertness as cadence_2 |
| `ws_cadence_10` | — | **skipped** | same inertness as cadence_2 |
| `ws_volume_1` | cloud | running | bc-6d94a41a |
| `ws_volume_5` | cloud | running | bc-78440d47 |
| `ws_volume_15` | cloud | running | bc-32e5935d |
| `ws_geo_5` | — | **aborted** | geo_velocity null (100% zero deltas) |
| `ws_feat_volume` | local | running | ~day 10/21 |
| `ws_precision_gate` | local | running | ~day 10/21 |
| `ws_fleet` | cloud | running | bc-edff5f1d |
| `ws_staged_drift` | cloud | running | bc-bbc337d7 |

**SoT:** `.workflow/2026-08-02-series-i-serial-calibration/state.json`

## DC drift-capability expansion

**Status:** COMPLETE (2026-08-02). See `.workflow/2026-07-30-drift-capability-expansion/`.
