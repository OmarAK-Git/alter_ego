# Tech Context

## Stack

- Python ≥3.11 · Pydantic v2 · SQLAlchemy · Alembic
- FastAPI + static analyst UI (`web/`)
- DuckDB for profile builds · Postgres+pgvector (docker-compose) or SQLite for local sweeps
- pytest · ruff · mypy (strict)

## Layout

| Path | Role |
|---|---|
| `core/` | ORM, schemas, math, settings |
| `worker/` | hot path: ingest, resolve, score, record, explain, vectorize |
| `batch/` | profile builder, synthetic scenarios, eval harness, replay |
| `web/` | triage API + UI |
| `config/scoring_config.yaml` | calibrated weights/thresholds |
| `docs/SPEC.md` | architecture spec |
| `scratch/` | one-off calibration drivers (not production entrypoints) |

## Commands

```bash
pip install -e ".[dev]"
pytest -v --tb=short
ruff check .
mypy .
uvicorn web.api:app --reload
docker compose up -d   # Postgres + pgvector
```

## Agent workflow surfaces

- Bootloaders: `AGENTS.md`, `CLAUDE.md` · lessons: `OPS.md`
- Live task memory: `memory-bank/`
- T3 runs: `.workflow/<slug>/`
- Completion gate: `.claude/stop-gate.json` (pytest + ruff)
