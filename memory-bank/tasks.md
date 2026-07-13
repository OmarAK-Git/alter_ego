# Tasks

**Canonical T3 state:** `.workflow/2026-07-12-v1-portfolio-ready/state.json`

## Autopilot

**Stopped:** `--stop-before-gate` — next item is `S4-EXIT-GATE`  
**Active sprint:** S4 (S4.1–S4.7 done)  
**Next gate:** `S4-EXIT-GATE` (chat_gate / phase_exit)

## Done

### S0–S3
- [x] S0–S3 packets + S1/S2/S3 EXIT-GATEs

### S4
- [x] S4.1 — Explainer slot-isolated low-trust fields
- [x] S4.2 — Explainer queue-depth + template fallback
- [x] S4.3 — Suppressed view + confidence_floor; aging/jitter deferred
- [x] S4.4 — Demo path seed → triage → explain → contain
- [x] S4.5 — First-class `replay_run_id`
- [x] S4.6 — Calendar/gap Path B defer
- [x] S4.7 — Asset/dependency Path B defer

## Now (blocked by stop-before-gate)

- [ ] **S4-EXIT-GATE** — skeptic-verifier + `pytest -v --tb=short --ignore=tests/live` + `ruff check .`; unlocks HUMAN-DRIFT-RESEARCH

## Later gates

- [ ] HUMAN-DRIFT-RESEARCH
