# S1-6 review / verify packet

**Task:** gov.anomaly_opens_workflow
**Claim:** both arms pass when `run_pipeline` scores at least one event anomaly and every such anomaly has `AlertWorkflowState.state == "new"`. Seeded DecisionRecord INSERT is theater.

Do not treat builder `PROFILE_BUILD` / `COHORT_DRIFT` rows as the scored-event pin. Do not lower `anomaly_threshold`. Fixture must produce a real pipeline anomaly.

Controller: `pytest tests/eval/test_gov_anomaly_opens_workflow.py -v --tb=short`
Also: `pytest tests/eval/test_e2e_kernel.py tests/eval/test_gov_no_knob_without_sweep.py -v --tb=short`
Ruff: `ruff check batch/eval/e2e_kernel.py batch/eval/kernel_fixtures.py tests/eval/test_gov_anomaly_opens_workflow.py`
