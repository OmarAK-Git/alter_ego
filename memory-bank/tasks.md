# Tasks

**Updated:** 2026-09-19T01:30Z

## Eval kernel Sprint 1 — EXIT ACCEPT-WITH-GAPS

| Item | Status |
|---|---|
| Design spec (PR #7) | accepted with follow-ups |
| Sprint 1 plan (PR #8) | accepted with follow-ups |
| S1-1..S1-16 + S1-21 + P0/P1 | **done** (prior drain) |
| S1-17 cap.attributed_s2_s3_s5 | **done** (aed7b3d; verifier ACCEPT) |
| S1-18 cap.drift_vs_point_axes | **done** (63752bc, b5afbcf; verifier ACCEPT) |
| S1-19 cap.no_n1_headline | **done** (179408d; verifier ACCEPT) |
| S1-P2-GATE | **done** ACCEPT |
| S1-20 GHA + completeness | **done** (e774854; verifier ACCEPT) |
| S1-EXIT-GATE | **done** ACCEPT-WITH-GAPS (252/1; stale precision_gate vs enabled=true) |
| Sprint 2/3 / Series J / `/api/ingest` | **closed / not staffed** |

## Series I serial calibration — FOLD CHAIN COMPLETE

| Phase | Status |
|---|---|
| Phase A weight search | archival complete |
| Phase B additive folds | **COMPLETE** (5/5) |

**Accepted:** `precision_gate.enabled=true`  
**Rejected:** feat_volume, fleet, staged, volume_drift, cadence, geo  
**calibrated:** false
