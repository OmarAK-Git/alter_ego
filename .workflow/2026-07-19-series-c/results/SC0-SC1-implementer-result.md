# SC0–SC1 Implementer Result

**Packets:** SC0 (scenario_5 inject) + SC1 (Series C sweep harness)  
**Date:** 2026-07-19  
**Status:** SC0=done, SC1=done (harness runnable; full sweep deferred to SC2)

## What changed

| File | Rationale |
|---|---|
| `tests/fixtures/boil_the_frog/s5_patient_cycle.yaml` | T-PATIENT schedule: segments `[[0,1],[2,3],[4,5,6]]`, `quiet_days: 4`, embedded S2 ladder |
| `batch/synthetic/generator.py` | `inject_scenario_5_patient_cycle` — ladder bursts + in-family quiet on `eval_scenario_5`; `exclude_entity_ids` for S2 coexistence |
| `core/schemas/events.py` | Added `eval_scenario_5` to `SimulationPartition` (required for Event validation) |
| `batch/profile_builder/builder.py` | `builder_partitions` += `eval_scenario_5` |
| `docs/superpowers/specs/2026-07-18-boil-the-frog-invariants-design.md` | scenario_5 partition: `(planned)` → live `eval_scenario_5` |
| `tests/test_generator.py` | S5 partition/label/gap/ladder/exclude tests; BUILDER_PARTITIONS updated |
| `scratch/run_series_c_sweep.py` | Seed-42 harness: Jan1→22 window, S1–S5, thr=45 metrics + §4.7/attribution extras |

## Verification

```text
PYTHONPATH=. pytest tests/test_generator.py -v --tb=short
→ 15 passed
```

Generation smoke (no pipeline): S1–S5 label counts 1/35/45/1/35; `eval_scenario_5` = 75 (35 attack + 40 quiet); S2≠S5 victims; last event ≤ Jan 21.

**Not run:** full day-window pipeline / multi-minute sweep (SC2).

## SC2 blockers / remaining work

1. **Execute** `python scratch/run_series_c_sweep.py` (long; expect more wall time than Series B — +7 baseline days + S5 quiet mass).
2. Promote `scratch/series_c_metrics.json` → `docs/calibration_series_c_metrics.json` (do **not** overwrite Series B).
3. `pre_absorption_tp_fraction` left `null` in harness (needs novel-mass vs profile); SC2 may refine if TPs exist.
4. Governance/residual (SC3) + exit gate still pending; do not claim CALIBRATED.
5. Detection YAML untouched (correct).

## Constraints honored

- No `config/scoring_config.yaml` edits
- No CALIBRATED claim
- Did not overwrite `calibration_series_b_metrics.json`
- Did not run full sweep in this packet
