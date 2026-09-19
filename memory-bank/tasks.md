# Tasks

**Updated:** 2026-09-18T23:55Z

## Eval kernel Sprint 1 — GSD LOADED (not yet implemented)

| Item | Status |
|---|---|
| Design spec (PR #7) | accepted with follow-ups — `docs/superpowers/specs/2026-09-08-eval-kernel-usefulness-canary-design.md` |
| Sprint 1 plan (PR #8) | accepted with follow-ups — `docs/superpowers/plans/2026-09-08-eval-kernel-sprint1.md` |
| GSD queue | loaded — 25 items in `.workflow/autopilot-queue.json` |
| S1-1 scorecard schema | **done** (0c682d2, 8ab4178; verifier ACCEPT) |
| S1-2 e2e kernel | **done** (81e99ae, c61eda0; verifier ACCEPT) |
| S1-3 scenario YAML loader | **done** (c39f75c; verifier ACCEPT) |
| S1-4 theater registry | **done** (78caae2; verifier ACCEPT) |
| S1-P0-GATE | **done** ACCEPT-WITH-GAPS (pre-existing precision_gate test vs enabled=true) |
| S1-5 gov.no_knob_without_sweep | **done** (4db2398; verifier ACCEPT) |
| S1-6 gov.anomaly_opens_workflow | **done** (e0bf028; verifier ACCEPT) |
| S1-7..S1-16 gov/des/thr/use | **done** (71e9284, e6d1386; verifier ACCEPT) |
| S1-P1-GATE | **done** ACCEPT |
| S1-21 docs SoT | **done** (e11019d) |
| S1-17..S1-19 capability | pending (next) |
| S1-17..S1-19 capability | pending |
| S1-21 docs + S1-20 GHA | pending |
| S1-EXIT-GATE | pending |
| Series J / `/api/ingest` / canary | **closed** |

## Series I serial calibration — FOLD CHAIN COMPLETE

| Phase | Status |
|---|---|
| Phase A weight search | archival complete |
| Phase B additive folds | **COMPLETE** (5/5) |

**Accepted:** `precision_gate.enabled=true`  
**Rejected:** feat_volume, fleet, staged, volume_drift, cadence, geo  
**calibrated:** false
