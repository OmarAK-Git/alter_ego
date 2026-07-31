# Packet R1 — skeptic-verifier

- Run: `.workflow/2026-07-30-reverse-spec-rfc-remediation`
- Model: `cursor-grok-4.5-high` (readonly)
- Scope: task (NOT a phase/sprint gate — ignore run-wide gaps)

## Goal under verification

The profile-builder aggregation test must actually execute under default pytest
discovery. Previously `tests/batch/profile_builder/builder.py` was never
collected because `pyproject.toml` sets only `testpaths = ["tests"]` with no
`python_files` override.

## Acceptance criteria

1. `tests/batch/profile_builder/builder.py` no longer exists; `tests/batch/profile_builder/test_builder.py` does.
2. The renamed file's contents are unchanged from the original (rename only, zero content delta).
3. `pytest tests/batch/profile_builder/test_builder.py -v` collects and PASSES `test_profile_builder_aggregates_correctly`.
4. `pytest -v --tb=short --ignore=tests/live` is fully green with no `import file mismatch`, and the count is exactly one higher than the pre-change baseline of 163.
5. `pyproject.toml` was NOT modified (no `python_files` override was added as a shortcut).
6. The commit is scoped: it contains ONLY the rename. No unrelated repo-root
   untracked files (`AS_BUILT.md`, `DEBT_LEDGER.md`, `5638f86d-*`, `scratch/*.log`)
   were committed.

## Paths

- `tests/batch/profile_builder/test_builder.py`
- `pyproject.toml` (must be untouched)
- Implementer result: `.workflow/2026-07-30-reverse-spec-rfc-remediation/results/R1-implementer-result.md`
- Prior evidence: `results/R1-collect-before.txt`, `results/R1-pytest-after.txt`

## Commands

```
pytest tests/batch/profile_builder/test_builder.py -v
pytest -v --tb=short --ignore=tests/live
git show --stat HEAD
git status --short
git diff HEAD~1 HEAD -- pyproject.toml
```

Treat every implementer claim as unevidenced until you reproduce it yourself.
