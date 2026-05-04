<![CDATA[<p align="center">
  <img src="docs/banner.png" alt="ALTER_EGO" width="100%"/>
</p>

<h1 align="center">ALTER_EGO</h1>

<p align="center">
  <strong>Behavioral Identity Detection System</strong><br/>
  Detect compromised accounts by learning what "normal" looks like — then finding what doesn't.
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.11+-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python 3.11+"/>
  <img src="https://img.shields.io/badge/postgres-pgvector-336791?style=flat-square&logo=postgresql&logoColor=white" alt="PostgreSQL + pgvector"/>
  <img src="https://img.shields.io/badge/DuckDB-analytics-FFF000?style=flat-square&logo=duckdb&logoColor=black" alt="DuckDB"/>
  <img src="https://img.shields.io/badge/status-Phase%201%20Complete-4CAF50?style=flat-square" alt="Phase 1 Complete"/>
</p>

---

## Overview

ALTER\_EGO is a local-first behavioral identity detection system designed to identify compromised user and service accounts by profiling entity behavior over time and flagging statistically anomalous activity. It is built for single-operator deployment with an emphasis on auditability, determinism, and explainability.

The system works by:
1. **Ingesting** authentication and process telemetry events
2. **Resolving** raw identifiers to canonical entities
3. **Profiling** each entity's behavioral baseline using cohort-relative histograms
4. **Scoring** new events against the baseline with a multi-feature anomaly scoring engine
5. **Explaining** anomalous decisions with structured, auditable artifacts

> **Design Philosophy:** Every decision is deterministic, every score is traceable, and every profile is versioned. ALTER\_EGO is built to be interrogated, not trusted blindly.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        ALTER_EGO                            │
│                                                             │
│  ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌─────────┐  │
│  │  Ingest  │──▶│ Resolver │──▶│ Profiler │──▶│ Scorer  │  │
│  │          │   │          │   │ (DuckDB) │   │         │  │
│  └──────────┘   └──────────┘   └──────────┘   └────┬────┘  │
│       ▲                                            │       │
│       │              ┌──────────┐                  │       │
│       │              │ Recorder │◀─────────────────┘       │
│       │              │ (append) │                          │
│  ┌────┴────┐         └──────────┘                          │
│  │ Synth.  │                                               │
│  │Generator│         ┌──────────────────────┐              │
│  └─────────┘         │   PostgreSQL + pgvec │              │
│                      │   ─────────────────  │              │
│                      │   events             │              │
│                      │   resolved_events    │              │
│                      │   profiles           │              │
│                      │   decisions (append)  │              │
│                      │   eval_ground_truth  │              │
│                      └──────────────────────┘              │
└─────────────────────────────────────────────────────────────┘
```

### Scoring Features

| Feature | Type | Description |
|---------|------|-------------|
| `login_hour_rarity` | Categorical | Info-content of login hour against entity/cohort histogram |
| `geolocation_rarity` | Categorical | Rarity of source geolocation |
| `endpoint_set_rarity` | Categorical | Rarity of endpoint device |
| `process_name_rarity` | Categorical | Rarity of executed process name |
| `command_line_embedding_similarity` | Embedding | Cosine distance of command line embedding *(Phase 0.5)* |
| `service_account_execution_frequency_deviation` | Temporal | Periodicity deviation for service accounts *(Phase 0.5)* |
| `cumulative_drift` | Composite | KL-divergence of behavioral histograms across profile versions |

### 4-Tier Cohort Fallback

When an entity lacks sufficient local data, scoring falls back through a confidence-adaptive hierarchy:

```
Entity Local (≥10 events, confidence=1.0)
    → Primary Cohort / Role (≥100 events, confidence=0.8)
        → Parent Cohort / Entity Type (≥500 events, confidence=0.8)
            → Global Terminus (confidence=0.5, cohort_unsupported flag)
```

---

## Project Structure

```
alter_ego/
├── batch/
│   ├── eval/
│   │   └── runner.py            # Time-stepping evaluation harness
│   ├── profile_builder/
│   │   └── builder.py           # DuckDB-based profile generation
│   └── synthetic/
│       └── generator.py         # High-fidelity synthetic event generator
├── config/
│   └── scoring_config.yaml      # Feature weights and thresholds
├── core/
│   ├── database.py              # SQLAlchemy engine and session
│   ├── math_utils.py            # KL-divergence, Laplace smoothing
│   ├── models.py                # ORM models (Postgres + pgvector)
│   ├── schemas/
│   │   ├── decisions.py         # DecisionRecord, FeatureContribution
│   │   ├── events.py            # Event, ResolvedEvent, SimulationPartition
│   │   └── profiles.py          # ProfileArtifact
│   └── settings.py              # Pydantic settings from .env
├── docs/
│   ├── banner.png
│   └── llm-determinism-check.md # LLM output variance analysis
├── scripts/
│   └── llm_determinism_check.py # Provider determinism verification
├── tests/
│   ├── test_audit.py            # Insert-only decision immutability
│   ├── test_generator.py        # Synthetic generator determinism
│   ├── test_schemas.py          # Pydantic contract validation
│   └── worker/
│       ├── test_resolver.py     # Entity resolution logic
│       └── test_scorer.py       # Scoring determinism, confidence, isolation
├── worker/
│   ├── ingest.py                # JSONL → database ingestion
│   ├── recorder.py              # Append-only decision recording
│   ├── resolver.py              # Raw ID → canonical entity resolution
│   └── scorer.py                # Multi-feature anomaly scoring engine
├── alembic/                     # Database migrations
├── docker-compose.yml           # PostgreSQL + pgvector
├── pyproject.toml
└── README.md
```

---

## Quick Start

### Prerequisites

- Python 3.11+
- Docker (for PostgreSQL + pgvector)

### Setup

```bash
# Clone the repository
git clone https://github.com/OmarAK-Git/alter_ego.git
cd alter_ego

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# .\.venv\Scripts\activate  # Windows

# Install dependencies
pip install -e ".[dev]"

# Start PostgreSQL with pgvector
docker compose up -d

# Configure environment
cp .env.example .env

# Run database migrations
alembic upgrade head
```

### Generate Synthetic Data

```bash
python -m batch.synthetic.generator
# Outputs: events.jsonl (~4MB, 14 days of telemetry) and ground_truth.jsonl
```

### Run the Pipeline

```bash
python -m batch.eval.runner events.jsonl ground_truth.jsonl
```

The evaluation harness processes events in configurable daily windows:
- **Ingests** events for each day
- **Resolves** entity identifiers
- **Builds** behavioral profiles (shadow profiles for blocked entities)
- **Scores** events against the active non-shadow profile

### Run Tests

```bash
pytest -v
```

---

## Synthetic Scenarios

The generator produces four adversarial scenarios for calibration, each tagged with a distinct `simulation_partition` label:

| # | Scenario | Partition Tag | What it tests |
|---|----------|---------------|---------------|
| 1 | **Sharp Credential Misuse** | `eval_scenario_1` | Login from unseen geolocation at 3 AM |
| 2 | **Slow-Roll Behavioral Drift** | `eval_scenario_2` | Gradual hour/process shift over 7 days |
| 3 | **Coordinated Compromise** | `eval_scenario_3` | 3 users in same cohort running `mimikatz.exe` |
| 4 | **Service Account Abuse** | `eval_scenario_4` | Off-schedule interactive command execution |

A fifth injection (`inject_tooling_rollout`) generates **correlated benign change** — multiple users in a cohort adopting a new process simultaneously — to test false positive suppression.

---

## Design Decisions

### Deterministic Decision IDs
Every `DecisionRecord` has an idempotent ID: `SHA-256(event_id || profile_version || scoring_config_version)`. Same inputs always produce the same decision, enabling replay and audit.

### Append-Only Audit Trail
Decision records are insert-only. The application layer rejects duplicate inserts via `IntegrityError`, and the Postgres role will enforce `REVOKE UPDATE` on the `decisions` table.

### Shadow Profile Mechanism
When an entity has an active anomaly alert, profiles are still computed but marked `is_shadow = True`. The scorer only reads non-shadow profiles, but drift calculation reads the full chain — ensuring behavioral drift continues to accumulate even while the entity is blocked.

### Confidence Aggregation
Decision-level confidence is the weighted mean of per-feature confidences, weighted by absolute contribution magnitude. Features evaluated at the global terminus carry `confidence=0.5`, enabling the suppressed-decisions mechanism to filter low-confidence alerts.

### Local Embedding Model
The system defaults to `nomic-embed-text` (768 dimensions) for local deployment without external API dependencies, following the principle that a security detection system should not depend on third-party inference endpoints.

---

## Roadmap

| Phase | Status | Description |
|-------|--------|-------------|
| **Phase 0** | ✅ Complete | Contracts, schemas, synthetic generator, LLM determinism check |
| **Phase 1** | ✅ Complete | Core detection pipeline, 4-tier fallback, shadow profiles, drift detection |
| **Phase 2** | 🔲 Next | Calibration gate — threshold tuning via per-scenario P/R curves |
| **Phase 3** | 🔲 Planned | Triage UI and analyst workflow |
| **Phase 4** | 🔲 Planned | pgvector embedding integration, real-time streaming |

---

## Configuration

All scoring parameters are defined in [`config/scoring_config.yaml`](config/scoring_config.yaml) and are designed to be swept during Phase 2 calibration:

```yaml
anomaly_threshold: 75.0      # Score threshold for anomaly flag
confidence_floor: 0.6        # Minimum confidence to surface a decision

features:
  login_hour_rarity:
    weight: 1.0
  process_name_rarity:
    weight: 1.0
  command_line_embedding_similarity:
    weight: 2.0               # Currently zeroed (stub) until Phase 0.5
```

---

## License

This project is for portfolio and educational purposes.

---

<p align="center">
  <sub>Built with adversarial specification review, DuckDB analytics, and pgvector similarity search.</sub>
</p>
]]>
