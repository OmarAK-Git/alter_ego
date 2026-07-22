# Series C finding — D4 `as_of` clock mismatch

**Date:** 2026-07-19  
**Source:** `scratch/series_c_s2_diagnosis.json` + code read of `worker/profile_store.py`  
**Status:** Confirmed by code inspection; Series C S2 trajectory consistent with this defect.

## Diagnosis recap (S2 `user_engineer_4`)

| Fact | Value |
|---|---|
| Scorer-visible promoted `cumulative_drift` | **0.0** (only 2 promotions, both pre-attack Jan 2–3; never superseded again) |
| Shadow max `cumulative_drift` | **24.33** through ladder |
| Auto-resolve **1817** | **ROWS** (`state=auto_resolved`), not entity cycles |
| S2 entity-level day-episodes | **2** (Jan 6, Jan 13) — quiet+dwell not strained |
| FP @45 | ~48% point-only · ~16% drift-primary · ~36% hybrid |
| Mid-attack `M_novel` | Vacuous (no promotions in/after attack window) |

## D4 paradox

Under a working D4, blocked + shadow drift 24.33 ⇒  
`score_drift = min(50, 24.33/5*100) = 50` ≥ thr=45 from drift alone.

Observed Series C: S2 event recall **0.0**, early_below_threshold **1.0**.

## Root cause (code)

```54:64:worker/profile_store.py
    def get_latest_shadow_profile(
        self, entity_id: str, as_of: datetime | None = None
    ) -> Optional[ProfileArtifact]:
        ...
        if as_of is not None:
            q = q.filter(ProfileArtifactModel.created_at <= as_of)
        model = q.order_by(desc(ProfileArtifactModel.created_at)).first()
```

Scorer passes `as_of=resolved_event.timestamp` (**sim** clock, e.g. 2026-01-10).  
Profile `created_at` is **wall** clock of the build host (Series C ~2026-07-19).  

`created_at <= as_of` ⇒ `2026-07-19 <= 2026-01-10` ⇒ **always false** ⇒ D4 never selects a shadow ⇒ scorer keeps promoted drift 0.

`get_active_profile` correctly keys on `promoted_at` / `superseded_at` (sim semantics). Shadow lookup must key on **`data_window_end`** (or equivalent sim field), not wall `created_at`.

## Implications for knob fork

This is **not** yet evidence for detection-weight retuning, and not evidence for attestation-horizon redesign. Resolution/laundering tempo remains a real §8 residual, but Series C S2 headline “scores never crossed” is explained by **D4 never wiring shadow drift into the score path** under day-window replay.

## Next (operator)

1. Fix D4 as_of → `data_window_end` (+ order_by same); TDD regression.  
2. Re-sweep = **Series D** (new baseline; no C→D FP/P/R claim deltas).  
3. Separate behavior-neutral packet: promote attestation defaults to YAML under its own S6.3 record.  
4. Only after D4-fixed Series D: re-apply the contingent knob families.
