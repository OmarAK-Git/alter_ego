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

Saved sweep: **46 drift alerts** at the operating point ([`calibration_final_metrics.json`](calibration_final_metrics.json)). S2 slow-roll recall is **1.0** (35/35) — drift path catches boil-the-frog under the current harness; S3 subtle does not fully.

---

## 2. Concrete residual risks (evidence-backed)

### 2.1 High false-positive rate @ thr=45

| Metric | Value | Source |
|---|---|---|
| FP | **3448** | [`calibration_final_metrics.json`](calibration_final_metrics.json) |
| Precision | **0.019** (~98% of positive decisions are benign) | same |
| Recall | 0.817 | same |
| Operating threshold | `anomaly_threshold: 45` (unchanged) | `config/scoring_config.yaml` v2.2 |

**Risk:** Analyst triage at thr=45 is impractical without downstream filtering. Drift contributes (`drift_alert` weight 100) but point-rarity features dominate FP volume — not solved by drift tuning alone.

**Evidence pointer:** [`phase2-s3-operating-point.md`](phase2-s3-operating-point.md) §Residual error modes #1.

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

**Hypothesis:** Attacks with pauses between steps reset accumulator faster than attack adds norm_drift — boil-the-frog caught for S2 (35 events) but not S3 (45 events, coordinated).

**Research:** Plot accumulator time series for S2 TP vs S3 FN entities; sensitivity analysis on `drift_half_life_days` in isolated scratch (governance required for YAML).

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

- **Not CALIBRATED** — global precision ~1.9%, 3448 FP, 15 S3 FN remain.
- **Not a threshold recommendation** — thr=55 is documented diagnosis only; thr=45 remains YAML operating point.
- **Not a weight-tuning mandate** — hypotheses require evidence before governance-approved changes.
- **Not a substitute for S6.3** — standing rule: no knob change without recorded sweep + governance.
