# Eval kernel

Sprint 1 harness for the ratified design
[`docs/superpowers/specs/2026-09-08-eval-kernel-usefulness-canary-design.md`](superpowers/specs/2026-09-08-eval-kernel-usefulness-canary-design.md).

Implementation plan:
[`docs/superpowers/plans/2026-09-08-eval-kernel-sprint1.md`](superpowers/plans/2026-09-08-eval-kernel-sprint1.md).

- Production call: `python -m batch.eval.runner` via `batch/eval/e2e_kernel.py` (`run_pipeline`).
- Suite: `pytest tests/eval -v --tb=short`
- Completeness: `python -m batch.eval.e2e_kernel --scorecard-out artifacts/eval-kernel-scorecard.jsonl --assert-complete`
- Detector SoT is Series I (`calibrated: false`). Series A metrics in older files are archival.
- This kernel does not claim usefulness. Capability quality `new_build` is pending.
