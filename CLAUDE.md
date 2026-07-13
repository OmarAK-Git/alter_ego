# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Agent Autopilot

This repo uses the `ultimate-agentic-workflow` skill for non-trivial AI coding work. Classify before acting: T0 answer/tiny edit; T1 goal note + verify; T2 plan first; T3 full `.workflow/<slug>/` traceability. Keep live task state in `memory-bank/` (and `.workflow/<slug>/state.json` for T3), not only chat. Do not claim completion without fresh verification evidence. Operational lessons live in `OPS.md`.

## Commands

```bash
# Install (includes dev extras for testing)
pip install -e ".[dev]"

# Run all tests
pytest -v --tb=short
# If not installed editable, prefix with: PYTHONPATH=. pytest -v --tb=short

# Run a single test file
pytest tests/worker/test_scorer.py -v

# Run tests by name pattern
pytest -k "drift" -v

# Lint (line-length: 100)
ruff check .

# Type checking (strict mode)
mypy .

# Database migrations
alembic upgrade head
alembic revision --autogenerate -m "message"
```

## Architecture

ALTER_EGO is a behavioral identity detection system. It profiles how users and service accounts normally behave, then scores incoming telemetry against those profiles to surface anomalies (credential misuse, lateral movement, insider drift).

**Pipeline:**
```
Ingest → Resolver → Profiler (DuckDB) → Scorer → Recorder
                         ↓
                    PostgreSQL + pgvector
```

**Key directories:**
- `core/` — ORM models (`models.py`), Pydantic schemas (`schemas/`), math utilities (`math_utils.py`), Pydantic settings (`settings.py`)
- `worker/` — runtime pipeline: `ingest.py` → `resolver.py` → `scorer.py` → `recorder.py`; also `vectorizer.py` (deterministic 3-gram embeddings) and `profile_store.py`
- `batch/profile_builder/builder.py` — DuckDB-based histogram profiling + cumulative drift engine
- `batch/synthetic/` — calibrated synthetic event generator with 4 attack scenarios (used in eval sweeps)
- `batch/eval/` — calibration sweep harness (`runner.py`), FP/FN analysis, threshold tuning
- `config/scoring_config.yaml` — all tunable weights and thresholds (current version: 2.2)
- `tests/` — 12 test files; `worker/` unit tests, `batch/` integration tests, root-level schema/audit/governance tests
- `docs/SPEC.md` — authoritative architecture spec and threat model

## Key Design Decisions

**Immutable profiles:** `ProfileArtifact` (in `core/schemas/profiles.py`) is `frozen=True`. Profile changes require promotion via `ProfileStore.promote_profile()`, never in-place mutation. Superseded profiles are retained with `superseded_at` timestamps.

**No LLM in core pipeline:** `worker/vectorizer.py` uses deterministic character-level 3-gram SHA-256 hashing into a 128-dim unit-norm vector (model id `alter-ego-ngram-v1`). Avoids prompt injection risk and ensures reproducibility. Alembic/ORM still default `nomic-embed-text` — deferred S1.4 debt, not shipping runtime.

**Drift engine:** `batch/profile_builder/builder.py` computes KL-divergence between a 3-day recent window and a 30-day baseline, normalizes by cohort-median drift, then accumulates with a 7-day exponential half-life. `drift_threshold` is **5.0** in `config/scoring_config.yaml`, weighted at 100.0 in scoring.

**Circuit breakers:** Staleness halt (`max_profile_staleness_days: 14`) gates scoring to zero if a profile is stale. Cohort novelty gate suppresses feature contributions common to >20% of same-role peers (requires ≥10 peers, 7-day window).

**Evaluation-first discipline:** No weight or threshold is changed without a full calibration sweep via `batch/eval/runner.py`. See `scratch/analyze_step*.py` for examples of how sweeps are analyzed.

**Audit log:** `AuditLogModel` is INSERT-only with application-layer hash chaining. See `tests/test_audit.py` for the immutability contract.
