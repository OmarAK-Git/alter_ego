# Active Context

**Updated:** 2026-07-13

## Current focus

**T3 run:** `.workflow/2026-07-12-v1-portfolio-ready/`  
**Active sprint:** S5 (S4 closed; **S4-EXIT-GATE done** + **HUMAN-DRIFT-RESEARCH acknowledged** 2026-07-13)  
**Next runnable:** **`S5.1`** (Dockerfiles + four-container compose) — S5.* unblocked  
**Roadmap:** `memory-bank/progress.md` · **Tasks:** `memory-bank/tasks.md`

**Phase honesty:** Phases 0–3 = Partial; Phase 2 = Partial (Phase 2A, closed-with-residual); Phase 4 = Open. **Not CALIBRATED.**

## Decisions locked

- Hybrid C for Scenario 2 / Phase 2 — S2 now catches (R=1.0); residual is high FP + S3 FN
- Cut line: portfolio-ready through S5
- Before S5: operator personal drift-methodology research
- Autopilot: `--stop-before-gate` stops before any `*-EXIT-GATE` or `HUMAN-DRIFT-RESEARCH`
- S3 knobs unchanged (v2.2 @ thr=45); thr=55 diagnostic only — `docs/scoring-config-governance-s3.md`
- S4.3/S4.6/S4.7 Path B deferrals recorded in SPEC with explicit banners: §11.4 aging escalation/jitter (view ships), §6.5/§6.6 calendar/gap, §12 assets; all three cross-referenced in §13.1 deferrable list

## Resume

1. `HUMAN-DRIFT-RESEARCH` acknowledged (done 2026-07-13) — S5.* unblocked; `S5.1` is `ready`.
2. Run `/gsd-autopilot-loop` to start S5 (deploy: Dockerfiles + compose, IaC, audit DB roles, staleness/circuit breakers, LLM determinism, embedding migration docs).
3. Gate commands for future gates: `pytest -v --tb=short --ignore=tests/live` + `ruff check .`
