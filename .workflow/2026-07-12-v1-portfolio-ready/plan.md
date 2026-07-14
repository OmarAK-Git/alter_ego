# V1 portfolio-ready completion — 2026-07-12

**Tier:** T3 (multi-sprint, multi-session, autonomous-loop candidate)  
**Canonical state:** `.workflow/2026-07-12-v1-portfolio-ready/state.json`  
**Human roadmap (projection):** `memory-bank/progress.md`  
**Task mirror (projection):** `memory-bank/tasks.md`

## Goal

Finish ALTER_EGO product **v1** to an honest portfolio-ready bar by clearing remaining gates from `docs/SPEC.md` (Phase 0–4) and `docs/SPEC_V3.md` (§7 reopen + §9 portfolio), demoting overstated claims, closing eval integrity gaps, running hybrid calibration, finishing Phase 3 UI/explain, then Phase 4 / §9 hardening — with a **human drift-research gate before S5**.

## Success Criteria

- Every packet `S0.*`–`S6.*` is `done`, `deferred` (with written downgrade note), or `wontfix` (with reason) in `state.json`
- Saved metrics + SPEC/README status language agree (no “CALIBRATED” / “100% recall” without evidence)
- Hybrid S2 policy honored: integrity fixes → re-sweep → residual documented if needed
- Portfolio §9 items shipped or explicitly downgraded in docs
- `verify_run.py` stays green for this slug; stop-gate checks (`pytest`, `ruff`) pass on closeout
- Human packet `HUMAN-DRIFT-RESEARCH` acknowledged before any `S5.*` packet starts

## Constraints

- Docs are source of truth; code/metrics beat narrative when they conflict
- No weight/threshold change without recorded eval sweep + scoring-config governance
- Do not commit `alter_ego_calibrate_v*.db`, `alter_ego_eval.db`, or `__pycache__` churn
- Do not install original `gsd-build/get-shit-done`; this run uses UAW T3 packets (GSD-style four-role loop via researcher / implementer / test-runner / skeptic-verifier)
- Execute **one sprint at a time**; do not parallelize packets that share write scopes
- Non-goals stay out: real SIEM, multi-tenant, live ingest, multi-agent detection, real IAM disablement

## Risks

| Risk | Approval | Mitigation |
|---|---|---|
| S2 still fails after integrity fixes | no | Hybrid C: document residual; do not claim Phase 2 closed |
| Spec forks (cohort artifacts, lifecycle, calendar) | no | Packet must implement **or** write explicit downgrade in progress.md + SPEC note |
| Autonomous loop scope creep into research | no | `HUMAN-DRIFT-RESEARCH` blocks S5; agents do not “research” by rewriting drift math without a packet |
| DB role / Docker changes break local dev | no | Prefer additive compose profiles; document rollback in packet result |
| False completion via weakened tests | no | skeptic-verifier + reward-hack check on every sprint close |

## Work Packets

Packet IDs match `memory-bank/progress.md`. Status values: `pending` | `ready` | `doing` | `done` | `blocked` | `deferred` | `wontfix`.

### Sprint S0 — Spec & claim hygiene

| ID | Objective | Owner | Status |
|---|---|---|---|
| S0.1 | Demote SPEC.md “CALIBRATED” header to Phase 2A / residual | main | pending |
| S0.2 | Correct phase1-audit-results 100% recall claim | main | pending |
| S0.3 | Lock embedding narrative to alter-ego-ngram-v1 / 128-d | main | pending |
| S0.4 | Inventory YAML knobs → wire / defer / delete | main | pending |
| S0.5 | Align README + memory-bank phase labels to Partial | main | pending |

### Sprint S1 — Eval integrity (pre-cal)

| ID | Objective | Owner | Status |
|---|---|---|---|
| S1.1 | Fix S2/S3 simulation_partition (exclude from training) | main | pending |
| S1.2 | Profile geolocations + include in drift KL | main | pending |
| S1.3 | Auto-write containment queue; wire containment_threshold | main | pending |
| S1.4 | Align embedding defaults/metadata to ngram runtime | main | pending |
| S1.5 | Smoke benign-only / correlated-benign under fixed partitions | main | pending |

### Sprint S2 — Phase 1 reopen leftovers

| ID | Objective | Owner | Status |
|---|---|---|---|
| S2.1 | Resolver collision/split → low_resolution_confidence | main | pending |
| S2.2 | Evidence-binding raw_score reconstruction test | main | pending |
| S2.3 | decision_id includes algorithm (+ embedding) version | main | pending |
| S2.4 | confidence n/(n+k) + confidence_k in scoring_config | main | pending |
| S2.5 | Frozen cohort artifacts **or** SPEC_V3 downgrade note | main | pending |
| S2.6 | total_volume_delta implement or remove from claims | main | pending |
| S2.7 | Lifecycle states minimal ship **or** defer note | main | pending |
| S2.8 | Apply YAML inventory (wire cheap / strip from calibrated claims) | main | pending |

### Sprint S3 — Hybrid calibration close

| ID | Objective | Owner | Status |
|---|---|---|---|
| S3.1 | Full eval sweep after S1/S2 fixes | main | pending |
| S3.2 | Refresh calibration_final_metrics.json + PR curve | main | pending |
| S3.3 | If S2 FN: residual-risk note (no fake CALIBRATED) | main | pending |
| S3.4 | If S2 catches: document operating point + residuals | main | pending |
| S3.5 | Update SPEC/phase2 docs status to match metrics | main | pending |
| S3.6 | Scoring-config governance record for any knob change | main | pending |

### Sprint S4 — Phase 3 product finish

| ID | Objective | Owner | Status |
|---|---|---|---|
| S4.1 | Explainer slot-isolated low-trust fields | main | pending |
| S4.2 | Explainer queue-depth + template fallback | main | pending |
| S4.3 | Suppressed aging/jitter **or** defer note (view required) | main | pending |
| S4.4 | Demo path seed → triage → explain → contain | main | pending |
| S4.5 | First-class replay_run_id on decisions/audit | main | pending |
| S4.6 | Calendar / telemetry-gap: ship or mark deferred | main | pending |
| S4.7 | Asset/service-dependency context: minimal or defer | main | pending |

### Exit gates (chat_gate / phase_exit)

| ID | Objective | Owner | Status |
|---|---|---|---|
| S1-EXIT-GATE | S1 close: skeptic + pytest + ruff; unlocks S2 | main | ready |
| S2-EXIT-GATE | S2 close: skeptic + pytest + ruff; unlocks S3 | main | pending |
| S3-EXIT-GATE | S3 close: skeptic + pytest + ruff + honest metrics; unlocks S4 | main | pending |
| S4-EXIT-GATE | S4 close: skeptic + pytest + ruff; unlocks HUMAN-DRIFT-RESEARCH | main | done |
| S5-EXIT-GATE | S5 close: skeptic + pytest + ruff; unlocks S6 | main | ready |

### Gate — human research (blocks S5; after S4-EXIT-GATE)

| ID | Objective | Owner | Status |
|---|---|---|---|
| HUMAN-DRIFT-RESEARCH | Operator starts personal drift-methodology research; ack before S5 | human | pending |

### Sprint S5 — Phase 4 / §9 portfolio

| ID | Objective | Owner | Status |
|---|---|---|---|
| S5.1 | Dockerfiles + four-container compose | main | pending |
| S5.2 | IaC **or** explicit portfolio IaC downgrade | main | pending |
| S5.3 | Postgres INSERT-only roles + REVOKE | main | pending |
| S5.4 | Scheduled audit hash-chain integrity job | main | pending |
| S5.5 | Staleness + active-alert mandatory escalation | main | pending |
| S5.6 | max_profile_build_block_days supervisor escalation | main | pending |
| S5.7 | Empirical LLM determinism vs pinned non-alias model | main | pending |
| S5.8 | pgvector / embedding migration playbook | main | pending |
| S5.9 | Schema/embedding mismatch detection at scorer startup | main | pending |
| S5.10 | Counterfactual corpus + harness **or** claim downgrade | main | pending |
| S5.11 | Advanced cohort prior-update gates **or** §13.1 defer | main | pending |
| S5.12 | Threat-model polish + README = implemented behavior | main | pending |

### Sprint S6 — Hardening empirical handoff

| ID | Objective | Owner | Status |
|---|---|---|---|
| S6.1 | Hardening sweep checklist (commands, seeds, artifacts) | main | done |
| S6.2 | Residual-risk + open drift hypotheses for human research | main | done |
| S6.3 | Standing rule: no silent weight changes (document in OPS) | main | done |

## Autopilot loop (UAW / GSD-style)

Use the installed `.claude` agent roster (not archived gsd-build):

| Role | Agent | When |
|---|---|---|
| Research | `researcher` | Ambiguous packet / fork (S2.5, S2.7, S4.6) |
| Implement | `implementer` | One `ready` packet, TDD, disjoint write scope |
| Test | `test-runner` | After implement; focused then regression |
| Verify | `skeptic-verifier` | Sprint close / completion claims |

**Loop rules**

1. Canonical progress = `state.json` packet statuses (update first, then sync memory-bank).
2. Only mark the current sprint’s packets `ready`; keep later sprints `pending` until the prior EXIT-GATE is `done`.
3. Do not start any `S5.*` until `HUMAN-DRIFT-RESEARCH` is `done` (operator ack). Do not start HUMAN until `S4-EXIT-GATE` is `done`.
4. Stop conditions: EXIT-GATE or HUMAN next with `--stop-before-gate`; 3× same failure → `blocked`; budget/checkpoint before Docker/DB-role / weight changes.
5. Validate: `python C:/Users/oalan/ultimate-agentic-workflow/scripts/verify_run.py --run-dir .workflow/2026-07-12-v1-portfolio-ready`

## Requirement Traceability Matrix

| Req | AC | Task | Verification | Status |
|---|---|---|---|---|
| REQ-S0 | Spec/README match metrics; ngram narrative locked | S0.1–S0.5 | Doc audit vs calibration_final_metrics.json | planned |
| REQ-S1 | Next sweep is partition/geo/containment-honest | S1.1–S1.5 + S1-EXIT-GATE | Focused tests + generator/builder checks + exit gate | planned |
| REQ-S2 | SPEC_V3 §7 honesty blockers closed or downgraded | S2.1–S2.8 + S2-EXIT-GATE | New tests + explicit defer notes + exit gate | planned |
| REQ-S3 | Hybrid calibration close with honest status | S3.1–S3.6 + S3-EXIT-GATE | Fresh metrics JSON + governance record + exit gate | planned |
| REQ-S4 | Phase 3 non-negotiable UI/explain/demo | S4.1–S4.7 + S4-EXIT-GATE | API/UI smoke + explainer tests + exit gate | planned |
| REQ-HUMAN | Drift research started before portfolio hardening | HUMAN-DRIFT-RESEARCH | Operator ack in state.json | planned |
| REQ-S5 | SPEC_V3 §9 / Phase 4 portfolio gate | S5.1–S5.12 + S5-EXIT-GATE | Deploy/docs/tests per packet + exit gate | planned |
| REQ-S6 | Empirical handoff ready for human sweeps | S6.1–S6.3 | Checklist + residual doc exist | done |

## Verification

- `python C:/Users/oalan/ultimate-agentic-workflow/scripts/verify_run.py --run-dir .workflow/2026-07-12-v1-portfolio-ready` → ok
- Per-packet: focused pytest / doc audit named in packet result
- Sprint close: `pytest -v --tb=short` + `ruff check .` (stop-gate)
- Program close: RTM all `done`/`deferred`; final-report.md written
