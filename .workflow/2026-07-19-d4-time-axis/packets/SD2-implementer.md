# Packet SD2 — implementer

**label:** `sprint:SD|obs|no-silent-fallback`  
**depends_on:** SD1  
**implementation_model:** composer-2.5

## Objective

When entity is blocked and shadow lookup returns `None`, do not fail silently: WARN log + explicit DecisionRecord flag.

## Write scope

- `worker/scorer.py` (D4 branch)
- `tests/worker/test_shadow_drift_under_block.py` (new fallback test) and/or dedicated test module
- Result: `results/SD2-implementer-result.md`

## ACs

1. On blocked ∧ `shadow is None`:
   - `active_shadow_count = ProfileStore(db).count_shadow_profiles(entity_id)` (no direct `ProfileArtifactModel` in scorer).
   - `logger.warning` with `entity_id`, `as_of` (= event timestamp), `active_shadow_count`.
   - Append flag `drift_shadow_fallback:no_shadow`.
2. Score still uses promoted `cumulative_drift` (behavior preserved; now observable).
3. When shadow found: no fallback flag; existing `drift_source_profile_version:` behavior unchanged.
4. Unit test covers miss path (blocked, no shadows) with flag + WARNING evidence.
5. No YAML writes.

## Verify

```bash
PYTHONPATH=. pytest tests/worker/test_shadow_drift_under_block.py -v --tb=short
```
