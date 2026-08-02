# Series I — STATUS (T2 restructure)

**Updated:** 2026-08-02T20:00Z
**Branch:** `series-i-serial-calibration` (pushed to `origin`)
**Calibrated:** false

## Step 1 — Hygiene

| Item | Status |
|---|---|
| Defender exclusions | **Pending operator (admin)** — run commands in `state.json` → `av_exclusions.commands` |
| Resume | **Partial yes** — `batch/eval/runner.py` supports chunked resume; `run_series_i_sweep.py --chunked` added; campaign orchestrator does not resume |
| Local fanout | **3 writers** — cadence + precision_gate + feat_volume (was 8–9) |

## Step 2 — Cadence inertness query

**Decision: do NOT kill cadence** (operator wait if threshold disputed).

| Metric | Value |
|---|---:|
| n (combined E/F/G/I cadence_2 profiles) | 4160 |
| frac exactly 0.0 | 0.713 |
| frac < 0.05 | 0.713 |
| mean | 0.280 |
| max | 1.0 |
| by entity_type | human only (n=4160) |

Series F `per_dimension_drift_decomposition.cadence.mean` = **0.288** when cadence enabled — dimension is not wholly inert.

Code facts confirmed:
- `builder.py:489` — `max(0.0, 1.0 - cv/0.3)` floors at 0 when cv≥0.3
- `builder.py:748–777` — `cadence_cov` computed once; appended as absolute value per prev profile (not Δ vs baseline)
- `builder.py:868` — `norm_drift = raw_drift - cohort_median(role)`
- `builder.py:810,914` — `cadence_cov` persisted unconditionally

DEBT-078 added (absolute vs delta cadence; cross-ref DEBT-012).

## Step 3 — Lane split

### Local (running)

| Lane | Progress |
|---|---|
| `ws_cadence_2` | ~day 6/21 logged; day 7 in progress (PID 77784) |
| `ws_precision_gate` | ~day 10/21 |
| `ws_feat_volume` | ~day 10/21 |

### Cloud (pending launch)

See [`CLOUD-I-LAUNCH.md`](CLOUD-I-LAUNCH.md). Partial progress through sim-day 2026-01-10; checkpoints at 2026-01-11.

| Lane | Status |
|---|---|
| `ws_volume_1` | pending_launch (local stopped → migrated) |
| `ws_volume_5` | pending_launch |
| `ws_volume_15` | pending_launch |
| `ws_staged_drift` | pending_launch |
| `ws_fleet` | pending_launch |

### Aborted

| Lane | Reason |
|---|---|
| `ws_geo_5` | `geo_velocity_delta_last_build` 100% zero in partial DB (n=585); Series G mean=0 |

## Next

1. Operator: run Defender exclusions (admin PowerShell).
2. Dispatch 5 cloud probes per `CLOUD-I-LAUNCH.md`.
3. Let local cadence + flag solos finish; collect metrics JSON before marking done.
