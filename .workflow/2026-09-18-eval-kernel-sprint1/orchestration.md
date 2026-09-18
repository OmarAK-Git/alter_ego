# Orchestration — 2026-09-18-eval-kernel-sprint1

Queue SoT: `.workflow/autopilot-queue.json`. Update `state.json` before memory-bank.

## Dispatch

- Next pending item whose `depends_on` are all `done`.
- researcher: skip unless a task actually has ≥2 viable paths (plan Tasks 1–21 are TDD-specified; default skip).
- implementer: composer-2.5-fast, one write-overlapping task at a time (`e2e_kernel.py` is shared after S1-2).
- code-reviewer: after every code-changing implement; blocking findings force retry.
- skeptic-verifier: cursor-grok-4.6-high-fast; no implementer reasoning in the packet.
- Gates: test-runner runs commands; verdict via Task `cursor-grok-4.6-high-fast` (`in_session_grok`). Never Opus.

## Parallelism

S1-3 and S1-4 may run after S1-2 if write scopes stay disjoint (loader vs theater). S1-5..S1-16 all touch `batch/eval/e2e_kernel.py` — drain sequentially. S1-19 can overlap S1-17 only if theater/headline files stay disjoint from the compact fixture work.

## Evidence

Write command logs under `.workflow/2026-09-18-eval-kernel-sprint1/results/`. Never mark `done` without verifier or gate evidence.
