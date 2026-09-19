# Active Context

**Updated:** 2026-09-18T23:55Z

## Eval kernel Sprint 1 — GSD LOADED (draining)

PRs #7 (design) and #8 (Sprint 1 plan) accepted with non-blocking follow-ups.
Queue: `.workflow/autopilot-queue.json` (25 items: 21 implement + 3 phase_exit + 1 run_exit).
T3 run: `.workflow/2026-09-18-eval-kernel-sprint1/`.
Branch: `gsd/eval-kernel-sprint1` @ `e0bf028`. Foundation + S1-5/S1-6 done. Next: S1-7 integrity skip pin.

Sprint 1 is a harness earn. Detector SoT remains Series I (`calibrated: false`). Do not claim usefulness. Do not staff Sprint 2/3.

## Series I — COMPLETE (merged to main)

All 5 additive folds done. **1 accept / 4 reject.**

**Production YAML:** `precision_gate.enabled=true` only (cadence, geo, fleet, staged, volume remain rejected/disabled).

**calibrated:** false.

Workflow: `.workflow/2026-08-02-series-i-serial-calibration/`
