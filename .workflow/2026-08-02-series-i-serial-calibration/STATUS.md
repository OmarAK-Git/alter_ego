# Series I — Overnight STATUS

**Updated:** 2026-08-02T11:20Z (local ~07:20)
**Branch:** `series-i-serial-calibration`
**Calibrated:** false

## Running now

- Campaign PID chain active since relaunch `2026-08-02T05:12:13Z`
- Current step: `ws_cadence_2` (`drift_weights.cadence.enabled=true`, `weight=2.0`)
- Progress: scoring through ~2026-01-14 of 2026-01-22 window (~day 13/21)
- Wall time this sweep: ~6h+ (anomaly storm under cadence weight makes later days ~40–60 min each)
- DB: `alter_ego_calibrate_series_i_ws_cadence_2.db` (~600MB, growing)

## Interim thr=45 snapshot (partial DB, not final)

| Metric | Interim | Baseline E–H |
|---|---:|---:|
| TP / FP / FN | 39 / 5886 / 78 | 54 / 7995 / 63 |
| P / R / F1 | 0.0066 / 0.333 / 0.0129 | 0.0067 / 0.462 / 0.0132 |
| S1 / S4 | 1.0 / 1.0 | 1.0 / 1.0 |
| S2 / S3 / S5 | 0.60 / 0.00 / 0.46 | 0.74 / 0.11 / 0.60 |

Directional read (pending full sweep): cadence w=2 **hurts recall** vs baseline; floors OK; F1 not improved. Higher grid points {5,10} expected worse → plan to **short-circuit reject** cadence after `ws_cadence_2` completes.

## Why slow

Series F/H cloud sweeps (~2.5h) used **weight=0** with `enabled=true` (deltas computed, no score effect). Non-zero cadence weight floods `drift_alert` contributions (often capped at 50), exploding anomaly/workflow work per day-window.

## Commits so far

- `53eac19` scaffold
- `4ffdfb2` / `d8e3dd3` campaign bookkeeping
- `4ecdd2e` quiet-log + budget tighten

## Next (auto when current sweep ends)

1. Formalize `ws_cadence_2` metrics + governance
2. Skip `ws_cadence_5` / `ws_cadence_10` if w=2 fails rank vs baseline
3. Continue volume/geo weight search + serial folds under remaining budget
4. Stop cleanly with `RESUME.md` / `RESULTS.md` if budget exhausted
