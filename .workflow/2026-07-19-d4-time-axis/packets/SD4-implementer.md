# Packet SD4 — implementer

**label:** `sprint:SD|metric|promotion-coverage`  
**depends_on:** SD1  
**implementation_model:** composer-2.5

## Objective

Replace ever-promoted-only coverage with dual reporting: old ever-definition + new in-window definition (N=5). Wire Series D sweep harness skeleton; **do not** run full seed-42 sweep.

## Write scope

- Prefer create: `scratch/run_series_d_sweep.py` (clone Series C harness; dual metrics)
- Create: `tests/batch/test_promotion_coverage_metrics.py`
- Result: `results/SD4-implementer-result.md`

## ACs

1. `promotion_coverage_ever` — Series C definition (scored entities ∩ active promoted / scored).
2. `promotion_coverage_in_window` — per entity, fraction of scored sim-days where serving promoted `data_window_end` is ≤ **N=5** sim-days stale; aggregate as documented.
3. Serving profile via `get_active_profile(entity, end_of_day(d))` — docstring cites that `promoted_at` is builder `as_of` (sim in eval sweeps), not wall `created_at`; track `serving_profile_missing_days` when None (do not silent-count as stale).
4. Docstring cites Series C `promotion_coverage=1.0` with S2 frozen through the attack as motivating counterexample.
5. Unit tests: ever vs in_window delta; N=5 boundary; sim-`promoted_at` axis smoke; wall-`promoted_at` trap documented.
6. Series D script exposes both keys; no full sweep execution in this packet.
7. No YAML writes.

## Verify

```bash
PYTHONPATH=. pytest tests/batch/test_promotion_coverage_metrics.py -v --tb=short
```
