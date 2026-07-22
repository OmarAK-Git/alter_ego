# SD4 implementer result

**Status:** complete  
**Date:** 2026-07-19

## Summary

Dual `promotion_coverage` metrics (ever + in-window N=5) implemented in Series D harness skeleton; unit tests green. Full seed-42 sweep **not** executed (SD6-gated).

## Files changed

| Path | Rationale |
|------|-----------|
| `scratch/run_series_d_sweep.py` | Series D harness (Series C clone) with `promotion_coverage_ever`, `promotion_coverage_in_window`, `serving_profile_missing_days`, and both metric keys in metrics JSON |
| `tests/batch/test_promotion_coverage_metrics.py` | Unit tests: ever vs in-window delta, N=5 boundary, sim-`promoted_at` smoke, wall-`promoted_at` trap |

## Verification

```text
PYTHONPATH=. pytest tests/batch/test_promotion_coverage_metrics.py -v --tb=short
4 passed in 0.85s
```

## Metric interfaces

- **`promotion_coverage_ever`** — Series C definition: scored entities with active promoted profile at sweep end (`is_shadow=False`, `promoted_at` set, `superseded_at` null).
- **`promotion_coverage_in_window`** — Unweighted mean of per-entity fractions of scored sim-days where serving promoted `data_window_end` is ≤ N=5 days stale; resolves via `get_active_profile(entity, end_of_day(d))`; tracks `serving_profile_missing_days` when profile is None (not counted as stale).

Docstrings cite Series C `promotion_coverage=1.0` with S2 frozen through the attack as the motivating counterexample.

## Concerns / notes

- Aggregation is **unweighted mean over entities** (not entity-day micro-average); stated in `promotion_coverage_in_window` docstring.
- `stale_entity_days` is reported for observability but is not part of the AC checklist.
- Full Series D sweep remains blocked until SD5 review + SD6 approval; harness `main()` is ready for SD6 execution.
- No YAML writes; worker/scorer/profile_store untouched per packet scope.
