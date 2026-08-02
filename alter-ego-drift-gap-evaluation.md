# Drift-Only Evaluation: Sentinel ADS Document vs alter_ego

**Document type:** Second deliverable — gap / divergence suggestions for **drift detection only**  
**Not in scope:** Full reimplementation of lakehouse ADS-01…09 inside alter_ego; network/email/OAuth productization

## Reference paths used

| Role | Path | Notes |
|------|------|-------|
| Document 1 (evaluated) | `C:\Users\oalan\Sentinel data lake\docs\ADS-detection-rules-pyspark-delta.md` | Operational-layer PySpark/Delta ADS rewrite (SpecterOps + Summiting + Sentinel lake + Panther patterns) |
| alter_ego (ground truth) | `C:\Users\oalan\alter_ego` | https://github.com/OmarAK-Git/alter_ego — verified from README, SPEC.md, `config/scoring_config.yaml`, `batch/profile_builder/builder.py`, `worker/scorer.py`, `docs/residual-risk-drift-hypotheses.md` |
| MITRE Summit (methodology lens) | `C:\Users\oalan\MITRE summit` | Robust / behavior-level observables; combining observables |
| ADS framework (format only) | `C:\Users\oalan\ADS framework` | Not required for this eval body |

## What alter_ego actually does (verified)

From README / SPEC / scoring config / builder / residual-risk doc:

| Capability | Status |
|------------|--------|
| Telemetry | **Auth + process execution** only (synthetic today). Network, email, file, OAuth **not implemented** (SPEC §2.2–2.3). |
| Point features | `login_hour_rarity`, `geolocation_rarity`, `endpoint_set_rarity`, `process_name_rarity`, `command_line_embedding_similarity`, `service_account_execution_frequency_deviation` |
| Drift engine | Recent (3d) vs prior promoted profiles; per-dimension KL / embedding cosine; cohort-median normalization; exponential accumulator (`drift_half_life_days: 7`); `drift_alert` weight 100; threshold 5.0 |
| Drift dimensions weighted | embedding **40**, process_name **20**, login_hour / geo / endpoint_set **5** each |
| Deferred (relevant to drift) | `total_volume_delta` (always 0), calendar dual-score / gap windows (S4.6), lifecycle-aware baselines (S2.7), cohort prior-update gates (S5.11) |
| Known residual | High FP @ thr=45; S3 subtle coordinated drift weakest; boil-the-frog claims tightly scoped (Design 1 B4); Series D baselines documented |

**Constraint honored:** Suggestions below only propose **drift / divergence / gap** adaptations that fit alter_ego’s existing auth+process identity engine—or explicitly mark “requires new telemetry” as out of scope for implementation, listed only as *why* a Document 1 rule does not map.

---

## Mapping: Document 1 ADS → alter_ego relevance

| Doc 1 ADS | Overlap with alter_ego drift? | Drift-only takeaway |
|-----------|------------------------------|---------------------|
| ADS-01 High Spray Score (Identity) | **Partial** — auth volume / distinct-target / entropy patterns | Strong candidate for **volume + multi-entity** drift signals (DRIFT-R1, R2) |
| ADS-02 DNS Beacon Cadence | **Method only** — alter_ego has no DNS; has service-account **interval CV** | Port **interval regularity / active-hours** ideas onto **process execution cadence** drift (DRIFT-R3) |
| ADS-03 Consent-to-Credential SP | **None** (no OAuth/audit graph) | No drift suggestion without new log types — skip |
| ADS-04 Export–Stage–Upload Exfil Chain | **Conceptual** — ordered multi-phase insider pattern ≈ subtle drift | Inspires **multi-feature staged drift** / velocity (DRIFT-R4), not Databricks connectors |
| ADS-05 Phish Attachment → Process | **Weak** — process rarity/embedding exist; email join does not | Only **process novelty bursts after rare parent context** if process parent metadata exists; else skip |
| ADS-06 Multi-Technique Convergence | **Partial** — alter_ego fuses features but not ATT&CK technique graphs | **Cross-dimension co-drift** / multi-signal agreement (DRIFT-R5) |
| ADS-07 Geographic Auth Velocity | **Partial** — `geolocation_rarity` exists; velocity/impossible-travel across successive successes is **not** a first-class drift dim | **Geo-velocity / successive-locus contradiction** as drift or point feature (DRIFT-R6) |
| ADS-08 Encoded DNS Label Payload | **None** (no DNS) | Out of scope — skip |
| ADS-09 Privileged OAuth Scope Auth | **None** (no OAuth consent telemetry) | Out of scope — skip |

**Drift story change vs prior Document 1:** Core ADS-01…06 drift transfers remain valid. New ADS-07 adds a **geo-velocity** drift gap that maps to alter_ego’s existing geo axis better than OAuth/DNS newcomers (ADS-08/09), which stay explicitly out of scope.

---

# Suggested drift-oriented rules for alter_ego

Format below follows ADS section headings for consistency with Document 1 / ADS framework. Each item is a **suggestion**, not a claim that alter_ego already implements it.

---

## DRIFT-R1: Auth Volume Delta as First-Class Drift Dimension

### Goal

Close the documented gap where hourly/auth **volume spikes** do not contribute to score or cumulative drift, despite being reserved in config.

### Categorization

[Credential Access / Brute Force](https://attack.mitre.org/techniques/T1110/) (spray/stuffing volume) and insider **Collection/Exfiltration** precursors when volume shifts without point rarity.

### Strategy Abstract

* Enable the deferred `total_volume_delta` feature (S2.6) as both a **point contribution** and a **drift_weights** dimension.
* Compare recent-window event counts (and distinct target accounts if present in auth events) to the entity’s historical hourly/daily distribution using the same Laplace-smoothed surprisal / KL style as other categorical dims.
* Feed normalized volume delta into the cumulative drift accumulator with a modest weight (avoid repeating embedding dominance—see residual H4 / H9).

### Why this is a drift gap (evidence)

* `config/scoring_config.yaml`: `total_volume_delta.weight: 1.0` but scorer emits 0 (`volume_delta_deferred`).
* `docs/residual-risk-drift-hypotheses.md` **H9**: volume patterns invisible to current drift dimensions; may relate to S3 subtle misses.
* Document 1 ADS-01 shows spray detection is fundamentally a **volume + diversity** operational behavior; alter_ego’s auth path currently underweights that axis for slow rolls.

### Blind Spots and Assumptions

* Assumes auth events carry stable entity_id and usable timestamps (already true in alter_ego schemas).
* Distinct-target counting needs a field such as destination UPN/account in `event_data`—verify generator/schema before relying on spray-like diversity.

### False Positives

* Load tests, migrations, quarter-end batch jobs.
* Mitigate with lifecycle states (deferred S2.7) and calendar dual-score (deferred S4.6)—same FP class already called out in residual doc.

### Priority

* **High** for drift roadmap (unlocks ADS-01-like spray *behavior* without copying IP-centric lakehouse logic).
* Do **not** ship weight changes without a recorded sweep + governance record (OPS / residual-risk standing rule).

### Validation

* Replay Series D / S3 harness with volume-delta armed; compare S3 recall and FP vs `calibration_series_d_metrics.json`.
* Synthetic: inject gradual auth-rate increase without geo/process novelty; expect earlier `cumulative_drift` growth than baseline.

### Response

* Treat as profile-drift incident: freeze promotion if alert arms (§5.5), review volume vs peer cohort, do not auto-contain on volume alone until calibrated.

### Additional Resources

* alter_ego `docs/residual-risk-drift-hypotheses.md` §2.5 S2.6, §H9  
* Document 1 ADS-01 spray_score feature mix (`distinct_users`, failure rate, entropy)

---

## DRIFT-R2: Multi-Entity Coordinated Drift (Anti–Cohort-Masking)

### Goal

Detect when several entities’ recent distributions shift **together** in the same direction—coordinated compromise that cohort-median subtraction can hide.

### Categorization

[Collection](https://attack.mitre.org/tactics/TA0009/) / insider coordinated misuse; aligns with alter_ego threat model “coordinated multi-entity compromise” (SPEC §3.2).

### Strategy Abstract

* Retain per-entity `norm_drift = raw_drift − cohort_median[role]` for individual scoring.
* **Add** a fleet-level drift rule: if fraction of role cohort with `raw_drift` above a soft threshold exceeds `max_changed_fraction` (config already has `0.2` under `cohort_gating_constants`) over the recent window, emit a **cohort_drift** decision (or raise all members’ drift contribution).
* This is the drift-native analogue of Document 1 ADS-01’s “many targets” and ADS-06’s “convergence,” without requiring ATT&CK behavior tables.

### Why this is a drift gap (evidence)

* Residual **H2**: cohort median subtraction masks coordinated drift.
* Residual **H7** / S5.11: prior-update rejection and `min_clean_observation_count` deferred; only scoring-time novelty suppression ships.
* S3 recall 0.667 with coordinated subtle inject (`inject_scenario_3_coordinated`).

### Blind Spots and Assumptions

* Needs `MIN_NORM_COHORT` / `min_cohort_size` large enough; solo privileged accounts already called out in **H3**.
* Must not equate red-team day or org-wide MFA reset with attack—pair with change windows when S4.6 exists.

### False Positives

* Org-wide policy changes (new VPN, new endpoint image) shifting geo/endpoint/process together.

### Priority

* **High** for closing S3 residual; governance-gated.

### Validation

* Use existing S3 coordinated scenario; measure whether cohort_drift fires before absorption and whether member-level recall improves without FP explosion on Series D tooling mix.

### Response

* Page as **fleet anomaly**; avoid single-entity containment storm; require analyst attestation before mass action (fits QUIET/ATTEST lifecycle thinking already in S55).

### Additional Resources

* SPEC §7.3 / §3.2 coordinated compromise  
* Document 1 ADS-06 convergence idea (multi-signal agreement)

---

## DRIFT-R3: Process Execution Cadence Drift (Beacon-Style CoV on Process Streams)

### Goal

Apply Document 1 ADS-02 DNS beacon **interval CoV + active-hours coverage** methodology to alter_ego’s **process execution** (and service-account) timelines—detect mechanical cadence shifts and 24/7 execution drift.

### Categorization

[Execution](https://attack.mitre.org/tactics/TA0002/) / [Persistence](https://attack.mitre.org/tactics/TA0003/) via scheduled or implant-like process timing.

### Strategy Abstract

* alter_ego already has `service_account_execution_frequency_deviation` (interval CV for scheduled accounts).
* **Extend drift dimensions** (not a new product surface):
  * Per entity (human + service): recent inter-event interval CoV and `ActiveHoursRatio` for process events vs baseline profile histograms.
  * Alert when CoV drops sharply (more mechanical) **or** ActiveHoursRatio rises vs baseline while process_name/embedding drift is still sub-threshold—early boil-the-frog tell.
* Keep DNS ADS-02 itself out of scope (no network telemetry).

### Why this is a drift gap (evidence)

* Service periodicity exists, but residual boil-the-frog / S2 path still struggles under FP+lifecycle regimes; humans lack an equivalent cadence drift feature.
* Document 1 ADS-02 shows **regularity** is a high-value operational observable (SpecterOps/Summiting-aligned) independent of IOC domains.
* Embedding weight **40** can dominate subtle categorical/timing drift (**H4**); an explicit cadence dimension diversifies the spanning set.

### Blind Spots and Assumptions

* Sparse human process streams → unstable CoV; require minimum event counts (mirror ADS-02 `QueryCount > 50` idea).
* Legitimate cron-like user automation may look mechanical.

### False Positives

* Developer build bots under user credentials; CI on workstations.

### Priority

* **Medium–High** for service accounts (extend existing feature into drift_weights).  
* **Medium** for human entities (after volume delta).

### Validation

* Inject fixed-interval process execution (e.g. every 5 minutes) under Design 1 / S2-style slow roll without huge embedding distance; expect cadence drift to accumulate.

### Response

* Investigate new persistent process; compare to peer role cadence; open drift alert workflow (existing recorder path).

### Additional Resources

* Document 1 ADS-02 metric table (CoV, ActiveHoursRatio)  
* `features.service_account_execution_frequency_deviation` in scoring_config.yaml

---

## DRIFT-R4: Staged Multi-Feature Drift (Ordered Capability Stacking)

### Goal

Detect slow insider-style progressions where individually weak shifts in **different** features appear in a **consistent order** over days (e.g. endpoint novelty → process novelty → command-line embedding drift → volume up)—the alter_ego-native analogue of Document 1 ADS-04’s export→stage→upload chain.

### Categorization

[Collection](https://attack.mitre.org/tactics/TA0009/) / [Exfiltration](https://attack.mitre.org/tactics/TA0010/) *behavioral staging* (without cloud connectors).

### Strategy Abstract

* During profile build, record which drift dimensions exceeded soft per-dim thresholds in each recent window.
* Score **ordered sequences** across the 3–7 day half-life horizon (e.g. endpoint_set then process_name then embedding).
* Emit a staged-drift bonus into `cumulative_drift` when sequence matches known bad progressions; do not require any single dim to cross paging threshold alone.

### Why this is a drift gap (evidence)

* S3 subtle / boil-the-frog residuals: point features and single accumulator may miss low-amplitude multi-step shifts (**H5** half-life vs attack tempo).
* Document 1 ADS-04 thesis: each hop looks legitimate; **pattern across phases** is the signal—maps cleanly to multi-feature drift staging inside existing telemetry.
* Does **not** require Databricks/CloudApp (out of scope).

### Blind Spots and Assumptions

* Sequence templates need careful calibration; over-specific orders → FN; over-broad → FP.
* Shadow drift under block (S55 D4) should include staged signals or they starve during alert lifecycle.

### False Positives

* Onboarding / role transition (explicitly deferred lifecycle S2.7—pairing recommended).

### Priority

* **High** conceptual fit for alter_ego’s stated residual research (`HUMAN-DRIFT-RESEARCH` / residual doc).  
* Implement only behind eval harness.

### Validation

* Construct a staged inject: day1 rare endpoint, day2 rare process, day3 embedding shift, day4 volume—each below anomaly_threshold alone; expect staged rule to fire.

### Response

* Same as drift_alert path; emphasize timeline of dimension order in LLM/template explanation slots.

### Additional Resources

* Document 1 ADS-04 chain rationale  
* residual-risk §2.2, §2.6, H5

---

## DRIFT-R5: Cross-Dimension Agreement Gate (Convergence Without ATT&CK Graphs)

### Goal

Raise confidence when **independent** alter_ego signal families agree—point rarity **and** cumulative drift **and** (once armed) volume/cadence/geo-velocity—mirroring Document 1 ADS-06’s multi-plane convergence without UEBA behavior tables.

### Categorization

Meta-detection / alert fusion (supports any ATT&CK tactic already implicated by underlying features).

### Strategy Abstract

* Define signal families: (A) geo/login hour, (B) endpoint/process categorical, (C) embedding, (D) drift accumulator, (E) volume/cadence/geo-velocity when implemented.
* Page **containment** or escalate priority only when ≥2 families contribute above soft floors—or when drift alone exceeds the existing “drift can trip alarm at ~2.25 accum” design **and** a second family is non-zero.
* Use as **precision tool** against thr=45 FP storm (residual §2.1 / §2.7), which currently starves drift via alert lifecycle interactions.

### Why this is a drift gap (evidence)

* Documented FP≈3448 @ thr=45; under §5.5, FP opens workflows that block promotion and freeze visible drift—**point-anomaly precision is prerequisite for drift path function**.
* Document 1 ADS-06: independent systems agreeing → higher confidence. alter_ego already has multiple features but thresholds them mostly via a single fused score.
* Does not invent new telemetry.

### Blind Spots and Assumptions

* Over-gating reduces S1 sharp-misuse recall if tuned too hard—sweep required.
* Must remain compatible with intentional “drift alone can trip” asymmetry in scoring_config comments—or consciously revise that policy with governance.

### False Positives

* Still possible when two weak noisy features correlate (e.g. geo + login hour on travel); travel/lifecycle context (S4.6 / S2.7) remains relevant.

### Priority

* **High** operationally for making drift *usable* under armed lifecycle, not merely mathematically present.

### Validation

* PR-curve / Series D replay: measure FP reduction vs S1/S2/S3/S5 recall deltas; refuse ship if S2 Design-1 B4 license regresses without explicit accept.

### Response

* Prefer convergence-gated alerts for auto-containment queue (`containment_threshold: 85`); keep single-family hits in suppressed / hunt views.

### Additional Resources

* scoring_config.yaml drift formula comments  
* residual-risk §2.1, §2.7  
* Document 1 ADS-06

---

## DRIFT-R6: Successive Geo-Locus Velocity Drift (from ADS-07)

### Goal

Complement static `geolocation_rarity` with **pairwise successive-login geographic velocity**—flag when an identity’s recent auth locus jumps farther/faster than its historical travel distribution (operational impossible-travel behavior without new log types).

### Categorization

[Initial Access / Valid Accounts](https://attack.mitre.org/techniques/T1078/) — session theft / dual-locus auth.

### Strategy Abstract

* On auth success events with geo coordinates (or city centroids), compute distance/Δt vs prior success for the same entity.
* Maintain a per-entity histogram of historical implied km/h (or binned “plausible travel” rates) in the profile builder.
* Contribute a **geo_velocity_delta** drift dimension when recent implied speed exceeds the entity’s (and optionally role cohort’s) baseline.
* Soften with known VPN/relay ASNs when enrichment exists—same FP class Document 1 ADS-07 documents.

### Why this is a drift gap (evidence)

* alter_ego already weights `geolocation_rarity` lightly (5); rarity of a *single* location ≠ contradiction between *two successive* successes.
* Document 1 ADS-07 (Panther impossible-travel pattern → lakehouse) is the closest new ADS to alter_ego’s auth+geo surface; prior Document 1 had no explicit geo-velocity rule.
* Helps S1-style sharp account misuse that may not move process embeddings.

### Blind Spots and Assumptions

* Requires lat/long or stable city→centroid mapping in synthetic/real auth events—verify generator fields.
* Sparse travelers have unstable baselines; require minimum paired successes.

### False Positives

* Corporate VPN egress far from user; privacy relays; GeoIP churn.

### Priority

* **Medium–High** after DRIFT-R1; natural fit for existing geo axis without new telemetry products.

### Validation

* Inject NZ→US success pair within 2 hours for a user whose baseline is local-only; expect geo_velocity_delta and earlier cumulative drift than geo rarity alone.

### Response

* User verification + session revoke path; combine with DRIFT-R5 before containment.

### Additional Resources

* Document 1 ADS-07  
* `features.geolocation_rarity` in scoring_config.yaml

---

## Explicitly not suggested (out of drift scope / unverified capability)

| Document 1 ADS | Reason to exclude from alter_ego drift suggestions |
|----------------|-----------------------------------------------------|
| ADS-03 Consent-to-Credential | Requires Entra audit / SP graph — not in alter_ego v1 scope |
| ADS-05 email↔endpoint hash join | Requires email + file telemetry — not implemented |
| ADS-02 as DNS TI hunter | Requires DNS/network + TI tables — not implemented (method only → DRIFT-R3) |
| ADS-04 Databricks connectors | Platform-specific; only the *staging pattern* was adapted (DRIFT-R4) |
| ADS-08 Encoded DNS labels | Requires DNS query names — not implemented |
| ADS-09 Privileged OAuth scopes | Requires consent/scope audit — not implemented |
| Copying spray_score formula onto IP entities | alter_ego entities are users/service accounts, not source IPs; volume/diversity must be entity-scoped (DRIFT-R1) |

---

## Priority order (practical)

1. **DRIFT-R1** — arm volume delta (already stubbed).  
2. **DRIFT-R5** — convergence gating to protect drift path from FP starvation.  
3. **DRIFT-R2** — coordinated cohort drift for S3.  
4. **DRIFT-R6** — geo-velocity on successive auth (new from ADS-07).  
5. **DRIFT-R3** — cadence CoV on process streams.  
6. **DRIFT-R4** — staged multi-feature sequences (research-heavy).

All require recorded eval sweeps; do not change `scoring_config.yaml` weights/thresholds without governance (alter_ego OPS / residual-risk standing rule).

---

## Summary

Document 1’s operational-layer ADS pack is largely **lakehouse / multi-telemetry** detection. alter_ego’s verified strength remains **identity behavioral drift** on auth+process. Honest “relevant rules for alter_ego” are still **drift-methodology transfers**: volume, coordinated cohort shift, execution cadence, staged multi-feature progression, multi-signal convergence, and (newly) successive geo-velocity—not ports of DNS/OAuth/email/Databricks graphs.

---

*End of Document 2.*
