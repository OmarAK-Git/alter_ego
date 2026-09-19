# S1-5 review / verify packet

**Task:** gov.no_knob_without_sweep
**Introduces:** `evaluate_scenario` dispatch on `batch/eval/e2e_kernel.py`

Required: both arms pass when live YAML SHA-256 matches pinned baseline; empty `knob_exceptions.yaml`; theater `series_j_fold` with staffs_series_j=False; no run_pipeline for this ID; no ScorecardRow theater field.

Controller: pytest tests/eval/test_gov_no_knob_without_sweep.py → 2 passed; ruff clean.
