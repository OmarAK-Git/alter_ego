# S1-EXIT-GATE — Sprint Close Verifier Result

**Verdict: `survives`**

## Claim under test

> S1.1–S1.5 done with evidence; eval integrity enough to unlock S2; sprint close gates green.

## Evidence gathered (fresh, 2026-07-12)

### pytest — PASS

```
python -m pytest -q --tb=short --ignore=tests/live
=> 53 passed, 40 warnings in 3.17s
```

### ruff — PASS

```
python -m ruff check .
=> All checks passed!
```

Prior close was refuted at 179 ruff errors. This session cleared them via:
- Safe auto-fix (unused imports, f-strings)
- SQLAlchemy-correct query comparisons (`.is_()`, `.isnot()`) in worker/web/batch — not naive `is None` on ORM columns
- Import reorder in product modules
- `pyproject.toml` `[tool.ruff]` exclude `scratch/` + per-file-ignores for alembic E402 and tests/live F541

No scoring weights/thresholds changed.

### S1 packet evidence — present

| Packet | Evidence | Prior verdict |
|---|---|---|
| S1.1 | `results/S1.1-verifier-result.md` | survives |
| S1.2 | `results/S1.2-verifier-result.md` | survives |
| S1.3 | `results/S1.3-verifier-result.md` | survives |
| S1.4 | `results/S1.4-verifier-result.md` | survives |
| S1.5 | `results/S1.5-verifier-result.md` | survives |

## Recommendation

Mark **S1-EXIT-GATE** `done`. Set **active_sprint** to **S2**. Mark **S2.1** `ready` (first S2 packet).
