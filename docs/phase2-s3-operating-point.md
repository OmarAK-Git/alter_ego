# Phase 2 — S3 operating point (residual modes)

**Status:** Phase 2A / closed-with-residual — **not CALIBRATED.**

Source of truth: `docs/calibration_final_metrics.json` (S3.1 sweep, seed 42, config v2.2). PR-curve diagnostics: `docs/calibration_pr_curve.json`.

## Operating point (applied)

`config/scoring_config.yaml` `anomaly_threshold: 45` — unchanged by S3.

| Metric | Value |
|---|---|
| Precision | 0.0191 |
| Recall | 0.8171 |
| F1 | 0.0373 |
| TP | 67 |
| FP | **3448** |
| FN | 15 |
| TN | 8969 |
| Drift alerts | 46 |

### Per-scenario recall @ thr=45

| Scenario | Recall | TP | FN |
|---|---|---|---|
| scenario_1_sharp_misuse | 1.0 | 1 | 0 |
| scenario_2_slow_roll | **1.0** | 35 | 0 |
| scenario_3_subtle | 0.667 | 30 | **15** |
| scenario_4_service_abuse | 1.0 | 1 | 0 |

**S2 (slow roll):** caught under this harness after S1/S2 integrity fixes (eval partitions, geo drift, containment wiring). Recall 1.0 (35/35).

## Residual error modes

1. **High false-positive rate** — 3448 FP at thr=45 (~98% of positive decisions are benign). Global precision ~1.9% makes analyst triage impractical at this threshold without downstream filtering.
2. **scenario_3_subtle misses** — 15 FN (recall 0.667). Subtle insider drift remains the weakest attack class; likely needs feature/threshold work beyond integrity fixes.
3. **Threshold tradeoff not taken** — PR-curve best-F1 at **thr=55** (P=0.0405, R=0.585, F1=0.076, FP=1136, FN=34) is documented for diagnosis only. **Not applied** to YAML; would trade recall (including S2/S3 hits) for fewer FP.

## What this is not

- Not a CALIBRATED or audit-grade claim.
- Not a recommendation to ship thr=45 to production analysts without further FP reduction (S3.6 governance if thresholds change).
- S3.5 owns SPEC.md / phase2 doc scrub; this note is the S3.4 residual record.
