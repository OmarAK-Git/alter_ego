# SC2 Sweep Result

**Date:** 2026-07-19
**Status:** PASS (exit 0)
**Calibrated claim:** **NOT CALIBRATED** — no B→C FP/P/R delta claims.

## Command

```powershell
cd C:\Users\oalan\alter_ego
$env:PYTHONPATH="."
python scratch/run_series_c_sweep.py
```

## Exit code

`0` (wall ~531s / ~8.9 min)

## Artifacts

| Path | Present |
|------|---------|
| `scratch/series_c_metrics.json` | yes |
| `alter_ego_calibrate_series_c.db` | yes |
| `docs/calibration_series_c_metrics.json` | yes (governance copy) |

## Headline @ anomaly_threshold=45 (seed 42, config 2.2)

| Metric | Value |
|--------|------:|
| Precision | 0.000301 |
| Recall | 0.008547 |
| F1 | 0.000582 |
| TP | 1 |
| FP | 3320 |
| FN | 116 |
| TN | 16037 |
| drift_alerts | 19 |
| active_alert_workflow_rows | 1523 |

## Per-scenario recall

| Scenario | Recall | TP | FN |
|----------|-------:|---:|---:|
| scenario_1_sharp_misuse | 1.0 | 1 | 0 |
| scenario_2_slow_roll | 0.0 | 0 | 35 |
| scenario_3_subtle | 0.0 | 0 | 45 |
| scenario_4_service_abuse | 0.0 | 0 | 1 |
| scenario_5_patient_cycle | 0.0 | 0 | 35 |

## Section 4.7 / lifecycle extras

| Field | Value |
|-------|------:|
| auto_resolved_count | 1817 |
| blocked_entity_count | 51 |
| blocked_entity_days_estimate | 646 |
| promotion_coverage.fraction | 1.0 (55/55) |

## Partition check (attack)

eval_scenario_1=1, _2=35, _3=45, _4=1, _5=75; all_partitions_eval_scenario=true.

## Honesty

- **Not CALIBRATED.**
- Cross-series FP/P/R vs Series B (or A) is **INVALID**.
- Design 1 B4 remains the only scoped boil-the-frog license; Series C does not reclaim it.
- scoring_config.yaml untouched (`knobs_changed: false`).
- SC3 governance / residual-risk deferred to parent.
