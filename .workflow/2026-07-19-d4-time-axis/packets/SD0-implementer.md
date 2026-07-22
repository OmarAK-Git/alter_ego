# Packet SD0 — implementer

**label:** `sprint:SD|test|c2-red-first`  
**implementation_model:** composer-2.5

## Objective

Rewrite C2 (`test_shadow_drift_under_block_equals_unblocked_accumulator`) to exercise the real wall-clock/sim-time seam. Capture FAIL evidence **before** any `profile_store` fix.

## Context

- Series C: D4 engagement = 0 because `get_latest_shadow_profile` filters `created_at <= as_of` while shadows get wall-clock `created_at`.
- Current C2 sets `created_at` in the sim past relative to the event — it never hits the seam.
- Design: `docs/superpowers/specs/2026-07-19-d4-time-axis-design.md`

## Write scope

- `tests/worker/test_shadow_drift_under_block.py` (test rewrite only)
- `.workflow/2026-07-19-d4-time-axis/results/SD0-C2-red.txt`
- Result: `results/SD0-implementer-result.md`

**Do not modify** `worker/profile_store.py` or `worker/scorer.py` in this packet.

## ACs

1. `_profile` helper accepts independent `created_at` and `data_window_end`.
2. Event `timestamp` = sim `as_of` (e.g. `2024-06-15`); shadow `data_window_end <= as_of`; shadow `created_at` = wall time after `as_of` (e.g. `2026-07-19`).
3. Promoted and shadow **`profile_version` strings differ** (e.g. `promoted_v1` vs `shadow_v2`); assert inequality so `drift_source_profile_version:` cannot fail for a same-version reason after the fix.
4. Asserts: `drift_alert.raw_value == shadow_drift`; `drift_source_profile_version:` present in flags.
5. Pytest on this test **FAILS** on current main (silent promoted fallback).
6. Full FAIL output saved to `results/SD0-C2-red.txt`.
7. Do not mark SD1 done; leave fix for SD1.

## Verify

```bash
PYTHONPATH=. pytest tests/worker/test_shadow_drift_under_block.py::test_shadow_drift_under_block_equals_unblocked_accumulator -v --tb=short
```

Expected: FAIL. Document exact assertion failure in result md.
