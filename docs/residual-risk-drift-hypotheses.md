# Residual risk + open drift hypotheses (S6.2)

**Status:** Phase 2A / portfolio handoff — **not CALIBRATED.**  
**Audience:** Operator personal drift-methodology research (`HUMAN-DRIFT-RESEARCH` gate) and S6 empirical sweeps.  
**Companion docs:** [`phase2-s3-operating-point.md`](phase2-s3-operating-point.md) · [`calibration_final_metrics.json`](calibration_final_metrics.json) · [`hardening-sweep-checklist.md`](hardening-sweep-checklist.md) · SPEC §6.4

Do **not** treat this document as permission to change weights or thresholds without a recorded sweep and governance record ([`scoring-config-governance-s3.md`](scoring-config-governance-s3.md), S6.3).

---

## 1. Current drift engine (as shipped)

Implementation: `batch/profile_builder/builder.py` (accumulator) + `worker/scorer.py` (runtime contribution).

| Stage | Mechanism | Config knobs |
|---|---|---|
| Recent vs baseline | 3-day recent histograms/centroid vs previous **N** promoted profiles (KL categorical + cosine embedding) | `recent_drift_window_days: 3`, `drift_comparison_history_count: 5`, `laplace_alpha: 1.0` |
| Blend | Weighted sum of per-dimension deltas | `drift_weights` (embedding **40.0**, process_name **20.0**, others **5.0**) |
| Cohort normalize | `norm_drift = raw_drift − cohort_median[role]`; roles with &lt;3 entities fall back to global median | `MIN_NORM_COHORT = 3` (code constant) |
| Accumulate | Exponential decay + additive normalized drift | `drift_half_life_days: 7` |
| Builder alert | `cumulative_drift ≥ drift_threshold` → drift `DecisionRecord` | `drift_threshold: 5.0` |
| Scorer contribution | `min(cap, (cumulative_drift / drift_threshold) × drift_alert_weight)` | `drift_alert` weight **100.0**, `contribution_scale_max: 50.0` |

Saved sweep artifacts:
- **Series A (archived):** [`calibration_series_a_metrics.json`](calibration_series_a_metrics.json)
- **Series B (archived for §5.5-arming-without-lifecycle):** [`calibration_series_b_metrics.json`](calibration_series_b_metrics.json) — S2 R=**0.0**; absorbing-block regime; **do not compare FP/P to Series A.**
- **Series C (archived, R-INTERLOCK + S5):** [`calibration_series_c_metrics.json`](calibration_series_c_metrics.json) — S2/S5 R=**0.0**; promotion_coverage_ever **1.0**; auto_resolved **1817**; D4 engagement **0**; **do not compare FP/P to A or B.**
- **Series D (current baseline, D4 time-axis fix):** [`calibration_series_d_metrics.json`](calibration_series_d_metrics.json) — S2 R=**0.714**; S5 R=**0.371**; promotion_coverage_ever **1.0**; promotion_coverage_in_window (N=5) **0.413**; D4 engagement **12840**; auto_resolved **2269**; **do not compare FP/P/R to A, B, or C.**

**Frozen framing:** S2 headline recall alone does **not** reclaim boil-the-frog — **B4 is the license**, and only under Design 1 fixture conditions. See §2.6 / H11.

---

## 2. Concrete residual risks (evidence-backed)

### 2.1 High false-positive rate @ thr=45

| Metric | Value | Source |
|---|---|---|
| FP | **3448** | [`calibration_final_metrics.json`](calibration_final_metrics.json) |
| Precision | **0.019** (~98% of positive decisions are benign) | same |
| Recall | 0.817 | same |
| Operating threshold | `anomaly_threshold: 45` (unchanged) | `config/scoring_config.yaml` v2.2 |

**Risk (reframed 2026-07-18):** FP rate is no longer only an analyst-triage cost. Under armed §5.5 (Series B semantics), **every FP is a detection kill-switch for the drift path**: each anomaly opens a permanent `AlertWorkflowState` row, which freezes the entity's profile promotion, which freezes the scorer-visible `cumulative_drift` at its pre-block value — permanently, because no lifecycle ever closes a workflow (§2.7). Analyst triage impracticality at thr=45 still holds, but it is now the *lesser* consequence.

The old framing ("point-rarity features dominate FP volume — not solved by drift tuning alone") is **inverted** by §2.7: point-anomaly precision is a **prerequisite for drift-path function**, at the top of the dependency graph — the drift path cannot operate at all in a sustained-FP regime until either point-anomaly precision or the §5.5 blocking/lifecycle design is fixed. Drift tuning is downstream of both.

**Evidence pointer:** [`phase2-s3-operating-point.md`](phase2-s3-operating-point.md) §Residual error modes #1; §2.7 Q1–Q3 tables (Series B DB, 2026-07-18).

### 2.2 scenario_3_subtle false negatives

| Metric | Value | Source |
|---|---|---|
| Recall | **0.667** (30 TP / **15 FN**) | [`calibration_final_metrics.json`](calibration_final_metrics.json) → `scenarios.scenario_3_subtle` |
| Attack class | Coordinated multi-entity subtle insider drift | `inject_scenario_3_coordinated` in `batch/synthetic/generator.py` (label `scenario_3_subtle`) |

**Risk:** Subtle coordinated compromise remains the weakest attack class. S5.11 deferred prior-update gates and `min_clean_observation_count`; only scoring-time novelty suppression ships — partial coverage per SPEC §7.3 / §10.3.

**Evidence pointer:** [`phase2-s3-operating-point.md`](phase2-s3-operating-point.md) §Residual error modes #2; S5.11 Path B defer in SPEC §7.3.

### 2.3 Threshold tradeoff documented but not applied (thr=55)

PR-curve best-F1 at **thr=55** is diagnostic only — **not** written to YAML.

| thr | P | R | FP | FN | F1 |
|---|---|---|---|---|---|
| **45** (applied) | 0.019 | 0.817 | 3448 | 15 | 0.037 |
| **55** (diagnostic) | 0.041 | 0.585 | 1136 | **34** | 0.076 |

**Risk:** Raising threshold would cut FP ~3× but loses recall (including S3 hits). No governance-approved knob change was made (S3.6 attestation).

**Evidence pointer:** [`calibration_pr_curve.json`](calibration_pr_curve.json) (`threshold: 55`); [`scoring-config-governance-s3.md`](scoring-config-governance-s3.md) §thr=55 diagnostic — not applied.

### 2.4 Embedding normalizer default (aligned)

| Location | Value |
|---|---|
| `core/schemas/profiles.py` / `core/models.py` default | `DEFAULT_EMBEDDING_INPUT_NORMALIZER_VERSION = **"1.0-char-3gram-hash-128"**` |
| Runtime vectorizer (`worker/vectorizer.py`) | `NORMALIZER_VERSION = **"1.0-char-3gram-hash-128"**` |
| Production builder (`batch/profile_builder/builder.py`) | Sets runtime value explicitly |

**Status (2026-07-14):** Schema/ORM default aligned with runtime. S5.9 still fail-closes on any explicit mismatch (fixtures that pass `"1.0"` remain a valid halt regression case).

**Evidence pointer:** `tests/test_embedding_defaults.py`; `tests/worker/test_embedding_metadata_mismatch.py`.

### 2.5 Path B deferrals (detection gaps by design)

These are documented non-ships, not hidden debt:

| Packet | Deferred capability | Impact on residuals |
|---|---|---|
| **S5.11** | Independent cohort-prior artifacts; prior-update rejection; `min_clean_observation_count` reader | Scenario 3 coordinated-compromise gates incomplete — novelty suppression only |
| **S2.7** | Profile `lifecycle_state` (dormant / reactivated / onboarding / role_transition) | Legitimate behavioral shifts may resemble drift; no lifecycle-aware baselines |
| **S4.6** | Calendar dual-score; telemetry-gap two-tier (`gap_windows.*`, `max_calendar_adjustment`) | Scheduled-change context and gap correlation cannot explain or suppress benign FP |
| **S2.6** | `total_volume_delta` feature (weight reserved; scorer always 0) | Volume-based subtle drift not scored |
| **S4.3** | Suppressed-decision aging escalation + jitter | Low-confidence benign events accumulate in suppressed view without auto-escalation |

**Evidence pointer:** SPEC §5.4, §6.5, §6.6, §7.3, §13.1 defer banners; `memory-bank/progress.md` knob inventory.

### 2.6 S2 boil-the-frog — scoped claim + residuals (updated 2026-07-18)

**Framing (frozen):** S2 R=1.0 alone does **not** reclaim boil-the-frog — **B4 is the license**, and only under Design 1 fixture conditions.

**Series A retraction:** production-only builder + powershell inject R=1.0 was artifactual (inherited drift + embedding).

**§5.5 finding (queried on Design 1 fixture before the fix):**  
Cause was **#2 — build-blocking did not arm on these alerts**. Builder correctly keys on `AlertWorkflowState` ∈ `{new, acknowledged, investigating}`, but `record_decision` wrote `is_anomaly=True` **without** opening a workflow row (0 workflow rows vs 36 anomaly decisions; 0 shadow profiles; M rose to ≈0.074 after catch). Drift `PROFILE_BUILD` DecisionRecords likewise never opened workflow state. Not “absorption predates alert.”

**Fix shipped:** `worker.recorder.open_active_alert_if_needed` on anomaly; builder drift DecisionRecords call the same. Acceptance: Design 1 **B3b** (containment / `M<α`) now **passes**.

**Design 1 fixture license (narrow):**  
> The drift path fires a pre-absorption, drift-necessary alert on an honest slow roll under Design 1 fixture conditions (7×5, clean baseline, seed 42).

A1/A2/B1/B2/B3a/B3b/B4 all green on that fixture. This does **not** generalize to the full four-scenario sweep.

**Series B full sweep** ([`calibration_series_b_metrics.json`](calibration_series_b_metrics.json), post-§5.5 arming, pre-lifecycle): S2 **R=0.0** (35 FN), `early_below_threshold_fraction=1.0`, `caught_before_absorption_proxy=false`, 2324 active workflows, **0** auto_resolved, promotion collapsed. Attribution fields are present. **Cross-series FP vs Series A remains invalid.**

**Series C full sweep** ([`calibration_series_c_metrics.json`](calibration_series_c_metrics.json), R-INTERLOCK + `scenario_5_patient_cycle`, 2026-07-19): S2/S5 **R=0.0**, S1 **R=1.0**, `auto_resolved_count=1817`, `promotion_coverage_ever=1.0`, D4 engagement **0**. Absorbing-block topology broken; slow-roll event catch still not earned. **B→C FP/P/R comparisons INVALID.**

**Series D full sweep** ([`calibration_series_d_metrics.json`](calibration_series_d_metrics.json), D4 time-axis fix, 2026-07-19): S2 **R=0.714** (25/35), S5 **R=0.371**, S1 **R=1.0**, `auto_resolved_count=2269`, `promotion_coverage_ever=1.0`, `promotion_coverage_in_window` (N=5) **0.413**, D4 engagement **12840** (vs Series C **0** — only permitted C→D claim). S2 stays blocked at sweep end (137 active `new` alerts); shadow drift visible in scorer. **C→D FP/P/R comparisons INVALID.**

**Residual §2.7:** Series B confirmed the deadlock; Series C re-measured under the approved interlock; Series D re-measures after D4 as-of fix (below).

---

### 2.7 §5.5 arming × FP storm = drift starvation deadlock (Series B confirmed; Series C topology update)

**Status (Series B):** Mechanism **confirmed by direct queries** against the Series B sweep DB (`alter_ego_calibrate_s31.db`, rebuilt 2026-07-18). Under pre-lifecycle §5.5 this was **ARCHITECTURAL, not parametric** — absorbing block (Q1–Q3 below preserved as Series B evidence).

**Status (Series C, 2026-07-19):** Design APPROVED and shipped (`.workflow/2026-07-18-s55-alert-lifecycle/`). Series C sweep ([`calibration_series_c_metrics.json`](calibration_series_c_metrics.json), seed 42, v2.2 @ thr=45, S1–S5 + tooling):

| Quantity | Series B | Series C |
|---|---|---|
| auto_resolved | 0 | **1817** |
| promotion_coverage_ever (end) | collapsed (~5/55 promoting) | **1.0 (55/55)** |
| active workflow rows | 2324 (all `new`) | 1523 |
| S2 event recall | 0.0 | 0.0 |
| S5 event recall | n/a | 0.0 |
| D4 engagement | n/a | **0** |
| `caught_before_absorption_proxy` (S2/S5) | false | false |

**Reading:** R-INTERLOCK removes the Series B *absorbing-block* failure mode (lifecycle closes `new` rows under QUIET∧ATTEST; D4 keeps shadow drift visible under block; promotion resumes). It does **not** earn full-sweep S2/S5 event recall under the tooling+FP mix — scores stay below thr=45 (`early_below_threshold_fraction=1.0`). New residual is **detection under recovered promotion**, not fleet promotion collapse. Design 1 B4 remains the only scoped boil-the-frog license. **Do not cite B→C FP/P as improvement.**

**Series C post-mortem (2026-07-19):** diagnostics in `scratch/series_c_s2_diagnosis.json` + `.workflow/2026-07-19-series-c/results/series-c-d4-asof-bug-note.md`. For S2, shadow `cumulative_drift` rose to **24.3** while scorer-visible promoted stayed **0.0**. Load-bearing defect: `ProfileStore.get_latest_shadow_profile(as_of=…)` filtered **`created_at` (wall)** against **event sim time** — D4 silently no-ops. Fixed in Series D (`.workflow/2026-07-19-d4-time-axis/`).

**Status (Series D, 2026-07-19):** D4 time-axis fix shipped; Series D sweep ([`calibration_series_d_metrics.json`](calibration_series_d_metrics.json), seed 42, v2.2 @ thr=45):

Only the **D4 engagement count** is a permitted C→D comparison. The Series C column below is **archival context, not a comparability baseline** — every non-engagement row is a **Series-D diagnostic**, and any C→D P/R/FP/recall delta read off it is **INVALID**.

| Quantity | Series C (archival, not a baseline) | Series D |
|---|---|---|
| D4 engagement (`drift_source_profile_version`) — *only permitted C→D claim* | **0** | **12840** |
| S2 event recall *(D-only diagnostic)* | 0.0 | **0.714** (25/35) |
| S5 event recall *(D-only diagnostic)* | 0.0 | **0.371** |
| P / FP *(D-only diagnostic)* | 0.0003 / 3320 | **0.011 / 5432** |
| promotion_coverage_ever | 1.0 | 1.0 |
| promotion_coverage_in_window (N=5) | n/a | **0.413** |
| fallback_flag_count | n/a | **1084** |
| S2 stays blocked (active `new` at end) | n/a | **137** |

**Reading:** D4 fix works — engagement 0→12840 is the **only permitted C→D comparison**. S2 shadow drift now feeds scorer (`drift_alert_raw` up to 16.86); entity re-alerted and stayed blocked as shadow cumulative_drift rose (peak 24.33). Within Series D framing S2 recall is **0.714**, but **C→D P/R deltas are INVALID** (the Series C column is archival context only). Precision is low (P≈0.011, FP=5432) — topology changed, not a calibration win. Fallback storm (1084 global `drift_shadow_fallback:no_shadow`) exceeds SD2 expectation. Dual coverage exposes staleness (`in_window` 0.413) that `ever` hides.

Governance: [`scoring-config-governance-series-d.md`](scoring-config-governance-series-d.md) (current); [`scoring-config-governance-series-c.md`](scoring-config-governance-series-c.md) (archived). Design: [`superpowers/specs/2026-07-19-d4-time-axis-design.md`](superpowers/specs/2026-07-19-d4-time-axis-design.md) + [`superpowers/specs/2026-07-18-s55-blocking-scope-and-alert-lifecycle-design.md`](superpowers/specs/2026-07-18-s55-blocking-scope-and-alert-lifecycle-design.md) (**APPROVED**).

**Follow-on (not executed):** Attestation YAML hygiene — promote `core/attestation.py` defaults to YAML under separate S6.3; acceptance = zero behavioral diff.

#### Series B confirmed causal chain (each link query-checked; historical)

1. The honest S2 ladder is sub-threshold by design, so S2 event detection depends on the `drift_alert` contribution: max S2 attack-event score **16.29** @ thr=45; `drift_alert` contribution **0.0 on all 35** attack-event decisions.
2. The point-anomaly layer opens `AlertWorkflowState` rows on every anomaly (correct §5.5 arming): **269 rows opened from the first scored day** (Jan 2 events); **2324** total by sweep end (2236 benign FP + 87 builder drift + 1 S1 attack event).
3. The builder's blocking predicate (`batch/profile_builder/builder.py`, `blocked_entities`) demotes any entity with an active own workflow row to **shadow-only builds**: promoted builds collapsed 55/55 (Jan 2–3) → **10/55 (Jan 4, third build)** → 5/55 by sweep end, and never recovered.
4. Nothing closes workflows (S4.3 deferral, §2.5): all **2324** rows end the sweep in state `new` — blocked is an **absorbing state**. 0 supervisor escalations fired (S5.6 `max_profile_build_block_days=30` exceeds the 19-day sweep, and escalation observes; it does not unblock).
5. The scorer reads only promoted profiles (`worker/profile_store.py` `get_active_profile`: `is_shadow=False`): scorer-visible `cumulative_drift` for the S2 entity is **0.0 at every build step of the sweep** (frozen at its Jan-3 promotion) → `drift_alert` contributes 0 to every S2 event → S2 R=**0.0** (35 FN).

**Circularity (Series B):** slow-roll *event* detection requires scorer-visible drift → scorer-visible drift requires profile promotion → promotion requires no active own alerts → sustained FP + no lifecycle guarantees active alerts forever.

#### Mechanism refinement (evidence-forced; supersedes the "accumulator flatline" phrasing)

Builds do not stop — **promotions** stop. Shadow builds continue, and the builder-side accumulator not only updates but **fires**: the S2 entity crossed `drift_threshold=5.0` on the **first attack day** (Jan-10 build, accumulator 7.66) and emitted builder drift DecisionRecords daily thereafter (8 total, scores 7.66→81.72). The drift signal was computed, alarmed — and then **quarantined**: shadow-lineage state never reaches the runtime score path (promotion frozen), and `PROFILE_BUILD` decisions never count toward event-level recall. Each quarantined drift alarm also opens another workflow row, deepening the entity's own block. The deadlock starves drift *visibility*, not drift *computation*; the detection kill at the headline-metric level is total either way.

#### Q1 — build starvation (S2 entity `user_engineer_11`)

| Quantity | Value |
|---|---|
| Sweep start / first own workflow row | Jan 1 / **Jan 2 07:17** (own benign FP, score 50.5) |
| Last promoted profile | **Jan 3** (2 promoted of 17 builds; 15 shadow) |
| Attack window | Jan 10 07:00 – Jan 16 10:40 |
| Promoted builds during or after the attack window | **0** — promotion never resumed |
| Fleet promoted-build collapse | 55/55 (Jan 2–3) → 10/55 (Jan 4) → 5/55 (sweep end) |

#### Q2 — accumulator vs scorer visibility (S2 entity)

| Series | Behavior |
|---|---|
| Shadow-lineage `cumulative_drift` | 0.02 (Jan 7) → 0.52 (Jan 8) → 2.32 (Jan 9, pre-attack) → **7.66 (Jan 10, first attack day — crosses `drift_threshold=5.0`)** → 81.72 (Jan 16) |
| Scorer-visible (promoted) `cumulative_drift` | **0.0 at all 17 build steps** — frozen at the Jan-3 promotion |
| `drift_alert` contribution on the 35 S2 event decisions | **0.0 on all**; max event score 16.29 |
| Builder drift DecisionRecords for the S2 entity | **8** (Jan 10–16, scores 7.66→81.72), `event_id="PROFILE_BUILD"` — invisible to event-level recall |

The `attack_raised_cumulative_drift_max: 81.72` field in [`calibration_series_b_metrics.json`](calibration_series_b_metrics.json) is the shadow-lineage maximum — it coexists with a 0.0 scorer-visible series; the two must not be conflated.

#### Q3 — blocking scope attribution

| Check | Result |
|---|---|
| Predicate scope (code: `builder.py` `blocked_entities`) | **Per-entity, own alerts only** — no cohort or global blocking exists |
| Empirical cross-check | 0 shadow builds without a prior own workflow row; 0 entities with workflow rows that kept promoting |
| First-block cause across all 50 blocked entities | **47 own benign FP · 3 own drift alert · 0 cross-entity/global** |
| S2 entity's own rows | 67 = **59 own benign FP + 8 own drift alerts** (0 attack-event rows) |
| Fleet frozen by sweep end | **50/55 entities (90.9%)**; only 5 service accounts never blocked; median 47 rows per blocked entity |

**Scope finding:** every block is caused by the entity's **own** alerts — overwhelmingly its own benign FPs. Per the remediation decision table, **the missing alert lifecycle is the primary defect**. The predicate's cross-entity *scope* is not implicated (it is already per-entity); the scope-adjacent defect is the predicate's **insensitivity** — any single active alert, of any severity, confidence, or age (here: a day-2 FP scoring 50.5, barely over thr=45) freezes the baseline forever.

#### Why Series B was architectural, not parametric

Threshold tuning changes the deadlock's **timescale, not its topology**. §2.3's thr=55 diagnostic (Series A, diagnostic only): FP 3448→1136 at the cost of **19 extra FN** (15→34, including S3 hits). Under block-forever semantics, *any* sustained FP rate ε>0 eventually freezes every entity's baseline with probability → 1; at Series B rates 45/55 entities froze after **one** scored day, and a 3× FP reduction only stretches the storm across days. No `anomaly_threshold` value simultaneously preserves recall and keeps the fleet promotable while workflows never close.

The two real design surfaces were addressed by the R-INTERLOCK design (shipped; see Series C status above):

1. **Workflow lifecycle** — QUIET∧ATTEST auto-resolution (`auto_resolved`); analyst `clear_with_reason` retained.
2. **Shadow-signal (D4)** — `drift_alert` reads shadow accumulator under block; baselines stay promoted.

**Frozen claim language (successor):** B4 is the license; Series B, C, *or* D S2/S5 R alone does not reclaim boil-the-frog. Full-sweep B4 generalization is **not earned** after Series D either (S2 R=0.714, not 1.0).

**Evidence:** `docs/calibration_series_b_metrics.json` §`s55_finding`; Series B DB queries (Q1–Q3, 2026-07-18); `docs/calibration_series_c_metrics.json` + `docs/calibration_series_d_metrics.json` + governance records; Design 1 fixture remains green — but see the fixture-limitation note in the Design 1 spec (no FP storm by construction).
---

## 3. Open drift hypotheses (for human research)

These are **open questions**, not solved or recommended changes. Validate with sweeps (`docs/hardening-sweep-checklist.md`, seed 42) before any knob promotion.

### H1 — Recent-window vs profile-history comparison

**Observation:** Drift compares a **3-day recent slice** against the mean KL/cosine to the last **5 promoted profiles**, not against the 30-day training histogram stored in the current profile.

**Hypothesis:** Subtle S3 attacks that shift slowly enough to update promoted profiles each build cycle may keep per-step KL below alert levels while cumulative intent is malicious. Alternative baselines (recent vs fixed anchor profile, vs 30d hist) may separate S3 FN from benign drift.

**Research:** Per-entity FN postmortem from `alter_ego_calibrate_s31.db`; compare `normalized_drift` and `cumulative_drift` at miss timesteps.

### H2 — Cohort median subtraction masks coordinated drift

**Observation:** `norm_drift = raw_drift − median_peer_drift[role]`. If multiple entities in a role drift together (Scenario 3), peer median rises and **subtracts** coordinated signal.

**Hypothesis:** S3 FN correlate with roles where ≥3 entities move together — cohort normalization intended to reduce tooling-rollout FP may cancel coordinated attack drift.

**Research:** Role-level scatter of `raw_drift` vs `norm_drift` during S3 inject window; cross-check with novelty gate (`max_changed_fraction`) which operates at score time, not build time.

### H3 — MIN_NORM_COHORT = 3 and privileged solo accounts

**Observation:** Roles with &lt;3 entities use **global** median instead of role median (Fix #4 in builder).

**Hypothesis:** Solo admin / service accounts may have distorted normalization — either too sensitive (global median unrepresentative) or too dull (if global median tracks their drift). Distinct from S3 but affects drift_alert FP/FN balance on high-privilege entities.

**Research:** List roles by entity count in sweep DB; stratify drift_alert decisions and FP by role cardinality.

### H4 — Embedding weight dominance vs subtle categorical drift

**Observation:** `drift_weights.embedding = 40.0` vs `5.0` for geo/login/endpoint; S3 may be primarily categorical/process drift with small embedding centroid movement (char 3-gram hash).

**Hypothesis:** S3 FN events score via rarity features but fail to accumulate `cumulative_drift` because embedding cosine is flat while categorical KL is diluted in the weighted sum.

**Research:** Decompose per-dimension `deltas` at profile builds for S3 attack entities; ablation study in scratch (no YAML change until sweep).

### H5 — Accumulator half-life vs attack tempo

**Observation:** 7-day half-life decay on `cumulative_drift`; S3 inject schedule may be slower or bursty relative to decay.

**Hypothesis:** Attacks with pauses between steps reset accumulator faster than attack adds norm_drift — may explain S3 FN (45 events, coordinated) under an honest harness (see H11; Series C S2/S5 event R=0.0 — do **not** treat any headline S2 R as a successful boil-the-frog catch; B4 remains the scoped license).

**Research:** Plot accumulator time series for S3 FN entities (and S2 only after partition/shape invariants land); sensitivity analysis on `drift_half_life_days` in isolated scratch (governance required for YAML).

### H6 — Dual semantics of `drift_threshold`

**Observation:** Same knob gates (a) builder drift `DecisionRecord` emission and (b) scorer `drift_alert` contribution scaling (`drift_accum / drift_threshold × 100`).

**Hypothesis:** Threshold calibrated for one semantics may be suboptimal for the other — 46 builder drift alerts vs thousands of point-anomaly FP suggests builder alerts are rare; scorer may under-contribute drift for sub-threshold accumulators that still matter in aggregate.

**Research:** Distribution of `cumulative_drift` at score time for TP vs FP vs S3 FN; correlate with `feature_contributions` for `drift_alert`.

### H7 — Missing prior-update gates (S5.11 defer)

**Observation:** SPEC §7.3 design calls for cohort prior-update rejection when `max_changed_fraction` of entities cross threshold during rebuild. v1 only has **scoring-time** novelty suppression.

**Hypothesis:** S3 FN include cases where profile training absorbed coordinated shift because cohort priors were not rejected at rebuild — attack behavior normalized into baselines before score-time gates fire.

**Research:** Inspect profile histogram shifts for S3 entities across build cycles; compare with `cohort_data` embedded in artifacts.

### H8 — Lifecycle-blind baselines (S2.7 defer)

**Observation:** No `lifecycle_state` on profiles; reactivation and role transition look like drift.

**Hypothesis:** A portion of FP @ thr=45 are legitimate lifecycle transitions misclassified as rarity + drift; conversely, S3 attackers mimicking “slow onboarding” may evade drift if treated as benign warm-up.

**Research:** Manual labeling of top FP contributors; design lifecycle-aware baseline experiment (spec-only until implemented).

### H9 — Volume and calendar gaps (S2.6 / S4.6 defer)

**Observation:** `total_volume_delta` stubbed to 0; no calendar adjustment or gap correlation.

**Hypothesis:** S3 subtle exfil or coordination may manifest as volume or timing patterns invisible to current drift dimensions.

**Research:** Feature postmortem on S3 FN events — would volume or gap features have fired if implemented?

### H10 — Laplace α and low-count categories

**Observation:** `laplace_alpha: 1.0` smooths KL for rare categories.

**Hypothesis:** Subtle one-off process or endpoint additions are damped — attacker stays inside smoothed KL envelope until cumulative steps matter.

**Research:** KL sensitivity to α on S3 vs benign rollout events (tooling rollout partition in sweep).

### H11 — S2 boil-the-frog claim discipline

**Observation:** Series A R=1.0 was harness-artifactual. After ladder + builder-visible S2/S3 + §5.5 alert-arming: Design 1 fixture A1–B4 green (scoped B4 license); Series B full mix S2 R=0.0 with attribution (`calibration_series_b_metrics.json`). Series C under R-INTERLOCK + S5: promotion recovered (`promotion_coverage_ever=1.0`, `auto_resolved=1817`) but S2/S5 event R still **0.0** (D4 engagement **0**). Series D after D4 as-of fix: S2 R=**0.714**, D4 engagement **12840**, but S2 stays blocked (137 active `new`); P≈0.011 / FP=5432.

**Hypothesis:** Fixture isolation (no tooling rollout) is required for the §6.4 demonstration; production-like FP + §5.5 still limits full-sweep slow-roll catch even after D4 unblocks shadow drift. Full-sweep generalization of the B4 license is **not** earned. **C→D P/R comparisons are INVALID** — cite Series D numbers only.

**Research:** FP reduction (S6.3) without disabling §5.5; keep B3a/B3b/B4 always-on; investigate fallback storm (1084 flags) and in-window staleness (0.413); do not round fixture B4 or Series D S2 partial recall up to a general “drift catches boil-the-frog” claim.

### H12 — Execution cadence as a drift dimension, not just a point feature

**Observation:** `worker/scorer.py` `compute_periodicity` already computes inter-event interval CoV → `service_account_execution_frequency_deviation` (weight 5.0), but only when `resolved_event.entity_type == "service_account"`, and only as a **point** contribution. `drift_weights` has no cadence dimension — only `login_hour`, `geolocation`, `endpoint_set`, `process_name`, `embedding`.

**Hypothesis:** Mechanical/regular execution-timing shifts (beaconing-style regularity, or 24/7 execution creep) may accumulate gradually across builds before any single point score crosses `anomaly_threshold`, and are invisible to `cumulative_drift` today. Extending cadence CoV into a 6th `drift_weights` dimension — and computing it for human entities too, above a minimum event-count floor — would diversify the drift spanning set beyond `embedding` (see H4 dominance concern).

**Research:** Per-entity cadence CoV series at build time for S2/S3 attack windows vs benign; minimum event-count floor for stable human CoV (sparse human process streams are noisy); sensitivity to weight choice so it doesn't just repeat H4's dominance problem.

**Source:** External review `alter-ego-drift-gap-evaluation.md` DRIFT-R3, adapted from a DNS-beacon CoV/ActiveHoursRatio methodology — method only, no network telemetry implied.

**Status (2026-08-02):** Implemented shadow-computed (`drift_weights.cadence`, `enabled: false`); `ot_polling` synthetic archetype added. Series F governance complete (`a916d13`, `docs/scoring-config-governance-series-f.md`) — no `enabled` flip authorized. **Series I abort (2026-08-02):** dimension cohort-constant as implemented — `cadence_cov` saturates per role (SA≈1, humans=0); cohort_median norm cancels contribution for any weight; Series I cadence weight sweep lanes aborted (see DEBT-078, DEBT-012). Requires **two-part code fix** (not implemented) before re-sweep: (1) **per-entity delta** — CoV(recent window) vs CoV(baseline profile), not absolute regularity computed once outside the `prev_profiles` loop; (2) **timescale-appropriate divisor** — `max(0, 1−cv/0.3)` tuned for `scorer.compute_periodicity`'s rolling 60-minute lookback, then applied unchanged to 60–1440-minute build windows in `compute_build_window_cadence_cov`; re-derive or parameterize the DEBT-012 `cv/0.3` floor for build-window timescales.

### H13 — Geo-velocity between successive auth successes

**Observation:** `core/schemas/events.py` `geolocation` is a free-text **label** (`entity.geography` in the synthetic generator, e.g. `"RU-Moscow"`), not lat/long. `geolocation_rarity` (weight 2.0 point / 5.0 drift) scores rarity of a single label; it does not compare an entity's **successive** locations or compute implied travel speed.

**Hypothesis:** A single location can be individually plausible (not rare enough to score) while being incompatible with the same entity's immediately preceding location — an impossible-travel pattern distinct from static rarity, and one that may catch session-theft-style misuse without moving process or embedding features at all.

**Research:** Blocked on a static label→centroid (lat/long) lookup table, which does not exist today — this is new reference data, not new telemetry. Needs a minimum paired-success count per entity for a stable per-entity baseline, and a VPN/relay allowlist design to bound the false-positive class before any scoring change.

**Source:** DRIFT-R6, adapted from an impossible-travel detection pattern (ADS-07).

**Status (2026-08-02):** Implemented shadow-computed (`drift_weights.geo_velocity`, `core/geo_centroids.py`, `enabled: false`). Series G governance complete (`b63884c`, `docs/scoring-config-governance-series-g.md`) — no `enabled` flip authorized.

### H14 — Cross-signal-family agreement as a precision gate

**Observation:** §2.1 documents FP=3448 / precision=0.019 @ thr=45, and that under §5.5 arming every FP opens a workflow that blocks that entity's own profile promotion, freezing `cumulative_drift` — point-anomaly precision is already a documented prerequisite for the drift path mattering at all, not a separate concern from it.

**Hypothesis:** Gating containment/escalation priority on agreement across independent signal families (rarity vs. drift vs., once implemented, cadence/volume/geo-velocity) rather than a single fused score may cut FP without costing recall on sharp single-signal attacks — a different lever from raising `anomaly_threshold`, which §2.3 already shows costs 19 extra FN for a 3× FP cut.

**Research:** This changes alert **triage** semantics, not `scoring_config.yaml` weights, and interacts with the intentional "drift alone can trip the alarm at 2.25" asymmetry documented in that file's header comment — needs its own design spec (S6.3-equivalent) before any change. PR-curve replay against the Series D baseline, scored per signal-family combination, is the first research step.

**Source:** DRIFT-R5, adapted from a multi-plane convergence concept (ADS-06) — method only, no ATT&CK technique graph implied or proposed.

**Status (2026-08-02):** Stage A implemented (`signal_family_agreement_count`, `precision_gate.enabled: false`). Stage B explicitly not built. Series H governance complete (`1cc2e3e`, `docs/scoring-config-governance-series-h.md`) — benign FP agreement mean=0.841 vs TP=1.0.

### H15 — Staged multi-feature drift ordering

**Observation:** `cumulative_drift` and the point-score aggregate are both order-blind — neither records which drift dimensions crossed soft thresholds, or in what sequence, across builds.

**Hypothesis:** A slow insider progression where individually-weak shifts land in different features in a consistent order (e.g. endpoint novelty → process novelty → embedding drift → volume, once armed) may stay sub-threshold at every single build while the ordered pattern itself is the signal. Related to H5 (half-life vs. attack tempo) but about sequence, not decay rate.

**Research:** The most speculative and calibration-heavy item in this batch — sequence templates risk high FN if over-specific, high FP if over-broad (source doc's own caveat). Treat as backlog research only; do not prioritize ahead of H12–H14.

**Source:** DRIFT-R4, adapted from an export→stage→upload chain concept (ADS-04) — platform-specific connector plumbing explicitly out of scope; only the staged-pattern idea transfers.

**Status (2026-08-02):** Implemented shadow-computed (`staged_drift.enabled: false`, crossing log + template match). Series H governance complete (`1cc2e3e`, `docs/scoring-config-governance-series-h.md`) — no `enabled` flip authorized.

**Not new — already tracked:** the source doc's DRIFT-R1 (volume delta as a drift dimension) and DRIFT-R2 (fleet-level coordinated-drift rule) restate existing tracked work rather than surface new gaps: DRIFT-R1 ≡ `DEBT-051`/`DEBT-019` (this doc's H9); DRIFT-R2 ≡ `DEBT-068`/`DEBT-075` (H2, H7). DRIFT-R2's one genuinely useful addition: it proposes keying a new fleet-level `cohort_drift` rule off `cohort_gating_constants.max_changed_fraction`, which — per `AS_BUILT.md` §5.4 — is **already read** by the scorer (for novelty-gate suppression), unlike `min_clean_observation_count` which is unread. Reusing an already-wired knob for this is cheaper than the S5.11 prior-update-gate route and worth folding into that recovery item.

---

## 4. Suggested research workflow

1. **Read residuals first** — this doc + [`phase2-s3-operating-point.md`](phase2-s3-operating-point.md) + saved metrics JSON.
2. **Inspect implementation** — `batch/profile_builder/builder.py` (lines ~284–460), `worker/scorer.py` drift contribution block.
3. **Replay sweep DB** — regenerate with [`hardening-sweep-checklist.md`](hardening-sweep-checklist.md); do not trust narrative docs over JSON.
4. **Hypothesis → experiment → sweep** — any knob change requires full sweep, refreshed `docs/calibration_*.json`, and governance record (S6.3).
5. **Feed back** — update this doc or a research log; do not mark CALIBRATED without audit-grade FP/FN.

**Scratch starting points:** `scratch/analyze_step*.py`, `scratch/run_s31_sweep.py`, per-entity queries against `alter_ego_calibrate_s31.db`.

---

## 5. What this doc is not

- **Not CALIBRATED** — Series D is the current baseline ([`calibration_series_d_metrics.json`](calibration_series_d_metrics.json)); prior Series A/C precision figures are not Series D rates. **C→D FP/P/R comparisons are INVALID.**
- **Not a threshold recommendation** — thr=55 is documented diagnosis only; thr=45 remains YAML operating point.
- **Not a weight-tuning mandate** — hypotheses require evidence before governance-approved changes.
- **Not a substitute for S6.3** — standing rule: no knob change without recorded sweep + governance.
