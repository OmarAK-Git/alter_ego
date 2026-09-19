# S1-3 implementer brief

Read first: plan **Task 3** only in `docs/superpowers/plans/2026-09-08-eval-kernel-sprint1.md` (until Task 4).

## Fit
S1-2 kernel exists. This task adds the YAML contract + first `des.production_call_shape.yaml`. Do not implement Task 4 theater registry (except define `ALLOWED_THEATER` locally as the plan says).

## Stem mismatch
The plan test expects `ValidationError` when filename stem != scenario_id. If you raise `ValueError`, wrap it as `pydantic.ValidationError` so the written test passes.

## Do not
Change scoring_config.yaml, add /api/ingest, implement remaining 14 YAML files, or modify `e2e_kernel.py` unless required to import the loader (prefer not).

Work from `C:\Users\oalan\alter_ego` on `gsd/eval-kernel-sprint1`. TDD. Commit with the plan message. Write `packets/S1-3-report.md`. Return status, SHA, test summary.
