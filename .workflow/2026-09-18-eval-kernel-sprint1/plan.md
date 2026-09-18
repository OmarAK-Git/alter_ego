# Eval kernel Sprint 1 — T3 run plan

**Slug:** `2026-09-18-eval-kernel-sprint1`  
**Authority:** PR #7 design + PR #8 Sprint 1 plan (ACCEPT WITH FOLLOW-UPS, 2026-09-18).  
**Queue SoT:** `.workflow/autopilot-queue.json`  
**Machine state:** `.workflow/2026-09-18-eval-kernel-sprint1/state.json`

## Goal

Ship the pytest-owned E2E eval kernel from `docs/superpowers/plans/2026-09-08-eval-kernel-sprint1.md`: 15 locked IDs, scorecard, theater detectors, GitHub Actions ownership. Sprint 1 is a harness earn. Do not claim the detector is useful.

## Scope

- Implement plan Tasks 1–21 only.
- Do not staff Sprint 2 (usefulness / Stage B / threshold sweep) or Sprint 3 (canary).
- Do not change `config/scoring_config.yaml` weights, thresholds, or `enabled` flags.
- Do not add `/api/ingest`, FakeProvider, Series J folds, or LLM merge gates.

## Follow-ups recorded at accept (non-blocking)

- PRs #7 and #8 are still drafts; no review comments.
- PR #7 CI `test (3.13)` failed on a docs-only change — treat as likely pre-existing / infra, not a spec defect.
- CI capability corpus is `ci_compact_seed42_shaped` (plan lock); full seed-42 Series I corpus is Sprint 2.
- Gate/verify model slug is `cursor-grok-4.6-high-fast` (available Task catalog). Older repo files named 4.5.

## Drain order

1. Foundation S1-1 → S1-4, then `S1-P0-GATE`.
2. Gov/des/thr/use S1-5 → S1-16 (write-overlap on `e2e_kernel.py` — sequential unless a task is file-disjoint), then `S1-P1-GATE`.
3. Capability S1-17 → S1-19, then `S1-P2-GATE`.
4. Docs S1-21, then GHA S1-20, then `S1-EXIT-GATE`.

## Agent / model defaults

| Role | When | Model |
|---|---|---|
| researcher | only if ≥2 viable paths / opportunity cost | composer-2.5-fast |
| implementer | every non-gate task | composer-2.5-fast |
| code-reviewer | after every code-changing implement | cursor-grok-4.6-high-fast |
| skeptic-verifier | every task verification | cursor-grok-4.6-high-fast |
| test-runner | phase exits + final exit | n/a (commands) |
| gate verdict | all `phase_exit` / `run_exit` | cursor-grok-4.6-high-fast (`in_session_grok`) |

Never mark `done` without skeptic-verifier evidence (or gate Grok verdict + command logs).
