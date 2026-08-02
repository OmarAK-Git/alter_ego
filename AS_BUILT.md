# AS_BUILT — ALTER_EGO reverse specification

**Extracted:** 2026-07-30  
**Method:** Structured code inventory (not aspirational SPEC). Citations are `path:symbol`.  
**Companion:** [`DEBT_LEDGER.md`](DEBT_LEDGER.md)

This document describes the system **as it exists in the repository**. Where behavior differs from `CLAUDE.md` / `SPEC.md` / `docs/SPEC.md`, the code wins and the delta is called out.

---

## 1. System identity

ALTER_EGO is a local behavioral identity detection stack:

1. Ingest telemetry events into PostgreSQL (or SQLite for tests).
2. Resolve raw entity IDs to canonical entities.
3. Build immutable profile artifacts (batch DuckDB histograms + drift).
4. Score resolved events against the active profile.
5. Persist insert-only decisions; open alert workflow / simulated containment when thresholds fire.
6. Optionally explain anomalies via LLM (warm path) with deterministic template fallback.
7. Expose an analyst triage API + static UI.

**Product version signal:** `pyproject.toml` `0.1.0`. Scoring config SoT: `config/scoring_config.yaml` **v2.2**. Calibration status in memory-bank: **not CALIBRATED**.

---

## 2. Module inventory

### 2.1 Packaged runtime (`pyproject.toml` setuptools include)

| Package | Purpose | Key modules |
|---------|---------|-------------|
| `core/` | Shared ORM, Pydantic contracts, settings, math, attestation | `models.py`, `database.py`, `settings.py`, `math_utils.py`, `attestation.py`, `schemas/*` |
| `worker/` | Live pipeline + stores + vectorizer + explainer | `ingest.py`, `resolver.py`, `scorer.py`, `recorder.py`, `profile_store.py`, `config_store.py`, `vectorizer.py`, `explainer.py` |
| `batch/` | Profile builder, synthetic data, eval, replay, audit job | `profile_builder/builder.py`, `synthetic/*`, `eval/*`, `replay_runner.py`, `audit_integrity.py` |
| `web/` | FastAPI analyst API + static UI | `api.py`, `static/*` |

### 2.2 Non-packaged but operational

| Path | Role |
|------|------|
| `config/scoring_config.yaml` | Tunable weights/thresholds (hot path loads raw YAML dict) |
| `alembic/` | Migrations (8 revisions through staleness-halt extensions) |
| `scripts/demo_path.py` | Demo seed/run without live LLM |
| `scripts/llm_determinism_check.py` | Temp=0 provider hash check → `docs/llm-determinism-check.md` |
| `persist_config.py` | Attempt to persist YAML via `ConfigStore` / `ScoringConfig` |
| `verify_lineage.py` | Lineage helper (stale version assumptions) |
| `docker-compose.yml` | `postgres` (pgvector), `web`, `worker`, `batch` |

### 2.3 Not runtime code

- **No `live/` package** — only `tests/live/`.
- `tests/`, `docs/`, `scratch/`, `memory-bank/`, `.workflow/` are verification, docs, and process.

### 2.4 Frozen / immutable types

| Type | Location | Mechanism |
|------|----------|-----------|
| `ProfileArtifact` | `core/schemas/profiles.py` | `ConfigDict(frozen=True)` |
| `ScoringConfig` | `core/schemas/config.py` | `frozen=True` (governance shape; **≠** live YAML) |
| `EmbeddingMetadataMismatch` | `worker/scorer.py` | `@dataclass(frozen=True)` |

### 2.5 Public entrypoints

| Entrypoint | How invoked |
|------------|-------------|
| Analyst API | `uvicorn web.api:app` |
| Ingest | `python -m worker.ingest <events.jsonl> [ground_truth.jsonl]` |
| Resolver | `python -m worker.resolver` |
| Scorer loop | `process_unscored_events()` (Docker worker; no `__main__`) |
| Profile build | `build_profiles(...)` (eval / manual; no `__main__`) |
| Eval pipeline | `python -m batch.eval.runner` |
| Audit integrity | `python -m batch.audit_integrity` |
| Synthetic generator | `python -m batch.synthetic.generator` (default scenarios 1–4) |
| Demo | `python scripts/demo_path.py …` |

Docker **worker** service: resolve + score every 5s — **does not** ingest or build profiles.

---

## 3. Data stores

| Store | Role |
|-------|------|
| **PostgreSQL + pgvector** | System of record: events, resolved events, profiles (`Vector(128)`), decisions, explanations, audit_logs, workflow, containment, scoring_configs, ground truth, staleness extensions |
| **SQLite** | Test / local fallback via `core/database.py` compilers (`JSONB`/`Vector` shims) |
| **DuckDB** | Ephemeral inside `build_profiles`: temp JSONL → histograms/centroids; **not** persisted |

---

## 4. Data flows (as-built)

### 4.1 Operational pipeline

```
JSONL / events
  → worker.ingest.ingest_events          → EventModel
  → worker.resolver.process_unresolved_events → ResolvedEventModel
  → batch.profile_builder.builder.build_profiles
        Postgres slice → temp JSONL → DuckDB aggregations
        → ProfileArtifactModel (promoted or shadow)
  → worker.scorer.process_unscored_events
        ProfileStore.get_active_profile + score_event → DecisionRecord
  → worker.recorder.record_decision      → DecisionRecordModel
        + AlertWorkflowStateModel (anomaly)
        + ContainmentQueueModel (containment flag)
```

Profiler is **batch**, not an inline stage of the Docker worker loop. CLAUDE’s linear “Resolver → Profiler → Scorer” diagram overstates live-path coupling.

### 4.2 Stage contracts

| Stage | Inputs | Outputs |
|-------|--------|---------|
| Ingest | JSONL → `Event` Pydantic | `EventModel` |
| Ingest GT | JSONL labels | `EvalGroundTruthModel` (raw dict; weaker validation) |
| Resolver | Unresolved `EventModel` | `ResolvedEvent` / `ResolvedEventModel` via `resolve_entity` |
| Profiler | Resolved events in partitions `production`, `eval_scenario_2\|3\|5`; YAML; active alerts | New profile rows; optional drift decisions; auto-resolve / build-block escalations |
| Scorer | `ResolvedEvent`, `ProfileArtifact`, config `dict` | `DecisionRecord` |
| Recorder | `DecisionRecord` | Insert-only decision; may open alert / queue containment |

### 4.3 Synthetic / eval path

1. `batch.synthetic.generator.EventGenerator` → events + labels (`eval_scenario_*` partitions). Five injectors exist (`inject_scenario_1`…`_5`); default `__main__` runs 1–4; `ScenarioType` enum has **4** members.
2. `batch.eval.runner.run_pipeline`: clear → windowed ingest → resolve → `build_profiles(as_of=…)` → score → metrics.
3. Related CLIs: `calibrate.py`, `report.py`, `rescore.py`, `analyze_misses.py`.

### 4.4 Replay path

`POST /api/replay` → `batch.replay_runner.run_replay`: re-score production resolved events in window; new `DecisionRecordModel` rows with `replay_run_id` (originals untouched). `ReplayRequest` old/new config version fields are **ignored** (always `load_scoring_config()`).

### 4.5 Explanation path (warm)

`POST /api/alerts/{decision_id}/explain` → `worker.explainer.generate_explanation`: queue-depth gate → LLM providers → validate → else `generate_template_explanation`. **Not** on the hot scoring path.

---

## 5. Interfaces

### 5.1 HTTP (`web/api.py`)

| Method | Path | Auth |
|--------|------|------|
| GET | `/` | none |
| GET | `/static/*` | none |
| GET | `/api/alerts` | none |
| GET | `/api/alerts/{decision_id}` | none |
| GET | `/api/suppressed` | none |
| GET | `/api/mandatory-escalations` | none |
| POST | `/api/alerts/{decision_id}/explain` | `X-API-KEY` |
| PUT | `/api/alerts/{decision_id}/workflow` | `X-API-KEY` |
| POST | `/api/alerts/{decision_id}/contain` | `X-API-KEY` |
| POST | `/api/mandatory-escalations/{entity_id}/extend-halt` | `X-API-KEY` |
| POST | `/api/replay` | `X-API-KEY` |

Auth: env `API_KEY`; bypassed when pytest is detected.

### 5.2 Cross-package APIs (high signal)

| Boundary | Symbols |
|----------|---------|
| batch/web → worker | `ingest_*`, `process_unresolved_events`, `process_unscored_events` / `score_event`, `load_scoring_config`, `record_decision`, `ProfileStore`, `generate_explanation`, vectorizer |
| worker/batch → core | models, schemas, `SessionLocal`, `math_utils`, `attestation` |
| web → batch | `run_replay`, `BUILD_BLOCK_SUPERVISOR_ESCALATION_FLAG` |

### 5.3 ORM ↔ schema map

| ORM (`core/models.py`) | Pydantic |
|------------------------|----------|
| `EventModel` | `Event` |
| `ResolvedEventModel` | `ResolvedEvent` |
| `ProfileArtifactModel` | `ProfileArtifact` (frozen; ORM mutable lifecycle cols) |
| `DecisionRecordModel` | `DecisionRecord` |
| `ExplanationRecordModel` | `ExplanationRecord` |
| `ContainmentQueueModel` | `ContainmentQueue` |
| `AlertWorkflowStateModel` | workflow schemas (`AlertStateUpdate`, …) |
| `ScoringConfigModel` | `ScoringConfig` / `ScoringConfigRecord` (**shape ≠ YAML**) |
| `EvalGroundTruthModel` | no dedicated schema |
| `AuditLogModel` | helpers only (`log_audit_event`, `verify_audit_log_chain`) |
| `StalenessHaltExtensionModel` | `ExtendHaltRequest` |

### 5.4 Config interface (what is actually read)

Hot path uses **raw YAML `dict`**, not `ScoringConfig`.

**Read by scorer / consumers:** `version`, `anomaly_threshold`, `drift_threshold`, `max_profile_staleness_days`, `confidence_floor`, `confidence_k`, `containment_threshold`, `contribution_scale_max`, `laplace_alpha`, `cohort_gate_window_days`, `cohort_gating_constants.min_cohort_size`, `.max_changed_fraction`, feature weights (except unused `total_volume_delta`), `explainer_queue_depth`.

**Read by builder:** `drift_weights`, `drift_threshold`, `drift_comparison_history_count`, `drift_half_life_days`, `laplace_alpha`, `max_profile_build_block_days`, `max_replay_window_days`, `recent_drift_window_days`, `version`.

**Present in YAML, not read in production:** `max_calendar_adjustment`, `age_jitter_hours`, `gap_windows.*`, `cohort_gating_constants.min_clean_observation_count`.

**Code constants, not YAML:** attestation knobs in `core/attestation.py` (`QUIET_WINDOW_DAYS`, `ALPHA_PROD`, `ALPHA_ANCHOR`, …).

Full knob inventory: `memory-bank/progress.md` (Scoring config knob inventory).

---

## 6. Invariants — enforced vs claimed

| Invariant | Status | Evidence |
|-----------|--------|----------|
| `ProfileArtifact` frozen | **ENFORCED** | `core/schemas/profiles.py`; `tests/test_profile_immutability.py` |
| No profile payload mutation; promote/supersede only | **PARTIAL** | Builder inserts new rows + sets `superseded_at`; `ProfileStore.promote_profile` exists but **builder does not call it**. DB role grants UPDATE only on `promoted_at`, `superseded_at` (`alembic/.../g6h7i8j9k0l1`). CLAUDE claim that changes “require `promote_profile()`” is overstated. |
| Deterministic char 3-gram 128-d vectorizer; model `alter-ego-ngram-v1` | **ENFORCED** | `worker/vectorizer.py`, schema defaults, S5.9 mismatch halt |
| No LLM on hot path | **ENFORCED** | Scorer uses vectorizer only; LLM in `explainer.py` |
| Drift windows / KL / cohort-median / half-life / thr 5.0 | **ENFORCED** params; **PARTIAL** wording | YAML + builder. CLAUDE “KL of 3d vs 30d baseline” ≠ code: recent window vs **prior promoted profiles** (up to `drift_comparison_history_count`), while 30d builds profile content. |
| Staleness halt (`max_profile_staleness_days: 14`) | **ENFORCED** | `score_event` → score 0, `staleness_halt`, not anomaly |
| Cohort novelty gate (≥10 peers, 20%, 7d) | **ENFORCED** | `_get_novelty_fraction` + suppress flags |
| Advanced prior-update / independent cohort artifacts | **CLAIMED-ONLY** | Deferred Path B (S5.11); `min_clean_observation_count` unread in prod |
| Audit INSERT-only + hash chain | **ENFORCED** | App hash chain + DB role + `batch/audit_integrity.py` |
| Decision insert-only | **ENFORCED** | `recorder` IntegrityError → ValueError |
| Scoring weights from config | **ENFORCED** (YAML dict); governance Pydantic **PARTIAL** | Live path ≠ `ScoringConfig` field set |

---

## 7. Error handling posture

| Mode | Behavior |
|------|----------|
| Fail-closed scoring | Stale profile / embedding metadata mismatch → `score=0`, `is_anomaly=False`, halt flags |
| Fail-open coverage | No active profile → `process_unscored_events` **skips** (event stays unscored) |
| Fail-open explain | LLM/validation failure → template explanation + warning |
| Fail-soft replay | Per-event `except Exception` → collect error, continue |
| Fail-closed decision write | Duplicate `decision_id` rejected |
| Ingest validation | Events: `Event.model_validate_json`. Ground truth: raw `json.loads` |
| HTTP | `HTTPException` 401/404/422/500 |
| Result types | None — raise / flags / HTTP only |
| Bare `except:` | Not found in production packages |

Representative anchors: `worker/scorer.py` (halts / skip); `worker/recorder.py` (IntegrityError); `worker/explainer.py` (ADC `pass`, template fallback); `batch/replay_runner.py` (continue); `web/api.py` (HTTPException).

---

## 8. Feature scoring surface (v2.2)

| Feature | Wired? | Notes |
|---------|--------|-------|
| `login_hour_rarity` | yes | Laplace rarity |
| `geolocation_rarity` | yes | Histograms + drift KL |
| `endpoint_set_rarity` | yes | |
| `process_name_rarity` | yes | |
| `command_line_embedding_similarity` | yes | Ngram cosine path |
| `drift_alert` | yes | weight 100; proportional to `drift_threshold` |
| `service_account_execution_frequency_deviation` | yes | Periodicity |
| `total_volume_delta` | **stub** | Always `0` + `volume_delta_deferred` |

Alert lifecycle (S55): shadow profiles under block, QUIET ∧ ATTEST auto-resolve (`core/attestation.py` + builder), mandatory escalations API.

---

## 9. Test coverage map

**Tooling:** pytest only (no pytest-cov). CI: `.github/workflows/ci.yml`. Marker: `live` (opt-in `--live`). **39** `tests/**/test_*.py` modules (CLAUDE “~31” is stale).

### 9.1 By area

| Area | Modules |
|------|---------|
| Root contracts | `test_audit`, `test_attestation`, `test_schemas`, `test_profile_immutability`, `test_embedding_defaults`, `test_scoring_config_governance`, `test_spec_alignment`, `test_generator`, `test_boil_the_frog_invariants`, `test_s55_invariants_c1_c3`, `test_simple_print` |
| Worker | scorer, six-feature, confidence, containment, resolver, resolution flags, profile selection, evidence binding, embedding mismatch, staleness, shadow as-of, shadow under block, explainer, LLM precedence, counterfactuals, alert workflow |
| Batch | shadow profiles, geo builder, build snapshot, build-block escalation, alert auto-resolve, replay, promotion coverage |
| Web | API, demo path, mandatory escalations |
| Live | `test_live_smoke`, `test_live_smoke_staged` |

Also: `tests/batch/profile_builder/builder.py` contains tests but is **not** named `test_*.py`.

### 9.2 Gaps (no dedicated tests)

| Module | Gap |
|--------|-----|
| `worker/ingest.py` | No dedicated tests |
| `batch/eval/*` | No pytest ownership (scratch sweeps only) |
| `worker/vectorizer.py` | Indirect only |
| `core/database.py`, `core/settings.py` | None |
| `process_unresolved_events` | Resolver unit tests cover `resolve_entity` mainly |

Kinds: unit (schemas/scorer/explainer), in-process integration (builder/lifecycle/replay), eval/invariant (boil-the-frog), live HTTP (opt-in).

---

## 10. Doc vs code deltas (brief)

| Claim | As-built |
|-------|----------|
| Live path includes Profiler | Profiler is batch; Docker worker = resolve+score |
| `live/` key directory | Missing; `tests/live/` only |
| “4 attack scenarios” | 5 injectors; enum/main still 4-centric |
| Promote only via `ProfileStore.promote_profile` | Builder owns promote/supersede |
| KL = 3d vs 30d baseline | Recent vs prior promoted profiles |
| ~31 test modules | 39 |
| `ScoringConfig` is YAML SoT | Hot path = raw YAML; Pydantic shape differs |
| `docs/SPEC.md` ≡ root `SPEC.md` | Byte-identical (verified) |
| Entity type ∈ `{human, service_account}` | Resolver can emit `"unknown"` |

---

## 11. Operating point (factual, not aspirational)

From `memory-bank/progress.md` / calibration artifacts:

- Config: v2.2, `anomaly_threshold=45`, `drift_threshold=5.0`, `drift_alert.weight=100`.
- Series A/S3 operating point and Series C/D sweeps exist; status remains **not CALIBRATED**.
- Do not treat historical “100% P/R” or “CALIBRATED (Audit Grade)” claims as current as-built truth.

---

*End of AS_BUILT. Debt traces → [`DEBT_LEDGER.md`](DEBT_LEDGER.md).*
