# §5.5 alert lifecycle × shadow-signal interlock — 2026-07-18

**Tier:** T3
**Canonical state:** `.workflow/2026-07-18-s55-alert-lifecycle/state.json`
**Design (approved):** `docs/superpowers/specs/2026-07-18-s55-blocking-scope-and-alert-lifecycle-design.md`
**Trigger:** residual-risk §2.7 drift-starvation deadlock (Series B)

## Goal

Ship the R-INTERLOCK design that breaks the §5.5 absorbing-block deadlock: machine auto-resolution gated on QUIET ∧ ATTEST (never time-only), and shadow-lineage drift visibility under block (D4), without defeating §5.5 anti-normalization.

## Success Criteria

- Design status = APPROVED; S6.3 governance record for declared §6 params + D5 semantics (no detection-YAML writes)
- SPEC §5.5 / §11.5 amended; root `SPEC.md` byte-identical to `docs/SPEC.md`
- `auto_resolved` state; builder auto-resolves `new` rows when QUIET ∧ ATTEST ∧ min_dwell; analyst-touched rows exempt
- Drift-class builder decisions refresh existing drift rows for already-blocked entities (D1 hygiene)
- D5: SLA breach enqueues mandatory analyst review (S5.5 queue pattern), not observe-only
- Scorer `drift_alert` reads shadow accumulator under block; baselines stay promoted; `drift_source_profile_version` recorded when distinct
- Clear path shows attestation status; override clears logged
- Invariants C1–C3 + Design 1F fixture + Design 1 scenario_5 table row; B3b remains green
- Series C sweep **deferred** to follow-on run
- Stop-gate: `pytest -v --tb=short --ignore=tests/live` + `ruff check .`

## Constraints

- No weight/threshold edits to `config/scoring_config.yaml` this cycle
- New §6 keys are **code defaults** (declared-not-derived); governance records them; YAML write waits for Series C if operator elects
- Full shadow scoring rejected (R3); time-only expiry rejected (R1)
- R-INTERLOCK: lifecycle and shadow-signal ship together — neither alone
- Execute packets sequentially when write scopes overlap
- UAW T3 GSD-style loop: researcher → implementer → test-runner → skeptic-verifier

## Risks

| Risk | Approval | Mitigation |
|---|---|---|
| Auto-resolution launders attack mass (P1/P2) | no | Peak-drift + novel-mass + anchor gates; C3 invariant |
| D4 alone without D3 re-creates Series B | no | R-INTERLOCK; exit gate requires both |
| Analyst clear overrides attestation | accepted | Display + override audit (SPEC §11.5 frozen) |
| Series C deferred → no fleet FP-rate proof yet | accepted | C1/C2/C3 fixtures; Series C tracked as follow-on |

## Work Packets

| ID | Objective | Write scope |
|---|---|---|
| S55.0 | Approve design + S6.3 governance (declared params, D5 semantics) | `docs/scoring-config-governance-s55-lifecycle.md`, design status, OPS/memory-bank |
| S55.1 | SPEC §5.5/§11.5 amendment + root SPEC sync | `docs/SPEC.md`, `SPEC.md` |
| S55.2 | `auto_resolved` enum + novel-mass / attestation helpers + unit tests | `core/schemas/workflow.py`, `core/attestation.py` (new), tests |
| S55.3 | Builder: QUIET∧ATTEST auto-res, D5 enqueue, drift-row refresh, audit | `batch/profile_builder/builder.py`, tests |
| S55.4 | Scorer D4 shadow drift + determinism field | `worker/scorer.py`, `worker/profile_store.py`, tests |
| S55.5 | Web/API: attestation at clear + S5.6 on mandatory-escalations queue | `web/api.py`, `web/static/*`, tests |
| S55.6 | C1–C3 invariants, Design 1F, scenario_5 table row | Design 1 spec, `tests/test_boil_the_frog_invariants.py`, fixtures |
| S55-EXIT-GATE | Full pytest + ruff + skeptic; sync memory-bank | results + final-report |

## Autopilot (UAW / GSD-style)

| Role | Agent |
|---|---|
| Research | `researcher` |
| Implement | `implementer` |
| Test | `test-runner` |
| Verify | `skeptic-verifier` |

Prefer implement `composer-2.5`, verify `cursor-grok-4.5-high` when dispatching via Task tool.

## Requirement Traceability

| Req | AC | Packet | Verification |
|---|---|---|---|
| REQ-INTERLOCK | D3 + D4 both ship; neither alone | S55.3–S55.4 + EXIT | skeptic + C1/C2 |
| REQ-NODEADLOCK | Benign FP blocks auto-resolve under QUIET∧ATTEST | S55.3, S55.6 C1 | C1 fixture |
| REQ-NOSANCTUARY | Block state absent from drift term | S55.4, C2 | C2 fixture |
| REQ-NOLAUNDER | Post-auto-res novel mass vs anchor < alpha_anchor | S55.2–S55.3, C3 | C3 fixture |
| REQ-CONTAIN | B3b stays green | S55.6 | Design 1 suite |
| REQ-AUDIT | Transitions audited | S55.3, S55.5 | unit + API tests |
| REQ-GOV | Declared params recorded; no detection YAML | S55.0 | governance doc |

## Verification

- Per-packet focused pytest named in packet result
- Exit: `pytest -v --tb=short --ignore=tests/live` + `ruff check .`
- Optional: `python <ultimate-agentic-workflow>/scripts/verify_run.py --run-dir .workflow/2026-07-18-s55-alert-lifecycle`
