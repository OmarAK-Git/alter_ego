# Sprint S1 Close — Skeptic-Verifier Result

**Verdict: `refuted`**

## Claim under test

> S1.1–S1.5 done with evidence; eval integrity enough to unlock S2.

Sprint close is defined (plan.md L167; state.json `verification[]`) as **both**
required stop-gates green: `pytest -v --tb=short` **and** `ruff check .`.

## Evidence gathered (fresh, this session)

### pytest — PASS

```
python -m pytest -v --tb=short --ignore=tests/live
=> 53 passed, 40 warnings in 3.34s
```

All 53 collected tests pass, including the S1 evidence tests: partition isolation
(`test_generator.py`), geolocation drift (`test_profile_builder_geo.py`),
containment queue wiring (`test_containment_queue.py`), and ngram embedding
defaults (`test_embedding_defaults.py`). Warnings are only `datetime.utcnow()`
deprecations — non-blocking.

### ruff — FAIL (blocking)

```
ruff check .
=> Exit code 1 — Found 179 errors.

ruff check . --statistics
  78 F401  unused-import
  31 E402  module-import-not-at-top-of-file
  18 E712  true-false-comparison
  13 E711  none-comparison
  13 F541  f-string-missing-placeholders
  11 E701  multiple-statements-on-one-line-colon
   6 F841  unused-variable
   4 F811  redefined-while-unused
   3 E741  ambiguous-variable-name
   1 E401  multiple-imports-on-one-line
   1 F403  undefined-local-with-import-star
```

The required `ruff check .` stop-gate is **red**. There is no `ruff.toml`,
`.ruff.toml`, or `[tool.ruff]` exclude/per-file-ignore config — `pyproject.toml`
only sets `line-length = 100`, so the gate covers the whole tree with default
E/F rules, exactly as the sprint-close contract specifies.

Errors include product code, not just scratch/tooling:

```
22 batch/profile_builder/builder.py
11 web/api.py
 9 worker/scorer.py
 5 worker/profile_store.py
 4 worker/explainer.py
 1 core/models.py, core/database.py, core/schemas/*.py, worker/resolver.py, batch/synthetic/generator.py
```

(Remaining ~90 errors are in `scratch/`, `alembic/`, `tests/`, `scripts/`,
`verify_lineage.py`, `persist_config.py`.)

## S1 packet evidence — present and independently `survives`

Not the failure point, but confirmed for completeness:

| Packet | Evidence file | Verdict line |
|---|---|---|
| S1.1 | `results/S1.1-verifier-result.md` | SURVIVES (L3) + test-runner result |
| S1.2 | `results/S1.2-verifier-result.md` | SURVIVES (L3) |
| S1.3 | `results/S1.3-verifier-result.md` | SURVIVES (L3) |
| S1.4 | `results/S1.4-verifier-result.md` | survives (L3) |
| S1.5 | `results/S1.5-verifier-result.md` | survives (this session) |

So the "S1.1–S1.5 done with evidence" sub-clause holds. The refutation is on the
second sub-clause: the sprint cannot be *closed to unlock S2* while a required
stop-gate is red.

## Attempts to salvage the claim (all failed)

- Is ruff out of scope? No — plan.md L167 and state.json both list
  `ruff check .` as a required sprint-close gate; no config waives it.
- Are the ruff errors only pre-existing debt outside S1's write scope? Largely
  yes (scratch/alembic/unused imports predate S1), but the gate is defined as
  the whole-tree command exit status, which is 1. A red required gate blocks a
  clean close regardless of blame attribution.
- Does passing pytest suffice? No — the close contract is `pytest` **and**
  `ruff`, conjunctive.

## Single strongest reason it is refuted

`ruff check .` — a required sprint-close stop-gate per plan.md and state.json —
exits 1 with 179 errors (including in `worker/`, `web/`, `batch/`, `core/`), so
S1 does not meet its own defined close criteria and cannot be certified as
unlocking S2. To flip to `survives`, either fix/`--fix` the lint errors to reach
`ruff check .` exit 0, or record an explicit, governance-approved scope
narrowing/waiver for the ruff gate.

## Recommendation

Do **not** mark S1 closed / S2 unlocked yet. pytest is green; resolve the ruff
gate (96 are auto-`--fix`able; the rest, esp. product-code F401/E712/E402, need a
short cleanup pass) or document a formal waiver, then re-run this close check.
