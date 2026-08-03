# Scoring-config governance — Series I / fold_07_staged_drift

**Timestamp:** 2026-08-03T09:50:37Z
**Status:** **Not CALIBRATED.** Decision: **reject**

## Overrides under test

```
precision_gate.enabled=true
staged_drift.enabled=true
```

## Headline @ thr=45

| F1 | R | FP | S1 | S4 |
|---:|---:|---:|---:|---:|
| 0.013481462988390962 | 0.46153846153846156 | 7840 | 1.0 | 1.0 |

## Decision reason

REJECT staged_drift.enabled: inert vs prior accepted baseline

Evidence report for Series I additive fold chain. calibrated: false.
