# SD0 implementer result

**Packet:** SD0 — C2 red evidence (before profile_store fix)  
**Status:** DONE  
**Date:** 2026-07-19

## Summary

Rewrote `test_shadow_drift_under_block_equals_unblocked_accumulator` to exercise the wall-clock vs sim-time seam. C2 **FAILS** on current code as required — shadow lookup misses because `get_latest_shadow_profile` filters `created_at <= as_of`, so scorer silently falls back to promoted drift `0.0`.

## Changes

| File | Rationale |
|------|-----------|
| `tests/worker/test_shadow_drift_under_block.py` | `_profile` accepts independent `created_at` / `data_window_end`; C2 uses sim `as_of=2024-06-15`, shadow `created_at=2026-07-19` (wall), shadow `data_window_end=as_of-1h`; distinct versions asserted |

## AC checklist

| # | AC | Result |
|---|-----|--------|
| 1 | `_profile` accepts independent `created_at` and `data_window_end` | PASS |
| 2 | Event `timestamp=as_of`; shadow `data_window_end<=as_of`; shadow `created_at` wall-after-as_of | PASS |
| 3 | Promoted/shadow `profile_version` differ; inequality asserted | PASS |
| 4 | Asserts `drift_alert.raw_value == shadow_drift` and `drift_source_profile_version:` in flags | Present (first assert fails before second runs) |
| 5 | Pytest FAILS on current code | PASS |
| 6 | Full FAIL output in `SD0-C2-red.txt` | PASS |
| 7 | SD1 fix not implemented | PASS |

## Verification

```powershell
cd C:\Users\oalan\alter_ego
$env:PYTHONPATH="."
pytest tests/worker/test_shadow_drift_under_block.py::test_shadow_drift_under_block_equals_unblocked_accumulator -v --tb=short
```

**Result:** 1 failed in 0.80s (expected red)

## Exact assertion failure

```
tests\worker\test_shadow_drift_under_block.py:162: in test_shadow_drift_under_block_equals_unblocked_accumulator
    assert abs(drift_c.raw_value - shadow_drift) < 1e-9
E   AssertionError: assert 3.0 < 1e-09
E    +  where 3.0 = abs((0.0 - 3.0))
E    +    where 0.0 = FeatureContribution(..., feature_name='drift_alert', raw_value=0.0, ...).raw_value
```

**Interpretation:** `drift_c.raw_value` is promoted `0.0`, not shadow `3.0`. `get_latest_shadow_profile(..., as_of=2024-06-15)` excludes the shadow row (`created_at=2026-07-19`), so D4 silent promoted fallback occurs. The `drift_source_profile_version:` flag assertion was not reached.

## Output artifacts

- `.workflow/2026-07-19-d4-time-axis/results/SD0-C2-red.txt`
- `.workflow/2026-07-19-d4-time-axis/results/SD0-implementer-result.md`

## Unresolved / handoff

None. SD1 may fix `get_latest_shadow_profile` to filter on `data_window_end` instead of `created_at`.
