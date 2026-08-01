# Scoring-config governance — Series G (2026-07-30)

**Plan:** Phases 3–4 (fleet cohort drift + geo-velocity)  
**Status:** **Not CALIBRATED.** Harness-only `fleet_drift_enabled` + `geo_velocity.enabled`.

## S3 recall with fleet cohort drift enabled

| Metric | Value |
|---|---|
| scenario_3_subtle recall | 0.1111111111111111 |
| scenario_3 tp / fn | 5 / 40 |

Series D archival S3 recall was **0.444** — cross-series comparison is **informational only** per repo discipline; topology changed with new dimensions.

## S1 recall (geo-velocity check)

| scenario_1_sharp_misuse recall | 1.0 |

## Headline @ thr=45

P/R: 0.0067 / 0.4615; FP=7995; TP=54.

Evidence report only — no committed YAML flip authorized.
