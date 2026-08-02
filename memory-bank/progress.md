# Progress

**Updated:** 2026-07-31  

## DC drift-capability expansion (active T3)

**Workflow:** `.workflow/2026-07-30-drift-capability-expansion/`  
**Report:** `.workflow/2026-07-30-drift-capability-expansion/results/SPRINT-PROGRESS-REPORT.md`

| Packet | Status | Notes |
|---|---|---|
| P0-1–P0-2, P0-GATE | done | Shadow baseline Phase 0 |
| P0-3 Series E | in_progress | chunk ~11/22; PID 63516; no metrics |
| P1–P2, P2-GATE | done | Cadence + volume delta |
| P2-3 Series F | in_progress | parallel with E |
| P3–P4, P4-GATE | done | Fleet cohort + geo velocity |
| P4-3 Series G | pending | after F |
| P5–P6, P5-GATE | done | Precision gate Stage A + staged sequences |
| P5-4 Series H | pending | after G |
| FINAL-DOCS | pending | needs E+F+G+H |
| DC-EXIT-GATE | pending | prior REJECT |

Committed YAML: all new `enabled` flags **false**. No production flip without governance.

---

**Updated (portfolio baseline):** 2026-07-30  
**Plan authority:** Honest merge of `docs/SPEC.md` (Phase 0–4, UI, threat model) + `docs/SPEC_V3.md` (§7 reopen gates, §9 portfolio). Doc revisions v2/v3 ≠ product versions; product scope remains **v1**.

**T3 autopilot (canonical):** `.workflow/2026-07-30-reverse-spec-rfc-remediation/` — **CLOSED** 2026-07-30 (**ACCEPT-WITH-GAPS**; Grok; pytest **165**, ruff clean). Commits: `5311d3a` (RFC-006), `2aaa4e0` + `019487e` (RFC-005). Accepted gap: Session identity-map retention without `expunge`. Gate standing order now Grok until operator overrides. Prior closed: D4 time-axis / Series D (ACCEPT-WITH-GAPS), Series C, S55, v1 portfolio.

## Decisions locked (2026-07-12)

| Decision | Choice |
|---|---|
| Acceptance bar | **C** — clear remaining gates from both specs; demote overstated Done claims |
| Scenario 2 / Phase 2 | **Hybrid C** — integrity fixes → one re-sweep → update metrics; if S2 still fails, document residual and continue (no fake “CALIBRATED”) |
| Cut line | **B** — portfolio-ready (Phase 3 non-negotiables + Phase 4 / SPEC_V3 §9) |
| Artifact | **A** — living table in this file; **T3 packets** in `.workflow/2026-07-12-v1-portfolio-ready/state.json` |
| Research | Personal drift-methodology research starts **right before S5 (Phase 4)**; agents keep building in-app |

## Phase status (honest)

| Phase | Status | Notes |
|---|---|---|
| 0 Contracts + generator | **Partial** | Schemas, synth, CI, app-layer audit chain. **Shipped S5/S6:** four-container compose (S5.1), INSERT-only `alter_ego_app` role (S5.3), audit integrity job (S5.4), pgvector playbook (S5.8). LLM determinism **executed** 2026-07-14 (Vertex; not bit-identical → lineage rule confirmed) |
| 1 Detection pipeline | **Partial** | Shadow profiles, six-feature path, drift, novelty gate — geo histograms + drift KL (S1.2), eval partitions fixed (S1.1), auto containment queue (S1.3), embedding metadata mismatch halt (S5.9); open: lifecycle states, volume_delta |
| 2 Calibration | **Partial (Phase 2A)** | S1/S2/S4 recall 1.0 @ thr=45; S3 subtle recall 0.667 (15 FN); 3448 FP; **not CALIBRATED** — see `docs/phase2-s3-operating-point.md` |
| 3 Triage UI + API + explain | **Partial** | Slot isolation (S4.1), queue depth (S4.2), suppressed view (S4.3), demo path (S4.4), replay_run_id (S4.5) shipped. **Deferred (Path B):** suppressed-decisions aging escalation + jitter (S4.3) |
| 4 Hardening / portfolio (§9) | **Partial** | S5.1–S5.10 shipped (compose, DB roles, audit integrity, staleness+alert escalation, build-block escalation, LLM determinism script, pgvector playbook, embedding mismatch, counterfactual harness). **Deferred:** S5.11 cohort prior-update gates (Path B), K8s/Terraform, debate transcripts |

## Saved eval point

Source: `docs/calibration_final_metrics.json` (S3.1 re-sweep, seed 42; do not trust older narrative docs over this file)

- **thr=45** (YAML current): P **0.019** · R **0.817** · F1 **0.037** · TP **67** · FP **3448** · FN **15**
- Per-scenario recall: S1 **1.0** · S2 **1.0** (35/35) · S3 **0.667** (15 FN) · S4 **1.0**
- PR-curve best-F1 **thr=55** (P 0.041, R 0.585, FP 1136) — diagnostic only, **not applied**
- **Not CALIBRATED.** Residual note: `docs/phase2-s3-operating-point.md`
- **S2 boil-the-frog claim retracted (2026-07-18):** R=1.0 is Series A harness artifact — see `docs/residual-risk-drift-hypotheses.md` §2.6 / H11; invariants in `tests/test_boil_the_frog_invariants.py` (A1/A2/B2 red)

## Follow-on — Series C (post §5.5 R-INTERLOCK)

**Status (2026-07-19):** Sweep executed — `.workflow/2026-07-19-series-c/`. Artifact: `docs/calibration_series_c_metrics.json`. Governance: `docs/scoring-config-governance-series-c.md`.

| Item | Status |
|---|---|
| Full Series C sweep under QUIET∧ATTEST + D4 | **done** (NOT CALIBRATED; S2/S5 R=0; promotion_coverage=1.0) |
| `scenario_5_patient_cycle` inject | **done** |
| YAML write of attestation knobs | **deferred** (still code defaults) |

**Do not** cite B→C FP/P/R deltas. B4 remains the only scoped boil-the-frog license.

## Follow-on — Series D (post D4 time-axis fix)

**Status (2026-07-19):** Sweep executed — `.workflow/2026-07-19-d4-time-axis/`. Artifact: `docs/calibration_series_d_metrics.json`. Governance: `docs/scoring-config-governance-series-d.md`.

| Item | Status |
|---|---|
| Full Series D sweep under D4 as-of fix | **done** (NOT CALIBRATED; S2 R=0.714; D4 engagement=12840) |
| Dual promotion_coverage (ever + in_window N=5) | **done** (ever=1.0; in_window=0.413) |
| YAML write of attestation knobs | **deferred** (still code defaults; separate S6.3 hygiene) |

**Do not** cite C→D FP/P/R deltas. Only permitted C→D claim: D4 engagement 0→12840. Concerns: fallback storm (1084), P≈0.011 / FP=5432.

## Follow-on (not started) — Design 2 + attribution governance

Tracked under `.workflow/2026-07-18-boil-the-frog-invariants/` packet `BTF1.1`:

1. Lift Design 2 sweep-report fields: `early_below_threshold_fraction`, `drift_necessary_tp_fraction`, `attack_raised_cumulative_drift`, plus `caught_before_absorption` / `absorbed` (predicates in Design 1 spec §1).
2. **S6.3 generalization:** any headline recall claim requires attribution decomposition showing TP signal is causally traceable to the injected attack (would have caught Phase 2B embedding-mock artifact and Series A S2 overstatement).
3. **§5.5 R-INTERLOCK (S55 — EXIT closed 2026-07-19):** design APPROVED; D1–D5 + C1–C3/Design-1F in `.workflow/2026-07-18-s55-alert-lifecycle/` (skeptic ACCEPT-WITH-GAPS: Series-C deferrals only; pytest 148). Detection YAML untouched. Governance: `docs/scoring-config-governance-s55-lifecycle.md`.
4. **Design 1 fixture limitation (documented):** fixture all-green has **no FP storm by construction** — Design 1F + C1 cover the deadlock companion; fixture green ≠ full-sweep evidence.

Do not treat Series B headline metrics as characteristic rates until Series C under R-INTERLOCK.

## Working config

`config/scoring_config.yaml` v2.2 — `anomaly_threshold: 45`, `drift_threshold: 5.0`, `drift_alert` weight 100.

**Knob inventory:** see [Scoring config knob inventory (2026-07-13)](#scoring-config-knob-inventory-2026-07-13) below (S0.4 baseline; S2.8 refresh).

## Overstatements register

| Claim | Reality | Fix in |
|---|---|---|
| SPEC.md header “CALIBRATED (Audit Grade)” | Global P ~0.019 @ thr=45; 3448 FP; S3 recall 0.667 — not audit-grade | done (S3.5; SPEC/README/phase2 scrubbed to “not CALIBRATED / not audit-grade”) |
| `phase1-audit-results.md` “100% Precision and Recall” | False vs saved metrics | S0 |
| Phase 2 audits: embeddings “mocked” | Runtime is char 3-gram 128-d (`alter-ego-ngram-v1`) | S0 |
| Schema / alembic default `nomic-embed-text` | Runtime ngram; SPEC_V3 still mentions nomic | S0, S1 |
| Four-container K8s / kind | `docker-compose.yml` four-container topology shipped S5.1; K8s/Terraform deferred | done (S5.1/S5.2) |
| DB-role INSERT-only immutability | S5.3 ships `alter_ego_app` role: true INSERT-only on audit/commit tables; profiles allow lifecycle-column UPDATE only (`promoted_at`, `superseded_at`) — not full table INSERT-only | done (S5.3) |
| `simulated_containment_queued` | Auto queue write when score ≥ threshold + confidence floor (S1.3) | done (S1.3) |
| `geolocation_rarity` as calibrated feature | Geo histograms + drift KL wired (S1.2) | done (S1.2) |
| `total_volume_delta` in feature table | Explicitly suppressed stub (always 0) | done (S2.6) |
| Empirical LLM determinism script | Script shipped S5.7; **executed** 2026-07-14 on Vertex `gemini-3.5-flash` — 4 unique hashes / 10 runs @ temp=0 → lineage authoritative | done (S5.7 empirical) |
| pgvector migration playbook | Shipped S5.8 — `docs/pgvector-embedding-migration.md` | done (S5.8) |
| Frozen cohort-prior artifacts (SPEC_V3) | Cohort data embedded in profiles only; SPEC_V3 downgraded (S2.5) | done (S2.5) |
| SPEC §10.2 partition discipline | S2/S3 inject with `simulation_partition="production"` → can train into profiles | S1 |

## Remaining work by sprint

Status legend: `todo` · `doing` · `done` · `deferred` · `wontfix` (with note)

### S0 — Spec & claim hygiene

**Goal:** Stop lying to future-you before more calibration or UI work.

| ID | Task | Spec ref | Status | Notes |
|---|---|---|---|---|
| S0.1 | Demote SPEC.md header / status from “CALIBRATED” to Phase 2A / residual | SPEC.md §1 header | done | Done 2026-07-12: SPEC header demoted; points at this file + `docs/calibration_final_metrics.json` |
| S0.2 | Correct `docs/phase1-audit-results.md` 100% recall claim | phase1-audit-results | done | Done 2026-07-12: Final Status rewritten; Phase 2 Partial (2A); points at `docs/calibration_final_metrics.json` |
| S0.3 | Lock embedding narrative to `alter-ego-ngram-v1` / 128-d everywhere claims appear | SPEC_V3 §5/§6.8, README | todo | 2026-07-12: SPEC_V3 §5/§6.8, README, CLAUDE, OPS locked to ngram/128-d; nomic framed as S1.4 schema debt |
| S0.4 | Inventory YAML knobs → wire / defer / delete list | SPEC §6.8 | done | 2026-07-12: full inventory below; 25 wired, 5 wire, 5 defer, 2 delete-candidate |
| S0.5 | Align README + memory-bank phase labels to Partial where overstated | README phase map | todo | Done 2026-07-12: README phase map + badge demoted to Partial (0–3); activeContext aligned to T3 run + progress.md authority |

### S1 — Eval integrity (pre-calibration)

**Goal:** Make the next sweep meaningful. Exit before claiming any new Phase 2 numbers.

| ID | Task | Spec ref | Status | Notes |
|---|---|---|---|---|
| S1.1 | Fix S2/S3 generator partitions to `eval_scenario_*` (exclude from training) | SPEC §10.2, V3 §6.9 | done | 2026-07-12: eval_scenario_2/3 + tests |
| S1.2 | Build `geolocations` into profile histograms + include in drift KL | SPEC §6.2/§6.4 | done | 2026-07-12: builder geo hist + drift KL |
| S1.3 | Auto-write containment queue when threshold + confidence met; wire `containment_threshold` | SPEC §6.8, V3 §7 | done | 2026-07-12: threshold+confidence gate + queue write |
| S1.4 | Align ProfileArtifact / DB defaults / builder metadata to ngram model id+dim | V3 §6.8 | done | 2026-07-12: alter-ego-ngram-v1 defaults + alembic e4f5a6b7c8d9 |
| S1.5 | Smoke: benign-only / correlated-benign path still runs under fixed partitions | V3 §6.9 | done | 2026-07-12: partition smokes; no new P/R |

**S1 exit gate (2026-07-12):** `S1-EXIT-GATE` passed — pytest 53/53, `ruff check .` green. S2 unlocked; see `results/S1-EXIT-GATE-verifier-result.md`.

### S2 — Phase 1 reopen leftovers (SPEC_V3 §7)

**Goal:** Close honesty blockers that invalidate “Phase 1 done.” Prefer implement; else explicit downgrade note in SPEC_V3 / this file.

| ID | Task | Spec ref | Status | Notes |
|---|---|---|---|---|
| S2.1 | Resolver collision/split fixtures → `low_resolution_confidence` | V3 §7 | done | 2026-07-13: collide/split fixtures + scorer flag |
| S2.2 | Evidence-binding: reconstruct `raw_score` from contributions within tolerance | V3 §7 | done | 2026-07-13: undamped + real damping divergence tests |
| S2.3 | decision_id / canonical serialization includes algorithm (+ embedding) version | V3 §6.1 | done | 2026-07-13: sorted-key JSON + SCORER_ALGORITHM_VERSION |
| S2.4 | Observation-count confidence `n/(n+k)`; put `confidence_k` in scoring_config | V3 §6.5 | done | 2026-07-13: YAML key + tests; scorer reads `config.get("confidence_k", 10.0)` |
| S2.5 | Frozen cohort-prior artifacts **or** document SPEC_V3 downgrade to profile-embedded cohorts | V3 §4/§6.6/§7 | done | 2026-07-13: Path B — SPEC_V3 downgraded; v1 = profile-embedded `cohort_data`; independent versioned cohort artifacts deferred to S5.11 |
| S2.6 | `total_volume_delta`: implement or remove from config/README/feature claims | SPEC §6.2 | done | 2026-07-13: Path strip/defer — README demoted; YAML weight reserved; scorer flag `volume_delta_deferred` |
| S2.7 | Lifecycle states (dormant / reactivated / onboarding / role_transition): minimal ship or defer note | SPEC §5.4 | done | 2026-07-13: Path B — SPEC §5.2/§5.4/§6.2/§11.1/§13.1 downgraded; v1 has no `lifecycle_state`; alert workflow (§11.5) ≠ profile lifecycle; partial substitutes: `cohort_unsupported` + staleness halt |
| S2.8 | Apply S0.4 inventory: wire cheap knobs or strip from “calibrated” claims | SPEC §6.8 | done | 2026-07-13: decay_lambdas stripped; inventory refresh (28/0/7/0) |

### S3 — Hybrid calibration close

**Goal:** Integrity → one full re-sweep → claim correctly. Not a hard S2-recall gate.
**Unlocked:** 2026-07-13 by `S2-EXIT-GATE` (done). **S3.3 closed N/A** — S2 no longer FN; remaining residuals (high FP, S3 misses) → **S3.4**.

| ID | Task | Spec ref | Status | Notes |
|---|---|---|---|---|
| S3.1 | Full eval sweep under current config + S1/S2 fixes | SPEC §10, Phase 2 | done | 2026-07-13: thr=45 P≈0.019 R≈0.817; S2 R=1.0; verifier survives |
| S3.2 | Refresh `docs/calibration_final_metrics.json` + PR curve artifact | SPEC §10.4 | done | 2026-07-13: artifacts from S3.1 DB; thr=55 diagnostic only |
| S3.3 | If S2 still FN: write residual-risk note (scores, why, next hypotheses) | Phase 2 / Hybrid C | wontfix | N/A — `scenario_2_slow_roll` recall **1.0** (35/35) @ thr=45 per S3.1/S3.2; no S2-FN residual doc; handoff → **S3.4** |
| S3.4 | If S2 catches: document operating point + residual modes for other errors | Phase 2 | done | 2026-07-13: `docs/phase2-s3-operating-point.md`; S2 R=1.0, FP=3448, S3 FN=15, thr=55 not applied |
| S3.5 | Update SPEC.md / phase2 docs status to Phase 2A or “closed with residual” | Docs hygiene | done | 2026-07-13: SPEC header/§6.8 demoted; phase2-audit + progress-report scrubbed; README Phase 1/2 aligned; root SPEC synced |
| S3.6 | Scoring-config governance record for any threshold/weight change | V3 §6.10 | done | 2026-07-13: `docs/scoring-config-governance-s3.md` — v2.2 @ thr=45 unchanged; thr=55 not applied |

### S4 — Phase 3 product finish

**Goal:** Non-negotiable explain + analyst UI for v1 portfolio claim.

| ID | Task | Spec ref | Status | Notes |
|---|---|---|---|---|
| S4.1 | Explainer: slot-isolated low-trust fields (`<command_line>` etc.) | SPEC §3.4/§8.2 | done | 2026-07-13: low-trust slots escaped/capped; high-trust JSON bindings |
| S4.2 | Explainer queue-depth limit + deterministic template fallback under load | SPEC §8.6 | done | 2026-07-13: `explainer_queue_depth: 8`; overflow → template fallback |
| S4.3 | Suppressed-decisions aging escalation (+ jitter) **or** defer note (view itself must exist) | SPEC §11.4, §13.1 | done | 2026-07-13: **Path B defer** — view wired via `confidence_floor` partition in `web/api.py`; aging indicators + auto-escalation + jitter deferred; SPEC §11.4 banner + §3.2/Phase 3/§13.1 downgraded; `age_jitter_hours`/`suppressed_decision_aging_days` unwired → Phase 4 |
| S4.4 | Demo path: seed → triage → explain → contain (simulated) | SPEC §11.5 | done | 2026-07-13: `scripts/demo_path.py` + README Demo path; `tests/web/test_demo_path.py` |
| S4.5 | Replay: first-class `replay_run_id` on decisions / audit path | SPEC §9.3, V3 §9 | done | 2026-07-13: `replay_run_id` on DecisionRecord/ORM; replay_runner + API; migration `f5a6b7c8d9e0` |
| S4.6 | Calendar dual-score / telemetry gap two-tier: ship or mark deferred | SPEC §6.5/§6.6 | done | 2026-07-13: **Path B defer** — no calendar store, gap detector, or dual-score in v1; SPEC §6.2/§6.5/§6.6/§11/§13.1 downgraded; three YAML knobs remain unwired → Phase 4 |
| S4.7 | Asset / service-dependency context minimal or defer | SPEC §12 | done | 2026-07-13: **Path B defer** — no asset/dependency artifacts, blast-radius computation, API fields, or triage UI indicators in v1; SPEC §12/§11.1/§13.1 downgraded; `infrastructure_volatile` flag deferred with §12 |

---

### Exit gates (first-class packets)

| ID | After | Unlocks | Status |
|---|---|---|---|
| S1-EXIT-GATE | S1.1–S1.5 | S2.* | done |
| S2-EXIT-GATE | S2.1–S2.8 | S3.* | done | Passed 2026-07-13: skeptic-verifier `survives`, pytest 69/69, ruff clean; `results/S2-EXIT-GATE-verifier-result.md` |
| S3-EXIT-GATE | S3.1–S3.6 | S4.* | done | Passed 2026-07-13: skeptic-verifier `survives`; `results/S3-EXIT-GATE-verifier-result.md` |
| S4-EXIT-GATE | S4.1–S4.7 | HUMAN-DRIFT-RESEARCH | done | Passed 2026-07-13: initial verify refuted (S4.3 aging/jitter SPEC banner missing); honesty patch applied; re-verify `survives`, pytest 85, ruff clean; `results/S4-EXIT-GATE-verifier-result.md` |
| S5-EXIT-GATE | S5.1–S5.12 | S6.* | done | 2026-07-13: chat_gate PASS (Opus inline). Fresh pytest **116 passed**, ruff clean. Caught + fixed a real cross-packet regression S5.9's focused verifier missed (`test_new_confidence_calculation` halted by S5.9 embedding metadata mismatch: stale fixture normalizer `1.0` vs runtime `1.0-char-3gram-hash-128`; test-only fix). `results/S5-EXIT-GATE-verifier-result.md` |

### ⚑ HUMAN POINTER — before S5 / Phase 4 (after S4-EXIT-GATE)

**Acknowledged 2026-07-13** — `HUMAN-DRIFT-RESEARCH` gate marked `done`; S5.* unblocked. Operator drift-methodology research proceeds in parallel with S5 in-app build.

**You (operator):** Start personal **drift detection methodology research** here.

- Agents continue in-app build (S5 portfolio gate).
- You research drift approaches, paper notes, alternative metrics, experiment design.
- Feed findings into **S6** hardening empirical sweeps (do not change weights without a sweep).
- Suggested inputs: operating-point / residual note from S3.4, `batch/profile_builder` drift math, `scratch/analyze_step*.py`, SPEC §6.4.

Do not start S5 claiming “research complete.” Parallel tracks are intentional.

---

### S5 — Phase 4 / SPEC_V3 §9 portfolio readiness

**Goal:** Binding portfolio gates — not optional decorations.

| ID | Task | Spec ref | Status | Notes |
|---|---|---|---|---|
| S5.1 | Dockerfiles + four-container compose (web/worker/batch/postgres) | SPEC §4.4, V3 §9 | done | 2026-07-13: shared Dockerfile + compose `web`/`worker`/`batch`/`postgres`; `docs/deployment.md`; verifier survives |
| S5.2 | IaC (Terraform or equivalent) **or** explicit downgrade of portfolio IaC claim | V3 §5/§9 | done | 2026-07-13 Path A: compose-as-equivalent IaC; §9 gate closed via `docker-compose.yml`; standalone Terraform/k8s deferred |
| S5.3 | Postgres INSERT-only roles + REVOKE for audit/profile commit tables | SPEC §9.2, V3 §6.3/§6.10 | done | 2026-07-13: migration `g6h7i8j9k0l1_add_app_db_roles`, compose DSN split; profiles = column-level lifecycle UPDATE only |
| S5.4 | Scheduled audit hash-chain integrity job / assertion | V3 §6.10/§9 | done | 2026-07-13: `batch/audit_integrity.py` + `verify_audit_log_chain` in `core/models.py` |
| S5.5 | Staleness circuit breaker + active-alert mandatory escalation | SPEC §5.7, V3 §9 | done | 2026-07-13: staleness halt escalation flags, mandatory escalation queue API, extend-halt persistence |
| S5.6 | `max_profile_build_block_days` supervisor escalation | SPEC §5.5, V3 §9 | done | 2026-07-13: profile builder emits `profile_build_block_supervisor_escalation` DecisionRecord |
| S5.7 | Empirical LLM determinism check vs pinned non-alias model (real, not mock) | SPEC §8.4, V3 §9 | done | 2026-07-13: `scripts/llm_determinism_check.py`; artifact honest not-executed until API keys |
| S5.8 | Full pgvector / embedding dimensionality migration playbook | SPEC §4.3, V3 §6.8/§9 | done | 2026-07-13: `docs/pgvector-embedding-migration.md` |
| S5.9 | Schema-version / embedding-metadata mismatch detection at scorer startup | V3 §9 | done | 2026-07-13: `check_profile_embedding_metadata` + `embedding_metadata_mismatch_halt` in scorer |
| S5.10 | Counterfactual consistency corpus + harness | SPEC §8.5/§10.5, V3 §9 | done | 2026-07-13: `build_top_k_counterfactuals` + corpus/harness; `docs/counterfactual-consistency.md` |
| S5.11 | Independent versioned cohort-prior artifacts + advanced prior-update gates beyond novelty **or** defer per §13.1 | SPEC §7.3, V3 §9 | done | 2026-07-13: **Path B defer** — novelty suppression ships; prior-update gates deferred |
| S5.12 | Threat-model polish in repo + README aligned to implemented behavior | SPEC Phase 4 | done | 2026-07-13: README phase map + portfolio docs; SPEC §3.2/§13 threat-model honesty; root SPEC synced |

### S6 — Hardening empirical handoff

**Goal:** Bridge app build → your personal drift research + empirical sweeps.

| ID | Task | Spec ref | Status | Notes |
|---|---|---|---|---|
| S6.1 | Document hardening sweep checklist (commands, seeds, artifacts to refresh) | Eval discipline | done | 2026-07-13: `docs/hardening-sweep-checklist.md`; OPS pointer; seed 42 / v2.2 / thr=45 canonical |
| S6.2 | Residual-risk + open drift hypotheses doc (feeds personal research) | SPEC §6.4 | done | 2026-07-13: `docs/residual-risk-drift-hypotheses.md` — FP=3448, S3 FN=15, thr=55 not applied, normalizer default trap, Path B deferrals, 10 open hypotheses |
| S6.3 | No weight/threshold change without recorded sweep + config governance | SPEC §10.1 | done | 2026-07-13: OPS standing rule = checklist + governance/`ConfigStore.save_config`; verifier survives |

## Scoring config knob inventory (2026-07-13)

Source: `config/scoring_config.yaml` v2.2 (S2.8 refresh). Grep scope: `worker/`, `batch/`, `core/` (+ tests/scratch for negative evidence). Labels: **wired** (production path reads key) · **wire** (planned near-term) · **defer** (later packet or explicit downgrade) · **delete** (orphan / superseded; stripped S2.8).

### Top-level

| Knob | Value (v2.2) | Status | Reader / notes | Later packet |
|---|---|---|---|---|
| `version` | `"2.2"` | wired | `worker/scorer.py` (`load_scoring_config`, decision stamp); `batch/profile_builder/builder.py` (profile stamp) | — |
| `anomaly_threshold` | 45.0 | wired | `worker/scorer.py` — anomaly gate | — |
| `drift_threshold` | 5.0 | wired | `worker/scorer.py` — drift score divisor; `batch/profile_builder/builder.py` — drift-alert flag when `cumulative_drift >= threshold` (dual semantics) | — |
| `max_profile_staleness_days` | 14 | wired | `worker/scorer.py` — staleness circuit breaker (`staleness_halt`) | S5.5 escalation beyond halt |
| `drift_comparison_history_count` | 5 | wired | `batch/profile_builder/builder.py` — prev-profile KL window | — |
| `drift_half_life_days` | 7 | wired | `batch/profile_builder/builder.py` — accumulator exponential decay (supersedes removed `decay_lambdas.drift`) | — |
| `confidence_floor` | 0.6 | wired | `worker/scorer.py` — low-confidence damping; containment gate floor (S1.3); `web/api.py` — triage vs suppressed partition (S4.3) | — |
| `confidence_k` | 10.0 | wired | `worker/scorer.py` — `n/(n+k)` observation-count confidence (S2.4) | — |
| `containment_threshold` | 85.0 | wired | `worker/scorer.py` — auto `simulated_containment_queued` + queue write via recorder (S1.3) | — |
| `contribution_scale_max` | 50.0 | wired | `worker/scorer.py` — per-feature contribution cap | — |
| `laplace_alpha` | 1.0 | wired | `worker/scorer.py` (rarity); `batch/profile_builder/builder.py` (KL) | — |
| `max_calendar_adjustment` | 0.3 | defer | **Not read.** Calendar dual-score deferred S4.6 Path B | **Phase 4** |
| `max_replay_window_days` | 30 | wired | `batch/profile_builder/builder.py` — profile build history window | — |
| `max_profile_build_block_days` | 30 | wired | `batch/profile_builder/builder.py` — supervisor escalation when block exceeds threshold (S5.6) | — |
| `recent_drift_window_days` | 3 | wired | `batch/profile_builder/builder.py` — recent window for drift KL | — |
| `cohort_gate_window_days` | 7 | wired | `worker/scorer.py` — novelty fraction lookback | — |
| `age_jitter_hours` | 4 | defer | **Not read.** SPEC §11.4 jitter deferred S4.3 (view ships without escalation) | future escalation packet |
| `suppressed_decision_aging_days` | — | defer | **Absent from YAML.** SPEC §11.4 aging indicators + auto-escalation not wired | future escalation packet |

### Removed (S2.8)

| Knob | Prior value | Action | Notes |
|---|---|---|---|
| `decay_lambdas.staleness` | 0.1 | **stripped** | Never read; staleness is binary halt via `max_profile_staleness_days` |
| `decay_lambdas.drift` | 0.05 | **stripped** | Never read; superseded by `drift_half_life_days` in builder |

### `cohort_gating_constants`

| Knob | Value | Status | Reader / notes | Later packet |
|---|---|---|---|---|
| `min_cohort_size` | 10 | wired | `worker/scorer.py` — novelty gate cohort floor | — |
| `min_clean_observation_count` | 5 | defer | **Not read** in scorer/builder (only `scratch/test_cohort_gate.py`). Prior-update rejection semantics deferred S5.11 Path B | **Phase 4** |
| `max_changed_fraction` | 0.2 | wired | `worker/scorer.py` — novelty suppression threshold | — |

### `gap_windows`

| Knob | Value | Status | Notes | Later packet |
|---|---|---|---|---|
| `gap_correlation_window` | 60 | defer | **Not read.** Telemetry-gap two-tier deferred S4.6 Path B | **Phase 4** |
| `investigation_context_window` | 14 | defer | **Not read.** Investigation timeline deferred S4.6 Path B | **Phase 4** |

### `features.*.weight`

| Feature | Weight | Status | Reader / notes | Later packet |
|---|---|---|---|---|
| `login_hour_rarity` | 1.0 | wired | `worker/scorer.py` `get_rarity_score` | — |
| `geolocation_rarity` | 2.0 | wired | Scorer + builder geo histograms + drift KL (S1.2) | — |
| `endpoint_set_rarity` | 2.0 | wired | `worker/scorer.py` | — |
| `process_name_rarity` | 3.0 | wired | `worker/scorer.py` | — |
| `command_line_embedding_similarity` | 2.0 | wired | `worker/scorer.py` | — |
| `drift_alert` | 100.0 | wired | `worker/scorer.py` — proportional drift contribution | — |
| `service_account_execution_frequency_deviation` | 5.0 | wired | `worker/scorer.py` — SA periodicity path | — |
| `total_volume_delta` | 1.0 | defer | Weight reserved; scorer **always** `score_vol=0.0` + `volume_delta_deferred` (S2.6) | post-S3 implement + sweep |

### `drift_weights`

| Dimension | Weight | Status | Reader / notes | Later packet |
|---|---|---|---|---|
| `login_hour` | 5.0 | wired | `batch/profile_builder/builder.py` KL blend | — |
| `geolocation` | 5.0 | wired | `batch/profile_builder/builder.py` — geo KL in `deltas` dict (S1.2) | — |
| `endpoint_set` | 5.0 | wired | `batch/profile_builder/builder.py` | — |
| `process_name` | 20.0 | wired | `batch/profile_builder/builder.py` | — |
| `embedding` | 40.0 | wired | `batch/profile_builder/builder.py` centroid cosine | — |

### Summary counts

| Label | Before (S0.4) | After (S2.8) | Delta |
|---|---|---|---|
| wired | 25 | **28** | +3 (`confidence_k`, `containment_threshold`, `drift_weights.geolocation` promoted; geo feature notes upgraded) |
| wire | 5 | **0** | −5 (all prior wire items resolved or reclassified) |
| defer | 5 | **7** | +2 (`min_clean_observation_count` reclassified wire→defer; `total_volume_delta` counted consistently) |
| delete | 2 | **0** | −2 (`decay_lambdas.*` stripped from YAML) |

**YAML tunables:** 35 keys (was 37 before S2.8 strip). No code-only gaps remain for inventoried knobs.

**Apply inventory:** S2.8 complete. S4.6 closed Path B (calendar/gap knobs → Phase 4). S5.11 closed Path B (`min_clean_observation_count` + prior-update gates → Phase 4). Remaining defer keys are explicit non-calibrated placeholders until S5.6 or post-S3 volume work.

## Explicitly out of scope (v1 non-goals)

Real SIEM integration · multi-tenant SaaS · production IAM disablement · live enterprise ingest · network-layer detection · mobile UI · Kubernetes operators · autonomous multi-agent detection · WORM / DB-superuser-proof audit.

## Next action

**Autopilot stopped:** `--stop-before-gate` — next runnable `S3-EXIT-GATE` (chat_gate). S3.1–S3.6 complete (S3.3 wontfix). See `results/autopilot-loop-stop-report.md`.

## Series I serial calibration (2026-08-02T04:25Z)

- Branch: `series-i-serial-calibration`
- Status: IN PROGRESS — Phase A weight search launching
- Harness: `scratch/run_series_i_campaign.py`
- Artifacts: `.workflow/2026-08-02-series-i-serial-calibration/`
- Calibrated: false (never claim CALIBRATED)
