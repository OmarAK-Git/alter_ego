# Deployment — four-container topology (v1)

SPEC §4.4 and SPEC_V3 §9 define a **compressed** local deployment: four containers that map logical modules to operational roles without splitting every Python package into its own service.

| Container | Modules | Default role in compose |
|---|---|---|
| `web` | analyst UI, ingest API, explainer API, containment queue API | FastAPI + static triage UI on port 8000 |
| `worker` | entity resolver, scorer, decision recorder | Polling loop: resolve → score → record |
| `batch` | profile builder (DuckDB), synthetic generator, eval harness, replay runner | Idle (`sleep infinity`); run jobs via `exec` |
| `postgres` | Postgres + pgvector | Operational state and artifacts |

**v1 IaC artifact:** `docker-compose.yml` (S5.2 Path A) — version-controlled, reproducible four-container topology via `docker compose up -d --build`.

**Not shipped (production upgrades):** Kubernetes/kind/k3d manifests, standalone Terraform, TLS, public ingress, or external auth. See [Production upgrades](#production-upgrades-not-v1) below.

## Prerequisites

- Docker Engine with Compose v2
- Local-only credentials (committed defaults — not for production):

| Variable | Compose default |
|---|---|
| `POSTGRES_USER` | `user` (bootstrap owner — migrations only) |
| `POSTGRES_PASSWORD` | `password` |
| `POSTGRES_DB` | `alter_ego` |
| `ALTER_EGO_APP_PASSWORD` | `alter_ego_app_dev` (override via `.env` or shell) |
| `DATABASE_URL` (runtime `web`/`worker`/`batch`) | `postgresql://alter_ego_app:alter_ego_app_dev@postgres:5432/alter_ego` |
| `API_KEY` (web) | `dev-key` (override via `.env` or shell) |

**DSN split (S5.3):** Alembic migrations run as owner `user` (inline override in the `web` startup command). Runtime services connect as least-privilege `alter_ego_app`. Committed defaults are local-dev only — not for production.

## Bring up the stack

```bash
# Build images and start all four services
docker compose up -d --build

# Validate compose file (no containers required)
docker compose config

# Tail logs
docker compose logs -f web worker
```

After `web` is healthy:

- Analyst UI + API: http://localhost:8000
- Privileged routes require header `X-API-KEY: dev-key` (or your `API_KEY` value)

The `web` container runs migrations as bootstrap owner `user`, then starts Uvicorn with the runtime `alter_ego_app` DSN:

```text
DATABASE_URL=postgresql://user:password@postgres:5432/alter_ego alembic upgrade head &&
uvicorn web.api:app --host 0.0.0.0 --port 8000
```

(Uvicorn reads `DATABASE_URL` from the container environment — the app role DSN — after Alembic completes.)

## What each container runs

### `web`

```text
DATABASE_URL=postgresql://user:password@postgres:5432/alter_ego alembic upgrade head &&
uvicorn web.api:app --host 0.0.0.0 --port 8000
```

Serves the analyst triage surface (`web/static/`) and REST APIs (explain, containment queue, replay triggers).

### `worker`

A simple polling loop (5 s interval):

1. `python -m worker.resolver` — map raw events to canonical `entity_id`
2. `process_unscored_events()` from `worker.scorer` — score and `record_decision`

This is suitable for portfolio demos; production would use a queue consumer or scheduler with backoff and observability.

### `batch`

Stays idle so DuckDB profile builds and eval sweeps do not compete with the hot path. Run on demand:

```bash
# Profile build (DuckDB materialization from Postgres)
docker compose exec batch python -c "from batch.profile_builder.builder import build_profiles; print(build_profiles())"

# Synthetic data generation (writes JSONL in container CWD)
docker compose exec batch python -m batch.synthetic.generator

# Full eval harness (requires mounted JSONL inputs)
docker compose exec batch python -m batch.eval.runner /path/events.jsonl /path/ground_truth.jsonl
```

Mount host data for eval/synthetic output, e.g. add a `volumes:` entry under `batch` in a local override file.

Replay is also available via the web API (`POST` replay endpoint) which calls `batch.replay_runner` in-process.

### `postgres`

`ankane/pgvector:latest` with a named volume (`pgdata`). Port `5432` is published for host-side `pytest` or `alembic` if needed.

**Embedding / pgvector migrations:** v1 locks `alter-ego-ngram-v1` at 128-d (`profiles.embedding vector(128)`). Future dimensionality or model changes require the operator playbook in [pgvector-embedding-migration.md](pgvector-embedding-migration.md) (stop worker → Alembic → rebuild profiles → resume scoring).

## Image layout

A single root `Dockerfile` builds `alter_ego:latest` shared by `web`, `worker`, and `batch`. Each service overrides `command:` only — no per-role image variants.

Build context is trimmed via `.dockerignore` (excludes `.git`, `tests/`, `scratch/`, local `*.db`, caches).

## Postgres-only (legacy / dev)

To run only the database (e.g. host Python against compose Postgres):

```bash
docker compose up -d postgres
export DATABASE_URL=postgresql://user:password@localhost:5432/alter_ego
pip install -e ".[dev]"
alembic upgrade head   # owner DSN required for role/grant migrations
export DATABASE_URL=postgresql://alter_ego_app:alter_ego_app_dev@localhost:5432/alter_ego
uvicorn web.api:app --reload
```

## Database roles (S5.3)

Migration `g6h7i8j9k0l1_add_app_db_roles` creates runtime role `alter_ego_app`. Password is set from `ALTER_EGO_APP_PASSWORD` (compose default `alter_ego_app_dev`).

| Role | Used by | Purpose |
|---|---|---|
| `user` | Alembic migrations (`web` startup inline override); host-side `alembic upgrade` | Bootstrap owner — DDL, role creation, grants |
| `alter_ego_app` | `web`, `worker`, `batch` at runtime | Least-privilege application writes |

### Grant matrix (`alter_ego_app`)

| Table | SELECT | INSERT | UPDATE | DELETE | Notes |
|---|---|---|---|---|---|
| `audit_logs` | yes | yes | **no** | **no** | Append-only commit |
| `decisions` | yes | yes | **no** | **no** | Append-only commit |
| `explanations` | yes | yes | **no** | **no** | Append-only commit |
| `scoring_configs` | yes | yes | **no** | **no** | Append-only governance chain |
| `profiles` | yes | yes | lifecycle cols only | **no** | `UPDATE` limited to `promoted_at`, `superseded_at` — payload immutable |
| `events` | yes | yes | **no** | **no** | Ingest insert path |
| `resolved_events` | yes | yes | **no** | **no** | Resolver insert path |
| `alert_workflow_state` | yes | yes | yes | **no** | Analyst workflow transitions |
| `containment_queue` | yes | yes | **no** | **no** | Simulated containment queue |
| `eval_ground_truth` | yes | yes | **no** | **no** | Side table for eval harness |

Sequences `audit_logs_log_id_seq` and `containment_queue_queue_id_seq`: `USAGE`, `SELECT`.

**Eval harness note:** `batch/eval/runner.py` `clear_db()` issues `DELETE` across multiple tables. Run eval sweeps with owner DSN (`postgresql://user:password@...`) via `docker compose exec -e DATABASE_URL=... batch ...`, not the default app role.

### Verify INSERT-only (manual, requires running Postgres)

After `docker compose up -d --build`:

```bash
# Connect as app role
docker compose exec postgres psql -U alter_ego_app -d alter_ego

# INSERT on audit_logs should succeed (minimal row)
INSERT INTO audit_logs (action, details) VALUES ('verify', '{}');

# UPDATE on audit_logs should fail
UPDATE audit_logs SET action = 'tamper' WHERE log_id = 1;
-- ERROR: permission denied for table audit_logs

# Profile payload UPDATE should fail
UPDATE profiles SET features = '{}'::jsonb WHERE profile_version = (SELECT profile_version FROM profiles LIMIT 1);
-- ERROR: permission denied (or no row)

# Lifecycle column UPDATE should succeed on an existing row
UPDATE profiles SET superseded_at = now() WHERE profile_version = (SELECT profile_version FROM profiles LIMIT 1);

# Profile build + promotion still work under app role (batch exec)
docker compose exec batch python -c "from batch.profile_builder.builder import build_profiles; print(build_profiles())"
```

SQLite `pytest` does not exercise Postgres roles — role behavior is verified via compose/manual checks above.

## Production upgrades (not v1)

- Split containers when a module needs independent scaling or blast-radius isolation
- Kubernetes (kind/k3d) manifests targeting the same four roles
- Standalone Terraform for cloud/multi-environment provisioning (v1 IaC is `docker-compose.yml`)
- TLS termination, external identity provider, secrets manager for `API_KEY` and DB credentials
