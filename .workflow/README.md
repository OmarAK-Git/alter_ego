# `.workflow/` runs

T3 accountable runs live here as `.workflow/<slug>/`.

## Layout per slug

```text
.workflow/<slug>/
|-- plan.md            # human plan (required sections)
|-- state.json         # canonical machine state
|-- orchestration.md   # optional dispatch notes
|-- packets/           # worker packets
|-- results/           # packet results
`-- final-report.md    # closeout
```

Validate before execution:

```bash
# Install/clone ultimate-agentic-workflow separately, then:
python <ultimate-agentic-workflow>/scripts/verify_run.py --run-dir .workflow/<slug>
```

## State ownership

- **Canonical live state for T3:** `state.json`
- **Projections:** `memory-bank/tasks.md`, `memory-bank/activeContext.md`, `IMPLEMENTATION_PLAN.md`

Update `state.json` first; sync memory-bank after.

## Active / recent runs

| Slug | Status | Purpose |
|---|---|---|
| `2026-07-30-reverse-spec-rfc-remediation` | **closed** (R-EXIT-GATE ACCEPT-WITH-GAPS on Grok) | RFC-005 chunked streaming + RFC-006 pytest discovery |
| `2026-07-19-d4-time-axis` | **closed** (SD-EXIT-GATE ACCEPT-WITH-GAPS) | D4 shadow sim-time axis + Series D re-sweep + governance |
| `2026-07-19-series-c` | **drained** (EXIT ACCEPT-WITH-GAPS) | Series C: R-INTERLOCK baseline + scenario_5; Not CALIBRATED |
| `2026-07-18-s55-alert-lifecycle` | **drained** (EXIT ACCEPT-WITH-GAPS) | §5.5 R-INTERLOCK: alert lifecycle × shadow-signal (D1–D5) |
| `2026-07-18-boil-the-frog-invariants` | closed (Series B) | Design 1 invariants + BTF claim hygiene |
| `2026-07-12-v1-portfolio-ready` | **drained** (S6-EXIT-GATE passed) | V1 portfolio-ready: S0–S6 packets + human drift gate; operator drift research remains open |
| `2026-07-12-agentic-bootstrap` | complete | Workflow + memory-bank + honest README bootstrap |

### Autopilot note

This repo’s “GSD autopilot” is the **UAW T3 packet loop** (researcher / implementer / test-runner / skeptic-verifier). Do not install archived `gsd-build/get-shit-done`. Packet labels use `sprint:S*|req:REQ-*` for filtering.
