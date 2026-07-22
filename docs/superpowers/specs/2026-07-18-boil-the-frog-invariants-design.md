# Design: Honest boil-the-frog invariants (Design 1)

**Date:** 2026-07-18  
**T3 run:** `.workflow/2026-07-18-boil-the-frog-invariants/`  
**Status:** Spec approved for Step 3 (2026-07-18 amendments: padding cohort, declared constants, pinned A2, B1↔B3 linkage)  
**Companion:** `docs/residual-risk-drift-hypotheses.md` §2.6, H11; SPEC.md §6.4, §5.5  
**Rejected:** Design 3 (golden score dumps). **Deferred:** Design 2 metric-contract fields (Step 4).

---

## 0. Partition semantics (authoritative)

### 0.1 Decision (locked)

For **scenario_2_slow_roll** and **scenario_3_subtle**, attack-injected events **feed the profile builder** (historical window and 3-day recent drift window). Labels still mark malice; partition is **not** a training firewall for those scenarios.

Rationale: production telemetry does not strip attacker events before profiling. SPEC §5.5 active-alert build-blocking only makes sense if poisoning is possible. H1/H7 (absorption race) are otherwise unmeasurable. S3 multi-entity injects moving role medians is **honest** cohort dynamics (H2), not a sanitization bug.

S1 / S4 remain builder-excluded (sharp one-shots; baseline poisoning is not the phenomenon under test).

### 0.2 Scenario → builder visibility table

| Scenario id | Label in GT | Current inject partition (as of S1.1) | **Target: feeds builder?** | Rationale |
|---|---|---|---|---|
| `scenario_1_sharp_misuse` | `scenario_1_sharp_misuse` | `eval_scenario_1` | **No** | Single sharp event; point-detection eval; must not poison baselines |
| `scenario_2_slow_roll` | `scenario_2_slow_roll` | `eval_scenario_2` | **Yes** | Boil-the-frog / absorption race is the object of measurement |
| `scenario_3_subtle` | `scenario_3_subtle` | `eval_scenario_3` | **Yes** | Coordinated drift + cohort-median interaction (H2) requires shared telemetry |
| `scenario_4_service_abuse` | `scenario_4_service_abuse` | `eval_scenario_4` | **No** | Service periodicity break; point / periodicity features; not gradual absorption |
| `scenario_5_patient_cycle` | `scenario_5_patient_cycle` | `eval_scenario_5` | **Yes** | T-PATIENT close→promote cycling; ladder split across attestation quiet windows; feeds builder same rationale as S2. |
| Benign baseline / tooling rollout | (unlabeled) | `production` | **Yes** | Always |

**Implementation note (remediation, not this Step 3):** builder filters become scenario-aware (include `eval_scenario_2` / `eval_scenario_3` in hist+recent, or retag those injects onto a builder-visible partition while keeping GT labels). S1.1 tests that assert “S2/S3 never production” must be rewritten in the remediation packet — **not** in Step 3.

**Tribal-knowledge ban:** any future scenario (e.g. S5) must add a row to this table before inject code lands.

### 0.3 Metrics discontinuity (new baseline series)

Once S2/S3 feed the builder, **the entire sweep distribution shifts**: attack mass enters profiles, cohort medians move, benign events rescore, FP/precision/PR-curve all move.

| Series | Semantics | Artifacts |
|---|---|---|
| **Series A** (current saved) | Attack partitions excluded from builder | `docs/calibration_final_metrics.json`, `docs/calibration_pr_curve.json` (S3.1, seed 42) |
| **Series B** (post-remediation) | S2/S3 feed builder per §0.2 | New files / versioned names — **do not overwrite Series A without renaming** |

**Rule:** Cross-series comparisons are **invalid** (e.g. citing “FP dropped from 3448” across the semantics boundary as improvement/regression). The first Series B sweep **establishes a new baseline**; portfolio writeups must name the series. Same class of error as the retracted S2 boil-the-frog claim, one level up.

Step 3 tests do **not** refresh `calibration_*.json`.

---

## 1. Operational metrics (not narrative labels)

All quantities below are computable from events + ground truth + `ProfileArtifact` + `DecisionRecord` (sweep DB or in-memory fixture). Constants are **declared here**; tests import them from a single module or fixture YAML — no free-floating magic numbers in asserts.

### 1.1 Shared primitives

| Symbol | Definition | Value | Provenance |
|---|---|---|---|
| `anomaly_threshold` | From `config/scoring_config.yaml` | **45.0** | **Derived** from shipping config (not a judgment call in this spec) |
| `C_attack(e)` | Set of `process_name` values on GT-malicious events for entity `e` in the scenario under test | Derived | Observable |
| `M(P, C)` | Attack mass fraction in promoted profile `P`: \(\sum_{c \in C} h[c] / \max(1, \sum h)\) where `h = P.features["process_names"]` | Derived | Observable |
| `α` | Absorption mass threshold on `M(P, C_attack)` | **0.02** | **Declared, not derived** — judgment call. Anchor: “attack categories under 2% of process histogram mass in any promoted profile = not yet absorbed.” Chosen as clearly-above-one-off-count for warm baselines, clearly-below “baseline owns the attack.” Retunable; say so when changing. |
| `β` | Late-event `process_name_rarity` contribution_score floor | **0.5** | **Declared, not derived** — judgment call. Anchor: near-noise vs `anomaly_threshold=45` after rarity centering; “category no longer meaningfully point-scores.” Retunable. |
| `δ` | Min `cumulative_drift(attack) − cumulative_drift(control)` at fixture end | **1.0** | **Declared, not derived** — judgment call, **re-derived after padding-cohort fix**. Anchor: 20% of `drift_threshold=5.0`; clearly-material-but-far-from the ~2.25 drift-alone alert-crossing point. With ≥3 static same-role padders, role median is a benign anchor so Δ measures full attack accumulation (not the H3 half-signal pathology). Prior δ=0.5 assumed a 2-entity fixture that ate half the signal — superseded. Retunable with that arithmetic in mind. |

**Do not treat α, β, δ as calibrated or audit-grade.** They are pre-registered judgment calls so asserts cannot silently reinterpret thresholds.

### 1.2 `drift_necessary(D)` (boolean)

For DecisionRecord `D` with contributions list:

```
contrib_drift = contribution_score of feature_name == "drift_alert"  (0 if missing)
drift_necessary(D) ⇔ (D.score >= anomaly_threshold) ∧ (D.score - contrib_drift < anomaly_threshold)
```

### 1.3 `caught_before_absorption(e, run)` (boolean)

True iff there exists a DecisionRecord `D` such that **all** hold:

1. `D.entity_id == e`
2. `D` is either:
   - scored against a GT-malicious event for the scenario, **or**
   - a builder-emitted drift decision for `e` with `flags.drift_alert == true` and `D.timestamp` in `[t_attack_start, t_attack_end + recent_drift_window_days]`
3. `drift_necessary(D)` **or** (builder drift DecisionRecord with `flags.drift_alert`)
4. Let `P` be the `ProfileArtifact` with `P.profile_version == D.profile_version` for entity `e`. Then `M(P, C_attack(e)) < α`

**Interpretation:** Alarm fires while the scored/comparison profile still has &lt; 2% mass in attack-injected process categories.

### 1.4 `absorbed(e, run)` (boolean)

True iff **either**:

**(A) Histogram mass:** ∃ promoted `ProfileArtifact` `P` for entity `e` with `P.data_window_end ∈ [t_attack_start, t_attack_end + recent_drift_window_days]` and `M(P, C_attack(e)) ≥ α`

**or**

**(B) Late rarity collapse:** Let `E_late` = chronologically last `ceil(|E_attack|/3)` GT-malicious events for `e`. Median over `E_late` of `process_name_rarity.contribution_score` `< β`, **and** each of those decisions’ profile satisfies `M(P, C_attack(e)) ≥ α/2`.

**Interpretation:** Attack categories are in the baseline (A), or late attack steps no longer look rare against an already-poisoned profile (B).

### 1.5 Scenario-run headline (Series B / honest harness)

For an S2 (or S3) eval run under §0.2 Yes-feeds-builder semantics:

| Outcome | Predicate |
|---|---|
| Honest boil-the-frog **catch** | `caught_before_absorption` ∧ ¬(optional: require early days sub-threshold — see Layer B) |
| **Absorbed without catch** | `absorbed` ∧ ¬`caught_before_absorption` |
| Invalid / artifactual TP | Any TP with `drift_necessary` false **or** `drift_necessary` true but `M(P,C)≥α` at fire time (alarm after absorption) **or** drift not attack-attributable (Layer B #3) |

Headline recall **must not** be reported as “boil-the-frog caught” unless `caught_before_absorption` is true for the attack entity. (Design 2 will lift these into sweep-report fields; this spec defines the predicates first.)

---

## 2. Design 1 test suite

**File:** `tests/test_boil_the_frog_invariants.py`  
**Always-on** under default `pytest` (no skip-if-DB-missing, no `--live` gate).  
**Step 3 scope:** implement tests only; expect **red** against current generator + production-only builder. No remediation.

### 2.1 Layer A — scenario shape (static)

**Fixture artifact (required):** `tests/fixtures/boil_the_frog/s2_process_ladder.yaml`

```yaml
# Authoritative gradual ladder — tests read this file; comments are not the contract.
seed: 42
victim_role: Engineer
# Exact baseline family for the victim in the Layer A/B fixtures (not “typical role processes” in prose).
baseline_family:
  - explorer.exe
  - chrome.exe
  - teams.exe
  - git.exe
  - python.exe
  - docker.exe
  - kubectl.exe
# Declared ramp: each day_index maps to allowed process_name set (subset of baseline_family ∪ ladder_only).
# ladder_only names are optional mild extensions still treated as in-ladder for Assert A1.
ladder_by_day:
  0: [git.exe, python.exe]
  1: [python.exe, kubectl.exe]
  2: [kubectl.exe]
  3: [kubectl.exe]           # args/command_line escalate in inject; process stays in family
  4: [kubectl.exe]
  5: [kubectl.exe]
  6: [kubectl.exe]
ramp:
  # Quantity d(day) = mean over that day's attack events of
  #   cosine_distance(vectorize(command_line), baseline_centroid)
  # where baseline_centroid = L2-normalized mean of vectorize(f"{p} --silent")
  # for each p in baseline_family (fixture-defined; not live baseline traffic).
  early_late_split: thirds
  # early_days = day_index in [0, floor(n_days/3))
  # late_days  = day_index in [n_days - floor(n_days/3), n_days)
  # For n_days=7: early={0,1}, late={5,6}  (floor(7/3)=2)
  spearman_min: 0.60         # Spearman ρ(day_index, d(day)) over all days with ≥1 attack event
  early_late_gap_min: 0.05   # mean_{late} d(day) − mean_{early} d(day); same units as cosine distance [0,1]
  sharp_distance_floor: 0.50 # scorer emb contribution turns on at dist>0.50
```

**Baseline family (precise):** the exact `baseline_family` list in that YAML for the fixture victim — **not** inferred from `EntityProfile._get_role_processes` unless the fixture explicitly copies it. Layer A asserts read the YAML.

| ID | Assert | Expect vs current `inject_scenario_2_slow_roll` |
|---|---|---|
| **A1** | Every S2 attack event’s `process_name` ∈ `ladder_by_day[day_index]` (day_index = inject step 0..6) | **FAIL** (`powershell.exe` from step 0) |
| **A2** | See pinned procedure below | **FAIL** (sharp anti-loophole) |
| **A3** | Module references SPEC §6.4 + this spec path | Meta |

**A2 pinned procedure (exact):**

1. Build `baseline_centroid` as above from `baseline_family`.
2. For each `day_index` with attack events, compute `d(day)` = mean cosine distance of that day’s attack `command_line` vectors to `baseline_centroid`.
3. **Sharp anti-loophole (conjunctive / unconditional fail):** if `min_day d(day) > sharp_distance_floor` (0.50), **A2 fails** — regardless of whether either ramp branch would pass. This is **AND-not**: `(ramp_ok) ∧ ¬sharp`. Sharp alone fails the test.
4. Else ramp evidence (disjunction, burst-tolerant): pass if **either**
   - Spearman ρ(`day_index`, `d(day)`) ≥ `spearman_min` (0.60), **or**
   - `mean(d(late_days)) − mean(d(early_days)) ≥ early_late_gap_min` (0.05),
   with early/late windows as in the YAML (`thirds`, sizes `floor(n_days/3)`).

### 2.2 Layer B — score path (in-memory sqlite, always built)

#### Fixture bounds

| Bound | Value | Notes |
|---|---|---|
| Engine | `sqlite:///:memory:` | Same pattern as other unit tests |
| Seed | **42** | Fixed |
| Entities | **1 attack + 1 control + ≥3 benign padding**, all same role (`user_engineer_*` so `extract_role` → `engineer`) | Padding: static in-family behavior only. Satisfies `MIN_NORM_COHORT=3` so role median is a **stable benign anchor**, not the H3 2-entity midpoint pathology. Production cohort-normalization path stays intact. Novelty gate may still see `cohort_too_small_*` vs `min_cohort_size=10` — allowed. |
| Baseline | ≥ **5** production days of in-family process events; identical schedules across entities except id | Stable histograms |
| Tooling rollout | **Forbidden** | Structurally no inherited production drift |
| Attack | Current inject shape under test (today: powershell); cardinality **7 days × 5 bursts** (`FIXTURE_ATTACK_DAYS=7`, `FIXTURE_BURSTS=5`) | Mirrors original 35 events |
| Partition | Attack tagged `eval_scenario_2` (current inject behavior) | Under **current** builder, attacks invisible → B2 fails; after remediation visible |
| Control / padders | Baseline only; **no** attack inject | Control must not be contaminated by 2-entity median math |
| Profile builds | Daily `as_of` at end of each day in window | |
| Config | Load real `scoring_config.yaml` v2.2 (`anomaly_threshold=45`) | |
| Runtime budget | Prefer **&lt; 30s** wall | Shrink cardinality only via named constants if needed |

**Why not 1+1:** With only attack+control, `len(role)<3` → global median → `norm_drift(attack)=(raw_a−raw_c)/2` and control is pushed by the attack. B2 would measure the H3 pathology, not drift accumulation. Padding fixes that.

**Fixture limitation (documented 2026-07-18):** the fixture's all-green status (A1–B4 incl. B3b) is a **limitation as well as a license**. By construction there is no FP storm — tooling rollout is forbidden, padders are static, and no benign event scores anomalous — so §5.5 arming only ever blocks the attack entity *after* its own drift alarm (the containment case B3b tests). The fixture therefore **isolates the drift mechanism from the FP interaction** that dominates the full sweep: it cannot exhibit, and does not test, the residual-risk §2.7 deadlock (benign FP → permanent own-block → promotion freeze → scorer-visible drift 0). Series B showed that regime kills S2 event recall fleet-wide while this fixture stays green. Do not read fixture green as full-sweep evidence — that is exactly the B4-scope rule, now with a named mechanism on the other side of the gap.

#### Asserts

| ID | Assert | Expect (pre-remediation) |
|---|---|---|
| **B1** | Day-0 max **full** score (incl. drift) over attack events &lt; `anomaly_threshold`. | PASS on clean fixture (no inherited drift) |
| **B2** | `cumulative_drift(attack) − cumulative_drift(control) ≥ δ` (δ=1.0), padding cohort | FAIL while S2 invisible to builder |
| **B3** | **Non-vacuous:** `tp_count > 0`, else hard fail with message naming vacuity. Then every attack TP: `drift_necessary` ∧ `M&lt;α`. | FAIL (zero TPs → vacuity failure). Do **not** `pytest.skip` on vacuity — skip greens the suite. |
| **B4** | **Eventual detection:** within the fixture window, ≥1 of: (a) attack DecisionRecord with `drift_necessary` ∧ `M&lt;α`, or (b) builder-emitted drift `DecisionRecord` for the attack entity with `flags.drift_alert`. | FAIL until the engine actually catches the slow roll. **This is the only assert whose green licenses re-claiming “drift catches boil-the-frog.”** |

**B3 vacuity ban:** a silent forall-over-empty-TPs pass must not survive review. `tp_count > 0` is mandatory before the forall.

**B1↔B3↔B4 linkage (load-bearing):**
- B1 = early steps sub-threshold (day 0 only).
- B3 = every TP that does fire is honest (drift-necessary, pre-absorption) — and there is at least one TP.
- B4 = detection actually occurs (aggregate trajectory cashing out as a firing).
Do not delete B3 or B4 believing the other covers it. All-green without B4 would re-license the retracted claim after a generator/partition-only remediation that never proves detection.

**B4 fixture-length caveat (pre-registered knobs only):** B4 may stay red after correct generator+partition remediation if `FIXTURE_ATTACK_DAYS × FIXTURE_BURSTS` is too short for `cumulative_drift` to yield a drift-necessary TP at current YAML parameters. If so: **document as a finding** (engine cannot catch honest slow-roll at current knobs in this window) → entry for H4/H5/H10 research. Allowed retune knobs (spec + test constants together, with rationale — **never** silent green-hunt):

| Knob | Allowed? | Notes |
|---|---|---|
| `FIXTURE_ATTACK_DAYS` / `FIXTURE_BURSTS` | Yes, with written rationale | Extend window / densify ramp |
| Ladder ramp slope (command_line schedule in YAML/generator) | Yes, with rationale | Must still satisfy A2 (¬sharp ∧ ramp) |
| `δ`, `α`, `β`, `anomaly_threshold`, drift weights | **No** in this test cycle | S6.3 sweep + governance only |
| Loosening B4 predicate | **No** | |

**No-attack-drift contamination:** tooling rollout forbidden in fixture.

### 2.3 What Step 3 will **not** do

- Change `generator.py`, `builder.py`, partitions, or S1.1 tests  
- Refresh `docs/calibration_*.json`  
- Implement Design 2 report fields  
- Mark any invariant `xfail` / skip to greenwash  

---

## 3. Mapping to SPEC §6.4

| SPEC intent | Spec predicate / assert |
|---|---|
| Each step below flagging threshold | **B1** (day-0 &lt; thr); A2 anti-loophole rejects sharp shapes |
| Aggregate trajectory suspicious via cumulative drift | **B2** (accumulator moves) + **B4** (trajectory cashes out as a firing) |
| Not “learned into baseline before catch” | **B3** (`M&lt;α` at fire) + B4 pre-absorption clause |
| Cohort-normalized drift | Unchanged engine; S3 feeds builder so H2 is real |

---

## 4. Remediation (operator-approved order)

1. **Generator** — `inject_scenario_2_slow_roll` reads ladder YAML; A1/A2 green; no scoring/partition changes in this step.
2. **Partition** — builder hist+recent include `eval_scenario_2`/`eval_scenario_3` per §0.2; rewrite S1.1 tests to the table; B2 green target.
3. **Observe B4** — do not tune detection knobs; red B4 after 1–2 is a finding.
4. **Series B sweep** — new baseline artifacts; governance; §2.6/H11 rewrite; no cross-series FP comparisons.

---

## 5. Step 4 follow-on (logged; not this cycle)

- Design 2 fields: `early_below_threshold_fraction`, `drift_necessary_tp_fraction`, `attack_raised_cumulative_drift`, plus `caught_before_absorption` / `absorbed`
- Governance: headline recall requires inject-attributable decomposition

---

## 6. Assert contract summary

| ID | Contract |
|---|---|
| A1 | `process_name ∈ ladder_by_day[day]` from YAML |
| A2 | Pinned `d(day)`; pass iff `¬sharp ∧ (ρ≥0.60 ∨ gap≥0.05)`; sharp unconditional fail |
| B1 | Day-0 max full score &lt; 45 |
| B2 | Δ cum_drift ≥ δ=1.0 with padding cohort |
| B3 | `tp_count > 0` (non-vacuous) ∧ every TP drift-necessary ∧ pre-absorption |
| B4 | ≥1 drift-necessary pre-absorption TP **or** builder drift DecisionRecord on attack entity — licenses the boil-the-frog claim |

Constants α/β/δ declared-not-derived (§1.1). Fixture retune knobs for B4 length pre-registered above — not detection YAML.
