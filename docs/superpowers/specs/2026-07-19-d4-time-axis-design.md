# D4 Time-Axis Fix — Design

**Date:** 2026-07-19  
**Workflow:** `.workflow/2026-07-19-d4-time-axis/`  
**Prior:** Series C (`.workflow/2026-07-19-series-c/`) — D4 engagement count = 0  
**Diagnosis:** `scratch/diagnose_d4_engagement.py` → artifact `scratch/series_c_d4_engagement_run.log`

## Problem

`ProfileStore.get_latest_shadow_profile(entity_id, as_of)` filters and orders on `created_at` (wall-clock build provenance). Eval/sweep events use synthetic `timestamp` (sim time). Result: under block, every shadow is excluded by `created_at <= as_of`, lookup returns `None`, scorer silently falls back to frozen promoted `cumulative_drift`, and `drift_source_profile_version` never fires. Series C reported D4 engaged with R-INTERLOCK semantics while the shadow channel was dead.

C2 (`tests/worker/test_shadow_drift_under_block.py`) sets shadow `created_at` in the sim past relative to the event, so it passes without exercising the wall-clock/sim-time seam.

## Non-goals (this packet)

- No detection weight/threshold YAML writes
- No attestation parameter changes
- Attestation YAML hygiene is a separate S6.3 record (zero behavioral diff)
- No Series C→D FP/P/R comparisons except `drift_source_profile_version` engagement 0 → nonzero
- Builder `_shadow_builds_during_block` / peak-drift `created_at` filters (deferred — evidence below)

## Design

### 1. Shadow lookup time axis

```text
get_latest_shadow_profile(entity_id, as_of=None):
  filter: entity_id ∧ is_shadow
  if as_of is not None:
    filter: data_window_end <= as_of          # as-of predicate (sim/data time only)
  order: data_window_end DESC,
         created_at DESC                     # tie-break only — not an as-of predicate
  return first or None
```

**As-of vs tie-break (explicit):**

- **As-of filter** must not use `created_at`. Only `data_window_end <= as_of`.
- **Order primary:** `data_window_end DESC`.
- **Order secondary:** `created_at DESC` among sim-equal `data_window_end` rows (rebuild of the same window). This is deterministic disambiguation of the latest build, not wall-clock as-of gating. Alternatives (`profile_version` / row id) are acceptable only if equally deterministic; pick `created_at DESC` as declared.

Without the secondary key, identical `data_window_end` rebuilds yield nondeterministic shadow selection → flaky Series D.

**profile_store audit (required close-out notes in SD1):**

| Method | Temporal predicates | Axis | Verdict |
|--------|---------------------|------|---------|
| `get_latest_shadow_profile` | **was** `created_at` filter+order; **becomes** `data_window_end` as-of + `created_at` tie-break only | data / provenance split | fix |
| `get_active_profile` | `promoted_at` / `superseded_at` | **builder `as_of` lifecycle** | OK for sweeps — see §5 |
| `get_promoted_history` | order by `promoted_at` (no as-of) | builder `as_of` | OK for ATTEST anchor |
| `promote_profile` | mutation only | N/A | N/A |
| `count_shadow_profiles` (new) | inventory count, no as-of | N/A | added for scorer |

**Why `promoted_at` is safe (not the same bug):** In `batch/profile_builder/builder.py`, promotions stamp `promoted_at = as_of` while `created_at = build_timestamp = datetime.utcnow()`. Eval runner calls `build_profiles(db, as_of=current_window_end)` with **sim** window end (`batch/eval/runner.py`). So `promoted_at` / `superseded_at` live on the **sim lifecycle axis** during Series C/D sweeps; only `created_at` is wall provenance. SD1 audit notes must restate this with file:line citations.

**Adjacent seams — builder deferral (with evidence, not assumption):**

| Seam | Behavior | Why deferral is OK for this packet |
|------|----------|--------------------------------------|
| `_shadow_builds_during_block` / `_get_latest_shadow_features` | filter/order shadows by `created_at` | **Series C produced shadow inventory**; lookup was the exclusive fail. Evidence: `scratch/series_c_d4_engagement_run.log` — S2 `profiles_ever.shadow_count` / `shadow_profiles_ever` = **19**, `profiles_in_attack_window.shadow_count` = **0** (filtered by wall `created_at` in attack sim window), `d4_flag_count` = 0, most-likely seam = `seam2_shadow_profile_available`. Builder was writing rows; scorer as-of excluded them. |
| Builder peak-drift vs sim `block_start` | `created_at >= block_start` with wall `created_at` and sim `block_start` tends to be **over-inclusive**, not starved | Opposite failure shape from lookup; ATTEST/auto_resolve still ran in Series C (`auto_resolved=1817`). Revisit if Series D fallback-flag rate contradicts inventory. |
| `web/api.py` timelines | `created_at` | UI provenance; not scoring as-of |

Do **not** expand builder write-scope in this packet unless Series D shows starved/malformed shadow inventory (fallback-flag storm with `active_shadow_count=0`).

### 2. No silent fallback

When entity is blocked and `get_latest_shadow_profile` returns `None`:

1. **WARN log** with `entity_id`, `as_of`, and `active_shadow_count` from **`ProfileStore.count_shadow_profiles(entity_id)`** (do not query `ProfileArtifactModel` directly in the scorer).
2. **Explicit flag** on the `DecisionRecord`: `drift_shadow_fallback:no_shadow` (same string channel as `drift_source_profile_version:*`).

Legitimate case: first score(s) after block arming before any shadow build exists. Any other miss (shadow rows exist but none with `data_window_end <= as_of`, query bug, etc.) shares the same flag+WARN path so operators can distinguish silence from engagement by correlating WARN+flag counts against shadow inventory (`active_shadow_count` in the WARN).

When a shadow **is** found: no fallback flag; set `drift_source_profile_version:{version}` when versions differ (unchanged).

### 3. C2 seam rewrite

Replace mock-aligned timestamps with:

- Event `timestamp` = sim `as_of` (e.g. 2024-06-15)
- Shadow `data_window_end` ≤ `as_of` (sim past)
- Shadow `created_at` = wall-clock **future** relative to `as_of` (e.g. fixed 2026-07-19)
- **Versions must differ:** fixture uses distinct `profile_version` strings (e.g. `promoted_v1` vs `shadow_v2`). Add an explicit assert `promoted.profile_version != shadow.profile_version` (or hard-code distinct versions) so the `drift_source_profile_version:` assert cannot fail for a same-version reason after the lookup fix.

Contract: blocked entity with existing shadow → `drift_alert.raw_value` equals shadow accumulator; `drift_source_profile_version` present. Must **fail on pre-fix main**, **pass after fix #1**. Failing evidence commits into the packet record before the fix lands.

### 4. Regression test

Dedicated test: shadow with `created_at > as_of` (wall) and `data_window_end <= as_of` (sim) must be returned by `get_latest_shadow_profile` and drive scorer D4. This is the test that would have failed Series C.

Also cover tie-break: two shadows with identical `data_window_end`, different `created_at` → lookup returns the later `created_at`.

### 5. `promotion_coverage` metric

**Old (report as `promotion_coverage_ever`):** fraction of scored entities with any active promoted profile (Series C definition; counterexample = 1.0 while S2 frozen through attack).

**New (report as `promotion_coverage_in_window`, primary):** per entity, fraction of scored **sim-days** where `(score_day − serving_promoted.data_window_end).days ≤ N`, then mean over entities (or entity-day micro-average — state in docstring). **N = 5** (= `anchor_history_count` at ~daily build cadence).

**Serving-profile resolution (clock-skew check before wiring):** Resolve the serving promoted profile via `get_active_profile(entity, end_of_day(d))`. This is safe for Series D day-window sweeps because `promoted_at`/`superseded_at` are stamped from builder **`as_of`** (sim), not from `datetime.utcnow()` — see §1 audit. Freshness then uses that profile's **`data_window_end`** (sim data axis).  

**If** a future harness stamps `promoted_at` with wall clock, `get_active_profile` would return `None` for all sim days and in-window coverage would collapse to ~0 for reasons unrelated to staleness — the exact Series C failure shape one method over. SD4 must: (a) cite the builder stamp in the metric docstring, (b) unit-test that a profile with sim `promoted_at`/`data_window_end` is found for a matching sim day, and (c) fail loudly (or report a separate `serving_profile_missing_days` count) rather than silently treating missing active profiles as “stale.”

Series D metrics JSON reports **both** coverage defs. Docstring cites Series C `promotion_coverage=1.0` with S2 frozen through the attack as the motivating counterexample.

### 6. Series D sweep (hard-gated)

After items 1–5 are reviewed and approved:

- seed 42; config v2.2 @ `anomaly_threshold=45`
- semantics R-INTERLOCK + D4 (actually engaged)
- New S6.3 governance record; new baseline (`docs/calibration_series_d_metrics.json`)
- Allowed C→D comparison: `drift_source_profile_version` engagement count only (0 → nonzero)
- Report: S2 `drift_alert` raw trajectory; S1→S5 recall; P/R/F1; fallback-flag count; auto_resolved; both coverage defs; ATTEST peak-drift gate outcomes for S2
- Watch: if fallback-flag rate is high **and** WARN `active_shadow_count=0`, reopen builder seam (do not treat as “expected quiet”)

### 7. Separate packet

Attestation YAML hygiene — own S6.3; acceptance = zero behavioral diff.

## Acceptance (items 1–5)

- [ ] Shadow as-of uses only `data_window_end`; secondary `created_at DESC` tie-break declared
- [ ] profile_store audit lists axes; `promoted_at` = builder `as_of`; metric safety stated
- [ ] Builder deferral cites Series C evidence (`shadow_ever=19`, lookup-only miss)
- [ ] Fallback WARN + `drift_shadow_fallback:no_shadow`; count via `ProfileStore.count_shadow_profiles`
- [ ] C2 rewritten with distinct versions; red-before-green evidence; green after fix
- [ ] Future-`created_at` + equal-`data_window_end` tie-break regression green
- [ ] Dual promotion_coverage definitions with N=5; serving-profile axis verified
- [ ] **Stop** — no Series D sweep until explicit approval
