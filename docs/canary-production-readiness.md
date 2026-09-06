# ALTER_EGO — Canary vs Production Readiness

**Date:** 2026-09-06  
**Assessor:** independent repo pass (docs, evals, CI, configs, core pipelines)  
**Owner context accepted:** pre-production; new evals swept and did not reduce FP in a useful way; not calibrated; architecture/governance/auditability valued; usefulness still in question.

## Verdict

| Deployment | Score | Decision |
|---|---:|---|
| **Shadow canary** (single-operator, no auto-containment, bounded real or replayed production logs) | **28 / 100** | **NO-GO** |
| **Production** (SOC-usable detector, live ingest, staffed triage, rollback, authz) | **12 / 100** | **NO-GO** |

Lab/demo on synthetic data is already the current state. That is not a canary.

**One-line:** the control-plane and honesty culture are unusually strong for a research stack; the detector is not useful yet, and the ops surface cannot safely host even a small live shadow.

---

## 1. What the system claims to do

ALTER_EGO is a **local-first UEBA-style behavioral identity engine**. It profiles how users and service accounts normally behave, then scores new auth/process events against immutable versioned profiles.

**Claimed pipeline** (`README.md`, `docs/SPEC.md` §4, `AS_BUILT.md` §1):

```
Ingest → Resolver → Profiler (DuckDB) → Scorer → Recorder
                                              ↓
                                    Postgres + pgvector
                                              ↓
                                    Analyst triage UI + simulated containment
```

**Product claims that the code actually supports:**

- Deterministic hot-path scoring (no LLM in `worker/scorer.py`). Embeddings are char 3-gram SHA-256 → 128-d (`worker/vectorizer.py`, model id `alter-ego-ngram-v1`).
- Frozen `ProfileArtifact` (`core/schemas/profiles.py`); promotion/supersede rather than payload mutation.
- Multi-feature fusion: login/geo/endpoint/process rarity, command-line embedding distance, cumulative KL drift, service-account periodicity.
- Post-threshold LLM explanation with slot isolation and template fallback (`worker/explainer.py`).
- Four named synthetic attack scenarios (plus S5 patient-cycle in later series).
- Simulated containment only — a queue write, not IAM disable (`SPEC.md` §2.1, `worker/recorder.py`).

**Claims that overshoot the code:**

| Claim | Reality |
|---|---|
| `docs/deployment.md` / `SPEC.md` §4.4: web container includes an **ingest API** | `web/api.py` has no ingest route. Ingest is `python -m worker.ingest <events.jsonl>` only. |
| README badge “v1 portfolio shipped” | Portfolio bar ≠ calibrated detector. Phases 0–4 remain **Partial**. |
| README / `docs/calibration_final_metrics.json` as current operating point (P≈0.019, FP=3448, S2 R=1.0) | Those are **Series A (S3.1)**. Latest campaign is **Series I** (2026-08-03): P≈0.0068, FP=7840, S2 R=0.743, S3 R=0.111. Cross-series FP/P/R comparison is forbidden by the project’s own rules. |
| `SPEC.md` §9.2 “scheduled” audit integrity job | `batch/audit_integrity.py` exists; `docker-compose.yml` `batch` is `sleep infinity`. Nothing schedules it. |
| `SPEC.md` §9.2 “no hardcoded credentials” | Compose defaults: `password`, `alter_ego_app_dev`, `API_KEY=dev-key` (`docker-compose.yml`). Documented as local-dev, still committed. |
| Hot-path scoring governed by `ConfigStore` / `scoring_configs` | Scorer reads **raw YAML file** (`worker/scorer.py` `load_scoring_config`). `worker/config_store.py` is a side store. |
| CLAUDE.md: profile changes require `ProfileStore.promote_profile()` | `AS_BUILT.md` §6: builder inserts + sets `superseded_at`; does not call `promote_profile()`. |
| Series A S2 recall 1.0 as evidence drift works | Retracted. `docs/residual-risk-drift-hypotheses.md` §2.6 / H11; `OPS.md` headline-recall rule. |

**Honest self-description** (this is a strength): README, SPEC header, `memory-bank/progress.md`, every Series I artifact, and `config/scoring_config.yaml` consumers all say **not CALIBRATED**. The project does not currently lie about being production-ready. It does still advertise stale Series A numbers as the saved operating point.

**Explicit v1 non-goals** (`memory-bank/progress.md`, `SPEC.md` §2.3): real SIEM, multi-tenant, production IAM disablement, live enterprise ingest, K8s operators, WORM/superuser-proof audit, TLS/public ingress.

---

## 2. Architecture maturity

### Boundaries — mature for a research system

Package split matches the spec: `core/` contracts, `worker/` hot path, `batch/` cold path, `web/` analyst surface. Three-tier latency model (cold profile build / hot deterministic score / warm explain) is real. Docker compresses that into four containers (`docker-compose.yml`): `postgres`, `web`, `worker`, `batch`.

### Authz — not production, and the shipped UI fights the lock

- Privileged writes (`explain`, `workflow`, `contain`, `replay`, `extend-halt`) require `X-API-KEY` matching `API_KEY` (`web/api.py` `verify_api_key`).
- All **GET** alert/escalation/suppressed routes are **unauthenticated**. Anyone who can reach port 8000 reads the queue.
- `verify_api_key` **no-ops when `pytest` is in `sys.modules`** — a production-code test bypass.
- `web/static/app.js` **never sends `X-API-KEY`**. Compose sets `API_KEY=dev-key`. Browser acknowledge / contain / explain therefore 401 in the documented four-container stack. The CLI demo (`scripts/demo_path.py --api-key`) works; the UI does not.
- No roles, no IdP, no per-analyst identity. SPEC maps this to “local authorization / detection_engineer” — that mapping is not implemented.

### Audit trails — strongest part of the repo

- INSERT-only `alter_ego_app` role; profile payload immutable; lifecycle columns only (`alembic/versions/g6h7i8j9k0l1_add_app_db_roles.py`, `docs/deployment.md` grant matrix).
- Application-layer hash chain (`core/models.py` `verify_audit_log_chain`, `tests/test_audit.py`).
- Integrity job exists (`batch/audit_integrity.py`) but is **on-demand**, not scheduled.
- Honest limit: not WORM, not superuser-proof (`SPEC.md` §3.3).
- Config governance *records* exist (`docs/scoring-config-governance-*.md`, `ConfigStore.save_config`) and the standing rule “no knob change without a sweep” is actually followed. Live scoring still ignores the DB config chain.

### Config — versioned file, not a control plane

`config/scoring_config.yaml` v2.2 is the live SoT. Feature `enabled` flags (`precision_gate`, `staged_drift`, `drift_weights.cadence|total_volume_delta|geo_velocity`, `features.total_volume_delta`) are real kill-switches. `ALTER_EGO_SCORING_CONFIG` env override exists for eval parallelism — that is the closest thing to a canary config hook.

Seven YAML keys remain unread in production (`AS_BUILT.md` §5.4 / `memory-bank/progress.md` inventory): calendar, aging jitter, gap windows, `min_clean_observation_count`, and the stubbed `total_volume_delta` score.

### Deployment — local compose only

- Single `Dockerfile`, no healthchecks, no restart policy, no resource limits.
- Worker is `while true; resolve; score; sleep 5` (`docker-compose.yml`). `docs/deployment.md` itself calls this “suitable for portfolio demos.”
- Worker **does not ingest and does not build profiles** (`AS_BUILT.md` §2.5). Cold path is manual `docker compose exec`.
- Postgres `5432` published to the host. Default passwords in compose.
- CI (`.github/workflows/ci.yml`): pytest on 3.11/3.12/3.13 only. **No ruff, no mypy, no compose smoke, no role-grant test.** `pyproject.toml` has strict mypy and ruff; they are local/agent gates, not CI.
- No Kubernetes, Terraform, TLS, secrets manager — deferred and documented.

**Architecture grade:** the *ideas* (immutability, fail-closed scoring, partition hygiene, evidence binding, replay constraints) are production-minded. The *runtime* is a demo stack with a governance paper trail.

---

## 3. Eval / calibration — owner claim confirmed

Owner: new evals were swept, they were **not** a gain in FP reduction, system is **not calibrated**. The tree agrees.

### Latest numbers (use these, not README)

Source: `.workflow/2026-08-02-series-i-serial-calibration/` (fold chain complete 2026-08-03). Headline after the only accepted fold (`precision_gate.enabled=true`):

| Metric @ `anomaly_threshold=45` | Series I accepted |
|---|---|
| Precision | **0.00684** |
| Recall | **0.462** |
| F1 | **0.0135** |
| TP / FP / FN | **54 / 7840 / 63** |
| S1 / S2 / S3 / S4 / S5 recall | 1.0 / 0.743 / **0.111** / 1.0 / 0.60 |

Baseline before the fold: FP **7995**. After: **7840**. That is a **2%** FP dip and **zero** TP change.

### Reconciliation with “new evals didn’t help FP”

Independent review already on disk (`.workflow/2026-08-02-series-i-serial-calibration/results/series-i-independent-review.md`) is the right reading:

1. **Across all 12 Series I runs, TP is 54.** Per-scenario recalls are bit-identical. Treatments did not change a single detection.
2. Four of five additive folds were rejected as inert or worse (`state.json` `rejected_flags`). Cadence and geo-velocity were aborted as **wired-but-null** (DEBT-078; geo delta 100% zero).
3. `precision_gate` is the only accept. It gates **containment at score≥85**, not the thr=45 anomaly path that generates the 7840 FPs. Calling that “FP reduction” is technically true and operationally meaningless.
4. F1@45 is dominated by point-anomaly FP. Drift carries 100% of TP in S2/S3/S5 (`drift_necessary_tp_fraction: 1.0`) and is invisible in the headline. The instrument cannot see the features it was asked to rank.
5. `anomaly_threshold: 45` was **never swept** in Series I. Series A PR curve (`docs/calibration_pr_curve.json`) never reaches usable precision: best-F1 is thr=55 at **P=0.041**, still 1136 FP. Raising further collapses recall (thr=70: P=0.005, R=0.049). There is no hidden good operating point in the saved curve.
6. Coverage artifacts: `promotion_coverage_in_window.fraction = 0.454`; `blocked_entity_count = 53/65`; `stale_entity_days = 550/1072`. Half the eval window scores stale profiles. 82% of entities are promotion-blocked.
7. `endpoint_set` drift is **identically zero** in all 12 runs (n=1300) while still weighted 5.0 — a shipped dimension that is a wiring failure, same class as cadence.
8. `attack_event_count: 157` but `tp+fn = 117`. **40 attack events (25%)** are missing from the recall denominator with no stated reason.

`state.json` `merge_recommendation.merge_to_main: false`, `calibrated: false`. Memory-bank (`memory-bank/activeContext.md`, `memory-bank/tasks.md`) matches: **1 accept / 4 reject; calibrated false.**

### Why this also kills usefulness

`docs/residual-risk-drift-hypotheses.md` §2.1 / §2.7: under §5.5 arming, **every anomaly opens a workflow that blocks that entity’s profile promotion**, freezing `cumulative_drift`. At ~145 false alerts per true one, the drift path — the only path that catches slow-roll / subtle / patient-cycle — starves. Point-anomaly precision is a prerequisite for drift to function, not a separate polish item.

Series A S2 R=1.0 is a retracted harness artifact. Series I S3 R=0.111 with `attack_raised_cumulative_drift_max ≈ 25.6` against `drift_threshold: 5.0` means the drift *signal* exists and the *gate/timing* still misses 40 of 45 subtle events. That is not a missing-feature problem. Series I spent a campaign proving it.

**Calibration status:** pending. Not “almost.” The threshold that defines the product has not been chosen from a usable PR curve, because no such point is in the artifacts.

---

## 4. Observability, failure modes, rollback, canary hooks

### Observability — nearly none

- Settings: `LOG_LEVEL` (`core/settings.py`). No Prometheus, OTel, Sentry, structured decision metrics, queue-depth gauge, or `/health`.
- Compose: Postgres has `pg_isready`. Web/worker/batch have **no healthcheck**.
- Audit integrity is a CLI you remember to run.
- No on-call, no SLO, no alert on worker-loop death (the loop is `sleep 5` in a shell `while true`).

### Failure modes that *are* designed

| Mode | Behavior | File |
|---|---|---|
| Stale profile | score 0, `staleness_halt`, not anomaly | `worker/scorer.py` |
| Embedding metadata mismatch | score 0, halt flag | `worker/scorer.py` |
| No active profile | event **skipped**, stays unscored (fail-open coverage) | `AS_BUILT.md` §7 |
| LLM down / queue overflow | template explanation | `worker/explainer.py` |
| Duplicate decision | IntegrityError → reject | `worker/recorder.py` |
| Profile build block exceeds SLA | supervisor escalation decision | builder + `max_profile_build_block_days` |

These are real and tested. They do not substitute for process liveness, ingest backlog, or “we are drowning in FP.”

### Rollback

- Decision replay: contiguous window only, originals preserved, `replay_run_id` (`batch/replay_runner.py`, `POST /api/replay`). This is a **re-score**, not a deploy rollback.
- Config rollback: change the YAML file (and, separately, maybe write `ConfigStore`). No traffic split, no versioned scorer binary pin, no automated “revert last config.”
- Compose: `docker compose down` is the rollback.

### Feature flags / canary hooks

YAML `enabled` flags are **algorithm kill-switches**, not canary. They apply to every scored event. There is no entity-allowlist, percentage rollout, shadow-vs-page dual-write, or “score but do not open workflow” mode for a subset of production identities.

`precision_gate.enabled=true` is the only promoted flag. Containment is already simulated, so the blast radius of a bad score is **alert volume and promotion deadlock**, not IAM. That is the one thing that makes a future shadow canary conceivable.

---

## 5. Gaps blocking canary vs gaps blocking production

**Canary** here means: one operator, shadow scores on a **bounded real or replayed production-shaped stream**, no auto-containment, goal = learn whether the detector is useful.

### Blocks canary (must fix or explicitly accept before any live/replay shadow)

1. **No real ingest path.** JSONL file only. No SIEM/HTTP/queue consumer. Worker does not ingest. You cannot attach a production stream without new code.
2. **Unusable alert volume at the only threshold.** ~145 FP per TP on synthetic. On real logs this gets worse, not better. A canary that opens thousands of workflows will freeze profiles (`blocked_entity_count` 53/65 in Series I) and teach you nothing about drift.
3. **Eval instrument is not trustworthy enough to interpret a canary.** TP frozen, 25% of attacks missing from the denominator, `endpoint_set` identically zero, half the window stale. You would not know if the canary “worked.”
4. **No health/metrics.** You cannot tell if the sleep-loop worker died, ingest stalled, or scoring halted fleet-wide.
5. **Read APIs open; write APIs broken from the UI.** Shadow canary on a reachable port leaks the queue; the analyst clicks do not authenticate.

A **synthetic-only** “canary” is not a new deployment — it is `pytest` + `scripts/demo_path.py` + compose. That already exists. Do not relabel it.

### Additional blocks for production

6. Calibrated operating point a human SOC can staff (precision that is not 0.7–4%).
7. Live ingest + schema adapters for real auth/process logs; partition discipline on real `production` vs eval.
8. TLS, secrets manager, real RBAC, remove pytest auth bypass, bind/publish hygiene (Postgres 5432).
9. Scheduled profile builds, scheduled audit integrity, restart/backoff, healthchecks, metrics, paging.
10. Config control plane actually on the hot path; replay/rollback runbook that an on-call can execute.
11. K8s/multi-env IaC if this leaves a single laptop (deferred, correctly).
12. WORM / external audit ship if the threat model includes a privileged operator (deferred, correctly).
13. Real containment — explicitly out of v1; do not add it until (6) is true.

Deferred product items (calendar dual-score, lifecycle states, volume_delta, cohort prior-update gates) are **not** the production gate. Usefulness and ops are.

---

## 6. Scores and top 5 blockers

### Scoring rationale (not a vibe)

| Axis | Canary | Prod | Note |
|---|---:|---:|---|
| Architecture / immutability / no-LLM hot path | 18 | 8 | Strong design, demo runtime |
| Governance / audit honesty | 6 | 3 | Culture is real; scheduled enforcement is not |
| Detection usefulness / calibration | 1 | 0 | Series I: TP invariant, P=0.007 |
| Ingest / deploy / control plane | 1 | 0 | JSONL + YAML file + sleep loop |
| Observability / authz / rollback | 2 | 1 | Flags exist; no canary machinery |
| **Total** | **28** | **12** | |

Points are reserved for what a later canary can *reuse* (fail-closed, simulated containment, YAML kill-switches, replay, hash chain). They are not a claim that 28% of a canary is “done.”

### Top 5 blockers (ranked)

1. **`anomaly_threshold=45` is an unusable, unswept operating point.** Latest honest precision is 0.68%. Series A’s best-F1 (thr=55) is still 4% precision. No saved curve has a SOC-viable point. This is the product.
2. **Usefulness is not demonstrated — and Series I showed new features do not move detections.** TP=54 in every run. S3 recall 0.11. Cadence/geo/volume/fleet/staged inert or aborted. Owner’s “not a gain in FP reduction” is correct; the deeper finding is **no detection effect at all**.
3. **FP × §5.5 promotion-block deadlock.** High point-anomaly FP freezes baselines, which blinds the drift path that carries the attack classes you care about. Shipping thr=45 into any live stream recreates Series B/I starvation.
4. **No production ingest and no live config plane.** Cannot attach real telemetry; scorer does not read `ConfigStore`; compose worker neither ingests nor profiles. A canary has nothing to eat and no safe knob to turn without a YAML edit + process bounce.
5. **Ops/auth gap that makes even a localhost shadow sloppy.** No `/health` or metrics; audit job unscheduled; GET queue unauthenticated; UI writes omit the API key; CI is pytest-only; default DB/API secrets in compose.

---

## Discarded hunches

- **“Portfolio shipped ≈ nearly canary.”** False. S0–S6 closed a *honesty and scaffolding* bar, not a detector bar. Phases remain Partial by the repo’s own table.
- **“README P=0.019 is the current number.”** False. Series I is current; Series A is archival. Cross-series P/R/FP comparison is invalid (`docs/residual-risk-drift-hypotheses.md` §5).
- **“precision_gate is the FP win that unblocks canary.”** False. −155 FP on 7995, TP unchanged, gates containment not triage.
- **“S2 R=1.0 means boil-the-frog is solved.”** Retracted. Series I S2=0.743 with 82% entities blocked.
- **“Audit is production-grade because the hash chain exists.”** App-layer + on-demand job. Fine for a portfolio; not a canary control.
- **“ConfigStore means config is governed at runtime.”** Only the YAML file is.

---

## What to do (actionable, not a backlog)

Do **not** run another feature-fold campaign. The last one could not see its treatments.

1. **Fix the instrument** (no sweep): `endpoint_set` identically zero; 157 vs 117 attack-event hole; report S2/S3/S5 and drift-vs-point axes separately (`series-i-independent-review.md` steps 1–3).
2. **Fix coverage** before any new “calibration”: in-window promotion 0.45 and 82% blocked entities dominate recall. Then re-anchor a baseline.
3. **Sweep `anomaly_threshold` only after (1)(2).** If precision never reaches even 0.1, that is the finding. It outranks every `enabled` flag.
4. **Do not attach real traffic** until there is a shadow mode that can **score without opening workflows** (or an entity allowlist) plus JSONL/HTTP ingest and a health endpoint.
5. Keep the governance culture. It is the part of this repo that is already acting like production.

**Canary go condition (minimum):** real-or-replay ingest on a tiny allowlist, score-without-block mode, health+alert-volume metrics, authenticated reads, a threshold (or gate) that does not freeze the fleet, and an eval denominator you trust.

**Production go condition:** canary condition plus a staffable precision, scheduled cold path + audit, secrets/TLS/RBAC, hot-path config versioning, and a rollback runbook that does not require the original author.

Until then: **NO-GO / NO-GO.**
