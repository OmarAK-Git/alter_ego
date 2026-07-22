# Packet SD6 — implementer (BLOCKED until SD5 approval)

**label:** `sprint:SD|eval|series-d-sweep`  
**depends_on:** SD5-REVIEW-GATE (operator OK)  
**status:** blocked  
**implementation_model:** composer-2.5

## Objective

Full Series D re-sweep under R-INTERLOCK + D4 (now actually engaged).

## Constraints

- seed **42**; config **v2.2** @ `anomaly_threshold=45`
- No detection/attestation YAML writes
- New baseline — no C→D FP/P/R comparisons except `drift_source_profile_version` engagement **0 → nonzero**

## Write scope

- `scratch/run_series_d_sweep.py` (execute)
- `docs/calibration_series_d_metrics.json`
- `results/SD6-sweep-result.md`

## Report (required fields)

- S2 `drift_alert` raw trajectory
- S1→S5 recall; P/R/F1
- fallback-flag count (expect ~0 after first shadow per block)
- auto_resolved
- both `promotion_coverage_ever` and `promotion_coverage_in_window`
- ATTEST peak-drift gate outcomes for S2 (with shadow drift visible, does S2 stay blocked?)
- D4 engagement count (acceptance signal vs Series C = 0)

## Do not start

Until `state.json` shows SD5-REVIEW-GATE operator-approved and SD6 unblocked.
