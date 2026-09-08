# alter_ego multi-sprint design: Eval kernel → Usefulness → Canary

**Date:** 2026-09-08
**Status:** ratified for planning (Approach A adapted; design approved section-by-section with Omar)
**Author note:** Omar locked every section below before this file was written. This document records that approval. It does not implement harness code, scenarios, or CI.
**Scope of this file:** design only. An implementation plan is a later artifact, after the owner reviews this file.

**Usefulness path under test (Sprint 2+):** deterministic behavioral scoring on the production offline call (`ingest_events` → `process_unresolved_events` → `build_profiles` → `process_unscored_events` → `record_decision`). The unmeasured layer is **whether the detector is useful**, not GenAI judgment. Do not copy praetor cite-to-subject, FakeProvider, Vertex, CBC-adapter, or `AlertEnvelope` language into this program.

**Companions (do not treat this file as a substitute):**

- [PR #5](https://github.com/OmarAK-Git/alter_ego/pull/5) `docs/canary-production-readiness.md` — canary-score SoT (shadow 28 / prod 12, **NO-GO**).
- [PR #6](https://github.com/OmarAK-Git/alter_ego/pull/6) `docs/pathfinding-next-program.md` — program SoT that this design ratifies.

---

## 1. Context and problem

ALTER_EGO is a local-first **synthetic behavioral scorer** with a strong control-plane *culture* and a demo runtime. Auth + process JSONL → prefix resolver → DuckDB histograms → deterministic fusion score → insert-only decisions + analyst UI. Governance records, fail-closed staleness, immutable profile payloads, and “no knob without sweep” culture are real. The detector is not useful. Compose cannot host live shadow.

Series I (2026-08-03, `.workflow/2026-08-02-series-i-serial-calibration/STATUS.md`) is the current detector SoT. It is **`calibrated: false`**. Headline after the only accepted fold (`precision_gate.enabled=true`):

| Metric @ `anomaly_threshold=45` | Series I accepted |
|---|---|
| Precision | **0.00684** (P≈0.007) |
| Recall | **0.462** |
| F1 | **0.0135** |
| TP / FP / FN | **54 / 7840 / 63** |
| S1 / S2 / S3 / S4 / S5 recall | 1.0 / 0.743 / **0.111** / 1.0 / 0.60 |

TP is **54 on every Series I run**. Per-scenario recalls are bit-identical. FN=63 every run. Treatments did not change a single detection. PR #5 scored shadow canary **28/100** and production **12/100** — **NO-GO / NO-GO**. That verdict stands. Do not staff canary or prod from this tree.

README / `docs/SPEC.md` / `docs/calibration_final_metrics.json` still publish Series A (P≈0.019, FP=3448, S3=0.667). Those numbers are archival. Do not mix series.

### Two corrections vs PR #5 (do not rubber-stamp)

1. **`attack_event_count: 157` vs `tp+fn=117` is naming, not a 25% missing-label hole.** S5 places quiet-gap events on `eval_scenario_5` without `is_malicious` (`tests/test_generator.py` `test_scenario_5_quiet_events_eval_partition_not_malicious`). Partition sum is 1+35+45+1+75=157; labeled malicious is 117; the 40 extras are S5 quiet. Recall denominator is labels (`batch/eval/runner.py` `is_malicious.is_(True)`). The instrument bug is that `partition_check.attack_event_count` counts partition rows, not attack labels.

2. **`precision_gate` Stage A cannot honestly be an FP win at thr=45.** Stage A is contracted **not** to change `is_anomaly` (`worker/scorer.py` `compute_signal_family_agreement`; design spec Phase 5). It gates containment at 85. `open_active_alert_if_needed` still fires on every `is_anomaly` (`worker/recorder.py`). Yet fold_06 was **accepted** on a thr=45 FP delta (7995→7840) in `results/scoring-config-governance-series-i-fold_06_precision_gate.md`. That accept is a **governance contradiction**, not a usefulness win. The 155-FP movement is either an undocumented side-effect or a campaign confound; it is not Stage A's job.

### Why the last campaign could not buy usefulness

Series I ranked `(F1, recall, −FP)` @ **45**. `batch/eval/runner.py` intersects `score >= thr` with `is_malicious` labels. It does not rank `drift_alerts`, family agreement, containment deferral, or in-window promotion.

- `drift_alerts=31` vs `fp=7840`. F1 is point-rarity volume.
- S2/S3/S5 `drift_necessary_tp_fraction=1.0` — drift carries the attacks that matter and is invisible in the headline.
- Governance tables report S1 and S4: **one labeled event each**. Structurally incapable of discriminating drift features.
- `promotion_coverage_in_window=0.454`; `blocked_entity_count=53/65` (~82%). Levels (R=0.46, S3=0.11) are coverage artifacts.
- `endpoint_set` drift mean=max=0 on n=1300 while weighted 5.0 — shipped dimension contributing nothing.
- `anomaly_threshold: 45` was **never swept** in Series I. All accepts/rejects are orderings inside P≈0.007.

There is **no gating E2E eval kernel**. Closest objects: `batch/eval/runner.py` (manual, `DEBT-041` — no pytest ownership), BTF fixtures (honest, often RED, no FP storm by construction), `tests/live/` (seeded HTTP). `tests/` is dense and mostly unit/invariant. CI is pytest-only. Until a kernel exists, “we evaluated it” means a script in `scratch/` and a JSON in `.workflow/`. That is not a gate.

The actual gap is operational, not typological: there is no kernel that (a) runs the production offline call across five product realms, (b) compares `old_build` vs `new_build`, (c) refuses to call a seeded `DecisionRecord`, an n=1 S1/S4 headline, or a demo INSERT a “detection win,” and (d) only then funds a usefulness experiment whose primary is **attributed S2/S3/S5 catch plus a deadlock cut**. After that experiment — and only if the primary is earned — canary readiness.

---

## 2. Goals and non-goals

### Goals

Run **Approach A adapted** as three sequential sprints:

1. **Eval kernel.** Ship an E2E harness (pytest-owned sibling of `batch/eval/runner.py`) and the initial 15-scenario set across five realms (capability, governance, design, threat, usability). Every scenario records `old_build` vs `new_build`. GitHub Actions owns the suite. Fixtures are deterministic. Live SIEM and live LLM are not merge gates.
2. **Usefulness proof.** Instrument the ranking axis, then raise in-window coverage (Stage B / score-without-workflow), then sweep `anomaly_threshold` only. Primary = attributed S2/S3/S5 TP. Secondary = point-anomaly precision / workflow-open rate. A clean negative (no threshold reaches P≥0.1) is a successful sprint (honest stop). An F1@45-only “win” is a fail.
3. **Canary readiness.** Only if Sprint 2 earns attributed catch **and** the deadlock cut. Allowlist JSONL/replay on the **same** Event path, score-without-block default, health + alert-volume, authenticated GETs + UI key, scheduled builder + audit job, SoT scrub. Not a fake ingest API and not a 28→50 points grind.

### Hard non-goals

| Non-goal | Why it is closed |
|---|---|
| **Series J** (another additive feature-fold campaign on cadence / geo / volume / fleet / staged) | Instrument cannot see treatments. TP frozen. Repeats Series I. |
| Fake HTTP `/api/ingest` that is not `worker.ingest` → `Event` | SPEC already advertises an ingest API that does not exist. A JSON wrapper that does not feed resolve→profile→score is a second intake type. |
| Relabeling compose + `scripts/demo_path.py` as “canary” | Demo **INSERT**s a decision. Not a scored event. Lab/demo already exists. |
| Copying praetor cite-to-subject / FakeProvider / Vertex cells | Wrong product. ALTER_EGO's unmeasured layer is **detector usefulness**, not GenAI judgment. |
| Staffing “production readiness” / canary now | Praetor rule applies: readiness is conditional on a usefulness earn. PR #5 NO-GO is correct. |
| Real IAM / EDR containment | Explicit v1 non-goal. Do not add blast radius before precision exists. |
| Making LLM explain a merge gate | Score path does not call the explainer. Template explain on a 145:1 FP queue is chrome. |
| Dual-writing YAML and `ConfigStore` without the scorer reading one SoT | Dual SoT (`DEBT-028`). Paper control plane. |
| Promoting cadence/geo/volume/fleet/staged because “code exists” | Config-off for a reason. Null or inert under the current instrument. |
| Applying thr=55 (or any thr) without a post-coverage PR curve + governance record | Series A thr=55 is a different topology and still P=0.041. OPS no-knob-without-sweep stands. |
| Claiming the detector is useful in Sprint 1 | Sprint 1 is a harness earn. Capability quality `new_build` is `pending`. |
| Starting Sprint 3 before Sprint 2 earns it | Canary is conditional. Honest stop if no threshold reaches P≥0.1. |
| Treating Stage A `precision_gate` as an FP or coverage win at thr=45 | Governance contradiction. Stage A gates containment @ 85. |
| Putting S1/S4 n=1 in decision criteria | Structurally incapable of discriminating drift. Theater pin `cap.no_n1_headline`. |

---

## 3. Program shape

Praetor: eval kernel → **judgment** proof → production readiness (conditional).
ALTER_EGO: eval kernel → **usefulness** proof → canary readiness (conditional).

Governance is already the mature layer. Do not spend Sprint 1 “improving audit.” The unmeasured layer is whether the detector is useful.

| Sprint | Name | Ships | Does not ship | Exit |
|---|---|---|---|---|
| **1** | Eval kernel | E2E sibling of `batch/eval/runner.py`; scorecard schema; 15 IDs (§5); pytest + GitHub Actions on the **deterministic** path (no LLM required); theater detectors | Feature folds; YAML threshold change; HTTP ingest; ConfigStore hot-path; “we are useful”; Series J | Suite green; 15 rows; gov/des/thr/use both arms pass (except `thr.fp_block_sanctuary` `new_build` pending); capability quality `new_build` **pending**; `cap.no_n1_headline` + `use.demo_honesty` pass |
| **2** | Usefulness | Instrument + coverage (§6: name the denominator, quarantine zero-drift, split axes) **then** Stage B / score-without-workflow **then** `anomaly_threshold` sweep; attributed S2/S3/S5 primary; point-precision / workflow-open secondary | New drift dimensions; canary; real containment; claiming P from Series A; F1@45 as the decision pin | Primary: attributed S3 up **and** S2/S5 held **and** workflow-open FP down on paired old/new, **or** honest stop if no thr reaches P≥0.1. F1@45-only win = fail |
| **3** | Canary readiness | Only if Sprint 2 earns it: allowlist JSONL/replay ingest on the **same** Event path; score-without-block default; `/health` + alert-volume; auth on GETs + UI key; scheduled builder + audit job; SoT scrub (SPEC/README → Series I) | Fake ingest API; K8s; IAM contain; “portfolio shipped ≈ canary”; 28→50 rubric grind | Entered **only** after Sprint 2 earn. Shadow canary go-condition from PR #5, not a points chase |

Sprint 2 cannot start until Sprint 1 exit is green. Sprint 3 cannot start until Sprint 2’s **attributed-catch + deadlock-cut** is earned. An honest-stop write-up is a successful Sprint 2 and **does not** authorize Sprint 3. Staffing Sprint 3 “anyway” is the praetor CBC-adapter mistake in this repo's clothing.

Sprint 1 is allowed to look like “just tests.” That is the point. Praetor Sprint 1 does not claim judgment; this Sprint 1 does not claim detection.

---

## 4. Harness architecture

### Placement

Add a pytest-owned sibling `batch/eval/e2e_kernel.py` next to `batch/eval/runner.py`. The kernel **imports and calls** `run_pipeline`. It does not reimplement ingest, resolve, build, score, or record. Rules:

- The production call shape is the **real offline path**: `batch/synthetic/generator` (or a frozen JSONL fixture that generator already emits) → `run_pipeline` (`ingest_events` → `process_unresolved_events` → `build_profiles` → `process_unscored_events` → `record_decision`).
- Do not grow a second “eval envelope.” Do not INSERT `DecisionRecord` and call it E2E (`tests/web/` and `scripts/demo_path.py` are not this path).
- Do not invent an HTTP ingest for the kernel. JSONL on disk is the intake. That is what `worker.ingest` actually is.
- Existing unit/invariant tests stay. The kernel **extends** them; it does not absorb or weaken them.
- `DEBT-041` is the nearby gap (no pytest ownership of `batch/eval/{runner,calibrate,rescore,report,analyze_misses}.py`). Sprint 1 gives pytest ownership of the **production call shape** via the kernel. Closing every file in that brace list is not a Sprint 1 exit requirement.

### Scorecard schema

Every scenario × arm emits one scorecard row. Schema is JSON, `additionalProperties: false`, written by the harness (never by the scenario asserting its own grade).

| Field | Type | Meaning |
|---|---|---|
| `schema_version` | `"1"` | Scorecard version. Bump only if columns change. |
| `scenario_id` | string | One of the 15 IDs in §5. |
| `realm` | `capability` \| `governance` \| `design` \| `threat` \| `usability` | Realm bucket. |
| `arm` | `old_build` \| `new_build` | Which wiring ran. |
| `status` | `pass` \| `fail` \| `pending` \| `error` | `pending` is legal **only** for capability **quality** `new_build` (`cap.attributed_s3`, `cap.drift_vs_point_axes`) and `thr.fp_block_sanctuary` `new_build` in Sprint 1. |
| `failure_class` | `none` \| `harness` \| `scorer` \| `theater_detector` | Required when `status` is `fail` or `error`. `none` when `pass` or `pending`. |
| `expected` | object | Frozen scenario expectation (pin / join / counts). |
| `observed` | object | What the pipeline actually produced. |
| `fixture` | `deterministic` | Only legal value. FakeProvider is N/A. Live SIEM / live LLM are not scorecard providers. |
| `notes` | string | Short, optional. Never used as a skip reason. |

`pending` is an explicit scorecard state, not a skip. A missing row is a **harness** failure.

ALTER_EGO scoring is deterministic (char 3-gram SHA-256 → 128-d, `alter-ego-ngram-v1`). There is no FakeProvider in this product. Stipulating a score in the fixture and grading that stipulation as capability is `theater_detector`.

### Scenario contract

New E2E scenarios live under `tests/eval/scenarios/` (or equivalent pytest-discovered tree). Required fields:

| Field | Required | Meaning |
|---|---|---|
| `schema_version` | yes | `"1"` |
| `scenario_id` | yes | Exact ID from §5. Filename stem matches. |
| `realm` | yes | One of the five realms. |
| `description` | yes | One sentence: what pin this scenario enforces. |
| `runner` | yes | Always `e2e_kernel`. The kernel may *call* `run_pipeline` or a named existing invariant helper internally; the scorecard row is still an E2E row. |
| `setup` | yes | Production call shape: JSONL events + GT side table (or generator seed + scenario list that emits those files) → `run_pipeline`. **No HTTP ingest. No seeded `DecisionRecord`. No LLM provider.** |
| `arms` | yes | Map of `old_build` / `new_build` → `{ expected, fixture: deterministic }`. |
| `scorecard_pins` | yes | Which observed fields are compared. |
| `theater_detector` | yes | One named check from the list in §8. Cannot be omitted. |

`setup` is the production call. A fixture that already goes through `run_pipeline` **is** that shape; reuse it. Do not invent a parallel eval intake.

### Old vs new wiring per realm

| Realm | Sprint 1 `old_build` | Sprint 1 `new_build` | Sprint 2 |
|---|---|---|---|
| **Capability** | Current `run_pipeline` on seed-42 (or the pinned fixture). Quality score recorded, not claimed. `cap.no_n1_headline` must `pass`. | Quality arms **pending.** Do not treat “we emitted a recall number” as a pass. Theater pin must `pass` (same as old). | Quality `new_build` = instrumented axes + Stage B / score-without-workflow + post-coverage threshold (§6). |
| **Governance** | Current §5.5 open-on-anomaly, OPS no-knob-without-sweep culture, audit-integrity skip behavior — pinned as tests. | Same pins. **Must not regress.** | Stage B may add an **explicit exception pin** on `gov.anomaly_opens_workflow`; it must not delete the row. |
| **Design** | Production call shape, no LLM in `score_event`, ngram-mismatch halt. | Same. **Must not regress.** | Same. |
| **Threat** | Cmdline injection survives ingest; API key required without pytest bypass; FP-block sanctuary `old_build` recorded. | Cmdline + API-key **must not regress.** `thr.fp_block_sanctuary` `new_build` is **pending** (Stage B unbuilt). | `thr.fp_block_sanctuary` `new_build` = shadow-drift TPs with B3a under score-without-block. |
| **Usability** | Pipeline-scored anomaly reaches `/api/alerts`; UI key honesty; demo honesty. | Same. **Must not regress.** `use.demo_honesty` both arms `pass`. | Same, plus SoT scrub if Sprint 2 honest-stops. |

`old_build` means “the tree as of the Sprint 1 baseline commit” (or an explicit checkout / import of that behavior). `new_build` means “this PR / this branch.” In Sprint 1, for non-capability realms (except `thr.fp_block_sanctuary`), `new_build` is the same code path as `old_build` plus the new harness — the comparison is “did adding the kernel regress the pin.”

### Providers / fixtures

| Mode | When | Gate |
|---|---|---|
| Deterministic fixtures / generator JSONL | Default local + default CI | **Merge gate.** No API key. No LLM. Seed pinned (seed **42** for corpus-scale capability rows). |
| Live SIEM / Kafka / HTTP ingest | Not in this program until Sprint 3, and only then as allowlist JSONL/replay on the same Event path | **Not** a merge gate. Not a Sprint 1 object. |
| Live LLM / Vertex / explainer | Opt-in operator only; never required | **Not** a merge gate. Failures classify as `harness` or are out of suite. Never a silent skip. Template explain is not a capability score. |

FakeProvider is **N/A**. Do not add one. The scorer is already deterministic.

### CI

Today’s GitHub Actions (`.github/workflows/ci.yml`) runs `pytest -v --tb=short` on 3.11/3.12/3.13. Live HTTP smoke is opt-in and skipped by default. That is not an eval kernel: pytest never asserts S1–S5 recall, never imports `batch.eval.runner`, never calls `ingest_events`.

Sprint 1 makes **GitHub Actions own the suite**:

1. Install `.[dev]`.
2. Run default `pytest` (existing unit/invariant suite, `tests/live` still skipped unless opted in).
3. Run the E2E kernel suite (pytest module that executes all 15 IDs and writes the scorecard).
4. Fail the job on any `fail` / `error` scorecard row, and on any missing row.
5. Do **not** require a live SIEM, a live LLM, or Vertex.
6. Do **not** treat `scripts/demo_path.py`, `tests/live/`, or a notebook as a substitute for the suite.

Existing CI may remain. It is not the gate for this program unless it actually runs the 15-ID kernel and fails on missing rows.

---

## 5. Initial E2E scenario set

Fifteen IDs, three per realm. Short descriptions are the pin. Do not add a sixteenth in Sprint 1. IDs are locked from the approved §3 / PR #6 gap map.

### Capability

| ID | Pin |
|---|---|
| `cap.attributed_s3` | Seed-42 `scenario_3_subtle`: attributed TP via B3a / `drift_necessary` (Design 1 §1.2: `score >= anomaly_threshold` ∧ `score - contrib_drift < anomaly_threshold`) and recall. Reject vacuous R=1.0. Sprint 1 `new_build` is `pending`. This row exists so Sprint 2 has a paired baseline, not so Sprint 1 can claim usefulness. |
| `cap.drift_vs_point_axes` | Scorecard emits `drift_alerts` and point-anomaly FP as **separate** observed fields. F1@45 is recorded and is **not** the decision pin for drift treatments. Sprint 1 `new_build` is `pending` on the quality comparison; emitting the split fields on `old_build` is required. |
| `cap.no_n1_headline` | Theater pin: a governance-style headline that only reports S1/S4 (n=1 each) fails the suite (`failure_class=theater_detector`). Both arms `pass` in Sprint 1 if the kernel refuses that headline. |

### Governance

| ID | Pin |
|---|---|
| `gov.no_knob_without_sweep` | A YAML weight/threshold/`enabled` diff without a paired governance record + metrics artifact → CI red (or an explicit, reviewed `pending` exception list in the kernel, never a silent skip). Pins the OPS.md standing rule as a test, not a culture note. |
| `gov.anomaly_opens_workflow` | Production `record_decision` on a **pipeline-scored** anomaly opens `AlertWorkflowState` `new`. A future Stage B arm must pin the *exception* (single-family does not open), not delete this row. |
| `gov.integrity_job_sees_decisions` | After N recorded decisions from `run_pipeline`, `batch/audit_integrity.py` does not skip because `decision_audit_count==0`. `record_decision` today writes no audit row; this pin makes that skip visible as `fail` / `harness` until the path is honest or fixed. Sprint 1 may `pass` by asserting the skip is **detected and named**, not by pretending the job already sees decisions. |

### Design

| ID | Pin |
|---|---|
| `des.production_call_shape` | Kernel invokes ingest→resolve→build→score→record (not INSERT decision). A missing stage is `failure_class=harness`. |
| `des.no_llm_in_score` | Import/AST guard: `worker/scorer.py` does not import explainer or LLM providers. A new import is `theater_detector`. |
| `des.ngram_mismatch_halts` | Nomic (or any non-`alter-ego-ngram-v1`) metadata in an ngram fleet → score 0 + halt flag, not a silent score. Existing S5.9 contract, pinned as an E2E row. |

### Threat

| ID | Pin |
|---|---|
| `thr.cmdline_injection_survives` | `IGNORE ALL RULES` (or equivalent) in `command_line` through **ingest** → score path unchanged; explain slots escaped if explain is invoked. Structural half is deterministic; live-model half is opt-in and never a silent skip. |
| `thr.api_key_required` | Missing/wrong `X-API-KEY` → 401 on workflow/contain/explain **without** the `pytest` `sys.modules` bypass (`web/api.py` `verify_api_key`). Subprocess or isolated app. |
| `thr.fp_block_sanctuary` | `old_build` misses the ladder under FP-block (Design 1 / S55 T-PATIENT P0). `new_build` is Stage B / score-without-block: shadow-drift TPs with B3a. Sprint 1 records `old_build` only; `new_build` is `pending`. |

### Usability

| ID | Pin |
|---|---|
| `use.pipeline_to_triage` | A pipeline-scored anomaly (not INSERT) appears on `GET /api/alerts`; contributions match the evidence-binding reconstruct contract. Seeded-decision list/ack tests are not this row. |
| `use.ui_sends_api_key` | Static `web/static/app.js` includes the `X-API-KEY` header, **or** an explicit documented local-dev exception is pinned and the privileged click cannot be a silent 401. Today the UI omits the header — Sprint 1 `pass` is “the kernel names this,” not “we shipped the header.” Shipping the header is allowed in Sprint 1 if it does not expand scope past the pin. |
| `use.demo_honesty` | README / SPEC / demo copy must not cite Series A as current, and must not claim CALIBRATED or canary while Series I SoT is `calibrated: false`. Theater pin. Both arms `pass` in Sprint 1 if the kernel refuses those claims. |

### Sprint 1 exit criteria for the set

1. All **15** IDs exist as scenario files and appear in the scorecard. Zero silent omissions.
2. GitHub Actions runs the suite on deterministic fixtures and fails the job on `fail` / `error` / missing row.
3. Governance, design, threat (except `thr.fp_block_sanctuary` `new_build`), and usability: `old_build` and `new_build` both `pass` (must-not-regress), with the honesty pins in `gov.integrity_job_sees_decisions` and `use.ui_sends_api_key` as specified above.
4. Capability quality arms (`cap.attributed_s3`, `cap.drift_vs_point_axes`): `old_build` recorded; `new_build` is `pending` (not `pass`). `cap.no_n1_headline` is a theater pin: both arms `pass` in Sprint 1 if S1/S4-only headlines are rejected (no pending).
5. `thr.fp_block_sanctuary` `new_build` is `pending`. `use.demo_honesty` both arms `pass`.
6. No scenario adds `/api/ingest`, a FakeProvider, a live SIEM adapter, or a Series J fold.
7. Scorecard `failure_class` is populated on every fail/error. Theater-detector trips are visible, not folded into `scorer`.

---

## 6. Sprint 2 — usefulness experiment

Entered only after Sprint 1 exit. This is the measurement sprint. It may conclude “still no useful operating point.” That is a success if the protocol was honest.

Sequence is locked: **instrument → Stage B / score-without-workflow → threshold sweep.** Do not invert it. Sweeping thr=45 before coverage re-ranks a half-dark system.

### In scope

1. **Instrument (no new features).**
   - Name `attack_event_count` vs labels correctly (157 partition rows ≠ 117 attack labels; S5 quiet is not a hole).
   - Fix or quarantine `endpoint_set` zero-drift (mean=max=0, weight 5.0). Quarantine is an explicit `wiring_failure` fail on the scorecard until max>0 or the dimension is disabled in YAML **with** a governance record.
   - Report all five scenarios with `n`. S1/S4 n=1 stays visible and is banned from headlines (`cap.no_n1_headline`).
   - Split point-anomaly vs drift axes (`cap.drift_vs_point_axes`). If `tp` is unchanged across a treatment, the verdict is **“no detection effect,”** not “inert feature.”
2. **Coverage / deadlock cut.** Implement **score-without-opening-workflows** or **Stage B** (single-family anomalies do not open §5.5 workflows — the cut Phase 5 deferred). Raise in-window promotion coverage well above 0.454 and cut blocked-entity-days. Re-anchor a baseline on the same seed-42 corpus **after** coverage moves. Calling Stage A a coverage fix is `theater_detector`.
3. **Threshold sweep after (1) and (2).** Sweep `anomaly_threshold` only. Record a PR-curve artifact. OPS no-knob-without-sweep applies: the chosen thr gets a governance record. Series A thr=55 is not pre-authorized.

### Out of scope

Series J · new drift dimensions · `/api/ingest` · canary · real containment · ConfigStore hot-path · claiming P from Series A · making LLM explain a gate · starting Sprint 3 on an F1@45 dip · treating fold_06's 7995→7840 as the baseline “win.”

### Arms (locked)

| Arm | Wiring | Primary score | Secondary score |
|---|---|---|---|
| `old_build` | Sprint 1 production call; current YAML (`precision_gate.enabled=true`, other new dims off); every `is_anomaly` opens workflow | Attributed S3 / S2 / S5 TP (B3a / `drift_necessary_tp_fraction`) on seed-42 | Point-anomaly FP; workflow-open count |
| `new_build` | Same corpus + instrumented scorecard + Stage B or score-without-workflow + post-coverage thr (if a thr is chosen) | Same attributed binaries | Same point-precision / workflow-open rate |

Paired comparison is **same seed-42 corpus**, same generator, same labels. Do not relabel after seeing cells. Do not compare Series I levels to Series A levels.

### Primary criterion

**Attributed catch + deadlock cut.** Frozen before the sweep:

- **Attributed S3 recall up** on `new_build` vs `old_build` (B3a / `drift_necessary`; vacuous R=1.0 rejected).
- **Attributed S2 and S5 recall held** (no loss). Headline-recall rule (`OPS.md`): any scenario recall claim requires attribution decomposition causally traceable to the inject. Series A S2 R=1.0 stays retracted.
- **Workflow-open FP down** on the same pairing (the deadlock cut). Auto-resolved count is **not** this number.

This is the only primary. F1@45 is not in this slot.

**Honest stop (locked):** if no threshold on the post-coverage PR curve reaches **P≥0.1**, **Sprint 3 does not start.** Write the negative. That finding outranks every `enabled` flag. Do not retune weights and rerun as if the experiment were exploratory.

### Secondary criterion

**Point-anomaly precision and workflow-open rate.** Frozen before the sweep.

- Recorded; used to confirm the deadlock cut is not “we raised the threshold until S3 died.”
- **Beating F1@45 while losing attributed S3 = fail.** That combination learned nothing useful (Series I already showed F1@45 is point-rarity volume). It is not an honest stop and not a Sprint 3 ticket.
- Secondary cannot override a primary miss. Primary miss + F1 dip is still a fail.

Also recorded with the secondary (not used to flip a primary miss): `promotion_coverage_in_window`; `blocked_entity_count` / blocked-entity-days; `endpoint_set` max; per-scenario `n`; `drift_alerts` vs point-anomaly FP.

### Hard fails (any one aborts the “we earned Sprint 3” claim)

| Hard fail | Class |
|---|---|
| F1@45 treated as the decision pin or the only reported win | `theater_detector` |
| Stage A `precision_gate` cited as the coverage or thr=45 FP fix | `theater_detector` |
| Counting `auto_resolved` as “we fixed FP” | `theater_detector` |
| Raising threshold until attributed S3 dies and calling it precision | `theater_detector` |
| Sweeping threshold before coverage (in-window still ≈0.45 / fleet still ~82% blocked) | `theater_detector` |
| `endpoint_set` still max=0 and not quarantined / governance-disabled | `harness` (`wiring_failure`) |
| S1/S4-only headline used in the Sprint 2 report | `theater_detector` |
| Silent skip of a scenario or arm (no scorecard row) | `harness` |
| GT labels imported by `score_event` | `theater_detector` |
| Seeded `DecisionRecord` / demo INSERT counted as TP | `theater_detector` |
| New drift dimension fold (Series J) staffed as this sprint | out of protocol; stop |
| Post-hoc relabel after seeing the curve | `theater_detector` |

---

## 7. Sprint 3 — canary readiness

**Gate:** Sprint 2 primary is a real win (attributed S3 up, S2/S5 held, workflow-open FP down) **and** the secondary does not contradict it. An F1@45-only win is a fail. A “no thr reaches P≥0.1” result is an honest stop. If that gate is closed, this section is idle. Do not staff it “anyway.”

PR #5 remains the canary-score SoT. This sprint does not grind 28→50. It satisfies the **canary go condition** PR #5 already named: real-or-replay ingest on a tiny allowlist, score-without-block mode, health + alert-volume metrics, authenticated reads, a threshold (or gate) that does not freeze the fleet, and an eval denominator the kernel trusts.

### In scope (only if earned)

- **Allowlist JSONL / replay ingest on the same Event path.** Mapper from real auth/process (or replayed production-shaped logs) onto `ingest_events`. No second intake type. No `/api/ingest` that is not this path.
- **Score-without-block default** on the allowlist (the Sprint 2 cut, on by default for canary). Workflow-open count is bounded by policy, not 6170.
- **`/health` + alert-volume.** Operator can tell worker-alive vs halt vs backlog from metrics. Compose today has no web/worker/batch healthcheck.
- **Authenticated GETs + UI sends the API key.** Close the PR #5 leak (queue readable on :8000) and the silent-401 privileged click.
- **Scheduled builder + audit integrity job.** Compose `batch: sleep infinity` is not this. The job must see decisions (`gov.integrity_job_sees_decisions` flips from “named skip” to “sees N rows”).
- **SoT scrub.** SPEC / README / `docs/calibration_final_metrics.json` consumers cite Series I and “not an operating point.” Series A remains archival.

### Out of scope (even if Sprint 2 won)

- Fake ingest API
- Kubernetes / multi-env IaC
- Real IAM / EDR containment
- “Portfolio shipped ≈ canary”
- Making live SIEM or live LLM a required CI job
- Declaring production quality from the synthetic corpus
- Another feature-fold campaign
- Rubric-score chasing (28→50) without the go-condition artifacts

If Sprint 2 honest-stops, a **docs-only SoT scrub** (Option 5 in PR #6) may still land as a separate change. That is not Sprint 3 and must not be labeled canary.

---

## 8. Error handling and honesty

The scorecard’s `failure_class` is the honesty mechanism. It is not optional commentary.

| Class | Means | Example |
|---|---|---|
| `harness` | Fixture, wiring, serialization, missing row, missing pipeline stage, integrity skip unnamed, `endpoint_set` wiring_failure | JSONL not ingested; `run_pipeline` skipped `build_profiles`; scenario file absent |
| `scorer` | Deterministic score path produced a pin reject that is not theater | Attributed S3 miss on a Sprint 2 `new_build` cell; ngram mismatch did not halt |
| `theater_detector` | The run looked green for a reason that is not the product | Seeded decision as E2E; S1/S4-only headline; Series A cited as current; Stage A called an FP win; F1@45 as usefulness |
| `none` | `pass` or explicit Sprint 1 quality / sanctuary `pending` | — |

Named `theater_detector` checks (scenario field must pick one):

| Name | Trips when |
|---|---|
| `seeded_decision_e2e` | `DecisionRecord` INSERT / `scripts/demo_path.py` / `tests/live/` seed is scored as a pipeline E2E win |
| `n1_headline` | Governance-style headline reports only S1/S4 (n=1) as the decision criterion |
| `unearned_demo_claim` | README / SPEC / demo / kernel copy cites Series A as current, or claims CALIBRATED / canary / useful while Series I is `calibrated: false` and Sprint 2 primary is unearned |
| `unit_as_e2e` | A unit/invariant test is wrapped and emitted as a kernel row without `run_pipeline` (or a documented existing production-call helper) |
| `f1_only_usefulness` | F1@45 is treated as the Sprint 2 primary or the only reported win |
| `stage_a_as_fp_win` | Stage A `precision_gate` is cited as a thr=45 FP or coverage win |
| `gt_in_scorer` | `worker/scorer.py` imports or reads `eval_ground_truth` / labels |
| `fake_ingest_api` | An HTTP `/api/ingest` (or equivalent) that is not `ingest_events(Event JSONL)` is introduced or scored as the production call |
| `series_j_fold` | An additive cadence/geo/volume/fleet/staged fold is staffed as this program |
| `auto_resolved_as_precision` | `auto_resolved` count is used as the FP-down number |

Rules:

- **No silent skips.** An unrun scenario is `error` / `harness`, which fails CI.
- **No skip flags** in scenario YAML. `pending` is only the Sprint 1 capability-quality `new_build` arms and `thr.fp_block_sanctuary` `new_build`, and it must still emit a row.
- Deterministic fixtures may pin expected scores for **governance / design / threat / usability** (those tests are authority / contract). Pinning an expected score as a capability **quality** `pass` in Sprint 1 is illegal.
- Live SIEM / live LLM failures, if someone runs them anyway, land on the scorecard as `harness` or are out of suite — never as omitted rows.
- Theater-detector failures fail the suite even if the scorer number matched the label.
- Harness bugs are not scorer bugs. Scorer misses are not theater. Do not collapse the three.

---

## 9. Success criteria summary

| Sprint | Pass looks like | Fail / stop looks like |
|---|---|---|
| **1 — Eval kernel** | 15 IDs on disk; GHA runs deterministic suite; gov/des/thr/use both arms `pass` (sanctuary `new_build` pending); capability quality `old_build` recorded, `new_build` `pending`; `cap.no_n1_headline` + `use.demo_honesty` both arms `pass`; no silent skips; no ingest API; no Series J | Missing ID; demo/live/notebook as “CI”; capability quality `new_build` marked `pass`; skip; FakeProvider added; `/api/ingest` |
| **2 — Usefulness** | Instrument named (157≠117; axes split; `endpoint_set` fixed or quarantined); Stage B or score-without-workflow; post-coverage PR curve; attributed S3 up **and** S2/S5 held **and** workflow-open FP down on paired seed-42; hard fails absent | F1@45-only “win” → **fail**; Stage A cited as FP win → **fail**; no thr reaches P≥0.1 → **honest stop, no Sprint 3**; hard fail → do not claim a win |
| **3 — Canary readiness** | Entered only after Sprint 2 earn; allowlist JSONL/replay on Event path; score-without-block default; `/health` + alert-volume; auth GETs + UI key; scheduled builder + audit; SoT scrub; PR #5 go-condition artifacts | Started without the earn; fake ingest API; IAM contain; K8s; 28→50 grind; live SIEM/LLM made mandatory CI; compose demo relabeled canary |

---

## 10. References

| Kind | Path |
|---|---|
| Architecture spec | [`docs/SPEC.md`](../../SPEC.md) (keep root `SPEC.md` byte-identical). Claims ingest API and “queues with an LLM explanation” overshoot the code. |
| Series I status | [`.workflow/2026-08-02-series-i-serial-calibration/STATUS.md`](../../../.workflow/2026-08-02-series-i-serial-calibration/STATUS.md) — `calibrated: false`; one accept (`precision_gate.enabled=true`) |
| Series I independent review | `.workflow/2026-08-02-series-i-serial-calibration/results/series-i-independent-review.md` — TP invariant; instrument cannot see treatments |
| fold_06 accept (governance contradiction) | `.workflow/2026-08-02-series-i-serial-calibration/results/scoring-config-governance-series-i-fold_06_precision_gate.md` — accepted on thr=45 FP delta; operator note says Stage A gates containment, not the anomaly path |
| PR #5 readiness | [PR #5](https://github.com/OmarAK-Git/alter_ego/pull/5) `docs/canary-production-readiness.md` — canary 28 / prod 12, **NO-GO**; canary go-condition |
| PR #6 pathfinding | [PR #6](https://github.com/OmarAK-Git/alter_ego/pull/6) `docs/pathfinding-next-program.md` — program SoT this file ratifies; 157 vs 117 correction; Stage A contradiction |
| DEBT-041 | [`DEBT_LEDGER.md`](../../../DEBT_LEDGER.md) — `batch/eval/{runner,calibrate,rescore,report,analyze_misses}.py` has no pytest ownership |
| OPS no-knob-without-sweep | [`OPS.md`](../../../OPS.md) — no weight/threshold edit without full sweep + governance record; headline-recall rule |
| Scorer | `worker/scorer.py` — deterministic fusion; Stage A `compute_signal_family_agreement` does not change `is_anomaly`; containment @ 85 |
| Recorder / §5.5 | `worker/recorder.py` `open_active_alert_if_needed` — every `is_anomaly` opens `new` |
| Eval runner | `batch/eval/runner.py` `run_pipeline` — production offline call; recall denominator is `is_malicious` labels |
| Stage A / Stage B | [`docs/superpowers/specs/2026-07-30-drift-detection-capability-expansion-design.md`](2026-07-30-drift-detection-capability-expansion-design.md) Phase 5 — Stage A built (containment gate); Stage B explicitly not built (suppress single-family workflow-opening) |
| B3a / `drift_necessary` | [`docs/superpowers/specs/2026-07-18-boil-the-frog-invariants-design.md`](2026-07-18-boil-the-frog-invariants-design.md) §1.2–1.3 |
| S55 lifecycle | [`docs/superpowers/specs/2026-07-18-s55-blocking-scope-and-alert-lifecycle-design.md`](2026-07-18-s55-blocking-scope-and-alert-lifecycle-design.md) — open-on-anomaly; T-PATIENT P0 block-as-sanctuary |
| Residual / deadlock | [`docs/residual-risk-drift-hypotheses.md`](../../residual-risk-drift-hypotheses.md) §2.1 / §2.7 — FP × §5.5 freeze; H14 Stage A note |
| Process analog (sequence only) | praetor Approach A (`OmarAK-Git/praetor` `docs/superpowers/specs/2026-09-06-eval-kernel-judgment-readiness-design.md`) — same *sequence* (kernel → proof → readiness), different *product*. Do not copy cite-to-subject, FakeProvider, Vertex, or CBC-adapter language. |

---

## What this file authorizes

| Authorizes | Does not authorize |
|---|---|
| Writing a Sprint 1 implementation plan after owner review of this file | Implementing the kernel, scenarios, or CI in the same change as this spec |
| Treating `run_pipeline` as the production call shape | A second eval envelope, seeded-decision E2E, or fake `/api/ingest` |
| Pending capability quality (and sanctuary `new_build`) in Sprint 1 | A Sprint 1 claim that the detector is useful |
| Sprint 3 only if Sprint 2 earns attributed catch + deadlock cut | Canary work after an F1@45 fold, an honest stop, or another Series J |
| Naming the 157/117 metric bug and the fold_06 governance contradiction | Relitigating Stage A as a usefulness win |
