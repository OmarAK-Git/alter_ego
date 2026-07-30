# Drift Detection Capability Expansion — Design

**Date:** 2026-07-30
**Planned workflow slug:** `.workflow/2026-07-30-drift-capability-expansion/` (created at plan time)
**Origin:** External review `alter-ego-drift-gap-evaluation.md`, synthesized into `docs/residual-risk-drift-hypotheses.md` §3 as H12–H15 (2026-07-30), plus one new finding (Phase 0) surfaced during this design's own investigation.
**Companion docs:** [`residual-risk-drift-hypotheses.md`](../../residual-risk-drift-hypotheses.md) · [`DEBT_LEDGER.md`](../../../DEBT_LEDGER.md) · [`AS_BUILT.md`](../../../AS_BUILT.md) · [`scoring-config-governance-series-d.md`](../../scoring-config-governance-series-d.md) · [`2026-07-19-d4-time-axis-design.md`](2026-07-19-d4-time-axis-design.md) (pattern this design extends)

Do **not** treat this document as permission to change weights, thresholds, or `enabled` flags without a recorded sweep and governance record (S6.3 standing rule, unchanged).

---

## Problem

Four newly-synthesized drift hypotheses (H12–H15) and one gap found while designing this spec (Phase 0) are worth building. They touch three layers (`batch/profile_builder/builder.py`, `worker/scorer.py`, `worker/profile_store.py`) and, taken together, are a large change to the drift engine's signal surface. This design covers all of it as one initiative, phased for incremental, independently-revertible delivery.

## Cross-cutting architecture principle: shadow-compute, flag-gated rollout

Every new signal in every phase below **computes and records its raw value + contribution unconditionally**, so sweep data accumulates from the moment code ships. It affects `raw_total` / `cumulative_drift` / `is_anomaly` / workflow-arming **only** when a new boolean `enabled` knob (default `false`) is set per feature:

```yaml
features:
  total_volume_delta:
    weight: 1.0
    enabled: false        # NEW key — default false preserves current behavior exactly

drift_weights:
  cadence:
    weight: 0.0            # reserved, same pattern as total_volume_delta today
    enabled: false          # NEW key
  geo_velocity:
    weight: 0.0
    enabled: false
```

This is strictly additive to `core/schemas/config.py` / the raw YAML dict — new keys only, existing keys and defaults unchanged, so shipping any phase's code is a **zero-behavioral-diff** change until its `enabled` flag is governance-flipped. This is the same acceptance bar already used for D4 / attestation-YAML-hygiene work in this repo. Flipping `enabled: true` for any one feature is the governed action requiring its own sweep + governance doc — exactly like a weight change today.

**Why this matters for scope:** it is what makes shipping seven phases in one initiative safe without requiring seven full calibration sweeps gated in series. Code review + tests can proceed per-phase; sweeps batch into four checkpoints (see Validation Plan).

---

## Phase 0 — Shadow-aware point-rarity & embedding baseline under block

**Problem.** `batch/profile_builder/builder.py:690-694` proves the drift accumulator never resets under block — `prev_accumulator` is read from `latest_any` (the latest profile artifact for the entity, shadow or promoted, ordered by `data_window_end`), not from the promoted lineage only. Combined with the existing D4 mechanism (`worker/scorer.py:569-591`: when `entity_has_active_uncleared_alert()` is true, `ProfileStore.get_latest_shadow_profile(entity_id, as_of=event.timestamp)` overrides `drift_accum`), the drift dimension is already fully shadow-aware — no data is lost under block, only its promotion (and, pre-D4, its visibility) was delayed.

But `worker/scorer.py`'s point-rarity computations (`s1`..`s4` for `login_hour_rarity`/`geolocation_rarity`/`endpoint_set_rarity`/`process_name_rarity`) and the embedding-cosine computation (`score_emb`), all computed **earlier in `score_event`, before** the D4 block at line 569, read `profile.features` / `profile.embedding` directly — where `profile` is always the result of `get_active_profile()` (promoted, `is_shadow=False`). For a blocked entity, that promoted profile is frozen at its pre-block state for as long as the block lasts. This means a blocked entity's point score is computed against a stale baseline — plausibly inflating point-anomaly FPs the longer a block persists, a feedback loop adjacent to (but distinct from) the one Series B/C/D already addressed.

**Design.** Extend the exact D4 pattern to the point-rarity/embedding block:

```text
score_event(db, resolved_event, profile, config):
  effective_profile = profile
  if entity_has_active_uncleared_alert(db, resolved_event.entity_id):
    shadow = ProfileStore(db).get_latest_shadow_profile(
        resolved_event.entity_id, as_of=resolved_event.timestamp)
    if shadow is not None:
      effective_profile = shadow
      if shadow.profile_version != profile.profile_version:
        flags.append(f"point_baseline_shadow_fallback:{shadow.profile_version}")
    else:
      active_shadow_count = ProfileStore(db).count_shadow_profiles(entity_id)
      logger.warning("point_baseline_shadow_fallback entity_id=%s as_of=%s active_shadow_count=%s", ...)
      flags.append("point_baseline_shadow_fallback:no_shadow")

  s1 = login_hour_rarity(event, effective_profile.features)
  s2 = geolocation_rarity(event, effective_profile.features)
  s3 = endpoint_set_rarity(event, effective_profile.features)
  s4 = process_name_rarity(event, effective_profile.features)
  score_emb, dist = embedding_similarity(event, effective_profile.embedding)
  # drift_accum block (existing D4 logic) unchanged, still resolves its own shadow independently
```

Compute the `entity_has_active_uncleared_alert()` + shadow lookup **once** per `score_event` call and reuse for both the point-rarity/embedding block and the existing drift block, rather than querying twice — a small refactor of the existing D4 code, not a behavior change to it.

**Non-goals.** Does not change whether/when `AlertWorkflowState` rows open (§5.5 arming unchanged). Does not change builder-side promotion/blocking logic — only which baseline the *scorer* compares point-rarity/embedding against while an entity is blocked.

**Why first, and alone.** This is the one change in this initiative that can shift point-FP volume for *already-blocked* entities before any new signal family exists. It ships and sweeps in isolation (Series E) so its effect is not confounded with Phases 1–6.

**Acceptance:**
- [ ] Single shared shadow-lookup call feeds both point-rarity/embedding and drift blocks
- [ ] `point_baseline_shadow_fallback:{version}` / `:no_shadow` flags mirror the existing `drift_source_profile_version` / `drift_shadow_fallback:no_shadow` contract exactly
- [ ] Regression test: blocked entity with a shadow profile whose histograms differ from the frozen promoted profile — point-rarity scores must reflect the shadow, not the promoted profile
- [ ] Regression test: blocked entity with no shadow yet — falls back to promoted profile, flag set, WARN logged
- [ ] Unblocked entity — zero behavioral diff (effective_profile == profile always)
- [ ] Series E sweep: report point-FP volume delta for previously-blocked entities specifically, before any Phase 1+ code ships

---

## Phase 1 — H12: execution-cadence-as-drift-dimension + OT synthetic archetype

**Problem.** `worker/scorer.py`'s `compute_periodicity` (interval CoV, `worker/scorer.py:363-386`) already exists and is already the right shape for H12 — but it only runs for `entity_type == "service_account"`, and only feeds the point feature `service_account_execution_frequency_deviation`. `drift_weights` has no cadence dimension (`login_hour`, `geolocation`, `endpoint_set`, `process_name`, `embedding` only).

**Design.**
1. Extend `compute_periodicity` to run for human entities too, gated by a minimum event-count floor in the lookback window (exact floor is a sweep output; start conservative, e.g. `n >= 20`, and record sensitivity — sparse human process streams are noisier than service-account cron-like patterns per H12's own caveat).
2. Add `drift_weights.cadence` (shadow-computed, `enabled: false` per the cross-cutting principle). Builder computes cadence CoV per entity per build window (reusing the same interval-CoV math as `compute_periodicity`, but at build-window granularity, not per-event) and stores it in profile `features`, contributing to `raw_drift` only when `enabled: true`.
3. The existing point-feature path (`service_account_execution_frequency_deviation`) is unchanged — Phase 1 adds a *drift* dimension alongside it, it does not replace it.

**New synthetic archetype.** `batch/synthetic/generator.py` gets an `ot_polling` service-account archetype: seconds-scale inter-event interval, near-zero jitter, 24/7 active-hours coverage — distinct from the existing IT-automation-style service accounts (minutes-scale, business-hours-weighted, more jitter). The signal under test is a *change* in regularity relative to the entity's own OT-appropriate baseline, not regularity itself (an `ot_polling` entity should score as normal at baseline despite looking mechanical — that's the correct behavior, and the archetype exists specifically to prove the drift dimension doesn't confuse "mechanical" with "anomalous").

**Weight-dominance discipline (H4 callback).** Starting weight is a sweep output, not pre-committed here. Series F must explicitly report cadence's contribution to `raw_drift` decomposed per-dimension (same ablation style H4 calls for on `embedding`) before any promotion beyond `enabled: false`.

**Non-goals.** No new entity type or schema field — `ot_polling` is a synthetic *archetype* (a generator-side behavioral template), not a new `entity_type` or persisted subtype marker. If Phase 1's sweep results argue for a persisted OT/IT subtype distinction in production entities, that is a separate future proposal, not built here.

**Acceptance:**
- [ ] `compute_periodicity`-equivalent build-window cadence CoV computed for both entity types, min-event-count floor documented and tested
- [ ] `drift_weights.cadence` present in YAML, `enabled: false`, weight `0.0` by default — zero behavioral diff on ship
- [ ] `ot_polling` archetype added to generator with a documented interval/jitter/active-hours profile distinct from existing service-account archetypes
- [ ] Unit test: cadence CoV computed correctly for both a clean `ot_polling` baseline and a drifted one (interval shift, jitter increase)
- [ ] Series F sweep: per-dimension `raw_drift` decomposition including cadence; explicit dominance check against `embedding`

---

## Phase 2 — Volume delta (closes `DEBT-051` / `DEBT-019`)

**Problem.** `worker/scorer.py:554-558` hardcodes `score_vol = 0.0` unconditionally (`volume_delta_deferred` flag), despite `total_volume_delta.weight: 1.0` already reserved in `scoring_config.yaml`.

**Design.** Implement real `score_vol`: Laplace-smoothed rarity (`laplace_alpha`, already read by builder) of the entity's recent-window event count against its own historical hourly/daily count distribution — same smoothing family already used for categorical rarity features, applied to a count histogram instead. Add `total_volume_delta` to `drift_weights` as a new dimension (build-window count-delta vs. baseline), both gated by the new `features.total_volume_delta.enabled` / `drift_weights.total_volume_delta.enabled` flags (default `false`). `volume_delta_deferred` flag is replaced by a real computed value once `enabled: true`; until then it remains for observability parity with today.

**Non-goals.** No distinct-target-account diversity metric (the ADS-01 "spray" analogue) — alter_ego's auth events are not verified to carry a stable destination-account field; that is out of scope unless a future phase confirms the field exists and is populated.

**Acceptance:**
- [ ] `score_vol` computed from real Laplace-smoothed count rarity, gated by `features.total_volume_delta.enabled`
- [ ] `drift_weights.total_volume_delta` present, `enabled: false` by default
- [ ] Unit test: count-rarity computation on synthetic count histograms (rare-spike vs. steady-state)
- [ ] Series F sweep (same checkpoint as Phase 1): volume dimension contribution reported alongside cadence

---

## Phase 3 — Fleet cohort drift (closes `DEBT-068` / `DEBT-075`)

**Problem.** H2/H7: cohort-median subtraction (`norm_drift = raw_drift - cohort_median[role]`) can cancel coordinated multi-entity drift (Scenario 3's weak spot, recall 0.667). `cohort_gating_constants.max_changed_fraction` (0.2) is **already read** by the scorer (novelty-gate suppression) but not used by the builder for any fleet-level rule.

**Design.** After the existing per-entity cohort-normalize phase (`builder.py` Phase 2, `cohort_drifts` / `cohort_medians` computation, ~line 668-681), add a fleet-level check per role: if the fraction of that role's cohort with `raw_drift` (pre-normalization) above a soft per-role threshold exceeds `max_changed_fraction` within `cohort_gate_window_days` (7, already wired), emit one new `cohort_drift` `DecisionRecord` (`event_id="COHORT_DRIFT"`, one row per affected role per build) — additive, gated by a new `cohort_gating_constants.fleet_drift_enabled` flag (default `false`). This does **not** change any individual entity's `norm_drift` / `cumulative_drift` math — it is a parallel fleet-level signal, not a fix to the per-entity subtraction itself (H2's masking mechanism is untouched; this adds a second detector that doesn't share its blind spot).

**Non-goals.** `cohort_drift` decisions are a new decision type and are explicitly **not** wired into the existing per-entity `blocked_entities` predicate — a fleet-level alert does not block any individual entity's profile promotion. Whether it should, in the future, is a Stage-B-style question deferred the same way H14 Stage B is.

**Acceptance:**
- [ ] Fleet-level `cohort_drift` check computed per role per build, gated by `fleet_drift_enabled: false` default
- [ ] Per-entity `norm_drift` / `cumulative_drift` computation unchanged (regression test: identical accumulator values before/after this phase for a fixed fixture)
- [ ] Unit test: role with ≥3 entities, ≥`max_changed_fraction` of them crossing the soft per-role threshold in-window → one `cohort_drift` decision; below threshold → none
- [ ] Series G sweep: measure S3 (`scenario_3_subtle`) recall specifically with `fleet_drift_enabled: true`

---

## Phase 4 — H13: geo-velocity

**Problem.** `core/schemas/events.py` `geolocation` is a free-text label (`entity.geography` in the synthetic generator, e.g. `"RU-Moscow"`), not coordinates. `geolocation_rarity` scores single-label rarity; nothing compares an entity's successive locations.

**Design.** New static reference table (e.g. `core/geo_centroids.py` or a bundled JSON/YAML data file) mapping the label vocabulary already in use — starting with the synthetic generator's existing labels — to lat/long centroids. No live geocoding API dependency; stays offline and deterministic like the rest of the system. Builder computes `geo_velocity_delta` per entity from paired successive auth-success events (timestamp delta + centroid distance → implied km/h), maintains a per-entity historical implied-speed distribution, and flags recent implied speed exceeding it. New `drift_weights.geo_velocity` dimension, gated by `enabled: false`. Minimum paired-success count per entity before a baseline is trusted (unstable for sparse travelers, per H13's own note). A VPN/relay allowlist knob (`geo_velocity_allowlist: []`, empty by default) exists from day one so the false-positive class H13 itself flags (corporate VPN egress, privacy relays, GeoIP churn) has a documented mitigation path even if unused initially.

**Non-goals.** No lat/long field added to the live event schema — the centroid table is a build-time/score-time lookup keyed on the existing string label, not a new required input field. Labels with no table entry contribute `0` to `geo_velocity_delta` plus an explicit flag (`geo_velocity:no_centroid`) — never a silent guess.

**Acceptance:**
- [ ] Centroid table covers 100% of labels currently emitted by `batch/synthetic/generator.py`
- [ ] `geo_velocity_delta` computed only for entities with ≥ minimum paired-success count; documented floor
- [ ] Unit test: NZ→US successive-success pair within 2 hours for a local-only baseline entity → high implied speed, non-zero delta; two nearby-city successes → low delta
- [ ] Unlabeled/unmapped geolocation string → `0` contribution + `geo_velocity:no_centroid` flag, never an exception
- [ ] Series G sweep (same checkpoint as Phase 3): geo-velocity dimension contribution reported; S1 (sharp single-signal misuse) recall impact specifically checked, per H13's rationale that this catches session-theft patterns other dimensions miss

---

## Phase 5 — H14: cross-signal-family precision gate (Stage A + versioned Stage B hook)

**Problem.** §2.1: FP=3448/precision=0.019 @ thr=45, and under §5.5 every FP opens a workflow that blocks that entity's own promotion — precision is already documented as a prerequisite for the drift path mattering. Phase 0 above addresses one contributor to this (stale point-rarity baseline under block); Phase 5 addresses it more directly via signal agreement.

**Design — Stage A (built in this spec).** Purely additive: does **not** change `is_anomaly`, §5.5 workflow-opening, or blocking for any entity.
1. Add `signal_family_agreement_count` to `DecisionRecord`: count of independent families — {rarity (s1-s4 combined), drift (`drift_alert`), cadence, volume, geo_velocity, once each is `enabled`} — whose individual contribution exceeds its own soft per-family floor on this decision.
2. `containment_threshold` (85) eligibility gains an additional Stage-A requirement: `agreement_count >= 2 OR raw_total` already exceeds containment_threshold by a wide margin (exact cutoff a sweep output — not pre-committed here). Analyst API/UI surfaces `agreement_count` for triage sort/filter.
3. **Governance pre-commitment (per explicit instruction during design):** the Series H sweep must report the natural `signal_family_agreement_count` distribution on benign (FP) traffic **separately from** TP traffic as a first-class metric, and this distribution — not a number chosen after seeing recall impact — is what any future Stage-B threshold proposal must cite. This is written down now specifically so the threshold is not reverse-fit later.
4. Add a versioned `precision_gate_version` field to `DecisionRecord` now, even though Stage A doesn't change decision *outcomes* — so that if/when Stage B ships, replay (`batch/replay_runner.py` / `POST /api/replay`) has a field to check gate semantics against, rather than silently reinterpreting old decisions under whatever gating logic is live at replay time. This is the same class of time-axis bug D4 fixed, applied to a config-semantics axis instead of a data-time axis. (Note: `ReplayRequest`'s existing config-version fields are already unused by `run_replay` per `DEBT-057` — Phase 5 does not fix that; it adds the field so a future fix has something to key on. Explicitly flagged as a carried-forward known limitation, not resolved here.)

**Design — Stage B (explicitly NOT built in this spec).** Promoting agreement-gating to suppress/delay §5.5 workflow-opening for single-family-only anomalies — i.e., cutting into the deadlock at its root rather than downstream of it. Separate future governance record, informed by (a) Stage A's real benign-vs-TP agreement measurements and (b) whatever Phase 0 turns out to do to the FP feedback loop on its own — Phase 0 may reduce Stage B's urgency, and that reassessment is a planned Series H output, not assumed here.

**Non-goals.** Stage A does not touch `worker/recorder.open_active_alert_if_needed` or any §5.5/S55 lifecycle code path. No ATT&CK technique graph or cross-decision correlation beyond per-decision signal-family agreement.

**Acceptance:**
- [ ] `signal_family_agreement_count` computed and stored on every `DecisionRecord`, using per-family soft floors documented in code
- [ ] `containment_threshold` eligibility check updated with the additional Stage-A requirement, unit-tested against fixtures with 1 vs. ≥2 agreeing families
- [ ] `precision_gate_version` field added to schema/model, stamped on every decision, no behavior tied to its value yet (Stage B concern)
- [ ] Series H sweep: benign-vs-TP `agreement_count` distributions reported as first-class, separate metrics — this is a hard gate before any Stage-B design doc is written
- [ ] Zero change to `is_anomaly`, workflow-opening, or promotion-blocking behavior anywhere in Stage A (regression tests against existing S55 invariant tests: `tests/test_s55_invariants_c1_c3.py`, `tests/test_boil_the_frog_invariants.py`)

---

## Phase 6 — H15: staged multi-feature drift ordering

**Problem.** `cumulative_drift` and the point-score aggregate are order-blind — neither records which drift dimensions crossed soft thresholds, or in what sequence, across builds. Most speculative/calibration-heavy item in this initiative per its own hypothesis text.

**Design.** Builder records, per entity per build, the set of drift dimensions (now up to 8, once Phases 1/2/4 land) that crossed a soft per-dimension threshold that build — a short ordered log (last N build-steps' crossing-sets) stored in profile `features`. A configurable, explicitly small sequence-template list (empty by default) scores ordered matches within roughly the `drift_half_life_days` window; contributes to `cumulative_drift` only when `enabled: true` and a template is configured. Spec commits to **at most 1–2 candidate templates** at launch (e.g. `endpoint→process→embedding`, `endpoint→process→volume`), chosen from real S3 FN postmortems in the Series D/E/F/G sweep DBs — not a general template library or DSL.

**Non-goals.** No general-purpose sequence-template authoring UI or config language. No claim of detecting novel/unforeseen sequences — only the specific templates validated against real FN postmortems.

**Sequencing rationale.** Built last because it benefits from having Phases 1/2/4's dimensions already present — more dimensions to sequence over, and their own Series F/G sweep data to mine for real candidate templates instead of guessing.

**Acceptance:**
- [ ] Per-build per-entity threshold-crossing log stored, bounded length (last N builds)
- [ ] At most 2 templates hardcoded/configured at launch, each cited against a specific S3 FN case from Series D/E/F/G sweep data
- [ ] Unit test: synthetic staged inject (below-threshold single dims, matching template order) → staged-drift contribution fires; same dims in non-matching order → does not fire
- [ ] Series H sweep (same checkpoint as Phase 5): S3 recall impact specifically reported

---

## Validation plan: batched Series, not seven sweeps

| Series | Phases covered | What it must report |
|---|---|---|
| **E** | Phase 0 alone | Point-FP volume delta for previously-blocked entities, isolated from any new dimension |
| **F** | Phases 1–2 | Cadence + volume dimension contributions, per-dimension `raw_drift` decomposition, explicit dominance check vs. `embedding` (H4) |
| **G** | Phases 3–4 | S3 (`scenario_3_subtle`) recall with fleet cohort drift enabled; geo-velocity dimension contribution + S1 recall impact |
| **H** | Phases 5–6 | Benign-vs-TP `signal_family_agreement_count` distributions (hard gate before any Stage-B proposal); staged-sequence S3 recall impact |

Each Series gets its own `docs/scoring-config-governance-series-{e,f,g,h}.md`, following the exact template of `scoring-config-governance-series-d.md`: knobs changed, cross-series-comparability rules (do not compare P/R/FP across a Series boundary unless explicitly permitted, same discipline as A→B→C→D), and the "Not CALIBRATED" caveat preserved throughout. The standing rule is unchanged: no `enabled` flag flips to `true` in a way that changes production scoring without its Series's sweep + governance record.

Shadow-compute/`enabled: false` tests proving zero behavioral diff (one per phase, see each phase's acceptance checklist) are the safety net that lets all seven phases merge incrementally between Series checkpoints without each one independently requiring a full sweep before code review can proceed.

## Error handling / fail-safe posture

Consistent with `AS_BUILT.md` §7 (existing fail-closed-scoring / fail-open-coverage postures): every new "no shadow" / "no reference data" / "no baseline" case fails toward an explicit flag + `0` contribution, never silent reuse of stale or guessed data. Phase 0 and Phase 4 both have this pattern spelled out explicitly above (`point_baseline_shadow_fallback:*`, `geo_velocity:no_centroid`) because they are the two phases most likely to hit a "just ship a fallback" temptation; the rest inherit the same posture from the cross-cutting `enabled`-gate principle.

## Global non-goals

- No §5.5/S55 alert-lifecycle rewrite beyond the Phase 5 Stage B hook (versioned field only; no behavior change).
- No live DNS/OAuth/email/network telemetry — matches the original evaluation's explicitly-out-of-scope list (`alter-ego-drift-gap-evaluation.md`, "Explicitly not suggested" table).
- No fix to `DEBT-057` (replay ignores historical `scoring_config_version`) — flagged as a carried-forward known limitation Phase 5 makes slightly more visible (via `precision_gate_version`) but does not resolve.
- No automatic promotion of any new `enabled` flag from `false` to `true` without its Series's recorded sweep + governance doc — standing repo rule, unchanged by this initiative.

## Open risks

- **Confounding across Series.** If Phase 0's Series E sweep shows a large point-FP shift, Phases 1–6 may need re-sequencing (e.g., Phase 5's benign-agreement baseline would need to be measured post-Phase-0, not pre-). Series F/G/H should each re-confirm they're comparing against the most recent prior Series, not stale Series-D-era assumptions.
- **`drift_weights` growing to 8 dimensions** mechanically changes the weighted-sum semantics of `raw_drift` the moment more than one `enabled` flag flips true, even if each was individually swept — Series G/H should include at least one combined-dimensions sweep, not only single-dimension-at-a-time comparisons.
- **OT archetype realism.** Phase 1's `ot_polling` archetype is a synthetic approximation, not real OT/ICS telemetry — if real telemetry becomes available later, the archetype's parameters should be revisited against it rather than treated as ground truth indefinitely.
