# Agentic bootstrap — 2026-07-12

## Goal

Initialize ALTER_EGO for accountable AI coding: ultimate-agentic-workflow bootloaders, stop gate, memory-bank, `.workflow/` convention, and an honest README.

## Success Criteria

- Preflight reports AGENTS/CLAUDE/OPS as ours and stop-gate configured
- `memory-bank/` initialized with project state
- `.workflow/<slug>/` validates via `verify_run.py`
- README matches calibration metrics (S2 open, no false “Phase 3 Complete” badge)

## Constraints

- Do not overwrite project architecture notes in `CLAUDE.md` wholesale
- Do not commit local `alter_ego_calibrate_v*.db` / `__pycache__` churn
- No scoring weight changes in this run

## Risks

- README rewrite may under-sell portfolio polish — mitigated by linking evidence + metrics
- Stop gate may block stops if env lacks pytest/ruff — expected; fix env rather than disable gate

## Work Packets

| ID | Objective | Owner | Status |
|---|---|---|---|
| 01-init | Install AGENTS/OPS/.claude kit; merge CLAUDE Autopilot | main | done |
| 02-retro | Capture OPS lessons; fix CLAUDE dim/threshold facts | main | done |
| 03-stop-gate | Add `.claude/stop-gate.json` (pytest + ruff) | main | done |
| 04-memory | Create and initialize `memory-bank/` | main | done |
| 05-workflow | Scaffold `.workflow/` + this bootstrap slug | main | done |
| 06-readme | Rewrite README to match metrics | main | done |

## Verification

- `python .../preflight.py --project-root .` → stop gate configured
- `python .../verify_run.py --run-dir .workflow/2026-07-12-agentic-bootstrap`
- Manual: README claims match `docs/calibration_final_metrics.json`
