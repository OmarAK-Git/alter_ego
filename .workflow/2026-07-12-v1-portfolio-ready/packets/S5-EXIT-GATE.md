# Packet S5-EXIT-GATE — chat_gate / phase_exit

## Objective

Sprint S5 exit gate: skeptic-verifier + pytest + ruff; unlock S6 only when green.

## Run mode

`chat_gate` — run **inline in the current chat** with the **UI-selected model** (Opus recommended). Do **not** dispatch mid-loop `skeptic-verifier` / `composer-2.5` for this gate unless the operator explicitly overrides.

## Depends on (all must be done)

S5.1 … S5.12

## Unlocks

S6.1, S6.2, S6.3

## Verification (`scope: phase_exit`)

```bash
pytest -v --tb=short --ignore=tests/live
ruff check .
```

## Acceptance (sprint close)

1. All S5.1–S5.12 have verifier `survives` evidence under `results/`.
2. Fresh pytest (ignore live) green.
3. Fresh `ruff check .` clean.
4. Portfolio honesty: Phase 4 / SPEC_V3 §9 gates either shipped or explicitly Path-B deferred (S5.2 Path A compose-as-IaC; S5.11 Path B cohort defer; S5.7 empirical LLM run may still await API keys — harness must exist).
5. No false CALIBRATED / 100% recall claims.
6. Write `.workflow/2026-07-12-v1-portfolio-ready/results/S5-EXIT-GATE-verifier-result.md`.
7. On pass: set packet `status: done`, append evidence, mark S6.* `ready` (clear `blocked_by`).

## Status

`ready` — next runnable under `/gsd-autopilot-loop` (without `--stop-before-gate`).
