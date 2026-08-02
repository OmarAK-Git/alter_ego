# Series I ? Overnight STATUS

**Updated:** 2026-08-02T13:12Z (local ~09:12)
**Branch:** `series-i-serial-calibration`
**Calibrated:** false

## Parallel plan (active)

Cadence monopolized overnight budget; operator authorized parallel **solo screens** (not additive folds):

| Lane | Steps | Isolation |
|---|---|---|
| Cadence (in-flight) | `ws_cadence_2` | Live shared YAML patch ? **do not touch** |
| Volume weights | `ws_volume_1/5/15` | `ALTER_EGO_SCORING_CONFIG` + own sqlite |
| Geo weight | `ws_geo_5` | same |
| Weightless flag solos | `ws_feat_volume`, `ws_fleet`, `ws_precision_gate`, `ws_staged_drift` | same |

**NOT started:** additive fold chain `fold_01`?`fold_07` (waits for weight decisions).

## Running now (PIDs)

| Role | PID | Notes |
|---|---:|---|
| Cadence `ws_cadence_2` | **77784** | Undisturbed; DB ~700MB+, day ~14/21 |
| Parallel launcher | 46556 | `series_i_parallel_weights.py` |
| Parallel collector | 28776 | governance on completion |
| Watchdog | 82920 | kills **campaign only**; spares parallel sweeps |
| `ws_volume_1` | 59924 | |
| `ws_volume_5` | 73336 | |
| `ws_volume_15` | 93860 | |
| `ws_geo_5` | 55172 | |
| `ws_feat_volume` | 22968 | `features.total_volume_delta.enabled` |
| `ws_fleet` | 44840 | `fleet_drift_enabled` |
| `ws_precision_gate` | 67800 | |
| `ws_staged_drift` | 80516 | |

Campaign orchestrator **stopped** so it cannot serially grab volume after cadence; watchdog resumes it after cadence metrics + parallel solos finish.

## Isolation mechanism

- `ALTER_EGO_SCORING_CONFIG` honored by `worker/scorer.py` + `batch/profile_builder/builder.py`
- Sweep writes `config/scoring_config.series_i_<step>.yaml` from cadence **backup** baseline (new drift dims off)
- Shared `config/scoring_config.yaml` remains cadence-enabled for PID 77784
- Eval runner temp windows are PID-scoped (`temp_window_<pid>_YYYYMMDD.jsonl`) to avoid WinError 32 clashes

## Cadence interim (directional)

Partial thr=45 earlier: cadence w=2 hurts recall; floors OK ? expect **reject + short-circuit** `{5,10}` after metrics land.

## First-launch note

Initial parallel wave failed on shared `temp_window_20260101.jsonl` locks; fixed in `batch/eval/runner.py` and relaunched ~09:11. Probes confirmed past `Processed window ending 2026-01-02`.

## ETA

- Weightless / volume / geo solos: roughly cadence-like wall time if non-zero weights storm; enable-only flags may finish closer to Series F/H (~2?4h) ? unknown until day-curve observed
- Cadence remaining: ~7?8 day-windows left; historically 40?60 min/day under weight storm ? **~5?8h** more

## Next

1. Collect metrics + governance per solo (accept/reject that dim/flag only)
2. Cadence metrics ? short-circuit higher cadence weights
3. Phase B additive folds only after weight winners known
4. No merge to main; no CALIBRATED claim
