# Orchestration — v1 portfolio-ready

## Mode

T3 subagent-driven + optional autonomous loop **within the active sprint only**.

## Dispatch order

1. Read `state.json` (`active_sprint`, packets with `status: ready`).
2. For fork packets (`label` contains `fork`): dispatch `researcher` first; record decision in packet result.
3. Dispatch `implementer` with one packet id, disjoint `files_or_sources`, TDD — Task `model`: `autopilot.implementation_model` (`composer-2.5`).
4. Dispatch `test-runner` on the packet’s tests + `pytest -k <area>` then broader if needed.
5. Mid-loop packet verify: dispatch `skeptic-verifier` via Task with `model`: `autopilot.verification_model` (`cursor-grok-4.5-high`), `readonly: true`.
6. Sprint-boundary / chat gates: run inline with **UI-selected Opus** (`gate_run_mode: chat_gate`); do not auto-pick the mid-loop verifier model.

## Hard gates

Explicit **exit gate** packets (chat_gate / `verification.scope: phase_exit`):

| Gate ID | Unlocks |
|---|---|
| `S1-EXIT-GATE` | S2.* |
| `S2-EXIT-GATE` | S3.* |
| `S3-EXIT-GATE` | S4.* |
| `S4-EXIT-GATE` | `HUMAN-DRIFT-RESEARCH` |
| `HUMAN-DRIFT-RESEARCH` | S5.* |

- Do not mark next-sprint packets `ready` while the previous EXIT-GATE is not `done`.
- Do not mark `S5.*` as `ready` while `HUMAN-DRIFT-RESEARCH.status != done`.
- With `--stop-before-gate`, stop when the next runnable item is any EXIT-GATE or `HUMAN-DRIFT-RESEARCH`.
- Exit-gate verify: UI-selected Opus inline; commands typically `pytest -v --tb=short --ignore=tests/live` + `ruff check .`.
- Do not change `config/scoring_config.yaml` weights/thresholds outside packets `S3.*` / explicit governance.
- Circuit breaker: same packet `failed` 3× → set `blocked`, stop loop, surface to operator.

## Packet result path

Write `results/<packet-id>.json` using the flat schema from UAW `orchestration.md`.
