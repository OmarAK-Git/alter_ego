# Scoring-config governance — Series I / fold_05_fleet

**Timestamp:** 2026-08-03T07:06:34Z
**Status:** **Not CALIBRATED.** Decision: **reject**

## Overrides under test

```
precision_gate.enabled=true
cohort_gating_constants.fleet_drift_enabled=true
```

## Headline @ thr=45

| F1 | R | FP | S1 | S4 |
|---:|---:|---:|---:|---:|
| 0.013481462988390962 | 0.46153846153846156 | 7840 | 1.0 | 1.0 |

## Decision reason

REJECT cohort_gating_constants.fleet_drift_enabled: inert vs prior accepted baseline

Evidence report for Series I additive fold chain. calibrated: false.
