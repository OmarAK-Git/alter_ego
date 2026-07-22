# SD2 implementer result — no silent fallback

**Status:** PASS

**Date:** 2026-07-19

## Summary

When a blocked entity has no eligible shadow profile at `as_of`, the scorer now logs a WARNING with `entity_id`, `as_of`, and `active_shadow_count` (via `ProfileStore.count_shadow_profiles`) and appends flag `drift_shadow_fallback:no_shadow`. Drift scoring still uses the promoted profile's `cumulative_drift`; shadow-hit path unchanged.

## Files changed

| Path | Rationale |
|------|-----------|
| `worker/scorer.py` | D4 branch: on blocked ∧ shadow `None`, WARN + `drift_shadow_fallback:no_shadow`; reuse single `ProfileStore` instance |
| `tests/worker/test_shadow_drift_under_block.py` | Added `test_blocked_shadow_miss_emits_fallback_flag` (additive at end; C2 test untouched) |

## Verification

```text
$ python -m pytest tests/worker/test_shadow_drift_under_block.py -v --tb=short

tests/worker/test_shadow_drift_under_block.py::test_shadow_drift_under_block_equals_unblocked_accumulator PASSED
tests/worker/test_shadow_drift_under_block.py::test_blocked_shadow_miss_emits_fallback_flag PASSED

2 passed in 0.44s
```

## AC checklist

1. Blocked ∧ shadow `None` → `count_shadow_profiles`, WARNING fields, `drift_shadow_fallback:no_shadow` — **met**
2. Score uses promoted `cumulative_drift` on miss — **met** (test asserts `raw_value == promoted_drift`)
3. Shadow found → no fallback flag; `drift_source_profile_version:` unchanged — **met** (C2 still passes)
4. Unit test covers miss path with flag + WARNING — **met**
5. Existing C2 passes — **met**
6. No YAML writes — **met**

## Concerns

- None blocking SD3. Fallback test is a new function at file end for clean SD3 regression additions.
- `count_shadow_profiles` is inventory-only (not as-of filtered); intentional per spec for observability when lookup misses.
