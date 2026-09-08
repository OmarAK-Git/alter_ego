# Active Context

**Updated:** 2026-09-08T20:40Z

## Sprint 1 plan (docs only)

Implementation plan for the eval kernel is at
`docs/superpowers/plans/2026-09-08-eval-kernel-sprint1.md`, stacked on the
ratified design spec (`docs/superpowers/specs/2026-09-08-eval-kernel-usefulness-canary-design.md`).
No harness, scenario, or CI code in this change. Detector SoT remains Series I
(`calibrated: false`). Do not claim usefulness.

## Series I — COMPLETE (merged to main)

All 5 additive folds done. **1 accept / 4 reject.**

**Production YAML:** `precision_gate.enabled=true` only (cadence, geo, fleet, staged, volume remain rejected/disabled).

**calibrated:** false.

Workflow: `.workflow/2026-08-02-series-i-serial-calibration/`
