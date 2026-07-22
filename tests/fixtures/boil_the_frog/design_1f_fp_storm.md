# Design 1F — FP-storm companion for §5.5 deadlock (S55.6)

Companion to Design 1 fixture. Exists because Design 1 all-green is FP-storm-free by construction.

**Behavior under test:** synthetic benign FP arms `AlertWorkflowState` → entity build-blocked → after QUIET∧ATTEST∧min_dwell, machine `auto_resolved` without analyst → next build promotes.

**Harness:** `tests/test_s55_invariants_c1_c3.py::test_design_1f_fp_injection_deadlock_resolves` (and C1).

**Series C:** `scenario_5_patient_cycle` inject is live (`batch/synthetic/generator.py`, partition `eval_scenario_5`); full-sweep metrics in `docs/calibration_series_c_metrics.json` (NOT CALIBRATED; S5 event R=0.0).
