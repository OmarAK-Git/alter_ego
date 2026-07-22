# ALTER_EGO — Architecture Specification (v2)

**Status:** Phase 2A / closed-with-residual — **not CALIBRATED** (high FP; S3 subtle misses)
**Scope:** Portfolio project, single-operator deployment, 8–10 week build
**Last updated:** July 2026
**Version:** 2.2 — interim operating point at Threshold = 45.0 (Phase 2 not closed)

**Metrics authority:** `docs/calibration_final_metrics.json`, `docs/phase2-s3-operating-point.md`, and `memory-bank/progress.md`. At thr=45: P≈0.019, R≈0.817, FP=3448; per-scenario S1/S2/S4 recall 1.0, S3 recall 0.667 (15 FN).

---

## 1. Problem Statement

Most enterprise threat detection is reactive. It depends on signatures, CTI feeds, and pre-written rules to recognize known-bad patterns, leaving organizations blind to novel attacks, insider threats, and credential misuse that doesn't match anything in the rulebook. Existing UEBA products attempt behavioral baselining but rely on hand-tuned statistical features and surface alerts without meaningful explanations, forcing SOC analysts to reverse-engineer why the system flagged something.

ALTER_EGO is a behavioral identity engine. It learns who each entity (user, service account) *is* based on their telemetry footprint over a configurable training window, enriched with metadata (endpoint, time, on-shift status, geolocation, role context). Each entity carries a deviation score against its learned profile. Sufficiently large or correlated deviation crosses an empirically-calibrated threshold and queues the entity for analyst review with an LLM-generated explanation grounded in the specific evidence that drove the score.

The project demonstrates production-grade LLM engineering applied to a real operational problem: behavioral identity reasoning that makes detection proactive rather than reactive, with explainability as a first-class output rather than an afterthought.

## 2. Scope and Non-Goals

### 2.1 In Scope (v1)

- **Two log types:** authentication events and process execution events
- **Two entity types:** human user accounts and service accounts
- ▲ **Synthetic event generator producing production-shaped events** with controlled anomaly injection and ground truth in a side table
- **Local Docker Compose deployment** (four-container `postgres` / `web` / `worker` / `batch`; Kubernetes kind/k3d deferred as production upgrade — see §4.4)
- **Simulated containment actions:** containment writes to a queue rather than disabling accounts
- **Analyst UI** with triage view, detail view, and ▲ suppressed-decisions view (§11.4)
- **Four named evaluation scenarios** (see §10) with documented precision/recall outcomes after Phase 2 calibration

### 2.2 Designed for Extension, Not Demonstrated

The architecture supports arbitrary log types and entity types through pluggable parsers and a generic identity schema with type-specific extensions. v1 demonstrates the system on the scoped subset above. Network logs, file events, email events, device entities, and application entities are documented as extension points but not implemented.

### 2.3 Out of Scope (v1)

- Real-world SIEM integration (the system *outputs to* a queue; integrations are documented, not built)
- Multi-tenant operation
- Production-grade IAM, secrets management, or external identity provider integration
- Network-layer detection
- Live ingest from production systems (batch and replay only)
- Mobile or remote analyst UI
- Kubernetes operators or custom resource definitions

## 3. Threat Model

### 3.1 Assets Defended

- Entity behavioral profiles (integrity, freshness)
- Scoring decisions and their audit trail
- LLM explanation outputs (semantic correctness, lineage)
- Scoring configuration (integrity, authenticated change)

### 3.2 In-Scope Adversaries

- **Compromised individual entity:** attacker with credentials of one user or service account, attempting to act undetected. *Primary threat.*
- **Slow-roll/boil-the-frog adversary:** attacker who shifts an entity's behavior gradually to train the profile to accept attack behavior as normal. *Addressed via cumulative drift detection (§6.4), active-alert profile-build blocking (§5.5), and `max_profile_build_block_days` supervisor escalation when block exceeds SLA (§5.5, shipped S5.6).*
- **Coordinated multi-entity compromise:** attacker controlling several accounts simultaneously, attempting to poison cohort priors. *Partially addressed in v1 via scoring-time novelty suppression (`max_changed_fraction`, §7.3); advanced prior-update rejection gates and `min_clean_observation_count` deferred to Phase 4 (S5.11 / Path B, §7.3). Residual risk documented as known limitation (§7.4).*
- **Prompt injection via behavioral data:** attacker who plants attacker-controlled strings (process command lines, file paths, URLs) intended to manipulate LLM explanation outputs. *Addressed via structured field binding (§8.2), constrained ExplanationRecord output schema (§8.3), prohibited-content output validation (§8.3), and slot-isolated low-trust fields (S4.1).*
- **Insider with config access:** detection_engineer-role user who attempts to disable detection by adjusting scoring_config. *Addressed via authenticated writes, Postgres INSERT-only audit/commit tables via runtime role `alter_ego_app` (§9.2, shipped S5.3 — profiles allow lifecycle-column UPDATE only), and replay scope limits (§9.3).*
- **Audit manipulator:** operator attempting to selectively recompute past decisions to hide false negatives or downgrade alerts. *Addressed via contiguous-window-only replay, original-record preservation (§9.3), and scheduled hash-chain integrity verification (`batch/audit_integrity.py`, shipped S5.4).*
- ▲ **Detection-invisibility attacker:** sustains suspicious behavior to keep an alert active, blocking profile rebuilds, until the staleness circuit breaker fires and the entity disappears from scoring. *Addressed via mandatory analyst escalation when staleness fires under active alert (§5.7, shipped S5.5).*
- ▲ **Confidence-floor evader:** crafts behavior that scores high on raw_score while triggering low confidence (sparse-feature exploitation, cohort_unsupported entities) to bypass the containment queue. *Partially addressed in v1 via the suppressed-decisions view (§11.4), which surfaces suppressed high-score decisions with audit rather than silently dropping them; mandatory aging escalation is deferred to Phase 4 (S4.3 / Path B, §11.4).*

### 3.3 Out-of-Scope Adversaries (v1)

- Network attackers between system components (deployment is local-only in v1; TLS and mutual auth documented as production upgrade)
- Supply-chain compromise of LLM providers or vector DB
- Physical access to the deployment machine
- Adversaries with code-execution privileges on the deployment host
- ▲ **Database superuser tampering with audit log.** v1 audit immutability is application-layer (Postgres INSERT-only role + hash chaining), not enforced against a host operator with database superuser access. Production upgrade path is external log shipping, WORM storage, or a managed audit service.

### 3.4 Field-Level Trust Boundaries

| Field source | Trust | Treatment in LLM context |
|---|---|---|
| Entity ID, role, account_type | high | structured field, bound by name |
| Profile statistics (counts, distributions) | high | structured field |
| scoring_config snapshot | high | structured field |
| Process command lines | low | escaped string, length-capped, slot-isolated |
| File paths, URLs | low | escaped string, length-capped, slot-isolated |
| Geolocation strings | medium | normalized to enum where possible |
| Free-text fields from logs | low | escaped, length-capped, isolated in template slot |

▲ **"Slot-isolated" defined.** Low-trust strings are placed in delimited template slots prefixed with a fixed-format label (e.g., `<command_line>...</command_line>`). The LLM is instructed not to interpret content inside such slots as instructions. Combined with the constrained ExplanationRecord output schema (§8.3), this structurally reduces prompt injection surface — the LLM cannot rewrite the JSON schema even if attacker content tells it to.

LLM explanation outputs are validated against a prohibited-content list (specific named threat actor groups, specific malware family names, claims of attribution beyond the evidence) before being persisted as the canonical explanation. Validation failure produces a deterministic template fallback explanation and logs the rejection.

## 4. Architecture Overview

ALTER_EGO is a typed, decomposed service architecture. It is **not** an autonomous multi-agent AI system. LLMs are used at specific bounded points (profile summarization, post-threshold explanation generation) and never appear in the per-event scoring path.

### 4.1 Execution Tiers

The system separates work into three execution tiers along latency and cost dimensions:

- **Cold path (batch, periodic):** Profile builds, peer cohort recomputation, scoring_config calibration. Runs on schedule or on-demand. May invoke LLMs for profile summarization.
- **Hot path (per-event, deterministic):** Score every incoming event against the current committed profile using a deterministic scoring function with versioned scoring_config. **No LLM in this path.**
- **Warm path (post-threshold, on-demand):** When a hot-path decision crosses the configured threshold, generate an LLM explanation grounded in the specific evidence that drove the score. Queue-depth limited; deterministic template fallback on overflow or LLM unavailability.

### 4.2 Logical Service Decomposition

▲ Service boundaries are enforced at the **module/package level in code**, with explicit interfaces. Services are NOT all deployed independently in v1 (see §4.4 for deployment topology).

| Service | Responsibility |
|---|---|
| `ingest` | Parse incoming auth + process logs into the canonical event schema, attach simulation_partition labels |
| `entity-resolver` | Map raw event fields to canonical entity IDs, emit resolution_confidence |
| `profile-builder` | Cold-path job that materializes versioned profiles from event history |
| `scorer` | Hot-path service that scores incoming events against the current committed profile |
| `decision-recorder` | Persist scoring decisions with idempotent decision IDs and full evidence lineage |
| `explainer` | Warm-path service that generates evidence-bound LLM explanations for threshold-crossing decisions |
| `containment-queue` | Receives high-confidence, threshold-crossing decisions for analyst review |
| `replay-runner` | Executes contiguous-window replays of historical decisions under new scoring_config versions |
| `analyst-ui` | Triage view + detail view + suppressed-decisions view for SOC analyst workflow |
| `eval-harness` | Runs the four evaluation scenarios, emits precision/recall artifacts |
| ▲ `synthetic-generator` | Phase 0 deliverable; produces production-shaped events with ground-truth labels in side table |

### 4.3 Storage

Hybrid storage with role separation:

- **Postgres (operational store):** entity registry, alert workflow state, decision records, scoring_config versions, audit logs, explanation lineage, containment queue, simulation partition metadata, ▲ ground-truth side table for eval events. Concurrent writes, transactional consistency.
- **DuckDB (analytical store):** profile computation. Per-build, the profile-builder service performs **deterministic batch materialization** from Postgres into a DuckDB instance, computes the profile, and writes the resulting versioned profile artifact back to Postgres. DuckDB is not a long-lived store; it is a per-build compute target.
- **pgvector (within Postgres):** embeddings of behavioral artifacts (command sequences, URL patterns, process-tree shapes) used for fuzzy similarity scoring against the entity's profile vectors.

▲ **Vector column dimensionality and embedding model migration.** pgvector vector columns are typed with fixed dimensionality at CREATE TABLE time (e.g., `embedding vector(768)`). A change in embedding model dimensionality therefore requires either (a) an explicit ALTER TABLE migration, or (b) versioned vector columns per embedding model generation (e.g., `cmd_embedding_v1 vector(768)`, `cmd_embedding_v2 vector(1536)`). v1 uses approach (a): embedding model changes are treated as breaking schema changes, documented in the [pgvector embedding migration playbook](pgvector-embedding-migration.md). The embedding_model_id, embedding_model_version, and embedding_dimensionality are recorded in every profile artifact (§5.6) so mismatch is detected before scoring resumes.

This split was selected over alternatives (Postgres-only; DuckDB-as-primary) because behavioral profiling query patterns are columnar and benefit from DuckDB's compute model, while operational state requires Postgres's concurrent-write semantics. Live two-store synchronization was explicitly rejected as over-engineering for v1; the deterministic batch materialization model (rebuild DuckDB slice from Postgres at each profile build) provides sufficient consistency.

### 4.4 Deployment

▲ **v1 deployment topology — compressed.** Logical service boundaries (§4.2) are enforced as Python packages with explicit interfaces. Deployment uses four containers:

| Container | Modules deployed |
|---|---|
| `web` | analyst-ui, ingest API, explainer API, containment queue API |
| `worker` | scorer, decision-recorder, entity-resolver |
| `batch` | profile-builder (with embedded DuckDB), eval-harness, replay-runner, synthetic-generator |
| `postgres` | Postgres + pgvector |

This compresses operational overhead while preserving every future split point. Independent service deployment is documented as a production upgrade and only justified when a specific scaling or isolation need emerges.

▲ **v1 shipped IaC (S5.2 / Path A).** The v1 Infrastructure-as-Code artifact is `docker-compose.yml`, which declares the four-container topology above (`postgres`, `web`, `worker`, `batch`). Reproducible bring-up: `docker compose up -d --build` (see `docs/deployment.md`).

- **Local-only:** no public ingress, no external auth, no TLS in v1 (documented as production upgrade)
- **Production upgrades (deferred):** Kubernetes (kind/k3d) manifests targeting the same four roles; standalone Terraform for cloud/multi-environment provisioning

## 5. Identity Model

### 5.1 What an Identity Is

An identity is a **versioned, immutable profile artifact** representing an entity's typical behavior over a training window. Each profile version is a snapshot — never mutated in place — and references the scoring_config version under which it was built.

### 5.2 Profile Composition

A profile contains, per entity:

- **Categorical attributes:** typical logon hours, geolocation distribution, on-shift schedule, endpoint set, role, account_type, peer cohort assignment
- **Sequence/semantic attributes:** command-sequence embeddings, URL access pattern embeddings, process-tree shape embeddings (stored in pgvector)
- **Feature-class confidence:** per-feature observation count and confidence value, used to gate that feature's contribution to scoring
- **Lifecycle state (deferred post-v1):** active, dormant, reactivated_dormant, onboarding, role_transition — design target in §5.4; v1 profile artifacts do not carry a `lifecycle_state` field
- **Build provenance:** training_window range, scoring_config_version, build_timestamp, source event count, simulation_partition exclusions
- ▲ **Embedding metadata:** embedding_model_id, embedding_model_version, embedding_dimensionality

### 5.3 Training Window

- Configurable `training_window_days` rolling window (default pending calibration)
- Rolling window, not landmark window — recent behavior is incorporated as the window advances
- Per-build materialization: each profile build re-reads the window from Postgres into DuckDB; no incremental update of profile state

### 5.4 Lifecycle States

▲ **v1 deferral (S2.7 / Path B).** The lifecycle state machine below is a design target, not shipped in v1. Profile artifacts have no `lifecycle_state` field; the scorer does not branch on dormant, reactivated, onboarding, or role_transition. **Alert workflow states** (`new`, `acknowledged`, `investigating`, etc. per §11.5) are separate and may ship in Phase 3 — they are not profile lifecycle. Partial v1 substitutes only: cohort fallback + `cohort_unsupported` (§6.3) for sparse/new entities; `stale_profile` flag + staleness circuit breaker (§5.7) for profile-age risk (halt ≠ dormant penalty scoring). Full lifecycle machine deferred to Phase 4 / portfolio hardening.

- **active:** entity has events within the training window above minimum observation thresholds
- **dormant:** entity has no events within the training window. Scored against last committed profile with stale-profile confidence penalty.
- **reactivated_dormant:** entity transitions from dormant back to active. **Scored normally with stale-profile confidence penalty applied through the existing confidence-floor gate. Not blocked from scoring; reactivation is high-risk and must be observed.** ▲ Analyst notification routes to the standard triage view with a `reactivated_dormant` flag, not a separate channel — preventing inconsistent analyst state where the notification and the scored decision live in different places.
- **onboarding:** new entity below minimum observation thresholds. Falls through cohort hierarchy (§6.3) until entity-local data is sufficient.
- **role_transition:** explicitly declared role change. Profile build for this entity uses an attenuated training window starting from the declared transition timestamp; pre-transition behavior is excluded.

### 5.5 Profile Build Schedule and Active-Alert Blocking

▲ **Active-alert profile-build blocking is a Phase 1 correctness invariant, not Phase 4 hardening.** Without it, slow-roll drift evaluation in Phase 2 calibration silently allows attack behavior to be learned into the entity baseline, producing thresholds that are invalid as soon as blocking is added. Therefore the implementation order requires this property to hold during calibration.

Profile builds run on schedule (cold path). **Builds for entities with active uncleared alerts are blocked or run in shadow mode only** — committing a new profile for an entity currently under suspicion would learn the suspected attack behavior into the new baseline, defeating drift detection. Shadow profiles are computed and stored but not promoted to the active profile until the alert is cleared **or auto-resolved** (below). Active (blocking) workflow states remain `{new, acknowledged, investigating}`. Terminal states `cleared` (analyst) and `auto_resolved` (machine) do not block.

▲ **R-INTERLOCK (shipped S55 lifecycle):** lifecycle closure and shadow-signal visibility are mandatory together. While an entity is build-blocked, the scorer's `drift_alert` contribution reads `cumulative_drift` from the entity's **latest shadow profile**; all other scoring features continue to read the **promoted** profile (full shadow scoring is rejected). When the consulted shadow version differs from `profile_version`, decisions record `drift_source_profile_version` for replay determinism. A blocking alert may leave the active set only via analyst `clear_with_reason` (§11.5) or machine **auto-resolution** gated on entity-level **QUIET ∧ ATTEST** (no time-only expiry): no new anomaly DecisionRecord within `quiet_window_days`, peak shadow `cumulative_drift` during the block below `drift_threshold`, and novel-mass gates vs last-promoted and anchor history (`alpha_prod` / `alpha_anchor` — declared code defaults; see `docs/scoring-config-governance-s55-lifecycle.md`). Auto-resolution transitions only `new` rows; analyst-touched `acknowledged` / `investigating` rows are exempt. Builder drift decisions for an already-blocked entity **refresh** the existing drift-class workflow row rather than stacking a new row per build.

▲ **Maximum profile-build-block duration (shipped S5.6; D5 enqueue S55).** A configurable `max_profile_build_block_days` (scoring_config, default=30) limits how long an entity can remain in build-blocked state. When exceeded without the alert being cleared, an auditable supervisor escalation (`profile_build_block_supervisor_escalation`) is emitted **and enqueued on the mandatory analyst review queue** (same surface as §5.7 staleness×active-alert escalations), **independent of the staleness circuit breaker (§5.7)**. Auto-resolution may still clear eligible `new` rows after escalation; the SLA forces human attention, it does not force closure.

### 5.6 Profile Schema Versioning

Profile artifacts carry a schema version. Schema-incompatible profiles cannot be scored against new code paths; the profile-builder must rebuild before scoring resumes. This is detected and flagged rather than silently failing.

▲ **Embedding model versioning is part of profile schema versioning.** Every profile records embedding_model_id, embedding_model_version, and embedding_dimensionality. Mismatch between the recorded values and the currently configured embedding model is treated as a profile incompatibility requiring rebuild before scoring resumes. If embedding_dimensionality has changed, the pgvector schema migration (§4.3) must complete before profile rebuild can proceed.

### 5.7 Profile Freshness Circuit Breaker

A scheduled profile build that fails (silent batch failure, source data unavailability, schema mismatch, ▲ embedding model mismatch) must not cause the system to score against an arbitrarily old profile. After a configured staleness threshold, the scorer halts for affected entities and emits a sensor-health incident.

▲ **Staleness + active-alert escalation (shipped S5.5).** When the staleness circuit breaker trips for an entity that **also has an active uncleared alert**, halt scoring AND automatically escalate to a mandatory analyst review queue with a configured time-bounded SLA. The analyst must either clear the alert (allowing fresh profile build) or explicitly extend the scoring halt with documented justification before the halt can continue. This closes the detection-invisibility loop where sustained suspicious behavior keeps an alert active, prevents profile refresh, trips the circuit breaker, and silently removes the entity from detection.

▲ **Embedding metadata mismatch (shipped S5.9).** Before feature scoring, the scorer compares each profile's `embedding_model_id`, `embedding_model_version`, `embedding_dimensionality`, and normalizer version against the shipping runtime contract. Mismatch emits `embedding_metadata_mismatch_halt` (score 0) rather than silent scoring against incompatible vectors. See [pgvector embedding migration playbook](pgvector-embedding-migration.md).

## 6. Scoring Model

### 6.1 Determinism

All hot-path scoring is deterministic given (event, profile_version, scoring_config_version). No LLM call. No randomness. Same inputs always produce the same `decision_id` and `raw_score`.

### 6.2 Decision Record Fields

Every scoring decision produces a record with at minimum:

- `decision_id` (idempotent — same inputs produce same ID)
- `event_id`, `entity_id`, `event_time`, `decision_time`
- `profile_version`, `scoring_config_version`, ▲ `embedding_model_version`
- `raw_score` (v1 schema/API field name: `score` — single operational anomaly score; no separate `context_adjusted_score` in v1; dual-score deferred with §6.6)
- `confidence` (separate from score; reflects evidence sufficiency)
- `feature_contributions[]` (per-feature contribution to the score, each with `contribution_id`, `raw_value`, `confidence_weight`)
- `cohort_used` (cohort tier in the fallback hierarchy that was consulted)
- `cohort_unsupported` boolean (true if scored entity-local-only)
- `simulation_partition` (label for evaluation isolation)
- `replay_run_id` (null if original; populated for replays)
- `flags`: `stale_profile`, `low_resolution_confidence`, `cohort_unsupported`, etc. ▲ `reactivated_dormant` deferred with §5.4 lifecycle states; ▲ `calendar_context_active` deferred with §6.6; ▲ `infrastructure_volatile` deferred with §12

▲ **Initial six-feature scoring contract for v1.** Phase 1 implements these six features. Each emits a contribution_id, raw value, and confidence weight:

1. **login_hour_rarity** (auth) — frequency of the observed logon hour against entity's typical-hour distribution
2. **geolocation_rarity** (auth) — observed geo against entity's typical geo distribution
3. **endpoint_set_rarity** (auth) — observed endpoint against entity's typical endpoint set
4. **process_name_rarity** (process) — observed process name against entity's typical process distribution
5. **command_line_embedding_similarity** (process) — cosine distance between embedding of observed command and entity's profile centroid
6. **service_account_execution_frequency_deviation** (process, service accounts only) — observed execution rate vs. entity's typical periodicity

Combined via calibrated weights in scoring_config: `raw_score = Σ (contribution_i × weight_i × confidence_i)`. Cohort shrinkage is applied per-feature before aggregation (§6.3). Cumulative drift (§6.4) is layered on after this baseline. ▲ Calendar adjustment (§6.6) is deferred post-v1 — v1 emits the single `score` above with no calendar layer.

### 6.3 Hierarchical Baselining

For entities with sparse observations on a given feature, scoring uses **confidence-adaptive shrinkage** toward a cohort prior:

- The weighting between entity-local statistics and cohort prior is **driven by feature-class confidence**, not a fixed ratio
- **Cohort priors are frozen per scoring window** — a single scoring decision uses a stable prior rather than chasing concurrent updates
- Cohort fallback chain: entity-local → primary cohort (e.g., role) → parent cohort (e.g., account_type) → **terminus: entity-local-only with `cohort_unsupported: true`, elevated confidence floor for containment gating, and UI warning surface**

▲ **Basic cohort shrinkage is a Phase 1 requirement, not Phase 4 hardening.** Scenario 4 (service account abuse) explicitly tests hierarchical baselining and confidence-adaptive shrinkage. Running Scenario 4 in Phase 2 calibration without basic shrinkage either tests a different scenario than specified or produces thresholds invalid for the post-shrinkage code path. Therefore basic cohort prior computation and confidence-adaptive shrinkage are required before Phase 2 calibration. Advanced cohort-poisoning gates (§7.3 prior-update rejection, independent versioned cohort artifacts) remain in Phase 4 (S5.11 / Path B).

### 6.4 Cumulative Drift Detection

Single-event scoring catches sharp deviations. Cumulative drift detection catches the boil-the-frog case where each individual step is below the flagging threshold but the aggregate trajectory is suspicious:

- **Profile version delta computation:** each new committed profile is compared against the previous N committed profiles for that entity, with delta magnitude scored
- ▲ **Delta metric, fully specified.** Per-feature KL-divergence for categorical distributions (logon_hour, geo, endpoint_set, process_name), with **Laplace smoothing** (additive pseudocount α, scoring_config parameter, default α=1.0, calibrated in Phase 2) to prevent infinite divergence on newly-observed categories. Cosine distance for embedding features (command sequences, URL patterns, process-tree shapes). Per-feature deltas combined via feature-class-weighted sum, with weights as scoring_config parameters subject to Phase 2 calibration.
- **Cohort-normalized:** drift is compared against peer-group drift to avoid false-positiving legitimate cohort-wide change (e.g., new tooling rollout)
- Drift events feed the same scoring/threshold path as point anomalies, with their own contribution weight in scoring_config

### 6.5 Telemetry Gap Handling — Two-Tier Policy

▲ **v1 deferral (S4.6 / Path B).** The two-tier telemetry-gap policy below is a design target, not shipped in v1. No gap detector, localized-vs-source correlation scorer, or sensor-health incident path exists in v1. The `gap_windows.*` keys in scoring_config are YAML placeholders with no production reader. v1 profile freshness relies on the staleness circuit breaker (§5.7) only. Full gap handling deferred to Phase 4 (§13).

Telemetry gaps (missing or delayed events from a source) are handled differently for automatic risk vs. analyst context:

- **`gap_correlation_window`** (short, default = configured analysis window for the entity type): gaps within this window automatically influence entity risk — but only for **localized or suspiciously correlated gaps**. Source-wide or collector-wide gaps emit sensor-health incidents and do not inflate per-entity risk.
- **`investigation_context_window`** (long, e.g., 14–30 days): used in the analyst detail view for timeline reconstruction. Does **not** automatically alter scoring.

### 6.6 Calendar Context — Dual Score, Triage Hidden

▲ **v1 deferral (S4.6 / Path B).** No scheduled-change calendar store, no `context_adjusted_score` computation, and no `max_calendar_adjustment` reader in v1. The v1 decision record and API expose a single operational `score` (schema field name; equivalent to the SPEC `raw_score` intent below). Triage and detail views show that score only — no calendar icons, dual-score display, or calendar entry linkage. Design invariant retained: calendar must never automatically suppress containment. Full calendar dual-score deferred to Phase 4 (§13).

Scheduled-change calendar entries (declared maintenance windows, deployments, etc.) are **analyst context only** when they appear in the triage view. They produce a `context_adjusted_score` *alongside* the `raw_score`, with a strict adjustment cap (defined in scoring_config) and an immutable audit field naming the calendar entry that drove the adjustment.

▲ **`context_adjusted_score` formula.** `context_adjusted_score = raw_score × (1 - calendar_adjustment_factor)`, where calendar_adjustment_factor is bounded by `max_calendar_adjustment` (scoring_config, calibration target). The formula is recorded in the decision record's `feature_contributions[]` as a synthetic contribution with `contribution_id = "calendar_adjustment"`. This makes the adjustment auditable and reproducible.

**Triage UI shows `raw_score` only.** A non-numeric `calendar_context_active` icon signals presence of context. The `context_adjusted_score`, its formula, and the calendar entry that drove it appear **only in the detail view**. This prevents the confirmation-bias / anchoring failure mode where a softened secondary number shifts analyst attention away from the unadjusted alert.

The calendar **never automatically suppresses containment**. A predictable suppression mechanism would be exploitable cover for timed attacks by any adversary with knowledge of the deployment schedule.

### 6.7 Evidence Binding

Every scoring decision carries the specific feature contributions that drove it. The explanation service (§8) cannot generate text that exceeds this evidence — explanations are constrained to the recorded feature contributions, and validation rejects outputs that introduce attribution beyond what the evidence supports.

### 6.8 Operating Parameters (Phase 2A — not audit-grade)

The parameters below are the current YAML operating point from the S3.1 re-sweep (`docs/calibration_final_metrics.json`). This is **not** an audit-grade or CALIBRATED claim — global precision ~1.9% and 3448 FP at thr=45 remain open residuals. See `docs/phase2-s3-operating-point.md` and `docs/phase2-audit-result.md` (historical narrative; metrics superseded by the JSON).

Current operating point:
- **Anomaly Threshold (`anomaly_threshold`):** 45.0 (P≈0.019, R≈0.817, FP=3448 @ saved sweep)
- **Confidence Floor (`confidence_floor`):** 0.6 (gated damping)
- **Observation-count confidence (`confidence_k`):** 10.0 — `n/(n+k)` in scorer (S2.4)
- **Containment Threshold (`containment_threshold`):** 85.0 — auto queue write when score ≥ threshold and confidence ≥ floor (S1.3)
- **Laplace Smoothing α (`laplace_alpha`):** 1.0 (smooths warm-up profiles)
- **Drift accumulator half-life (`drift_half_life_days`):** 7 — replaces legacy `decay_lambdas.drift` (removed S2.8; never read)
- **Cohort Gating (`min_cohort_size`):** min_size=10 fallback

Deferred / unwired (present in YAML but not production-calibrated): `min_clean_observation_count`, `total_volume_delta` weight, `max_calendar_adjustment`, `gap_windows.*`, `age_jitter_hours`. `max_profile_build_block_days` is wired in the profile builder (S5.6 supervisor escalation). See `memory-bank/progress.md` §Scoring config knob inventory.

## 7. Profile Build and Cohort Mechanics

### 7.1 Build Trigger

- Scheduled (configurable cadence per entity type)
- On-demand for a named entity (operator action, audited)
- Suppressed when the entity has active uncleared alerts (§5.5)
- ▲ Suppressed when embedding_model_id has changed and pgvector migration is incomplete

### 7.2 Build Process

1. Read the entity's events within `training_window_days` from Postgres
2. Apply simulation_partition exclusion (§10.2) — events labeled as injected for evaluation are excluded from training data
3. Materialize the slice into a DuckDB instance
4. Compute per-feature statistics, embeddings, observation counts, and feature-class confidence
5. ▲ Record embedding_model_id, embedding_model_version, embedding_dimensionality on the new profile artifact
6. Compute profile version delta against previous N profiles for cumulative drift signal (§6.4)
7. Write the new immutable profile artifact to Postgres with full provenance metadata
8. Promote to active profile (or hold as shadow if entity has active alert)

### 7.3 Cohort Maintenance

▲ **v1 deferral (S5.11 / Path B).** Advanced §7.3 cohort-prior **update** gates and independent versioned cohort artifacts are design targets, not shipped in v1. v1 ships: profile-embedded `cohort_data` (§6.3), active-alert profile-build blocking (entities under alert excluded from training), and **scoring-time novelty suppression** (`max_changed_fraction` + `cohort_gate_window_days` in `worker/scorer.py`). v1 does **not** ship: separate cohort recomputation schedule, prior-update rejection on cohort rebuild, `min_clean_observation_count` reader, or analyst-facing cohort-prior update rejection events. Full §7.3 prior-update gating deferred to Phase 4 (§13.1).

Cohorts are recomputed on a separate schedule from individual profile builds. Cohort updates are gated:

- **Minimum cohort size:** below the configured minimum, a cohort cannot be the primary cohort; fall to parent
- **Minimum clean-observation count:** new cohort prior cannot be accepted unless N entities in the cohort have observations not under active alert
- **Maximum changed-fraction gate:** if more than the configured fraction of cohort entities show simultaneously novel behavior, the cohort prior update is **rejected** and an investigation event is emitted (this is the coordinated-compromise signal)

▲ **"Simultaneously novel behavior" operationalized.** Defined as: entities whose `raw_score` crossed the anomaly threshold within `cohort_gate_window_days` (scoring_config parameter, default = analysis window for the entity type) at the time of cohort recomputation. This window is calibrated in Phase 2 against Scenario 3 (coordinated multi-entity compromise). Without this operationalization, the gate would be unverifiable and gameable: an attacker could time activity during analyst off-hours when the active-alert count is artificially low to slip past a gate that depends on that count.

These gates are versioned scoring_config parameters, not normative architectural constants.

### 7.4 Known Limitation: Cohort Prior Poisoning

Coordinated compromise of a substantial fraction of a small cohort, sustained across multiple scoring windows, can eventually corrupt the cohort prior even with the gates in §7.3. This is a load-bearing known limitation of any cohort-based behavioral system and is **explicitly documented in the spec**, not silently accepted. Mitigation in v1: minimum-cohort-size gating and scoring-time population-fraction novelty suppression (§7.3 banner). Prior-update rejection and analyst review of cohort-prior update rejections deferred with §7.3 (S5.11 / Path B).

## 8. LLM Explanation Service

### 8.1 Invocation Boundary

LLM is invoked **only after** the hot-path scorer has produced a decision crossing the configured threshold, and **only to generate the analyst-facing explanation**. The LLM is never consulted to produce or modify the score itself.

### 8.2 Inputs (Structured)

- The decision record (§6.2)
- The relevant slice of the entity's profile (the features that drove the score)
- Recent context within the analysis window
- The scoring_config snapshot active at decision time

All inputs are passed via **structured field bindings**, not concatenated free text. Low-trust fields (§3.4) are escaped, length-capped, and slot-isolated.

### 8.3 Output Validation — ExplanationRecord Schema

▲ **The ExplanationRecord Pydantic schema is a Phase 0 deliverable**, committed alongside the event schema and decision schema. It is the validation target for §8.3, the contract between the prompt template and the UI renderer, and the canonical structure for §8.7 explanation lineage records.

```python
from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel

class ConfidenceLabel(str, Enum):
    very_low = "very_low"
    low = "low"
    moderate = "moderate"
    high = "high"
    very_high = "very_high"

class ClaimObject(BaseModel):
    contribution_id: str           # references decision_record.feature_contributions[i].contribution_id
    claim_text: str                # natural-language claim, length-capped
    evidence_binding: list[str]    # contribution_ids this claim is grounded in (must resolve)
    confidence_label: ConfidenceLabel  # SET BY EXPLAINER SERVICE, NOT BY LLM

class CounterfactualEntry(BaseModel):
    contribution_id: str
    counterfactual_text: str       # "if logon_hour had been within typical range, score would have been X lower"
    score_delta: float             # quantitative impact

class ValidationStatus(str, Enum):
    passed = "passed"
    template_fallback = "template_fallback"
    rejected = "rejected"

class ExplanationRecord(BaseModel):
    decision_id: str
    summary_text: str
    claim_objects: list[ClaimObject]
    counterfactuals: list[CounterfactualEntry]
    validation_status: ValidationStatus
    validation_notes: Optional[str]
    llm_model_id: str              # pinned, non-alias
    prompt_hash: str               # SHA-256 of the exact prompt sent
    response_hash: str             # SHA-256 of the exact response received
    created_at: datetime
```

LLM-generated explanations are validated against:

- **Schema compliance:** required fields populated, optional missing-evidence fields explicitly marked
- **Prohibited-content list:** no named threat actor attribution, no specific malware family claims, no language asserting confidence beyond the evidence
- **Evidence binding:** every `claim_object.evidence_binding` must reference a real `contribution_id` in the decision record. Empty or invalid bindings are rejection conditions.
- ▲ **Confidence label binding:** `confidence_label` is computed deterministically by the explainer service from the decision record's numeric confidence and passed to the LLM as a fixed input. The LLM does not select the confidence label.

Validation failure produces a **deterministic template fallback explanation** drawn from the feature contributions directly (no LLM in the fallback path), and the rejection is logged.

### 8.4 ▲ LLM Determinism, Caching, and Lineage

- LLM calls use **temperature = 0** to reduce output variance. **Bit-identical outputs across runs are not guaranteed by any inference provider** — CUDA floating-point non-associativity, distributed inference, and provider-side variations make byte-level determinism a property the architecture must NOT depend on.
- ▲ **The audit lineage record is the single authoritative record for any explanation.** Re-invoking the LLM to verify a prior explanation is **prohibited**. Reproducibility is provided by the immutable lineage (full prompt, full response, model version, timestamp), not by future LLM calls.
- Explanations are **cached by deviation-object-hash** (`hash(decision_id || scoring_config_version || profile_version || llm_model_id)`). Identical inputs produce the cached output.
- ▲ **LLM model ID is pinned to a specific non-alias identifier** (e.g., `claude-sonnet-4-6`, not `claude-sonnet-latest`). This is required so model version changes are detectable in lineage records.
- ▲ **v1 shipped empirical determinism check (S5.7):** `scripts/llm_determinism_check.py` sends the same prompt 10 times at temperature=0 to the configured pinned model and records whether outputs are byte-identical. Artifact: [`docs/llm-determinism-check.md`](llm-determinism-check.md). **Honest scoping:** the script ships; an empirical conclusion requires live provider credentials — the committed artifact may read "not executed" until an operator runs it. The architecture functions correctly regardless; lineage (§8.7) is authoritative, not provider reproducibility.
- **LLM model version changes do not invalidate prior explanations.** Old explanations remain immutable historical artifacts. New decisions or replays generate new explanations under the new model version, with the model version recorded in the lineage.

### 8.5 Top-K Counterfactuals

The detail view includes **top-K counterfactual** information: the K features that, if behavior had been within the entity's typical range, would most have lowered the score. These are populated as `CounterfactualEntry` objects (§8.3) and grounded in actual feature contributions, not abstract narrative.

▲ **v1 shipped (S5.10).** `build_top_k_counterfactuals` in `worker/explainer.py` is the single source of truth; counterfactuals are deterministic from contribution scores, not LLM-generated. Consistency is verified by a pytest harness and JSON corpus — see [`docs/counterfactual-consistency.md`](counterfactual-consistency.md).

### 8.6 Queue Depth Limit and Fallback

The explainer service has a configurable queue depth. On overflow, decisions are not dropped — they receive the deterministic template explanation immediately, and the dropped-explanation event is logged for audit. This prevents containment-queue stall during alert storms.

### 8.7 Explanation Lineage

Every explanation is persisted as an `ExplanationRecord` (§8.3) with:

- The exact prompt sent to the LLM (hash + content)
- The exact response received (hash + content)
- The validation outcome
- ▲ The pinned LLM model ID (non-alias)
- The cache hit/miss status
- The decision_id and scoring_config_version it explains

Lineage is **immutable**. Replays produce new explanation records, never overwriting prior records.

## 9. Scoring Config Governance

### 9.1 What scoring_config Holds

All tunable numeric parameters listed in §6.8.

### 9.2 Authentication and Audit

- v1 uses **local authorization**: OS-level file permissions or a local credential store, mapped to the `detection_engineer` role
- Credentials supplied via **gitignored .env file**, with `.env.example` committed to the repository documenting required fields without values
- **No external auth dependency** in v1 (documented as production upgrade path)
- **No hardcoded credentials in the repository** under any circumstance
- Every scoring_config write emits an **immutable audit record** with: `previous_config_hash`, `new_config_hash`, `author`, `timestamp`, `change_reason`

▲ **Audit immutability mechanism (shipped S5.3).** v1 enforces immutability at the database-role layer via the runtime Postgres role `alter_ego_app` (Alembic migration `g6h7i8j9k0l1_add_app_db_roles`):

1. **Postgres role-based access control:** migrations run as bootstrap owner `user`; `web` / `worker` / `batch` connect as `alter_ego_app`. That role has `INSERT` + `SELECT` and **no** `UPDATE` or `DELETE` on append-only commit tables: `audit_logs`, `decisions`, `explanations`, `scoring_configs`. On `profiles`, payload columns are immutable after INSERT — the role may `UPDATE` only lifecycle columns `promoted_at` and `superseded_at` (promotion/supersede paths). Operational tables (`events`, `resolved_events`, `alert_workflow_state`, `containment_queue`, `eval_ground_truth`) have broader grants documented in `docs/deployment.md`.
2. **Hash chaining:** each audit record carries `prev_record_hash` referencing the SHA-256 of the previous record. Any deletion or modification breaks the chain and is detectable on integrity check.
3. **Scheduled integrity check (shipped S5.4):** `python -m batch.audit_integrity` counts audit records against expected counts from decision records and verifies hash chain continuity. Discrepancy emits a sensor-health incident (non-zero exit).

▲ **Honest scoping.** This protects against application-layer mistakes (accidental UPDATE/DELETE in code) and forensic-layer review (interviewer can verify chain). It does **not** protect against a database superuser tampering with audit records, which is out of scope for v1 (§3.3). Production upgrade path: external log shipping, WORM storage, or a managed audit service.

### 9.3 Replay Mechanics

scoring_config changes do **not** automatically recompute pending decisions. Existing decisions are flagged with `reevaluation_recommended: true`; the operator must explicitly invoke replay.

Replay constraints:

- Requires `replay_run_id`, `start_time`, `end_time`, `old_scoring_config_version`, `new_scoring_config_version`, `author`, `timestamp`, `change_reason`
- Replays **all eligible decisions in the declared contiguous event-time window**. Selective per-decision replay is **prohibited in v1** to prevent audit cherrypicking.
- **Original decision records are preserved immutably.** Replays create new decision records linked to the replay_run_id.
- **`max_replay_window_days`** (default 30, configurable in scoring_config) limits routine replay scope. Larger windows are permitted but require explicit `change_reason` justification, making mass historical recomputation visible in the audit log.
- Asynchronous execution is acceptable for large windows, provided scope is declared up front and immutable.

## 10. Evaluation

### 10.1 Evaluation-First Discipline

Architecture being settled does not mean the system works. Empirical calibration of scoring_config defaults under the named evaluation scenarios is the **Phase 2 calibration gate**. ▲ Calibration is run after Phase 1 (core detection) is built, not before — a system cannot be calibrated before it exists. No detection performance claims may be made before the calibration gate clears.

### 10.2 Simulation Partition Discipline and Synthetic Generator

▲ **Ground-truth labels live in a side table, not on the event itself.** Every event in the system carries a `simulation_partition` label: `production`, `eval_scenario_1`, `eval_scenario_2`, etc. **Ground-truth labels for eval events live in a separate Postgres table** (`eval_ground_truth(event_id PK, label, scenario_id, injection_metadata)`) keyed by event_id. The eval harness joins on event_id; the scorer never has access to this table. This eliminates the leakage attack surface where an accidental field reference in the scorer could read ground truth.

Profile builds **exclude eval-partition events** from training data. Scoring **does not consult the simulation_partition label** — partition metadata is invisible to the scoring evidence to prevent leakage. This is the discipline that prevents "I trained on the test set" failures.

▲ **Synthetic generator requirements (Phase 0 deliverable):**

1. **Production-shape fidelity.** Output events conform directly to the canonical Pydantic event schema. ECS-aligned where reasonable; Sentinel-shaped where ECS is silent. Swapping the generator for a real SIEM forwarder must be purely an ingest-source change, not a schema change.
2. **Realistic per-entity baseline behavior.** Per-entity schedules, role-cohort structure, endpoint affinity, geography distributions, service-account periodicity, process families, command-line templates, **correlated benign changes** (e.g., simulated tooling rollouts that affect a cohort simultaneously). Without correlated benign change, rarity features trivially separate attacks and Phase 2 produces inflated precision/recall.
3. **Scenario injection with controlled ground truth.** All four scenarios parameterizable. Ground truth written to the side table at injection time, before any profile build.
4. **Reproducibility via seeded RNG.** Same seed produces byte-identical event streams across runs.
5. **Cohort structure sufficient for Scenario 3.** Cohorts must contain enough entities (≥ min_cohort_size at calibrated value, target ≥10) to make the population-fraction gate meaningful.
6. **Service account periodicity for Scenario 4.** Service accounts must exhibit realistic automation patterns (periodic execution, narrow process sets), not just sparse counts.

### 10.3 The Four Evaluation Scenarios

Each scenario produces a labeled event stream with ground truth. Each is evaluated under threshold sweeps to produce precision/recall curves; operating-point thresholds are then selected from these curves and documented in the canonical scoring_config.

1. **Sharp credential misuse:** an account performs a clear single-step deviation (login from anomalous geo, access to anomalous resource set). Tests baseline detection sensitivity and explanation quality.

2. **Slow-roll behavioral drift:** an account's behavior shifts gradually across N days, each step below the per-event threshold, terminating in a clearly malicious action. Tests cumulative drift detection (§6.4) and the anti-normalization protections (§5.5). ▲ Requires active-alert profile-build blocking to be in place during calibration; otherwise calibration silently allows attack normalization.

3. **Coordinated multi-entity compromise:** several accounts in the same cohort exhibit simultaneously novel behavior. ▲ **v1 partial (S5.11 / Path B):** scoring-time novelty suppression ships (`max_changed_fraction`, `cohort_gate_window_days` in `worker/scorer.py`); cohort-prior **update** rejection gates and `min_clean_observation_count` are deferred. Calibration tunes `cohort_gate_window_days` against the shipped scorer path; full §7.3 prior-update defense is Phase 4.

4. **Service account abuse:** a service account with sparse observations is misused. Tests hierarchical baselining (§6.3), the cohort fallback terminus, and behavior under low feature-class confidence. ▲ Requires basic cohort shrinkage to be in place during calibration; otherwise calibration tests entity-local-only scoring with cohort_unsupported=true rather than the scenario as specified.

### 10.4 Reported Artifacts

For each scenario:

- Precision/recall curve at varied thresholds
- Selected operating point with documented justification
- Confusion matrix at operating point
- Sample explanation outputs (validated and template-fallback) reviewed for quality
- False-positive rate against the benign background load that runs in parallel
- Comparison against a baseline (statistical UEBA, isolation forest, or simple threshold) where computationally tractable

### 10.5 Explanation Quality Metrics

Beyond detection precision/recall, explanation quality is itself measured:

- **Evidence binding rate:** fraction of explanation claims that map to a feature contribution in the decision record (per ExplanationRecord §8.3, this is structurally enforced and should approach 100%)
- **Validation pass rate:** fraction of LLM outputs that pass §8.3 validation without falling back to template
- **Counterfactual consistency:** does the top-K counterfactual list (§8.5) match the largest feature contributions in the decision record — verified by pytest harness (S5.10; `docs/counterfactual-consistency.md`)

## 11. Analyst UI

### 11.1 Triage View

- One row per active alert
- `raw_score` prominently displayed (v1 API field: `score`), no other numeric scores in this view
- Entity ID, timestamp, ▲ asset blast-radius indicator deferred with §12, ▲ alert workflow state badge (`new`, `acknowledged`, `investigating`, `cleared`, `auto_resolved` per §11.5) — not profile lifecycle (§5.4, deferred)
- Non-numeric icons for: `stale_profile`, `low_resolution_confidence`, `cohort_unsupported`. ▲ `calendar_context_active` icon deferred with §6.6; ▲ `infrastructure_volatile` icon deferred with §12; ▲ `reactivated_dormant` icon deferred with §5.4
- Sort/filter by score, time, entity type. ▲ Sort/filter by asset class deferred with §12

### 11.2 Detail View

- All triage information, plus:
- Full feature contribution breakdown (each `feature_contributions[i]` rendered)
- Top-K counterfactuals (§8.5) rendered from `ExplanationRecord.counterfactuals`
- LLM explanation rendered from `ExplanationRecord.summary_text` and `claim_objects`, with validation status indicator
- Profile snapshot at decision time (the slice that scored)
- Containment action queue status
- Decision lineage (replay history if any)

▲ **v1 ships (S4.6 / Path B).** Score (`score` field), feature contributions, explanation/counterfactuals when present, and decision lineage. ▲ **Deferred post-v1:** `context_adjusted_score` and calendar entry display (§6.6); recent entity timeline within `investigation_context_window` (§6.5) — Phase 4 / future packet.

### 11.3 Confidence Separation

Confidence values are surfaced **separately from scores**, never collapsed into a single number. The detail view shows score and confidence on independent axes; the triage view uses confidence to gate which decisions surface (low-confidence decisions below a configurable confidence floor are suppressed with audit, not promoted — see §11.4).

### 11.4 ▲ Suppressed-Decisions View

A dedicated UI surface for decisions that scored above the anomaly threshold but were suppressed because confidence fell below the configurable confidence floor. This partitions suppressed high-score decisions into an audited surface separate from triage, addressing the adversarial confidence-floor evasion path (§3.2) where an attacker crafts behavior using sparse-feature exploitation to score high while triggering low confidence and bypassing the containment queue.

▲ **v1 partial (S4.3 / Path B).** The suppressed-decisions view itself ships in v1: decisions below the configurable confidence floor are partitioned out of triage into a distinct, audited surface (`/api/suppressed`). Aging indicators, automatic escalation to triage, and aging jitter (the three bullets below) are **deferred to Phase 4 (§13.1)** — `suppressed_decision_age`, `suppressed_decision_aging_days`, and `age_jitter_hours` are documented placeholders, not wired in v1.

- **Visually distinct** from the primary triage queue (separate tab/section, distinct styling) to prevent analysts from learning to deprioritize the queue as routine
- ▲ **Aging indicators** (deferred with §13.1) show how long each suppressed decision has been pending review
- ▲ **Automatic escalation to triage view** (deferred with §13.1) after `suppressed_decision_age` (scoring_config) elapses without analyst review
- ▲ **Aging jitter** (deferred with §13.1) of `±age_jitter_hours` (scoring_config) applied to escalation timing to prevent simultaneous floods when a cohort of suppressed decisions ages together. Without jitter, analysts face predictable step-function workload increases that they learn to expect and deprioritize.

### 11.5 ▲ Analyst Workflow State Transitions

The UI must support these alert state transitions:

- `acknowledge` — analyst assigns to self
- `mark_investigating` — alert is actively being worked
- `clear_with_reason` — alert is resolved; clearing is a documented action with a required `clear_reason` field. **Clearing unblocks profile builds for the entity (§5.5).** The detail/clear surfaces **must display the entity's shadow attestation status** at clear time; clearing against a failing attestation is allowed and logged as `attestation_override` on the audit chain.
- `auto_resolved` — machine path (builder): entity-level **QUIET ∧ ATTEST** (§5.5); not an analyst control, but must appear as a terminal badge distinct from `cleared`
- `queue_simulated_containment` — exercises the containment queue and the simulated-action path
- `view_lineage` — opens decision/explanation/replay lineage in detail view

These transitions make active-alert profile blocking, shadow profile promotion, containment queue state, and the replay mechanism operationally real rather than decorative.

## 12. Asset and Service Dependency Context

▲ **v1 deferral (S4.7 / Path B).** Static asset classification artifacts, service-dependency maps, blast-radius computation, service-account criticality surfacing, and `infrastructure_volatile` entity distinction are design targets, not shipped in v1 portfolio. No committed config artifacts, enrichment loader, scorer flag emission, API fields, or triage UI indicators exist in v1. Full asset/service-dependency context deferred to Phase 4 (§13).

A static asset classification artifact and a static service-dependency map are committed to the repository. These are read-only metadata sources used to:

- Compute **blast-radius** indicators for each entity (what would compromise reach)
- Surface **service-account criticality** (which downstream services depend on this account)
- Distinguish **infrastructure_volatile** entities (intentionally noisy by role) from quiet entities

These are not a CMDB. They are the minimum context required to make explanations meaningful for service accounts and to avoid presenting all entities as equal-risk.

## 13. Implementation Sequencing

▲ **Phase ordering reversed from v1.** Calibration cannot precede the system that gets calibrated. The corrected sequence:

### Phase 0 — Infrastructure Scaffolding and Contracts

Repository, CI, four-container deployment topology (§4.4, **shipped S5.1** — `docs/deployment.md`), Postgres + DuckDB + pgvector, decision schema, audit tables with INSERT-only role and hash chaining (**shipped S5.3/S5.4**), scoring_config governance with .env credential mechanism. ▲ Phase 0 deliverables include:

- Canonical Pydantic event schema (auth + process)
- Decision schema (Pydantic)
- ExplanationRecord schema (Pydantic, §8.3)
- Profile schema with embedding_model_id/version/dimensionality fields (§5.6)
- Ground-truth side table (§10.2)
- **Synthetic event generator** producing production-shaped events with ground-truth labels (§10.2)
- LLM determinism check script (§8.4, **shipped S5.7** — empirical artifact may await API credentials; see `docs/llm-determinism-check.md`)
- pgvector schema migration playbook (§4.3, **shipped S5.8**)

### Phase 1 — Core Detection Path with Required Correctness Invariants

▲ **Active-alert profile-build blocking and basic cohort shrinkage are required in Phase 1**, not deferred to Phase 4. Without them, Phase 2 calibration produces invalid thresholds for Scenarios 2 and 4.

- Ingest service (parses generator-shaped events into canonical schema, attaches simulation_partition labels)
- Entity-resolver service (raw_entity_refs → canonical entity_id, resolution_confidence)
- Profile-builder with versioning, **active-alert blocking (§5.5)**, embedding_model_version recording
- Hot-path scorer with the **six baseline features (§6.2)**, **basic cohort shrinkage (§6.3)** with fallback terminus, deterministic scoring
- Decision-recorder with idempotent decision IDs and full evidence lineage
- Cumulative drift detection (§6.4) with KL-divergence + cosine + Laplace smoothing metric
- Eval harness running all four scenarios end-to-end (no thresholds claimed yet)

### Phase 2 — Calibration Gate (HARD MILESTONE)

▲ **No detection performance results may be claimed in any artifact until this phase clears.**

- Run all four evaluation scenarios under threshold sweeps
- Produce precision/recall curves
- Select operating points with documented justification
- Calibrate Laplace smoothing α, feature weights, decay lambdas, cohort gates, max_calendar_adjustment, gap windows, max_replay_window_days, max_profile_build_block_days, cohort_gate_window_days, age_jitter_hours
- Write calibrated values to canonical scoring_config
- Compare against baseline (statistical UEBA, isolation forest, simple threshold) where tractable
- Document residual error modes and known limitations

### Phase 3 — Explanation and Analyst UI

- LLM explanation service with structured input binding (§8.2), pinned non-alias model ID, ExplanationRecord output validation (§8.3), prohibited-content list, top-K counterfactuals, deterministic template fallback, queue depth limit
- Triage UI with raw_score primacy and confidence/scoring flags (alert workflow states per §11.5; profile lifecycle §5.4 deferred)
- Detail UI with confidence separation, ExplanationRecord rendering
- **Suppressed-decisions view (§11.4)** ships (confidence-floor partition); ▲ aging escalation and jitter deferred to Phase 4 (S4.3 / Path B)
- **Analyst workflow state transitions (§11.5)**
- Replay mechanism with contiguous-window enforcement (§9.3)

### Phase 4 — Hardening and Documentation (partial — S5.1–S5.12)

**Shipped (S5.1–S5.10):**

- Four-container `docker-compose.yml` topology + `docs/deployment.md` (S5.1, S5.2)
- Postgres `alter_ego_app` INSERT-only role for audit/commit tables (S5.3)
- Scheduled audit hash-chain integrity job (`batch/audit_integrity.py`, S5.4)
- Profile freshness circuit breaker (§5.7) including staleness + active-alert mandatory escalation (S5.5)
- `max_profile_build_block_days` supervisor escalation (S5.6)
- LLM determinism check script + honest artifact (S5.7; empirical run requires API keys)
- pgvector / embedding dimensionality migration playbook (S5.8)
- Embedding metadata mismatch detection at scorer (S5.9)
- Counterfactual consistency corpus + harness (S5.10; `docs/counterfactual-consistency.md`)
- Threat-model + README aligned to shipped behavior (S5.12)

**Deferred (Path B or production upgrade):**

- Advanced cohort poisoning gates (§7.3) beyond basic shrinkage and scoring-time novelty suppression (S5.11 / Path B: prior-update rejection, independent versioned cohort artifacts, `min_clean_observation_count`)
- Suppressed-decisions aging escalation + jitter (S4.3 / Path B)
- Telemetry-gap two-tier policy, calendar dual-score, asset/service-dependency context (S4.6/S4.7)
- Profile lifecycle state machine (§5.4)
- Architecture-debate transcripts under `docs/` (optional)
- Multi-service Kubernetes / standalone Terraform deployment

### ▲ 13.1 Schedule Cut Priority

If the 8-10 week schedule slips, cuts must protect the core portfolio claim: deterministic behavioral detection with grounded explanations and calibrated evaluation.

**Non-negotiable (must ship):**
- Event ingest with simulation_partition discipline and ground-truth side table
- Versioned profile artifacts with embedding_model_version
- Deterministic scorer with six features and feature contributions
- Decision recorder with full lineage
- Active-alert profile-build blocking
- Basic cohort shrinkage with fallback terminus
- Four-scenario eval harness with calibration artifacts
- Constrained-JSON ExplanationRecord with deterministic template fallback
- Basic triage and detail UI with raw_score primacy
- Workflow state transitions sufficient to clear alerts and exercise containment queue
- Suppressed-decisions view (without escalation if necessary; the view itself is non-negotiable)

**Deferrable (document as future work, not implement):**
- Telemetry-gap two-tier policy (§6.5): gap detector, localized-vs-source correlation scoring, sensor-health incident path (`gap_windows.*` placeholders only in v1)
- Calendar dual-score (§6.6): calendar store, `context_adjusted_score`, triage/detail calendar UI (`max_calendar_adjustment` placeholder only in v1)
- Asset/service-dependency context (§12): static classification artifacts, dependency map, blast-radius indicators, service-account criticality, `infrastructure_volatile` flag (no stub artifacts or UI placeholders in v1)
- Suppressed-decisions aging escalation + jitter (§11.4): aging indicators, `suppressed_decision_age`/`suppressed_decision_aging_days` auto-escalation, `±age_jitter_hours` scheduling (the confidence-floor suppressed view itself ships; escalation/jitter are placeholders only in v1)
- Profile lifecycle state machine (§5.4): dormant retention, reactivation penalties, onboarding/role_transition build rules (v1 partial coverage via `cohort_unsupported` + staleness halt only)
- Full replay UI (replay engine ships; UI for invoking it can be CLI in v1)
- Advanced cohort poisoning gates beyond basic shrinkage (§7.3 prior-update rejection, independent versioned cohort artifacts, `min_clean_observation_count`; v1 ships profile-embedded `cohort_data`, blocked-entity exclusion, and scoring-time novelty suppression only — S5.11 / Path B; keep the `cohort_unsupported` terminus)
- Multi-service Kubernetes deployment (the four-container topology is sufficient; **shipped S5.1** via `docker-compose.yml`)
- Elaborate sensor-health workflows beyond basic staleness circuit breaker and audit integrity job (telemetry-gap two-tier deferred S4.6)
- Schema migration tooling beyond embedding metadata mismatch detection (**shipped S5.9**) and documented pgvector playbook (**shipped S5.8**)

## 14. Provenance

This specification was produced through two adversarial dual-LLM debates (Claude + GPT) with the human author as checkpoint at each consensus boundary. The first debate (14 turns) produced architecture v1. The second debate produced v2 by reviewing v1 against an implementation lens, surfacing six load-bearing flaws not caught in v1, and converging on the changes documented in §0 above. Full debate transcripts (`docs/architecture-debate-v1.md`, `docs/architecture-debate-v2.md`) are optional provenance artifacts and are **not** shipped in the v1 portfolio repository (see §13 Deferred).

Notable v2 decisions and their origin:

- **Phase reordering (Phase 1 = Core Detection, Phase 2 = Calibration Gate):** v2 turn 1 (GPT) proposed; v2 turn 2 (Claude) refined to require active-alert blocking and basic cohort shrinkage in Phase 1 as correctness invariants
- **Temperature=0 reframed as variance reduction, not determinism:** v2 turn 2 (Claude) caught spec-internal contradiction
- **Profile delta metric specified (KL + cosine + Laplace smoothing):** v2 clarification round
- **ExplanationRecord schema as Phase 0 deliverable:** v2 clarification round
- **pgvector schema migration requirement:** v2 turn 2 (Claude)
- **max_profile_build_block_days with separate escalation:** v2 turn 2 (Claude)
- **Suppressed-decisions aging jitter:** v2 turn 2 (Claude)
- **cohort_gate_window_days operationalization:** v2 turn 2 (Claude)
- **Pinned non-alias LLM model IDs and empirical determinism check:** v2 question debate
- **Postgres INSERT-only role for audit (and column-level profile lifecycle grants):** v2 question debate — **shipped S5.3** via `alter_ego_app` migration + compose wiring; see §9.2 and `docs/deployment.md`
- **Compressed v1 deployment topology (4 containers):** v2 question debate
- **Synthetic generator as production-shaped Phase 0 deliverable:** v2 question debate (rejected LANL+injection)
- **Six-feature initial scoring contract:** v2 question debate
- **Suppressed-decisions view with workflow state transitions:** v2 question debate
- **Schedule cut priority:** v2 question debate
- **Staleness + active-alert escalation:** v2 question debate
