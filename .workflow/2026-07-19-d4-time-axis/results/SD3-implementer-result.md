# SD3 implementer result

**status:** PASS  
**packet:** SD3 — regression test for wall-clock-future shadows  
**date:** 2026-07-19

## Summary

Added three additive regression tests to `tests/worker/test_shadow_drift_under_block.py` covering `get_latest_shadow_profile` data_window_end-as-of selection and scorer D4 under block with wall-future `created_at`.

## Changes

| File | Rationale |
|------|-----------|
| `tests/worker/test_shadow_drift_under_block.py` | `test_shadow_lookup_uses_data_window_end_not_created_at` — wall-future `created_at` + sim-past `data_window_end` still returned |
| same | `test_shadow_lookup_tiebreak_prefers_later_created_at` — equal `data_window_end` → later `created_at` wins |
| same | `test_shadow_lookup_future_created_at_drives_scorer_d4` — optional scorer path assert (shadow drift + `drift_source_profile_version:` flag) |

No production code changes.

## Verification

```text
$ python -m pytest tests/worker/test_shadow_drift_under_block.py -k "data_window_end_not_created_at or shadow_drift_under_block" -v --tb=short

collected 5 items
test_shadow_drift_under_block_equals_unblocked_accumulator PASSED
test_blocked_shadow_miss_emits_fallback_flag PASSED
test_shadow_lookup_uses_data_window_end_not_created_at PASSED
test_shadow_lookup_tiebreak_prefers_later_created_at PASSED
test_shadow_lookup_future_created_at_drives_scorer_d4 PASSED

5 passed in 0.51s
```

## AC checklist

- [x] AC1: Insert shadow with `data_window_end < as_of`, `created_at > as_of` → found
- [x] AC2: Tie-break — identical `data_window_end`, later `created_at` wins
- [x] AC3: Scorer D4 under block uses shadow accumulator (optional test added)
- [x] AC4: Tests green with SD1 fix; existing C2 + fallback tests unchanged

## Concerns

None. Tests depend on SD1 `get_latest_shadow_profile` filtering on `data_window_end` (not `created_at`); would fail if selection reverted to `created_at <= as_of`.
