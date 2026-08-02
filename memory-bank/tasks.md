# Tasks

**Updated:** 2026-08-02 — Series I T2 campaign

## Active: Series I serial calibration

| Item | Status |
|---|---|
| T2 restructure (hygiene + cadence query + lane split) | **in progress** |
| Phase A weight search | in progress |
| Phase B serial folds | pending weight decisions |
| Cloud probe dispatch (5 lanes) | **pending operator / cloud agent** |
| `ws_cadence_2` completion | running |
| `ws_cadence_5/10` | queued (cadence not killed) |

### Lane table (authoritative snapshot)

| Lane | Host | Status | Notes |
|---|---|---|---|
| `ws_cadence_2` | local | running | PID 77784; ~6/21 windows logged |
| `ws_cadence_5` | — | queued | |
| `ws_cadence_10` | — | queued | |
| `ws_volume_1` | cloud | pending_launch | local stopped; checkpoint 2026-01-11 |
| `ws_volume_5` | cloud | pending_launch | local stopped; checkpoint 2026-01-11 |
| `ws_volume_15` | cloud | pending_launch | local stopped; checkpoint 2026-01-11 |
| `ws_geo_5` | — | **aborted** | geo_velocity null (100% zero deltas) |
| `ws_feat_volume` | local | running | ~day 10/21 |
| `ws_precision_gate` | local | running | ~day 10/21 |
| `ws_fleet` | cloud | pending_launch | local stopped; checkpoint 2026-01-11 |
| `ws_staged_drift` | cloud | pending_launch | local stopped; checkpoint 2026-01-11 |

**SoT:** `.workflow/2026-08-02-series-i-serial-calibration/state.json`

## DC drift-capability expansion

**Status:** COMPLETE (2026-08-02). See `.workflow/2026-07-30-drift-capability-expansion/`.
