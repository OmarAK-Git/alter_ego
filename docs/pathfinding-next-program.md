# ALTER_EGO — Pathfinding: eval kernel → usefulness → canary

**Date:** 2026-09-07  
**Status:** assessment + recommended program (docs only). Does **not** implement harness, knobs, ingest, or CI.  
**Companion (do not merge as a substitute):** [PR #5](https://github.com/OmarAK-Git/alter_ego/pull/5) `docs/canary-production-readiness.md` (draft, not on `main`).  
**Process analog:** praetor Approach A (`OmarAK-Git/praetor` PR #1) — same *sequence* (kernel → proof → readiness), different *product*. Do not copy cite-to-subject, FakeProvider, Vertex, or CBC-adapter language.

**One-line:** governance culture is real; the detector is not useful; the eval instrument cannot see the treatments it ranks; compose cannot host live shadow. Next ship is an E2E kernel that measures `new_build > old_build` on the **production call shape**, not another feature fold.

---

## Verdict on the prior readiness review

| Prior claim | This pass |
|---|---|
| Series I `calibrated: false` | **CONFIRMED.** Every Series I `*metrics.json`, `STATUS.md`, `state.json`. YAML has no `calibrated` key. |
| Precision ~0.007 @ thr=45 | **CONFIRMED for Series I** (`0.00684`, FP 7840, TP 54). **Stale elsewhere:** README / `docs/SPEC.md` / `docs/calibration_final_metrics.json` still publish Series A P≈0.019 / FP=3448 / S3=0.667. Do not mix series. |
| TP stuck at 54 | **CONFIRMED.** All 12 Series I metrics files. Per-scenario recalls bit-identical. FN=63 every run. |
| S3 recall ~0.11 | **CONFIRMED (Series I).** 5/45. `early_below_threshold_fraction=0.8889`. `attack_raised_cumulative_drift_max≈25.6` vs `drift_threshold: 5.0`. |
| One accept cut FP ~2% | **CONFIRMED as arithmetic** (7995→7840 = 1.94%). **Mechanism is broken** — see §C. |
| Shadow canary ~28, prod ~12, NO-GO | **CONFIRMED as PR #5's scored verdict**, not as a number in this tree. Scores are a rubric, not a measurement. The **NO-GO** conclusion is independently supported by this pass. |
| Detector not useful; runtime cannot host live shadow | **CONFIRMED.** P=0.0068 is not an operating point. Compose worker neither ingests nor profiles. |
| Do not run another feature-fold campaign | **CONFIRMED and strengthened.** Series I changed **zero detections**. |
| Top 5 blockers (unswept thr=45, usefulness, FP×block deadlock, no ingest/config plane, ops/auth) | **CONFIRMED**, with two deepenings below. |

**Do not rubber-stamp PR #5 on these two points:**

1. **`attack_event_count: 157` vs `tp+fn=117` is not a 25% missing-label hole.** S5 places quiet-gap events on `eval_scenario_5` without `is_malicious` (`tests/test_generator.py` `test_scenario_5_quiet_events_eval_partition_not_malicious`). Partition sum is 1+35+45+1+75=157; labeled malicious is 117; the 40 extras are S5 quiet. Recall denominator is labels (`batch/eval/runner.py` `is_malicious.is_(True)`). The real instrument bug is **naming**: `partition_check.attack_event_count` counts partition rows, not attack labels. Independent review defect B overstated this.

2. **`precision_gate` cannot honestly “cut FP” at thr=45.** Stage A is contracted **not** to change `is_anomaly` (`worker/scorer.py` `compute_signal_family_agreement`; design spec Phase 5). It gates containment at 85. Yet fold_06 was **accepted** on a thr=45 FP delta (`results/scoring-config-governance-series-i-fold_06_precision_gate.md`). That accept is a governance contradiction, not a usefulness win. The 155-FP movement is either an undocumented side-effect or a campaign confound; it is not Stage A's job.

---

## A. What ALTER_EGO actually is

Local-first **synthetic behavioral scorer** with a strong control-plane *culture* and a demo runtime. Auth + process JSONL → prefix resolver → DuckDB histograms → deterministic fusion score → insert-only decisions + analyst UI.

### Claims vs code

| Advertised | Class | Reality |
|---|---|---|
| UEBA / “catch compromised accounts before they cause damage” (GitHub description, `docs/SPEC.md` §1) | **PARTIAL / theater at the claim layer** | Real rarity+drift math on **synthetic** `user_*` / `svc_*` only. Two log types. Precision 0.7%. Not calibrated. |
| Deterministic score; LLM never scores | **REAL** | `worker/scorer.py`. Char 3-gram SHA-256 → 128-d (`worker/vectorizer.py`, `alter-ego-ngram-v1`). Heavily tested. |
| Immutable profiles | **REAL (payload)** | `ProfileArtifact` `frozen=True`. Builder inserts new rows + `superseded_at`. DB role: lifecycle-column UPDATE only. |
| `ProfileStore.promote_profile()` is the only promote path (`CLAUDE.md`) | **OVERSTATED** | Builder does insert+supersede (`batch/profile_builder/builder.py`). `promote_profile()` is a test helper (`worker/profile_store.py`). |
| Cumulative drift / boil-the-frog | **PARTIAL** | Accumulator is real. Series A S2 R=1.0 **retracted**. Series I S2=0.743, S3=0.111, 82% entities blocked. |
| Explain | **PARTIAL** | On-demand `POST /api/alerts/{id}/explain`. Default = template. LLM is optional post-hoc. SPEC §1 “queues with an LLM explanation” is false — scoring does not call the explainer. |
| Containment | **SIMULATED** | `action="simulate_containment"` queue row (`worker/recorder.py`). No IAM/EDR. |
| Ingest API (`docs/SPEC.md` §4.4, `docs/deployment.md`) | **MISSING** | No `/api/ingest`. JSONL CLI only (`worker/ingest.py`). Untested (`DEBT-039`). |
| Live enterprise ingest / SIEM | **MISSING** | Explicit v1 non-goal (`memory-bank/projectbrief.md`). Zero adapters. |
| Four-container “product” | **DEMO** | `docker-compose.yml`: worker = resolve+score loop; batch = `sleep infinity`; no ingest, no profile build, no scheduled audit. |
| Analyst SOC console | **PARTIAL / broken live** | Real tables + static UI. `web/static/app.js` never sends `X-API-KEY`. Privileged writes 401 in compose. GETs unauthenticated. |
| pgvector / embeddings | **PARTIAL** | 128-d hash vectors stored; score is in-process cosine, not ANN search. |
| Calibrated threshold | **MISSING** | YAML `anomaly_threshold: 45` unswept in Series I. No usable PR-curve point in artifacts. |
| Extra drift dims (cadence, geo-velocity, volume, fleet, staged) | **CODE-ON / CONFIG-OFF** | Implemented; `enabled: false` except `precision_gate.enabled: true`. |

**Honest docs already say not CALIBRATED.** The theater is SPEC §1 problem-statement register, “ingest API” packaging, UI chrome, and README still citing Series A as the saved operating point.

**What is actually good (keep):** fail-closed staleness + embedding-mismatch halts; insert-only decisions; hash-chained audit *records*; partition hygiene on S2/S3/S5; evidence-binding tests; “no knob without sweep” *culture* (OPS.md — not a CI gate); shadow profiles under alert-block.

---

## B. Production / canary call graph

There is **no `live/` package**. Two orchestrations share stages; only eval actually runs the full chain.

```
SYNTHETIC / EVAL (real, offline)              COMPOSE “RUNTIME” (incomplete)
batch/synthetic/generator  → JSONL            [MISSING: HTTP / SIEM / Kafka]
batch.eval.runner.run_pipeline                worker.ingest CLI (manual, not in compose)
  clear_db → ingest_events                    python -m worker.resolver          ← compose, 5s
           → process_unresolved_events        process_unscored_events()          ← compose, 5s
           → build_profiles(as_of=…)          build_profiles                     ← NOT in worker
           → process_unscored_events          batch: sleep infinity
                    ↓
              record_decision
                ├─ DecisionRecord (insert-only)     NO audit row on decision
                ├─ AlertWorkflowState "new" if is_anomaly   ← always; no shadow-score mode
                └─ containment_queue simulate_* if flag
              web/api triage / explain / workflow / contain / replay
```

| Stage | Status | Cite |
|---|---|---|
| Ingest | File loader only. `auth` \| `process`. Default partition `"production"`. | `worker/ingest.py` |
| Resolver | Prefix stub. `user_`→human 1.0, `svc_`→service 1.0, else `unknown` 0.5. | `worker/resolver.py:24-47` |
| Profile | Real DuckDB. **Not on the compose loop.** Shadows if entity blocked. | `builder.py`; `docker-compose.yml:37-57` |
| Score | Real. Skip if no active profile (fail-open coverage). Halt → score 0. | `worker/scorer.py` |
| Record | Real insert-only. **Every** `is_anomaly` opens workflow. | `worker/recorder.py:72-75` |
| Alert / workflow | Real SM + auto-resolve (QUIET∧ATTEST). | `web/api.py`, builder |
| Containment | Simulated only. Auto if score≥85 (+ Stage A agreement). | `recorder.py:7-18`, `scorer.py:768-781` |
| Explain | Click-to-generate; template fallback. | `web/api.py:343` |
| Audit | App-layer hash chain. Writers: clear, auto-resolve, build-block. **Not** `record_decision`. Integrity job exists, unscheduled; count check skipped when `decision_audit_count==0`. | `core/models.py`, `batch/audit_integrity.py` |
| Config | Live SoT = YAML file (`load_scoring_config`). `ConfigStore` is a sidecar the scorer never reads. `ScoringConfig` ≠ YAML (`DEBT-028`). | `worker/scorer.py`, `worker/config_store.py` |
| Auth | Writes: `X-API-KEY`. GETs: none. Pytest bypass in production function (`web/api.py:50-53`). UI omits header. Compose `API_KEY=dev-key`, DB `password`. | `web/api.py`, `docker-compose.yml` |

**Can it host live shadow traffic?** No, as shipped.

What would break: no adapters; unknown IDs → low-confidence / possible schema fail; no profile → silent skip; no scheduled builder → staleness halt fleet-wide in 14 days; every anomaly opens a workflow and freezes promotion; containment looks real and is not; alert GETs leak on :8000.

**Score-without-opening-workflows does not exist.** That is the canary precondition PR #5 named, and it is still unbuilt (Stage B, design spec Phase 5, explicitly deferred).

---

## C. Why evals did not buy FP reduction

Not “run more folds.” Series I was **mechanically sound and epistemically blind** (`.workflow/2026-08-02-series-i-serial-calibration/results/series-i-independent-review.md`).

### C1. The ranking axis cannot see the treatments

Campaign rank: `(F1, recall, −FP)` @ **45**, floors S1=S4=1.0.

`batch/eval/runner.py` intersects `score >= thr` with `is_malicious` labels. It does not rank `drift_alerts`, family agreement, containment deferral, or in-window promotion.

- `drift_alerts=31` vs `fp=7840`. F1 is point-rarity volume.
- S2/S3/S5 `drift_necessary_tp_fraction=1.0` — drift carries the attacks that matter and is **invisible** in the headline.
- Governance tables report S1 and S4: **one labeled event each**, `drift_necessary_tp_fraction=0.0`. Structurally incapable of discriminating drift features.

Inert-reject tolerance is FP **5**. Fleet/staged with identical F1/R/FP were “inert.” That phrase will be misread as “we tried fleet and it failed.” The measurement could not resolve them.

### C2. Stage A is the wrong lever for thr=45 FP

The only accept (`precision_gate.enabled=true`) gates **containment @ 85**, not workflow-opening @ 45. `open_active_alert_if_needed` still fires on every `is_anomaly`. Stage B (suppress single-family workflow-opening — the deadlock cut) is **unbuilt**.

Accepting a containment gate on a thr=45 FP ranking is how a 2% dip gets laundered into “progress.”

### C3. Coverage / block dominate the *level*

Series I accepted fold (`fold_06` / `ws_precision_gate` metrics):

| Quantity | Value |
|---|---|
| `promotion_coverage_in_window` | **0.454** |
| `stale_entity_days` | 550 / 1072 |
| `blocked_entity_count` | **53 / 65** (~82%) |
| `blocked_entity_days_estimate` | 714 |
| `auto_resolved_count` | 1755 |
| `active_alert_workflow_rows` | 6170 |

`blocked_filter` drops blocked entities from cohort histograms (`builder.py:654-664`). Constant across folds → comparisons unbiased, **levels** (R=0.46, S3=0.11) are coverage artifacts. Cadence aborted as cohort-constant (DEBT-078). `endpoint_set` drift **mean=max=0** on n=1300 while weighted 5.0 — shipped dimension contributing nothing.

R-INTERLOCK (S55) auto-resolves some FPs (`promotion_coverage_ever=1.0`) but does **not** clear the in-window / blocked-days problem. The deadlock topology remains: any ε>0 FP + §5.5 open-on-anomaly → freeze with probability →1 (`docs/residual-risk-drift-hypotheses.md` §2.1 / §2.7).

### C4. Threshold never left the unusable bin

Series I **never varied** `anomaly_threshold: 45`. All accepts/rejects are orderings inside P≈0.007.

Series A PR-curve (different topology — do not compare levels): best-F1 thr=55 is P=0.041 / FP=1136 — still not staffable; **not applied**. No saved curve has a SOC-viable point.

### C5. TP invariance is the finding

**No configuration under test changed a single detection.** That should have stopped the campaign on day one. Five folds ranked FP jitter at precision 0.7%.

S3: drift signal 5× threshold, 40/45 still missed, 89% `early_below_threshold`. Timing/gating/coverage, not a missing dimension. Series I spent a campaign proving it.

---

## D. Path-forward options that are not theater

### Rejected (do not staff)

| Path | Why it is theater |
|---|---|
| **Blind feature-fold campaign (Series J)** | Instrument cannot see treatments. TP frozen. Repeats Series I. |
| **Fake HTTP `/api/ingest` that is not `worker.ingest` → Event** | SPEC already advertises an ingest API that does not exist. A JSON wrapper that does not feed resolve→profile→score is a second intake type. |
| **Relabel compose + `scripts/demo_path.py` as “canary”** | Demo **INSERT**s a decision (`scripts/demo_path.py`, `tests/live/`). Not a scored event. Lab/demo already exists. |
| **UI polish / LLM explainer as the product** | Score path does not call the LLM. Template explain on a 145:1 FP queue is chrome. |
| **Wire `ConfigStore` to look governed without the scorer reading it** | Dual SoT (`DEBT-028`). Paper control plane. |
| **Promote cadence/geo/volume/fleet/staged because “code exists”** | Config-off for a reason. Null or inert under the current instrument. |
| **Copy praetor cite-to-subject / FakeProvider / Vertex cells** | Wrong product. ALTER_EGO's unmeasured layer is **detector usefulness**, not GenAI judgment. |
| **Staff “production readiness” now** | Praetor rule applies: readiness is conditional on a usefulness earn. PR #5 NO-GO is correct. |
| **Real IAM containment** | Explicit v1 non-goal. Do not add blast radius before precision exists. |

### Option 1 — Eval kernel (recommended first ship)

**What changes:** pytest-owned sibling of `batch/eval/runner.py` that **is** the production call (`ingest_events` → `process_unresolved_events` → `build_profiles` → `process_unscored_events` → `record_decision`). Scorecard schema. Initial 15 E2E IDs across five realms. CI runs the suite (not notebook, not “we have 50 unit files”). Theater-detector field required. Capability *quality* `new_build` is **pending** in this sprint — recorded, not passed.

**What it proves:** the project can measure `old_build` vs `new_build` on the real path, classify harness vs model vs theater, and refuse stipulated / n=1 / demo-INSERT “wins.”

**new > old:** kernel exists; all 15 IDs emit rows; gov/design/threat/usability both arms pass (must-not-regress); capability quality not marked pass; no silent skips. That is a harness earn, not a detector earn.

**Theater risk:** wrapping unit tests and calling them E2E; seeding `DecisionRecord` like `tests/web/`; scoring Fake/template explain as capability; putting S1/S4 n=1 in the decision criteria.

### Option 2 — Instrument + coverage repair (no new features)

**What changes:** name `attack_event_count` vs labels correctly; fix or quarantine `endpoint_set` zero-drift; report all five scenarios with `n`; split point-anomaly vs drift axes; if `tp` unchanged, verdict is “no detection effect.” Then raise in-window promotion (Stage B **or** score-without-workflow **or** attestation/lifecycle that actually unblocks) until coverage is near 1.0. Re-anchor baseline. **Then** sweep `anomaly_threshold` only.

**What it proves:** whether a usable precision exists *at all* on this generator, and whether S3's 25.6 drift / 0.11 recall is timing vs darkness.

**new > old:** (a) `endpoint_set` max>0 or explicit `wiring_failure` fail; (b) in-window coverage ≫ 0.454 with blocked-entity-days down; (c) PR-curve artifact where precision ≥ 0.1 **or** a written finding that no threshold reaches 0.1 (honest stop — outranks every flag).

**Theater risk:** sweeping thr=45 *before* coverage (re-ranks a half-dark system); calling Stage A a coverage fix.

### Option 3 — Usefulness proof (Stage B + attributed catch)

**What changes:** implement **score-without-opening-workflows** (or Stage B: single-family anomalies do not open §5.5 workflows). Primary metric: attributed S2/S3/S5 TP (`drift_necessary_tp_fraction` / B3a — causally traceable to the inject). Secondary: point-anomaly precision / workflow-open rate. Frozen before the sweep.

**What it proves:** drift can operate without the FP kill-switch; slow-roll / subtle / patient-cycle are catchable as *attacks*, not as harness artifacts.

**new > old:** paired old vs new on the same seed-42 corpus: attributed S3 recall up **and** workflow-open FP down, without S2/S5 attributed recall loss. Beating F1@45 while losing attributed S3 = fail (praetor stump-only analog).

**Theater risk:** counting auto_resolved as “we fixed FP”; raising threshold until S3 dies and calling it precision.

### Option 4 — Tiny real-or-replay shadow (only after 1–3)

**What changes:** JSONL mapper from **real** auth/process (or replayed production-shaped logs) on an **entity allowlist**; health endpoint; authenticated GETs; UI sends the API key; scheduled builder; score-without-block on by default. No IAM. No “ingest API” that isn't this path.

**What it proves:** the detector is interpretable on non-synthetic IDs without freezing the fleet.

**new > old:** allowlist scores land as decisions; workflow-open count is bounded by policy (not 6170); operator can tell worker-alive vs halt vs backlog from metrics.

**Theater risk:** HTTP POST that writes `EventModel` and never profiles; shadow that still opens workflows.

### Option 5 — Honest stop / portfolio-only

**What changes:** nothing in the detector. Align README/SPEC SoT to Series I; leave compose as a demo; do not claim canary.

**What it proves:** the repo stops lying about the operating point. Valid if Option 2's PR-curve finds no P≥0.1.

**new > old:** SPEC/README/metrics authority cite Series I and “not an operating point.” Theater risk: calling this “shipping v1.1.”

**Recommendation:** 1 → 2 → 3, then 4 only if 3 earns it. 5 is the off-ramp if 2's curve is empty.

---

## E. Eval gap map — five realms

Praetor pattern: three IDs per realm, production call shape, `old_build` vs `new_build`, required `theater_detector`. ALTER_EGO has **no** such kernel. Closest: `batch/eval/runner.py` (manual, `DEBT-041`), BTF fixtures (honest, often RED, no FP storm by construction), `tests/live/` (seeded HTTP).

`tests/` is dense (~50 `test_*.py`) and mostly **unit/invariant**. `test_simple_print.py` asserts `True`. CI is pytest-only (no ruff/mypy). Default suite skips `tests/live`.

### Capability

| Exists | Missing / theater |
|---|---|
| Sweep script + Series I JSON. BTF Layer B (`tests/test_boil_the_frog_invariants.py`) — B3a every TP drift-necessary. Generator partition tests. | Pytest never asserts S1–S5 recall. S1/S4 R=1.0 is n=1. S2 R=1.0 retracted. No CI attribution decomposition. Six-feature tests hack weights. |

**Candidate E2E (new > old):**

1. `cap.attributed_s3` — seed-42 S3: attributed TP (B3a) and recall; reject vacuous R=1.0. Sprint 1 `new_build` **pending**.
2. `cap.drift_vs_point_axes` — scorecard emits `drift_alerts` and point-anomaly FP separately; F1@45 is not the decision pin for drift treatments.
3. `cap.no_n1_headline` — theater pin: governance-style headline that only reports S1/S4 fails the suite.

### Governance

| Exists | Missing / theater |
|---|---|
| Frozen profile schema; audit hash chain; ConfigStore chain; staleness halt; embedding mismatch halt; S55 C1/C3/1F; shadow-under-block. | “No knob without sweep” is OPS.md, not CI. Frozen Pydantic ≠ SQL UPDATE rejected. Pytest auth bypass in `verify_api_key`. Audit job unscheduled. |

**Candidate E2E:**

1. `gov.no_knob_without_sweep` — YAML diff without a governance+metrics artifact → CI red (or an explicit `pending` exception list).
2. `gov.anomaly_opens_workflow` — production `record_decision` on a pipeline-scored anomaly opens `new`; a future Stage B arm must pin the *exception*, not delete this row.
3. `gov.integrity_job_sees_decisions` — after N recorded decisions, integrity path does not skip because `decision_audit_count==0`.

### Design

| Exists | Missing / theater |
|---|---|
| Evidence-binding reconstruct; scorer determinism; AST “scorer does not import GT”; ngram defaults; PIT profile; replay_run_id; as-of sim clock. | No AST/import guard that `score_event` never calls an LLM. No ingest tests. Resolver is prefixes. `ReplayRequest` config versions unused (`DEBT-057`). |

**Candidate E2E:**

1. `des.production_call_shape` — kernel invokes ingest→resolve→build→score→record (not INSERT decision). Missing stage = `harness` fail.
2. `des.no_llm_in_score` — import/AST guard: `worker/scorer.py` does not import explainer/LLM providers.
3. `des.ngram_mismatch_halts` — nomic metadata in an ngram fleet → score 0, not silent score.

### Threat

| Exists | Missing / theater |
|---|---|
| Explainer slot escape / prohibited content / queue overflow → template. Precision-gate unit. 1F FP-storm deadlock fixture. | No auth 401 test (pytest bypasses the lock). No malformed ingest. Containment never touches a control plane. No live-LLM jailbreak (optional, never a silent skip). |

**Candidate E2E:**

1. `thr.cmdline_injection_survives` — `IGNORE ALL RULES` in `command_line` through **ingest** → score path unchanged; explain slots escaped.
2. `thr.api_key_required` — missing/wrong `X-API-KEY` → 401 on workflow/contain/explain **without** pytest bypass (subprocess or isolated app).
3. `thr.fp_block_sanctuary` — old_build misses ladder under FP-block; new_build shadow-drift TPs with B3a (Stage B / score-without-block arm; Sprint 1 records old only).

### Usability

| Exists | Missing / theater |
|---|---|
| API tests on **seeded** decisions: list, ack, clear, suppressed, replay id. Demo path. Mandatory escalations. | No browser test. Demo/live skip the detector. No time-to-disposition vs 7840-FP reality. UI does not send API key. |

**Candidate E2E:**

1. `use.pipeline_to_triage` — pipeline-scored anomaly (not INSERT) appears on `/api/alerts`; contributions match evidence-binding.
2. `use.ui_sends_api_key` — static `app.js` includes the header or an explicit documented local-dev exception; privileged click cannot be a silent 401.
3. `use.demo_honesty` — README/SPEC/demo copy must not cite Series A as current or claim CALIBRATED / canary while Series I SoT is `calibrated: false`. Theater pin.

---

## F. Recommended program (praetor Approach A, adapted)

Praetor: eval kernel → **judgment** proof → production readiness (conditional).  
ALTER_EGO: eval kernel → **usefulness** proof → canary readiness (conditional).

Governance is already the mature layer (same as praetor's PolicyGate). Do not spend Sprint 1 “improving audit.” The unmeasured layer is **whether the detector is useful**.

| Sprint | Name | Ships | Does not ship | Exit |
|---|---|---|---|---|
| **1** | Eval kernel | E2E sibling of `batch/eval/runner.py`; scorecard; 15 IDs (§E); pytest + GitHub workflow on the **deterministic** path (no LLM required); theater detectors | Feature folds; YAML threshold change; HTTP ingest; ConfigStore hot-path; “we are useful” | Suite green; 15 rows; gov/des/thr/use both arms pass; capability quality `new_build` **pending**; `cap.no_n1_headline` + `use.demo_honesty` pass |
| **2** | Usefulness | Instrument+coverage (§D option 2) then Stage B / score-without-workflow; attributed S2/S3/S5 primary; point-precision secondary; `anomaly_threshold` sweep **after** coverage | New drift dimensions; canary; real containment; claiming P from Series A | Primary: attributed S3 (and S2/S5 held) **and** workflow-open FP down on paired old/new **or** honest stop if no thr reaches P≥0.1. F1@45-only win = fail |
| **3** | Canary readiness | Only if Sprint 2 earns it: allowlist JSONL/replay ingest on the **same** Event path; score-without-block default; `/health` + alert-volume; auth on GETs + UI key; scheduled builder + audit job; SoT scrub (SPEC/README → Series I) | Fake ingest API; K8s; IAM contain; “portfolio shipped ≈ canary” | Entered **only** after Sprint 2 earn. Shadow canary go-condition from PR #5, not a 28→50 points grind |

Sprint 2 cannot start until Sprint 1 is green. Sprint 3 cannot start until Sprint 2's **attributed-catch + deadlock-cut** (or the honest-stop write-up). Staffing Sprint 3 “anyway” is the praetor CBC-adapter mistake in this repo's clothing.

### Highest-leverage first ship

**Sprint 1 eval kernel.** Not a threshold tweak, not Stage B, not an ingest route.

Without it, every later change will be ranked the way Series I was: F1@45 on a half-dark fleet, S1/S4 as the headline, TP frozen, “inert” misread as “feature failed.”

Sprint 1 is allowed to look like “just tests.” That is the point. Praetor Sprint 1 does not claim judgment; this Sprint 1 does not claim detection.

### Locked non-goals (until an exit earns them)

- Another additive fold on cadence / geo / volume / fleet / staged
- `/api/ingest` that is not `ingest_events(Event JSONL)`
- Relabeling demo/live smoke as canary
- Applying thr=55 (or any thr) without a post-coverage PR curve + governance record
- Real containment
- Making LLM explain a merge gate
- Dual-writing YAML and `ConfigStore` without the scorer reading one SoT

### What this file authorizes

| Authorizes | Does not authorize |
|---|---|
| Writing a Sprint 1 implementation plan after owner review | Implementing the kernel in the same change |
| Treating `run_pipeline` as the production call shape | A second “eval envelope” or seeded-decision E2E |
| Pending capability quality in Sprint 1 | A Sprint 1 claim that the detector is useful |
| Sprint 3 only if Sprint 2 earns attributed catch + deadlock cut (or documents honest stop) | Canary work after another FP-jitter fold |

---

## G. Completeness

### Read (this pass)

- `docs/SPEC.md`, `docs/SPEC_V3.md` (headers/scope), `README.md`, `AS_BUILT.md`, `DEBT_LEDGER.md`, `OPS.md`, `docs/deployment.md`, `docs/residual-risk-drift-hypotheses.md` (§1–2), `memory-bank/{projectbrief,activeContext,tasks,progress}.md`
- `config/scoring_config.yaml` v2.2
- `docker-compose.yml`, `.github/workflows/ci.yml`
- `worker/{ingest,resolver,scorer,recorder,profile_store}.py` (hot path); `web/api.py` routes + `verify_api_key`; `web/static` (no `X-API-KEY`)
- `batch/eval/runner.py`, `batch/profile_builder/builder.py` (blocked_filter / promote), `batch/synthetic/generator.py` (S5 quiet)
- Series I: `STATUS.md`, `state.json` (spot), `results/series-i-independent-review.md`, `series_i_ws_precision_gate_metrics.json`, fold_06 governance
- Tests: tree via researcher; `tests/test_generator.py` S5 quiet; `tests/test_simple_print.py`; confirmed **no** pytest import of `batch.eval.runner` or `ingest_events`
- GitHub: PRs 1–5; **PR #5 full text** (`docs/canary-production-readiness.md` on `cursor/canary-production-readiness-8910`); praetor PR #1 Approach A spec
- `docs/superpowers/specs/2026-07-30-drift-detection-capability-expansion-design.md` Stage A/B

### Spot-checked, not fully re-derived

- All 12 Series I JSON files (TP=54 via prior review + one primary file)
- Alembic grant migration (trusted `AS_BUILT` / PR #5)
- Explainer / LLM provider internals
- Every `docs/scoring-config-governance-series-*.md`
- Scratch sweep launchers (ranking rule cited from independent review + `runner.py`)

### Not covered

- Re-running any sweep or pytest in this session (assessment, not verification of a code change)
- Browser pass of the UI (inferred 401 from missing header + `verify_api_key`)
- Live Vertex / RealLLMProvider behavior beyond docs
- Whether `unknown` entity_type fails Pydantic on resolve in current schemas (flagged, not executed)
- Full `DEBT_LEDGER` triage
- Merging PR #5 (left as the canary-score SoT; this file is the program SoT)

### SoT after this file

| Question | Authority |
|---|---|
| Canary/prod scores 28 / 12, go/no-go | PR #5 `docs/canary-production-readiness.md` |
| Latest detector numbers | Series I workflow metrics, **not** `docs/calibration_final_metrics.json` |
| Why folds did nothing | `series-i-independent-review.md` + §C here (with the 157/117 correction) |
| What to build next | **This file** |
| What is implemented | `AS_BUILT.md` wins over SPEC/CLAUDE |

Until Sprint 1 exists, “we evaluated it” means a script in `scratch/` and a JSON in `.workflow/`. That is not a gate.
