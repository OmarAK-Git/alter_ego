# Packet SD3 — implementer

**label:** `sprint:SD|test|regression-future-created-at`  
**depends_on:** SD1  
**implementation_model:** composer-2.5

## Objective

Dedicated regression: shadows with wall-clock `created_at` in the future relative to event `as_of` but `data_window_end` in the sim past must be found. This is the test that would have failed Series C.

## Write scope

- `tests/worker/test_shadow_drift_under_block.py` (add `test_shadow_lookup_uses_data_window_end_not_created_at`)
- Result: `results/SD3-implementer-result.md`

## ACs

1. Insert shadow: `data_window_end < as_of`, `created_at > as_of` (wall future).
2. `get_latest_shadow_profile(entity, as_of)` returns that shadow.
3. Tie-break: two shadows with identical `data_window_end`, different `created_at` → later `created_at` wins.
4. Optionally assert scorer D4 path under block uses its accumulator.
5. Tests green with SD1 fix; would fail if selection reverted to as-of-on-`created_at`.

## Verify

```bash
PYTHONPATH=. pytest tests/worker/test_shadow_drift_under_block.py -k "data_window_end_not_created_at or shadow_drift_under_block" -v --tb=short
```
