# Series I — STATUS (Phase B additive folds)

**Updated:** 2026-08-02T23:00Z
**Branch:** `series-i-serial-calibration` (pushed to `origin`)
**Calibrated:** false

## Phase B — Additive folds (MAIN CAMPAIGN)

**Folds unblocked.** Cadence kill does not gate folds. Weight grids do not gate folds.

| # | Step | Host | Agent | Status |
|---|---|---|---|---|
| 1 | `fold_02_feature_volume` | cloud | [bc-29a79b5f](bc-29a79b5f-14e2-47a2-ba14-629b42724baa) | **running** |
| 2 | `fold_06_precision_gate` | cloud | — | queued (after fold 1 metrics) |
| 3 | `fold_05_fleet` | cloud | — | queued |
| 4 | `fold_07_staged_drift` | cloud | — | queued |
| 5 | `fold_03_drift_volume` | cloud | — | deferred last (provisional w=5.0) |

Skipped: `fold_01_cadence`, `fold_04_geo`.

See [`CLOUD-I-FOLDS.md`](CLOUD-I-FOLDS.md).

## Weight/solo probes — PRESERVE (archival, not gates)

**Policy:** Defer **new** weight work. **Do not kill** in-flight lanes. Let finish; keep DBs/logs/metrics for post-fold review.

### Cloud (background — keep running)

| Lane | Agent | Role |
|---|---|---|
| `ws_volume_1` | bc-6d94a41a | archival weight probe |
| `ws_volume_5` | bc-78440d47 | archival weight probe |
| `ws_volume_15` | bc-32e5935d | archival weight probe |
| `ws_fleet` | bc-edff5f1d | archival solo screen |
| `ws_staged_drift` | bc-bbc337d7 | archival solo screen |

### Local (background — keep running)

| Lane | PID | Progress |
|---|---|---|
| `ws_feat_volume` | 64496 | ~day 13/21 |
| `ws_precision_gate` | 89136 | ~day 13/21 |

## Aborted / skipped

| Lane | Reason |
|---|---|
| `ws_geo_5` / `fold_04_geo` | geo_velocity 100% zero deltas |
| `ws_cadence_*` / `fold_01_cadence` | cohort-constant dimension (DEBT-078) |

## Next

1. Await `series_i_fold_02_feature_volume_metrics.json` from cloud agent bc-29a79b5f.
2. Governance accept/reject → dispatch fold 2 (`fold_06_precision_gate`) on cloud.
3. Let archival ws_* lanes finish independently; collect metrics after flag folds.
