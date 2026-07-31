# Packet R1 — implementer

- Run: `.workflow/2026-07-30-reverse-spec-rfc-remediation`
- Model: `composer-2.5`
- Plan ref: `docs/superpowers/plans/2026-07-30-reverse-spec-rfc-remediation.md` — Task 1, Steps 1–5
- Repo: `C:\Users\oalan\alter_ego` (Windows, PowerShell)

## Objective

`tests/batch/profile_builder/builder.py` contains a real, currently-passing test
(`test_profile_builder_aggregates_correctly`) but `pyproject.toml`'s
`[tool.pytest.ini_options]` sets only `testpaths = ["tests"]` with no
`python_files` override, so pytest's default `test_*.py` / `*_test.py`
discovery pattern applies and the file is silently skipped. Rename it so it is
collected.

## Allowed write scope

- `tests/batch/profile_builder/builder.py` → `tests/batch/profile_builder/test_builder.py` (rename only)
- `.workflow/2026-07-30-reverse-spec-rfc-remediation/results/R1-*.txt`

Do **not** edit `pyproject.toml`. Do **not** change the test file's contents.
Do **not** touch any other file.

## Steps

1. Capture pre-rename evidence:
   `pytest tests/batch/profile_builder/ -v --collect-only`
   Save full output to `.workflow/2026-07-30-reverse-spec-rfc-remediation/results/R1-collect-before.txt`.
   Expected: zero items collected from `builder.py`.
2. `git mv tests/batch/profile_builder/builder.py tests/batch/profile_builder/test_builder.py`
3. `pytest tests/batch/profile_builder/test_builder.py -v` — save output to
   `.workflow/2026-07-30-reverse-spec-rfc-remediation/results/R1-pytest-after.txt`.
   Expected: `test_profile_builder_aggregates_correctly` collected and PASSED.
4. `pytest -v --tb=short --ignore=tests/live` — confirm no `import file mismatch`
   and no regressions. Record the pass/fail counts in your result file (you do
   not need to save the whole log).
5. Commit with a scoped add only:
   `git add tests/batch/profile_builder/builder.py tests/batch/profile_builder/test_builder.py`
   `git commit -m "test: fix pytest discovery for profile builder aggregation test"`
   The repo root has unrelated untracked files (`AS_BUILT.md`, `DEBT_LEDGER.md`,
   `*-rfcs.md`, `*-run_log.md`, `scratch/*.log`) — they must NOT be committed.
   Do not use `git add -A` / `git add .`.
   Note: `.workflow/` artifacts for this run may remain untracked; leave them.
   If `tests/batch/profile_builder/__pycache__` contains a stale `builder` pyc,
   leave it alone (it is gitignored).

## Constraints

- Do not mark this packet `done` — the controller does that after verification.
- Do not run phase/sprint exit verification; this is not a gate.
- Stop and ask for approval before: installing dependencies, editing `.codex`
  or `.claude`, cloning repos, writing outside the allowed scope, or any
  destructive git operation.

## Deliverable

Write `.workflow/2026-07-30-reverse-spec-rfc-remediation/results/R1-implementer-result.md` with:

- header: `model: composer-2.5`, packet id, timestamp
- what changed (exact paths)
- the before/after collection counts
- full-suite pass count
- commit SHA
- anything you could not do
