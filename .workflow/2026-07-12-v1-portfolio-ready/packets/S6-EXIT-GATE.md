# Packet S6-EXIT-GATE — chat_gate / phase_exit

## Objective

Program closeout for sprint S6 / portfolio-ready T3 run: fresh pytest + ruff after all S6 packets, write verifier evidence, and clear remaining stop-gate verification rows that are still pending when checks pass.

## Run mode

`chat_gate` — run **inline in the current chat** with the **UI-selected model** (Opus recommended). Do **not** dispatch mid-loop `skeptic-verifier` / `composer-2.5` for this gate unless the operator explicitly overrides.

## Depends on (all must be done)

S6.1, S6.2, S6.3

## Unlocks

Program drain complete (no further sprint packets in this run). Optional operator follow-ons (human drift research, empirical LLM check) remain outside the queue.

## Verification (`scope: phase_exit`)

```bash
pytest -v --tb=short --ignore=tests/live
ruff check .
```

Optional (if UAW scripts available):

```bash
python <ultimate-agentic-workflow>/scripts/verify_run.py --run-dir .workflow/2026-07-12-v1-portfolio-ready
```

## Acceptance (program close)

1. All S6.1–S6.3 have verifier `survives` evidence under `results/`.
2. Fresh pytest (ignore live) green.
3. Fresh `ruff check .` clean.
4. No false CALIBRATED claims introduced in S6 docs.
5. Write `.workflow/2026-07-12-v1-portfolio-ready/results/S6-EXIT-GATE-verifier-result.md`.
6. On pass: set packet `status: done`, append evidence; mark `verification[]` stop-gate pytest/ruff (and verify_run if executed) `pass`.

## Status

`ready` — next runnable under `/gsd-autopilot-loop` (without `--stop-before-gate`).
