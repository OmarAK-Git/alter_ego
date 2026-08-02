# Scoring-config governance — Series H (2026-07-30)

**Plan:** Phases 5–6 (precision gate Stage A + staged sequences)  
**Status:** **Not CALIBRATED.**

## Benign vs. TP signal-family agreement (Stage-B evidence base)

| Cohort | n | mean | histogram |
|---|---:|---:|---|
| benign FP | 8026 | 0.8413904809369549 | {'0': 1273, '1': 6753} |
| TP | 54 | 1.0 | {'1': 54} |

*This distribution is the evidence base for any future Stage-B threshold proposal. No proposal may cite a number not derived from this table.*

## Phase 6 staged-sequence recall impact

| scenario_3_subtle recall | 0.1111111111111111 |

Harness-only `precision_gate.enabled` + `staged_drift.enabled`; committed YAML remains false.
