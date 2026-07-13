# System Patterns

## Pipeline

```
Ingest → Resolver → Profiler (DuckDB cold path) → Scorer → Recorder
                         ↓
              PostgreSQL (+ pgvector optional) / SQLite for local eval
```

## Hard invariants

- **Immutable profiles:** `ProfileArtifact` is frozen; promote via `ProfileStore`, never mutate in place.
- **No LLM on the scoring path:** embeddings are deterministic char 3-gram hashes (`worker/vectorizer.py`, default 128-d).
- **Evaluation-first:** never change weights/thresholds without a calibration sweep (`batch/eval/` or `scratch/analyze_step*.py`).
- **Shadow profiles:** entities under active alert still accumulate drift shadows that are not promoted.
- **Audit:** INSERT-only decision/audit records with application-layer hash chaining.

## Scoring features (config v2.2)

login/geo/endpoint/process rarity · command-line embedding distance · drift_alert · service periodicity · volume delta.

Authoritative knobs: `config/scoring_config.yaml`.
