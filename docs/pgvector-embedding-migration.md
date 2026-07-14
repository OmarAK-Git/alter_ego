# pgvector / Embedding Dimensionality Migration Playbook

SPEC §4.3, SPEC_V3 §6.8, and portfolio gate SPEC_V3 §9 require a documented operator playbook before any embedding model or dimensionality change. This document is that playbook.

**Scope:** `profiles.embedding` — the only pgvector column in v1. Command-line centroid vectors for `command_line_embedding_similarity` scoring.

---

## Current lock (runtime truth)

v1 ships a **fixed** embedding contract. Do not change these values without executing this playbook end-to-end.

| Field | Locked value |
|---|---|
| `embedding_model_id` | `alter-ego-ngram-v1` |
| `embedding_model_version` | `1.0` |
| `embedding_dimensionality` | **128** |
| `embedding_input_normalizer_version` | `1.0-char-3gram-hash-128` |
| Vectorizer | `worker/vectorizer.py` — deterministic char 3-gram SHA-256 hash, unit-norm |
| pgvector column | `profiles.embedding vector(128)` |

**Historical note (not runtime):** Early Alembic revisions and the initial schema used placeholder defaults from an abandoned neural embedder (`nomic-embed-text`, 768-d / 1536-d exploration). Migration `a2b3c4d5e6f7` moved the column to 128-d; migration `e4f5a6b7c8d9` aligned `embedding_model_id` server defaults to `alter-ego-ngram-v1`. **No external per-event model runs in the hot path today.** S1.4 debt is limited to aligning any remaining schema defaults — not adopting nomic at runtime.

---

## Why dimensionality changes are breaking

pgvector `vector(N)` columns are **typed at DDL time**. Postgres stores and indexes vectors with a fixed `N`. You cannot `INSERT` a 128-d vector into `vector(768)` or silently widen a column in place.

Consequences for ALTER_EGO:

1. **Schema:** `profiles.embedding` must be dropped and re-added (or replaced via a versioned column) when `N` changes.
2. **Stored centroids:** Every profile centroid in `profiles.embedding` becomes invalid — cosine distance against new-dimension event vectors is undefined.
3. **Metadata:** `embedding_model_id`, `embedding_model_version`, `embedding_dimensionality`, and `embedding_input_normalizer_version` on each profile artifact must match the shipping vectorizer or scoring must not resume (SPEC §5.6).
4. **Decisions:** `decision_id` is sensitive to `embedding_model_version` (see `tests/worker/test_scorer.py`). Replays after migration produce new decision IDs for the same events — expected, not a bug.
5. **Profile build suppression:** SPEC §7.1 — profile builds are suppressed when `embedding_model_id` has changed and pgvector migration is incomplete.

v1 uses **approach (a)** from SPEC §4.3: explicit `ALTER TABLE` via Alembic (drop column → re-add with new dimension). Approach (b) — versioned columns such as `embedding_v1`, `embedding_v2` — is not implemented; use only if a zero-downtime dual-write period is required in a future production design.

---

## Pre-migration: detect mismatch

Run these checks **before** changing code or schema.

### 1. Profile metadata vs shipping constants

```sql
-- Rows that would be incompatible with current vectorizer
SELECT profile_version, entity_id,
       embedding_model_id, embedding_model_version,
       embedding_dimensionality, embedding_input_normalizer_version
FROM profiles
WHERE superseded_at IS NULL
  AND (
    embedding_model_id != 'alter-ego-ngram-v1'
    OR embedding_dimensionality != 128
    OR embedding_model_version != '1.0'
  );
```

Expect **zero rows** on a healthy v1 deployment. Non-zero → schedule profile rebuild after schema is aligned (Step 4).

### 2. pgvector column dimension vs ORM

```sql
-- Postgres: atttypmod for vector is dimension + 4 (pgvector convention)
SELECT a.attname,
       format_type(a.atttypid, a.atttypmod) AS column_type
FROM pg_attribute a
JOIN pg_class c ON a.attrelid = c.oid
WHERE c.relname = 'profiles'
  AND a.attname = 'embedding'
  AND NOT a.attisdropped;
```

Expect `vector(128)`. Mismatch with `core/models.py` `Vector(128)` or `DEFAULT_EMBEDDING_DIMENSIONALITY` → migration required before scoring.

### 3. Alembic head vs code

```bash
# Owner DSN for DDL
DATABASE_URL=postgresql://user:password@localhost:5432/alter_ego alembic current
DATABASE_URL=postgresql://user:password@localhost:5432/alter_ego alembic heads
```

Pending revisions that touch `profiles.embedding` must be applied (or explicitly rolled back) before worker restart.

### 4. Operational signals (current v1)

- **Staleness halt** (`staleness_halt` flag, `max_profile_staleness_days` in `config/scoring_config.yaml`) — scoring zeros when profiles are too old; does not by itself detect embedding mismatch.
- **Schema/embedding startup check** — shipped S5.9: scorer halts with `embedding_metadata_mismatch_halt` when profile metadata disagrees with runtime contract; see `worker/scorer.py` and this playbook.

---

## Migration procedure (approach a)

Treat as a **maintenance window**. Embedding migration is not hot-swappable.

### Phase 0 — Plan

1. Record target `embedding_model_id`, `embedding_model_version`, `embedding_dimensionality`, and normalizer version in a change ticket.
2. If dimensionality changes, **full calibration sweep is required** before production claims (SPEC evaluation discipline) — out of scope for schema-only ops but mandatory for threshold changes.
3. Notify analysts: decisions during the window are stale; containment queue may lag.

### Phase 1 — Stop scorers (offline window)

```bash
# Compose deployment — stop hot path only; keep postgres up
docker compose stop worker

# Optional: stop web ingest if you must prevent new events during rebuild
# docker compose stop web
```

Verify no in-flight scoring:

```bash
docker compose ps worker   # should show "exited"
```

**Do not** run profile builds while the `embedding` column is mid-migration (drop/add window).

### Phase 2 — Schema migration (Alembic)

Author a new revision following the precedent in `alembic/versions/a2b3c4d5e6f7_phase1_closeout.py`:

```python
# Pattern (illustrative — replace NEW_DIM and metadata defaults)
op.drop_column("profiles", "embedding")
op.add_column(
    "profiles",
    sa.Column("embedding", pgvector.sqlalchemy.Vector(dim=NEW_DIM), nullable=True),
)
# Update embedding_model_id / embedding_dimensionality server defaults if needed
```

Apply as owner:

```bash
docker compose exec web bash -c \
  'DATABASE_URL=postgresql://user:password@postgres:5432/alter_ego alembic upgrade head'
```

Or host-side:

```bash
DATABASE_URL=postgresql://user:password@localhost:5432/alter_ego alembic upgrade head
```

**Code deploy (same window):** Update `worker/vectorizer.py` `dim`, `core/schemas/profiles.py` defaults, `core/models.py` `VectorType`, and `batch/profile_builder/builder.py` imports — all must agree on `NEW_DIM` and model metadata before rebuild.

### Phase 3 — Invalidate old profile vectors

Existing `profiles.embedding` values were dropped with the column. Metadata columns may still reference the old model:

```sql
-- Optional: mark all active profiles superseded to force rebuild
UPDATE profiles
SET superseded_at = NOW()
WHERE superseded_at IS NULL
  AND promoted_at IS NOT NULL;
```

Or leave promotion state and let rebuild supersede via `ProfileStore.promote_profile()` — builder creates new `profile_version` rows.

### Phase 4 — Rebuild profiles

Run as app role (batch container):

```bash
docker compose exec batch python -c \
  "from batch.profile_builder.builder import build_profiles; print(build_profiles())"
```

For each entity with events in the training window, confirm new rows have:

- `embedding` non-null (when command-line history exists)
- `embedding_model_id` / `embedding_dimensionality` matching shipping constants
- `promoted_at` set for production scoring

Re-run until build errors (schema mismatch, active-alert block per §5.5) are resolved or documented.

### Phase 5 — Resume scoring

```bash
docker compose start worker
docker compose logs -f worker
```

Monitor first decisions for expected flags (no silent zeros from dimension errors).

---

## Rollback

Rollback is safe **only** if Phase 4 has not promoted new profiles into production scoring, or you accept re-rebuilding again after revert.

1. `docker compose stop worker`
2. `alembic downgrade -1` (or to the revision before the embedding change) — restores prior `vector(N)` column; **destroys** centroids written under the new dimension.
3. Revert application code to prior model constants.
4. Either:
   - **Restore Postgres volume from snapshot** taken before Phase 2 (fastest for demo environments), or
   - Re-run `build_profiles()` under the reverted model.
5. `docker compose start worker`
6. Re-run verification checks (below).

If rollback happens after mixed old/new profile versions exist, query `profiles` by `embedding_dimensionality` and supersede or delete inconsistent rows before resuming.

---

## Post-migration verification

| Check | Command / query | Pass criterion |
|---|---|---|
| Column type | `format_type` query above | `vector(<target_dim>)` |
| Alembic at head | `alembic current` | Shows latest revision |
| Profile metadata | SQL in § Pre-migration §1 | Zero incompatible active profiles |
| Centroid length | `SELECT profile_version, vector_dims(embedding) FROM profiles WHERE embedding IS NOT NULL LIMIT 5;` | All `vector_dims` = target dim |
| Smoke score | Ingest one process event, wait for worker cycle | Decision recorded; `command_line_embedding_similarity` contribution present when profile has centroid |
| Staleness | No spurious `staleness_halt` on freshly promoted entities | Scores non-zero when profile fresh |
| Audit | `batch/audit_integrity.py` or API integrity endpoint | Chain intact (migration should not touch `audit_logs`) |

**Regression tests (dev):**

```bash
pytest tests/test_embedding_defaults.py tests/worker/test_scorer.py -v --tb=short
```

---

## Same-dimension model change (version bump only)

If only `embedding_model_version` or the normalizer changes but **dimension stays 128**:

1. pgvector column DDL **unchanged** — no drop/add.
2. Still stop worker, deploy code, supersede/rebuild profiles (old centroids are not comparable under a new hash scheme).
3. Update `DEFAULT_EMBEDDING_MODEL_VERSION` / `NORMALIZER_VERSION` consistently.
4. Expect new `decision_id` values for identical events (embedding metadata is in the decision hash).

---

## Production upgrades (not v1)

- **Approach (b):** dual `embedding_v1` / `embedding_v2` columns with a read cutover — avoids drop/add downtime; not in v1 schema.
- **Blue/green:** migrate on a clone, rebuild profiles, swap DSN — preferred when `pgdata` volume rollback is unacceptable.
- **Index rebuild:** if `ivfflat` / `hnsw` indexes are added later on `profiles.embedding`, plan `REINDEX` after dimension change.

---

## Related documents

- [SPEC.md §4.3 Storage](SPEC.md#43-storage) — hybrid storage and migration policy
- [SPEC.md §5.6 Profile Schema Versioning](SPEC.md#56-profile-schema-versioning) — embedding metadata on artifacts
- [SPEC_V3.md §6.8 Embedding Lock](SPEC_V3.md#68-embedding-lock) — locked shipping values
- [deployment.md](deployment.md) — four-container topology and batch exec patterns
