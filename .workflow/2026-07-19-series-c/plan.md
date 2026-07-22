# Series C — post-R-INTERLOCK calibration baseline

**Tier:** T3  
**Canonical state:** `.workflow/2026-07-19-series-c/state.json`  
**Plan:** `docs/superpowers/plans/2026-07-19-series-c.md`  
**Prior:** `.workflow/2026-07-18-s55-alert-lifecycle/` (R-INTERLOCK shipped)

## Goal

Establish Series C baseline under QUIET∧ATTEST + D4, including `scenario_5_patient_cycle`. No B→C FP/P/R claim deltas.

## Success Criteria

- `inject_scenario_5_patient_cycle` + `eval_scenario_5` feeds builder
- Seed-42 sweep artifact `docs/calibration_series_c_metrics.json` with attribution + §4.7 fields
- Governance record; residual-risk updated; detection YAML untouched unless separate evidenced revision
- pytest + ruff green; skeptic ACCEPT or ACCEPT-WITH-GAPS (honest)

## Constraints

- seed 42; v2.2 @ thr=45
- Cross-series B→C FP/P/R comparisons prohibited
- Headline recall needs attribution decomposition
- Not CALIBRATED without earned evidence

## Packets

| ID | Objective |
|---|---|
| SC0 | scenario_5 inject + builder partition + tests |
| SC1 | Series C sweep harness + report fields |
| SC2 | Execute sweep + write series_c metrics JSON |
| SC3 | Governance + residual-risk + memory-bank |
| SC-EXIT-GATE | pytest + ruff + skeptic |

## Verification

- Focused S5/generator/BTF tests after SC0
- Full `pytest --ignore=tests/live` + `ruff check .` at EXIT
- Sweep: `python scratch/run_series_c_sweep.py`
