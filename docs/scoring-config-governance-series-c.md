# Scoring-config governance — Series C (2026-07-19)

**Packet:** `.workflow/2026-07-19-series-c/`  
**Status:** Series C baseline established. **Not CALIBRATED.** Detection knobs **unchanged**.

## What this sweep covers

| Item | Value |
|---|---|
| Seed | 42 |
| Config | v2.2 @ `anomaly_threshold=45` |
| Semantics | R-INTERLOCK (QUIET∧ATTEST + D4) + `scenario_5_patient_cycle` on `eval_scenario_5` (feeds builder) |
| Artifact | [`docs/calibration_series_c_metrics.json`](calibration_series_c_metrics.json) |
| Harness | `scratch/run_series_c_sweep.py` |
| Knobs changed | **false** — attestation params remain code defaults (`core/attestation.py`); no YAML write |

## Headline (Series C only — not comparable to A/B)

| Metric @ thr=45 | Value |
|---|---|
| P / R / F1 | 0.000301 / 0.008547 / 0.000582 |
| TP / FP / FN | 1 / 3320 / 116 |
| S1→S5 recall | 1.0 / 0 / 0 / 0 / 0 |
| auto_resolved | 1817 |
| promotion_coverage | 1.0 (55/55 active promoted) |
| active_alert_workflow_rows | 1523 |

## Cross-series rule

**B→C (and A→C) FP/P/R deltas are INVALID** as improvement or regression claims. Series C is a new baseline under new lifecycle semantics + S5.

## Honest reading vs Series B deadlock

Under Series B, blocked was absorbing (0 auto_resolved; fleet promotion collapsed). Under Series C R-INTERLOCK:

- Auto-resolution fires at scale (`auto_resolved_count=1817`)
- Promotion coverage recovers to **1.0** by sweep end

The **absorbing-block deadlock topology is no longer the Series C failure mode**. Slow-roll / patient-cycle event recall nevertheless remains **0.0** for S2 and S5 (`early_below_threshold_fraction=1.0`, `caught_before_absorption_proxy=false`). Design 1 B4 remains the only scoped boil-the-frog license.

## Standing rule

No knob edits without sweep + governance. Headline recall requires attribution decomposition. Do not reclaim boil-the-frog from Series C S2/S5 R.
