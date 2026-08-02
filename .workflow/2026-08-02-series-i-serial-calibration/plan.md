# Series I — Serial Calibration Campaign (2026-08-02)

## Goal

Bounded weight search for zero-weight drift dims, then serial additive flag promotions for all 7 enablement flags. Operator merge review only — **do not merge to main**.

## Objective (thr=45)

Rank by **F1**, then higher recall, then lower FP.
Floors: prefer keep **S1=1.0** and **S4=1.0**; reject candidates that collapse them.

## Baseline (Series E–H)

P≈0.0067 R≈0.4615 F1≈0.0132 TP=54 FP=7995 FN=63
S1=1 S2≈0.74 S3≈0.11 S4=1 S5=0.60

## Phase A — Weight search (≤3 candidates / dim)

| Dim | Grid | Notes |
|---|---|---|
| `drift_weights.cadence` | {2, 5, 10} | Enable only cadence during search |
| `drift_weights.total_volume_delta` | {1, 5, 15} | Enable only volume drift dim |
| `drift_weights.geo_velocity` | {5} once | Skip remaining if inert (Series G mean≈0) |

## Phase B — Serial additive folds (order fixed)

1. `drift_weights.cadence.enabled` (+ winning weight)
2. `features.total_volume_delta.enabled` (weight 1.0)
3. `drift_weights.total_volume_delta.enabled` (+ winning weight)
4. `drift_weights.geo_velocity.enabled` (+ weight; skip if Phase A inert)
5. `fleet_drift_enabled`
6. `precision_gate.enabled`
7. `staged_drift.enabled`

After each: full empirical sweep → governance → accept into branch baseline or revert → next.

## Harness

- `scratch/run_series_i_sweep.py` — configurable flags/weights, seed 42, config 2.2, thr=45
- Dedicated sqlite DBs under `alter_ego_calibrate_series_i_*.db`
- `"calibrated": false` always
- No DEBT-028 / `core/schemas/config.py` / Stage B

## Budget

~8h overnight. If short: stop cleanly with `RESUME.md`.
