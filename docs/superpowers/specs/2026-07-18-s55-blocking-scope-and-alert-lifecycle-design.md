# Design: §5.5 build-block lifecycle × shadow-signal interlock

**Date:** 2026-07-18 (stub opened and evolved to full design same day, operator-directed)
**Status:** **APPROVED 2026-07-18 (operator).** Implementation authorized under T3 `.workflow/2026-07-18-s55-alert-lifecycle/`. No detection YAML/knob changes in this cycle; Series C sweep deferred to follow-on.
**Trigger:** residual-risk §2.7 (confirmed drift-starvation deadlock, Series B)
**Companion:** `docs/residual-risk-drift-hypotheses.md` §2.1 (reframed), §2.5, §2.7; `docs/scoring-config-governance-btf-series-b.md` degenerate-regime caveat; SPEC §5.5, §5.7, §6.1, §11.5; Design 1 spec (`2026-07-18-boil-the-frog-invariants-design.md`) §1 predicates + fixture-limitation note
**Governance:** every parameter and semantic change herein routes through **S6.3** (recorded sweep + governance record). First post-design sweep = **Series C**.

---

## 0. Decision summary

| # | Decision | Status |
|---|---|---|
| D1 | All anomaly alerts open workflow rows AND arm build-blocking at open (no severity gate at arming) | **Approved** |
| D2 | Blocking scope stays **per-entity, own-alerts-only** | **Approved** (confirms shipped behavior) |
| D3 | Lifecycle: add `auto_resolved` (machine) alongside `cleared` (analyst); auto-resolution gated on **QUIET ∧ ATTEST**, never on time alone | **Approved** |
| D4 | Shadow-signal channel: scorer's `drift_alert` contribution reads the **shadow-lineage accumulator** for blocked entities; baseline features stay promoted-profile | **Approved** |
| D5 | S5.6 SLA escalation upgraded from observe-only to mandatory-review enqueue (S5.5 queue pattern) | **Approved** |
| R1 | Time-only expiry of alerts | **Rejected** (T-PATIENT P1) |
| R2 | Severity/score-gated arming as the anti-deadlock mechanism | **Rejected** (evidence: no score separation, §4.1) |
| R3 | Scoring events against shadow profiles (full shadow scoring) | **Rejected** (defeats §5.5 anti-normalization) |
| R4 | Cohort-wide or global blocking scope | **Rejected** (§4.2) |
| R5 | Disabling §5.5 | **Rejected** (standing; B3b containment must survive this design) |

---

## 1. Problem statement (confirmed 2026-07-18, residual-risk §2.7)

Armed §5.5 build-blocking is per-entity and keyed on *any* active `AlertWorkflowState` row. No pipeline component ever transitions a row out of an active state (S4.3 deferral; §11.5 `clear_with_reason` exists in schema only). Blocked is an **absorbing state**.

Series B: 47 of 50 blocked entities were first blocked by their **own benign FP**, most within the first scored day; 50/55 entities were promotion-frozen by sweep end. The scorer reads only promoted profiles, so the drift accumulator kept rising in shadow lineage (S2 attack entity: 81.72, builder drift alarms from the first attack day) while the scorer-visible `cumulative_drift` stayed 0.0 — S2 event recall 0.0. Slow-roll *event* detection requires drift → drift visibility requires promotion → promotion requires no active own alerts → sustained FP + no lifecycle = active alerts forever. Architectural: threshold tuning changes the timescale, not the topology.

---

## 2. Named threat: T-PATIENT (the patient attacker)

Adversary refinement of SPEC §3.2's slow-roll adversary. **Kerckhoffs assumption: T-PATIENT knows the lifecycle design and its parameters.** The design is not done until every play below has a named answer (§5). The benign twin — T-STORM, an organic FP storm with no adversary — is the *already-observed* Series B failure; any design that survives T-PATIENT survives T-STORM, not vice versa.

**Plays:**

- **P0 — Block-as-sanctuary.** Under shipped semantics, an active block freezes scorer-visible drift at its pre-block value. The attacker *wants* an open FP alert on the target account before starting the ladder: the block blinds the drift path for the duration. Series B demonstrates this unintentionally — the Jan-2 FP protected the Jan 10–16 ladder.
- **P1 — Close-and-launder cycling.** If alerts expire on a timer: trip an alert (or wait for an organic FP), run ladder rungs while blocked (sub-threshold at score time), go fully in-family until the drift accumulator decays (7-day half-life), wait for expiry, and let the resumed promotion absorb the rungs — which remain in the 30-day histogram window even after drift has decayed. **Accumulator decay ≠ window hygiene.** Repeat per rung. A time-expiry lifecycle is a metronome for laundering.
- **P2 — Sub-gate slow roll (budget compounding).** Against any per-closure attestation bound: keep per-cycle novel mass below the bound and compound absorption across many close→promote cycles.
- **P3 — Storm cover.** Trigger or ride cohort-wide FP storms (tooling rollout) so cohort-median normalization eats the attack drift (H2) and/or analyst throughput saturates; under shipped semantics a storm also freezes the fleet (Series B).
- **P4 — Block-as-DoS.** Induce FPs on *victim* accounts (not the attacker's own) to freeze the victims' baselines and, under shipped semantics, blind drift detection on them — detection suppression of arbitrary targets via the blocking mechanism itself.

---

## 3. Core requirement: R-INTERLOCK

**Lifecycle and shadow-signal visibility are one design, not two.** Each surface alone re-creates a failure world already observed or directly derivable:

- **Lifecycle without shadow-signal** (any closure rule that does not consult what accumulated during the block) = **normalization pump**: closure promotes the block-era window wholesale; P1 executes it on demand. Time-expiry is the degenerate case, but *any* attestation-blind closure has the same defect.
- **Shadow-signal without lifecycle** (visibility fixes, blocks still absorbing) = **Series B forever**: fleet promotion still collapses (50/55), baselines staleness-inflate drift fleet-wide (48/87 drift alerts fired on non-attack entities), cohort histograms shrink to the unblocked remnant (Fix #6), and every rate degrades unboundedly.

**Formal statement (both clauses mandatory, neither ships alone):**

1. **No closure without attestation.** A blocking alert may leave the active set only via analyst `clear_with_reason` (§11.5) or via machine auto-resolution whose predicate **consumes the shadow-lineage record of the block era** (§4.5). Wall-clock age is never a sufficient condition.
2. **No block without detection.** While an entity is blocked, the drift signal must remain effective in the runtime score path (§4.4). A block may suppress *learning* (promotion); it must never suppress *detection*.

Derived requirements: **R-NODEADLOCK** (at characteristic FP rates, FP-caused blocks resolve without analyst action; fleet promotion coverage stays bounded away from collapse), **R-CONTAIN** (B3b and Design-1 fixture properties preserved), **R-TPATIENT** (each play P0–P4 has a named answer, §5), **R-AUDIT** (every state transition is auditable; §4.7), **R-DETERMINISM** (§6.1 replay determinism preserved under D4; §4.4).

---

## 4. Design

### 4.1 Arming (D1): every anomaly blocks at open; severity gating rejected as load-bearing

Every anomaly DecisionRecord (point or builder-drift) opens a workflow row and arms build-blocking, as shipped. **Severity/score-gated arming is rejected as an anti-deadlock mechanism on direct evidence:** in Series B the only real event-level TP (S1 sharp misuse) scored **50.04**, *inside* the benign FP cluster (FP p50 = 50.1, p90 = 69.0, max = 90.8). Any floor that meaningfully cuts FP arming (≥55 still arms 659 FPs; ≥80 still arms 55) would also have failed to arm on the genuine S1 attack. Scores at open do not separate; **evidence accumulated over the block does** — which is the lifecycle's job. Gating-by-severity may be revisited in Series C as a measured diagnostic only.

Arming hygiene: a builder drift decision for an already-blocked entity **refreshes** the entity's existing drift-class row (updates score/timestamp) instead of inserting a new row per build cycle (Series B: 8 stacked drift rows on the S2 entity served no function). Point-anomaly rows remain one-per-decision (audit trail).

### 4.2 Scope (D2): per-entity, own-alerts-only — retained

Q3 confirmed the shipped predicate is per-entity. Retained: cohort/global blocking would let one FP freeze a fleet (Series B × N), and cohort contamination is already handled by excluding blocked entities from cohort histograms (builder Fix #6, retained). The S3-coordinated case needs no scope change: coordinated attackers each trip their own drift alerts and block individually.

### 4.3 Lifecycle (D3): state machine

States: `new` → `acknowledged` → `investigating` → `cleared` (analyst path, exists in schema) plus **`auto_resolved`** (machine path, new). Active (blocking) set: `{new, acknowledged, investigating}` — unchanged.

| Transition | Actor | Condition |
|---|---|---|
| `new → auto_resolved` | machine (builder cycle) | entity-level **QUIET ∧ ATTEST** (§4.5) ∧ row age ≥ `min_dwell_builds` |
| `new → acknowledged → investigating` | analyst | as shipped (§11.5) |
| `{any active} → cleared` | analyst | `clear_with_reason` — always available, always unblocks (SPEC §11.5 frozen text). UI **must** display the entity's shadow attestation status at clear time; clearing against a failing attestation is allowed but logged as an override (§4.7) |
| escalation (state unchanged, flagged) | machine | block age > `max_profile_build_block_days` (existing S5.6 key, default 30) → **enqueue mandatory analyst review** (S5.5 queue pattern), not observe-only (D5). Auto-resolution remains possible after escalation; the SLA forces human attention, it does not force closure |

Rules: auto-resolution operates at **entity level** — when the entity-level predicate passes, all of that entity's `new` rows resolve together. Rows an analyst has touched (`acknowledged`/`investigating`) are **exempt from auto-resolution**: human attention supersedes the machine path. **Time-only expiry does not exist** (rejected R1: it is P1's enabling condition). Interplay with §5.7: because blocks now resolve at characteristic rates, the block→staleness→halt chain is bounded; the S5.5 staleness×active-alert escalation remains the backstop for the long-block intersection.

### 4.4 Shadow-signal channel (D4): drift visible under block, baseline still frozen

While an entity is blocked, `score_event`'s `drift_alert` contribution reads `cumulative_drift` from the entity's **latest shadow profile** instead of the frozen promoted profile. All other features (histograms, centroid, cohort data) continue to read the **promoted** profile — the scoring *baseline* never learns block-era behavior (that is §5.5's anti-normalization property, preserved); the drift *accumulator* is not a baseline but an alarm integrator, and reading it is one-directional evidence. Full shadow scoring stays rejected (R3): scoring rarity against a shadow that absorbed attack behavior is normalization at score time.

**Determinism (R-DETERMINISM):** §6.1 requires decisions be deterministic given (event, profile_version, scoring_config_version). D4 adds an input: the consulted shadow profile. The DecisionRecord therefore records `drift_source_profile_version` (in flags/contributions) whenever it differs from `profile_version`; replay determinism holds over the extended tuple. The `drift_alert` contribution's `raw_value` already carries the accumulator value consumed.

**Known cost, bounded by the interlock:** shadow drift under block is computed against frozen promoted baselines, so it inflates with benign staleness over long blocks (Series B: 48/87 drift alerts on non-attack entities). D4 is calibratable *only because* D3 keeps blocks short at characteristic FP rates — visibility leans on lifecycle exactly as lifecycle leans on visibility (R-INTERLOCK).

### 4.5 Attestation predicate (QUIET ∧ ATTEST)

All terms computable from pipeline state — no ground-truth labels.

- **QUIET:** no new anomaly DecisionRecord (point or drift) for the entity within the trailing `quiet_window_days`.
- **ATTEST** (all three, evaluated at the builder against the candidate shadow profile `S`, the last promoted profile `P₀`, and the promoted profile `P₋ₙ` from `anchor_history_count` promotions back):
  1. **Peak-drift gate:** max `cumulative_drift` recorded across all shadow builds during this block < `drift_threshold`. *Peak, not terminal* — the accumulator decays with a 7-day half-life but the histogram window does not; terminal-value gating is P1's other enabler.
  2. **Novel-mass gate:** `M_novel(S, P₀)` < `alpha_prod`, where `M_novel(S, P)` = the **max over categorical histogram dimensions** (`process_names`, `endpoints`, `geolocations`) of the fraction of `S`'s mass in categories absent from `P`'s support (production analogue of Design 1's `M(P, C_attack)` — same shape, label-free; max-over-dimensions so laundering cannot route through a non-process dimension).
  3. **Anchor gate (anti-P2):** `M_novel(S, P₋ₙ)` < `alpha_anchor`. Bounds *compounded* novel mass across close→promote cycles within the anchor horizon, so per-cycle sub-`alpha_prod` laundering cannot sum unbounded.

Attestation failure never auto-clears and never silently extends: failed attestation + SLA breach = mandatory review (§4.3).

### 4.6 Promotion on resolution

When an entity leaves the blocked set (auto-resolution or analyst clear), the **next scheduled build promotes normally** — the attestation (or the analyst's documented judgment) *is* the promotion gate; no separate quarantine rebuild. Superseded/shadow artifacts are retained as shipped (immutability unchanged).

### 4.7 Audit and observability

Every lifecycle transition (auto-resolution with attestation values, escalation, analyst clear including attestation-override flag) is written to the INSERT-only audit chain (`AuditLogModel` pattern). Sweep/ops metrics: blocked-entity-days, promotion coverage per build, auto-resolution latency distribution, attestation failure reasons, override count. These are Series C report fields (§7).

---

## 5. T-PATIENT: play → answer → residual

| Play | Design answer | Residual |
|---|---|---|
| **P0** sanctuary | D4: drift contribution reads shadow accumulator under block — rung scores rise as if unblocked (invariant C2) | None identified beyond D4's staleness inflation (§4.4) |
| **P1** close-and-launder | §4.5 peak-drift gate (in-block rungs counted at peak, decay doesn't wash them) + novel-mass gate (window content checked directly, not via accumulator); R1 time-expiry rejected | Rungs below *both* gates absorb < `alpha_prod` per cycle → P2 |
| **P2** budget compounding | Anchor gate: compounded novel mass vs `P₋ₙ` bounded by `alpha_anchor` over the anchor horizon | An attacker slower than the anchor horizon degrades into the legitimate-change regime; backstop is cohort normalization (H1/H2), which is imperfect. **Honest limit, not a claim of elimination** (§8) |
| **P3** storm cover | R-NODEADLOCK: auto-resolution throughput must exceed characteristic FP arrival (Series C measures); Fix #6 keeps blocked entities out of cohort baselines; H2 cohort-median cancellation is a pre-existing open hypothesis, not worsened by this design | H2 itself remains open |
| **P4** block-as-DoS | Victim blocks auto-resolve (D3) and no longer blind detection while active (D4) — the blocking mechanism stops being a detection-suppression primitive | Induced-FP triage load remains an analyst-cost attack |

---

## 6. Parameters (declared-not-derived; S6.3 before any YAML write)

Same discipline as Design 1 §1.1: pre-registered judgment calls with anchors, **not calibrated**, revisable only with recorded rationale. Existing keys are reused as anchors wherever possible to minimize new magic numbers.

| Parameter | Candidate | Anchor / provenance |
|---|---|---|
| `quiet_window_days` | 3 | = `recent_drift_window_days` (one full recent-drift window of silence) |
| `min_dwell_builds` | 2 | ≥ 2 build cycles so attestation sees at least one full shadow delta |
| `alpha_prod` | 0.02 | = Design 1 `α` (absorption-mass judgment call, same anchor text) |
| `alpha_anchor` | 0.05 | 2.5× `alpha_prod` over an `anchor_history_count` horizon — bounds compounding while tolerating legitimate category churn; weakest anchor here, flagged for Series C attention |
| `anchor_history_count` | 5 | = `drift_comparison_history_count` |
| peak-drift gate bound | `drift_threshold` (5.0) | existing key, existing semantics — no new number |
| SLA | `max_profile_build_block_days` (30) | existing S5.6 key; semantics upgraded observe→enqueue (D5) |

**None of these are written to `config/scoring_config.yaml` in this cycle.** Detection weights/thresholds (v2.2 @ thr=45) untouched.

---

## 7. Eval contract (Series C)

1. **Scenario table row (Design 1 §0.2 tribal-knowledge ban):** T-PATIENT becomes eval scenario `scenario_5_patient_cycle` — ladder split across close→promote cycles with in-family quiet periods tuned to the attestation windows. Partition: feeds builder (same rationale as S2/S3). Row must land in the Design 1 spec table before inject code exists.
2. **Design 1F fixture (FP-storm companion):** Design 1 fixture + synthetic benign FP injection — exists precisely because the Design 1 fixture's all-green is documented as FP-storm-free by construction. Tests the §2.7 deadlock and its resolution directly.
3. **Invariants** (Step-4 tracker item 3 becomes writable on approval of this design):
   - **C1 (no indefinite non-attack block):** every entity whose active alerts are all GT-benign re-promotes within `SLA` sim-days without analyst action. *This is the formerly blocked-on-design invariant.*
   - **C2 (no sanctuary):** an S2 rung's `drift_alert` contribution under an active benign block equals the contribution computed from the same accumulator state unblocked — block state must not appear in the drift term.
   - **C3 (bounded laundering):** after any auto-resolution, `M_novel(next promoted, P₋ₙ)` < `alpha_anchor` — always, including under `scenario_5_patient_cycle`.
   - **B3b preserved:** Design 1 fixture containment stays green unchanged.
4. **Report fields:** §4.7 metrics + Design 2 attribution fields (`memory-bank/progress.md` follow-on items 1–2). Series C is a new baseline; **B→C cross-series comparisons prohibited** (governance record caveat).

## 8. Honest limits and non-goals

- **The patient-attacker guarantee is a tempo floor, not elimination.** The design forces T-PATIENT below the anchor horizon's effective tempo; beneath that, attack drift is indistinguishable in principle from legitimate change and the backstop is cohort normalization with its known gaps (H1, H2). Series C measures the floor; nothing here claims to abolish the adversary.
- **Analyst clear is an unguarded human path by design** (§11.5 frozen). Attestation display + override logging is mitigation, not prevention; social engineering of analysts is out of scope (SPEC §3.3).
- **`alpha_anchor` is the least-anchored parameter** in §6 and the most likely Series C revision.
- **Non-goals:** S5.11 cohort-prior gates, S2.7 profile lifecycle states, S4.6 calendar/gap handling remain deferred as shipped; no generator/partition changes in this spec beyond the §7 additions; no detection-YAML changes anywhere.

## 9. Sequencing and governance

1. Operator review of this draft (**hard gate — nothing below starts before it**).
2. S6.3 governance record for the new §6 keys + D5 semantics change; SPEC §5.5/§11.5 amendment drafted alongside (root `SPEC.md` kept byte-identical).
3. Implementation packet(s) under a new `.workflow/` run: recorder/builder (lifecycle + attestation), scorer/profile_store (D4 + determinism fields), web/UI (§11.5 attestation surface), migrations.
4. §7 fixtures + invariants (C1–C3, Design 1F, `scenario_5_patient_cycle` table row first).
5. Series C sweep + governance record; §2.7/§2.1 and H11 updated with Series C evidence.

**Frozen claim language stands throughout:** B4 is the license; Series B S2 R alone does not reclaim boil-the-frog; full-sweep generalization is not earned until Series C demonstrates it under this design with attribution decomposition.
