# Orchestration — Reverse-Spec RFC Remediation

Packet-mode T3 run. `state.json` is canonical; `memory-bank/` mirrors follow.

## Queue SoT

Packet mode (no `.workflow/autopilot-queue.json` in this repo — see `.workflow/README.md`).
Packets: `R1` → `R2` → `R-EXIT-GATE`, strictly sequential.

R1 and R2 have disjoint write scopes (`tests/batch/profile_builder/` vs
`batch/profile_builder/builder.py` + `tests/batch/test_profile_build_snapshot.py`),
but R2's Step 6 full-suite check expects R1's renamed file to exist, so R2
`depends_on: [R1]` and they drain sequentially anyway.

## Agent routing

| Stage | Agent | Model |
|---|---|---|
| Research | `researcher` | (skipped — see per-packet `research.reason`) |
| Implement | `implementer` | `composer-2.5` |
| Review | `code-reviewer` | `composer-2.5` |
| Verify | `skeptic-verifier` | `cursor-grok-4.5-high` (readonly) |
| Gate commands | `test-runner` | `composer-2.5` |
| Gate verdict | Task w/ Grok | `cursor-grok-4.5-high` |

Per-task order: implement → code-review → skeptic-verify. Blocking review
findings force `retry`, never `done`. Verifier packets carry goal + ACs +
paths + commands only — no implementer reasoning.

Gate runs in-session (`gate_run_mode: in_session_grok`): `test-runner` executes
the gate commands, then the verdict is dispatched via Task with Grok
(`cursor-grok-4.5-high`). Standing order 2026-07-30: all gates use Grok until
the operator says otherwise. The operator did not pass `--stop-before-gate`,
so the gate is not a stop.

## Red-before-green contract

R2 Step 2 must capture the failing regression run
(`TypeError: build_profiles() got an unexpected keyword argument 'chunk_size'`)
to `results/R2-regression-red.txt` **before** `builder.py` is edited. A green-only
result artifact is a verifier gap.

## Out of scope (do not implement)

- RFC-001 — rejected, fabricated premise (`ScenarioType` is never read by `builder.py`).
- RFC-002 / RFC-003 — KILL affirmed.
- RFC-004 — dropped by the citation breaker.

Untracked repo-root artifacts (`AS_BUILT.md`, `DEBT_LEDGER.md`, `*-rfcs.md`,
`*-run_log.md`, `scratch/*.log`) and `evidence/` are off-limits; commits must
use scoped `git add` of the plan's named files only.
