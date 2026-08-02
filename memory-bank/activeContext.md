# Active Context

**Updated:** 2026-08-02T23:00Z — Phase B additive folds launched

## Current focus

**T2:** Phase B additive flag folds on cloud (main campaign)
**Workflow:** `.workflow/2026-08-02-series-i-serial-calibration/`
**Branch:** `series-i-serial-calibration`
**Calibrated:** false

## Phase

`B_additive_folds` — serial additive flag promotions on cloud. Folds unblocked; weight grids are NOT gates.

## Fold chain (running)

| # | Step | Cloud agent | Status |
|---|---|---|---|
| 1 | `fold_02_feature_volume` | bc-29a79b5f-14e2-47a2-ba14-629b42724baa | **running** |
| 2–4 | precision_gate → fleet → staged | — | queued serial |
| 5 | `fold_03_drift_volume` | — | deferred last (provisional w=5.0) |

See `CLOUD-I-FOLDS.md`.

## Archival probes — PRESERVE (do not kill)

In-flight weight/solo lanes continue in background for post-fold evidence review:

- Cloud: `ws_volume_1/5/15`, `ws_fleet`, `ws_staged_drift`
- Local: `ws_feat_volume` (64496), `ws_precision_gate` (89136)

No new weight-search launches until flag folds complete.

## Aborted (unchanged)

Cadence (DEBT-078), geo (100% zero deltas).

## Standing order

Do **not** merge Series I to main. Never claim CALIBRATED.
