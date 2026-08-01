# Tasks

**Canonical T3 state:** `.workflow/2026-07-30-drift-capability-expansion/state.json`

## Autopilot

**Active sprint:** DC (drift capability expansion) — **in progress**  
**Queue SoT:** `.workflow/autopilot-queue.json`  
**Gate model:** `cursor-grok-4.5-high` (all gates, in_session_grok)

## Queue status (2026-07-31)

| Status | Count | Items |
|---|---:|---|
| done | 18 | P0-1, P0-2, P0-GATE, P1-1, P1-2, P2-1, P2-2, P2-GATE, P3-1, P4-1, P4-2, P4-GATE, P5-1..P6-2, P5-GATE |
| in_progress | 1 | P0-3 (Series E–H chunked sweeps restarting) |
| pending | 5 | P2-3, P4-3, P5-4, FINAL-DOCS, DC-EXIT-GATE |

## Implementation landed (uncommitted)

Phases 0–6 code + tests: **204 pytest passed**, ruff clean. All new signals `enabled: false`.

## Blockers

Series E–H full sweeps (~hours each) must complete before governance docs + exit gate.
