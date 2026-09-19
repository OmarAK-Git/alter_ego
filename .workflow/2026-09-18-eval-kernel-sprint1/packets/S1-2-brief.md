# S1-2 implementer brief

Read first: `docs/superpowers/plans/2026-09-08-eval-kernel-sprint1.md` section **Task 2** only (through Task 3 heading). That section is the requirements. Use the code blocks verbatim unless Windows/SQLite bind forces a local adaptation.

## Where this fits
S1-1 is done (`ScorecardRow`, 15 locked IDs). S1-2 adds the kernel that **calls** `run_pipeline` on a rebound SQLite engine. Do not change `run_pipeline`'s signature. Do not INSERT `DecisionRecord` in the kernel.

## Work from
`C:\Users\oalan\alter_ego` on branch `gsd/eval-kernel-sprint1`.

## Windows note
`sqlite_path` from pytest `tmp_path` is an absolute Windows path. Bind with a SQLAlchemy-safe URL (posix path / extra slashes as needed). Do not assume `sqlite:///{path}` works for `C:\...`.

## Empty labels
If `ingest_ground_truth` raises on an empty labels file, write one benign label instead of changing ingest.

## CLI
`--only des.production_call_shape` may synthesize a scorecard row from `run_production_call` on the mini fixture. `--assert-complete` must still exit nonzero (30 rows missing). That is the Task 2 success condition.

## TDD
Write tests first, run fail, implement, then:
```
pytest tests/eval/test_e2e_kernel.py -v --tb=short
pytest tests/eval/test_scorecard_schema.py tests/eval/test_e2e_kernel.py -v --tb=short
ruff check batch/eval/e2e_kernel.py batch/eval/scorecard.py batch/eval/kernel_fixtures.py tests/eval
```
Commit with: `Add e2e kernel that calls run_pipeline on a SQLite bind`

## Report
Write `C:\Users\oalan\alter_ego\.workflow\2026-09-18-eval-kernel-sprint1\packets\S1-2-report.md`
Return only: status (DONE / DONE_WITH_CONCERNS / BLOCKED), commit SHA, test summary, concerns.

Do not implement Task 3+.
