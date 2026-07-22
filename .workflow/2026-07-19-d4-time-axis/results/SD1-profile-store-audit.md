# SD1 — ProfileStore time-axis audit

**Packet:** SD1 (`get_latest_shadow_profile` fix)  
**Date:** 2026-07-19

## Summary

`get_latest_shadow_profile` previously filtered and ordered on `created_at` (wall-clock build provenance). SD1 moves as-of selection to `data_window_end` (sim/data time) with `created_at DESC` only as a tie-break among equal windows.

---

## Method inventory

### `_to_artifact(model)` (static)

Maps ORM row → frozen `ProfileArtifact` Pydantic schema. No time-axis queries.

### `get_active_profile(entity_id, event_time)`

**Time axis:** `promoted_at` / `superseded_at` (sim-aligned in eval).

- Filter: `is_shadow=false`, `promoted_at <= event_time`, and (`superseded_at > event_time` OR `superseded_at IS NULL`).
- **No `created_at` in filter or order.**
- Safe for in-window coverage when `event_time` is sim time and builder stamps `promoted_at = as_of` (see below).

### `get_latest_shadow_profile(entity_id, as_of=None)` — **fixed in SD1**

**Time axis:** `data_window_end` for as-of; `created_at` tie-break only.

- Filter: `is_shadow=true`, and when `as_of` set: `data_window_end <= as_of` only.
- Order: `data_window_end DESC`, then `created_at DESC` (disambiguation among rebuilds at the same window end).
- **`created_at` must not appear in any as-of filter.**

### `count_shadow_profiles(entity_id)` — **new in SD1**

**Time axis:** none (inventory count).

- Returns total shadow rows for entity; not as-of filtered.
- Supports observability / deferral diagnosis (inventory existed but lookup missed).

### `get_promoted_history(entity_id, limit)`

**Time axis:** `promoted_at`.

- Filter: `is_shadow=false`, `promoted_at IS NOT NULL`.
- Order: `promoted_at DESC`.
- Used for anchor gate; sim-aligned when builder sets `promoted_at = as_of`.

### `promote_profile(profile_version, promoted_at)`

**Time axis:** caller-supplied `promoted_at` on write.

- Sets `profile.promoted_at = promoted_at` and supersedes prior active with `superseded_at = promoted_at`.
- No reads on `created_at`.

---

## `promoted_at` vs `created_at` — why `get_active_profile` in-window coverage is safe

| Field | Source in builder | Semantics |
|-------|-------------------|-----------|
| `promoted_at` | `as_of` when not shadow (`promoted_at = as_of if not is_shadow_profile else None`) | **Sim/data time** — eval runner passes `build_profiles(db, as_of=current_window_end)` |
| `created_at` | `build_timestamp = datetime.utcnow()` at build | **Wall-clock provenance** — when the row was physically written |
| `data_window_end` | `rec["window_end"]` from event aggregation | **Sim/data time** — end of the profile's data window |

`get_active_profile` keys off `promoted_at`/`superseded_at`, which the builder stamps with sim `as_of`. Eval runner advances `current_window_end` in sim time (`batch/eval/runner.py`), so promoted profile selection tracks the simulation clock, not wall clock.

Shadow rows intentionally have `promoted_at=None`; they are selected only via `get_latest_shadow_profile` on `data_window_end` (SD1 fix).

---

## Series C builder deferral evidence

Source: `scratch/series_c_d4_engagement_run.log` (S2 victim `user_engineer_4`).

| Metric | Value |
|--------|-------|
| `shadow_profiles_ever` | **19** |
| `shadow_profiles_in_attack_window` (by `created_at`) | **0** |
| `promoted_profiles_in_attack_window` | **0** |
| D4 flag count (`drift_source_profile_version`) | **0** |

**Interpretation:** Builder produced shadow inventory (19 rows lifetime) but attack-window lookup by `created_at` found zero eligible shadows — a **lookup-only miss**, not builder starvation. Shadows' `data_window_end` may fall inside the attack window while `created_at` (wall `utcnow()`) is always ≥ real run time, so the old `created_at <= event.timestamp` filter excluded them.

Builder peak-drift deferral uses wall `created_at` for block timing, which tends to **over-include** shadows (built after sim block start in wall time) — the opposite failure mode from lookup starvation. Fixing lookup to `data_window_end` addresses the Series C D4=0 seam without changing builder deferral.

---

## Adjacent: `web/api.py` timeline (UI only)

Profile timeline endpoint filters shadow history with `created_at >= earliest` and orders by `created_at`. This is **display-only** and does not affect scorer D4 shadow consult. A future SD packet may align UI to `data_window_end` for consistency; out of SD1 scope.

---

## SD1 change checklist

- [x] As-of filter: `data_window_end <= as_of` only
- [x] Order: `data_window_end DESC`, `created_at DESC` tie-break
- [x] Docstring documents as-of vs tie-break split
- [x] `count_shadow_profiles` added (inventory, not as-of filtered)
