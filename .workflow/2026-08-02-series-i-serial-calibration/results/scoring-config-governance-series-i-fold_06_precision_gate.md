# Scoring-config governance — Series I / fold_06_precision_gate

**Timestamp:** 2026-08-03T04:21:41Z
**Status:** **Not CALIBRATED.** Decision: **accept**

## Overrides under test

```
precision_gate.enabled=true
```

## Headline @ thr=45

| F1 | R | FP | S1 | S4 |
|---:|---:|---:|---:|---:|
| 0.013481462988390962 | 0.46153846153846156 | 7840 | 1.0 | 1.0 |

## Decision reason

ACCEPT precision_gate.enabled: improves vs prior accepted baseline (F1 0.01322556943423953→0.013481462988390962, R 0.46153846153846156→0.46153846153846156, FP 7995→7840)

Evidence report for Series I additive fold chain. calibrated: false.
