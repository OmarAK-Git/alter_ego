# SD1 implementer result

**Status:** DONE  
**Packet:** SD1 — Fix `get_latest_shadow_profile` time axis  
**Date:** 2026-07-19

## Changes

| File | Rationale |
|------|-----------|
| `worker/profile_store.py` | As-of filter on `data_window_end`; order `data_window_end DESC, created_at DESC`; docstring; add `count_shadow_profiles` |
| `results/SD1-profile-store-audit.md` | Full method inventory, promoted_at vs created_at axis, Series C deferral evidence |
| `results/SD1-C2-green.txt` | C2 PASS evidence |
| `results/SD1-implementer-result.md` | This report |

## AC verification

| AC | Result |
|----|--------|
| 1. As-of filter `data_window_end <= as_of` only | PASS — `created_at` removed from filter |
| 2. Order `data_window_end DESC`, `created_at DESC` tie-break | PASS |
| 3. Docstring states as-of vs tie-break split | PASS |
| 4. `count_shadow_profiles(entity_id) -> int` | PASS — inventory, not as-of filtered |
| 5. Audit covers all methods + promoted_at safety | PASS — see `SD1-profile-store-audit.md` |
| 6. Audit cites Series C log (S2: ever=19, attack-window=0, D4=0) | PASS |
| 7. C2 PASSES | PASS — see `SD1-C2-green.txt` |
| 8. No YAML writes | PASS |

## Verification command

```
cd C:\Users\oalan\alter_ego
$env:PYTHONPATH="."
pytest tests/worker/test_shadow_drift_under_block.py::test_shadow_drift_under_block_equals_unblocked_accumulator -v --tb=short
```

**Result:** 1 passed in 0.43s

## Root cause fixed

Prior `get_latest_shadow_profile` used `created_at <= as_of` and ordered by `created_at`. Shadow rows built during eval have `created_at = utcnow()` (wall) but `data_window_end` at sim time. SD0's C2 test proves the bug: shadow with `created_at` in the wall future but `data_window_end` one hour before sim `as_of` was excluded. SD1 selects on `data_window_end`, so the shadow is found and D4 drift uses `shadow_drift=3.0`.

## Unresolved / out of scope

- `web/api.py` timeline still uses `created_at` for shadow display (noted in audit; UI-only).
- SD2+ (silent fallback observability, scorer changes) not in this packet.

## Concerns

None.
