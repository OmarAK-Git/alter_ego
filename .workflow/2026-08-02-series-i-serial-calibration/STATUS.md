# Series I — STATUS (Phase B COMPLETE)

**Updated:** 2026-08-03T12:40Z · **Calibrated:** false · **Merge to main:** no (operator review)

## Fold chain — final results

| # | Step | Agent | Governance |
|---|---|---|---|
| 1 | fold_02_feature_volume | bc-29a79b5f | REJECT (inert) |
| 2 | fold_06_precision_gate | bc-40622c65 | **ACCEPT** |
| 3 | fold_05_fleet | bc-9da7fc31 | REJECT (inert) |
| 4 | fold_07_staged_drift | bc-e6bb797e | REJECT (inert) |
| 5 | fold_03_drift_volume | bc-46045319 | REJECT (worse vs accepted) |

## Campaign outcome

**Single promotion:** `precision_gate.enabled=true` on branch YAML.

| Metric | Series E–H baseline | Accepted branch |
|---|---:|---:|
| F1 | 0.0132 | **0.0135** |
| R | 0.462 | 0.462 |
| FP | 7995 | **7840** |
| S1 / S4 | 1.0 / 1.0 | 1.0 / 1.0 |

**Rejected:** feat_volume (feature), fleet, staged, volume drift (w=5.0 worse than precision_gate alone). Cadence/geo aborted pre-chain.

**Archival evidence:** all ws_* probes complete (volume grid best F1 at w=1.0 FP=7870 — still worse than precision_gate fold).

## Next (operator)

1. Review governance docs in `results/scoring-config-governance-series-i-fold_*.md`
2. Decide merge-to-main for precision_gate only
3. Do **not** claim CALIBRATED
