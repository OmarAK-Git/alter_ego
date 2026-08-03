# Scoring-config governance — Series I / fold_03_drift_volume

**Timestamp:** 2026-08-03T12:37:28Z
**Status:** **Not CALIBRATED.** Decision: **reject**

## Overrides under test

```
precision_gate.enabled=true
drift_weights.total_volume_delta.enabled=true
drift_weights.total_volume_delta.weight=1.0
```

## Headline @ thr=45

| F1 | R | FP | S1 | S4 |
|---:|---:|---:|---:|---:|
| 0.013348164627363737 | 0.46153846153846156 | 7920 | 1.0 | 1.0 |

## Decision reason

REJECT drift_weights.total_volume_delta: worse/equal rank vs prior accepted (F1 0.013481462988390962→0.013348164627363737, R 0.46153846153846156→0.46153846153846156, FP 7840→7920)

Evidence report for Series I additive fold chain. calibrated: false.
