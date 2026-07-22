# Packet SD1 — implementer

**label:** `sprint:SD|fix|shadow-time-axis`  
**depends_on:** SD0  
**implementation_model:** composer-2.5

## Objective

Fix `ProfileStore.get_latest_shadow_profile` to select/order by sim `data_window_end`, never wall `created_at`. Audit every other `profile_store` query for the same conflation.

## Context

- SD0 left C2 red with wall-future shadow provenance.
- Spec §1: `data_window_end <= as_of`, order `data_window_end desc`.

## Write scope

- `worker/profile_store.py`
- `.workflow/2026-07-19-d4-time-axis/results/SD1-profile-store-audit.md`
- `.workflow/2026-07-19-d4-time-axis/results/SD1-C2-green.txt`
- Result: `results/SD1-implementer-result.md`

## ACs

1. When `as_of` set: filter `data_window_end <= as_of` only (no `created_at` in as-of filter).
2. Order: `data_window_end DESC`, then **`created_at DESC` tie-break** among equal windows (disambiguation, not as-of).
3. Docstring states as-of vs tie-break split.
4. Add `ProfileStore.count_shadow_profiles(entity_id) -> int` (inventory; not as-of filtered).
5. Audit md covers all methods + **`promoted_at` = builder `as_of` (sim in eval runner)** vs `created_at = utcnow` — why in-window coverage via `get_active_profile` is safe.
6. Audit md cites Series C evidence for builder deferral: `scratch/series_c_d4_engagement_run.log` — S2 `shadow_profiles_ever=19`, attack-window-by-created_at=0, D4=0 (lookup-only miss; builder produced inventory).
7. C2 from SD0 now **PASSES**; output in `results/SD1-C2-green.txt`.
8. No YAML writes.

## Verify

```bash
PYTHONPATH=. pytest tests/worker/test_shadow_drift_under_block.py::test_shadow_drift_under_block_equals_unblocked_accumulator -v --tb=short
```

Expected: PASS.
