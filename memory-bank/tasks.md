# Tasks

**Updated:** 2026-08-02T23:00Z — Phase B folds priority

## Active: Series I serial calibration

| Item | Status |
|---|---|
| Phase A weight search | **deferred** (in-flight lanes preserved as archival) |
| Phase B additive folds | **running** — fold 1 on cloud |
| Cloud fold dispatch | **fold_02** bc-29a79b5f running |

### Fold chain (main campaign)

| Step | Host | Status | Agent |
|---|---|---|---|
| `fold_02_feature_volume` | cloud | **running** | bc-29a79b5f |
| `fold_06_precision_gate` | cloud | queued | — |
| `fold_05_fleet` | cloud | queued | — |
| `fold_07_staged_drift` | cloud | queued | — |
| `fold_03_drift_volume` | cloud | deferred last | — |

### Archival background (preserve — not gates)

| Lane | Host | Status | Notes |
|---|---|---|---|
| `ws_volume_1/5/15` | cloud | running | weight probes |
| `ws_fleet`, `ws_staged_drift` | cloud | running | solo screens |
| `ws_feat_volume`, `ws_precision_gate` | local | running | solo screens |

**SoT:** `.workflow/2026-08-02-series-i-serial-calibration/state.json`

## DC drift-capability expansion

**Status:** COMPLETE (2026-08-02).
