# Phase 1 Hardening Results

## Overview
This document summarizes the results of the Phase 1 hardening sprint, documenting how the architectural gaps identified in the initial self-audit were resolved.

## Resolved Gaps
- **Profile Effective Intervals**: [CLOSED] Implemented `promoted_at` and `superseded_at` in `ProfileArtifactModel`. `ProfileStore` now performs deterministic point-in-time selection.
- **Scoring Config Governance**: [CLOSED] Implemented `ScoringConfigRecord` with SHA-256 hashing and append-only `ConfigStore`. Every decision now links to a specific config version.
- **Feature Completeness**: [CLOSED] Implemented the standardized six-feature set, including service account periodicity (CV-based) and novelty detection. No more stubs.
- **Evaluation Integrity**: [CLOSED] Enforced via `test_scorer_ground_truth_isolation` and repeatable `as_of` build boundaries. Scorer cannot query ground truth.
- **Profile Drift During Alerts**: [CLOSED] Implemented shadow profile logic; entities under containment generate shadow profiles that are never promoted to the active scoring baseline.

## Final Status

**Phase 1 hardening:** CLOSED. The architectural gaps above are resolved; the foundation is stable and auditable for Phase 1 scope.

**Phase 2 calibration:** **Partial (Phase 2A)** — not a full calibration pass. Authoritative metrics live in `docs/calibration_final_metrics.json` (see also `memory-bank/progress.md`):

| Metric | Value |
|---|---|
| Precision | 1.0 (0 FP) |
| Global recall | ~0.42 (5 TP, 7 FN) |
| S1 sharp misuse recall | 1.0 |
| **S2 slow-roll recall** | **0.0 (7 FN)** |
| S3 coordinated recall | 1.0 |
| S4 service abuse recall | 1.0 |

Phase 1 foundation work does not imply Phase 2 is calibrated. S2 slow-roll remains an open residual until a re-sweep under S3.
