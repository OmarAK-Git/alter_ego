# S5.1 — Dockerfiles + four-container compose

**Tier:** T3 packet (task-scoped verification)  
**Goal (verbatim):** Dockerfiles + four-container compose (web/worker/batch/postgres)

## Scope

- `docker-compose.yml`, `Dockerfile*`, `.dockerignore`, `docs/` deployment notes
- Not: IaC (S5.2), DB roles (S5.3), app logic changes

## Acceptance criteria

1. Dockerfiles for web/worker/batch (shared base OK)
2. Compose has four services: web, worker, batch, postgres (pgvector)
3. web runs FastAPI; worker/batch have documented commands
4. DATABASE_URL wired to compose postgres; local-dev credentials only
5. Docs describe bring-up; no false K8s claims
6. Lean `.dockerignore`
7. Validate with `docker compose config` if docker available

## Verification commands

- `docker compose config` (if docker available)
- File audit: four services + Dockerfiles + docs
- `ruff check .` optional (docs/yml only — expect no Python churn)

## Models

- implement: `composer-2.5`
- verify: `cursor-grok-4.5-high`
