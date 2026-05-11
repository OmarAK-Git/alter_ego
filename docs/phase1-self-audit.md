# Phase 1 Self-Audit

## Overview
This document captures the gaps and risks identified during the transition from the initial Phase 1 attempt to the hardened Phase 1 reopening.

## Identified Gaps
- **Profile Effective Intervals**: Build timestamps were used instead of explicit effective intervals (`promoted_at`, `superseded_at`), leading to potential scoring ambiguity during concurrent builds.
- **Scoring Config Governance**: Calibration was being performed without versioned, hashed config records, making it impossible to trace the evolution of the detection logic.
- **Feature Completeness**: Command-line embeddings and service account periodicity were stubs, invalidating early calibration numbers.
- **Evaluation Integrity**: Scorer isolation from ground truth was not mechanically enforced.

## Risk Assessment
| Risk | Mitigation |
|---|---|
| Calibration against stubs | Block Phase 2 until all six features are real and tested. |
| Profile drift during alerts | Implement shadow profile non-promotion logic. |
| Identity ambiguity | Harden resolver with low-confidence flags for collisions/splits. |
