# Tasks

**Canonical T3 state:** `.workflow/2026-07-30-reverse-spec-rfc-remediation/state.json` (CLOSED)

## Autopilot

**Active sprint:** R (reverse-spec RFC remediation) — **drained**  
**Next runnable:** none  
**Gate model standing order:** `cursor-grok-4.5-high` (all gates) until operator overrides

## Queue (all done)

- [x] **R1** — RFC-006 pytest discovery rename — DONE (`5311d3a`)
- [x] **R2** — RFC-005 chunked streaming extraction — DONE (`2aaa4e0`, `019487e`)
- [x] **R-EXIT-GATE** — ACCEPT-WITH-GAPS (Grok; pytest 165 / ruff clean)

## Later (operator / separate)

- [ ] Attestation YAML hygiene S6.3 (zero behavioral diff)
- [ ] Operator-owned untracked: `AS_BUILT.md`, `DEBT_LEDGER.md`, `alter-ego-drift-gap-evaluation.md`, drift-expansion plan, RFCs — leave alone
- [ ] Optional follow-up from exit gap: `expunge` streamed rows in `_stream_events_to_jsonl` to fully bound Session identity-map memory

## Prior drained

- D4 time-axis + Series D — EXIT ACCEPT-WITH-GAPS; Not CALIBRATED
- Series C — EXIT ACCEPT-WITH-GAPS; Not CALIBRATED
- S55 R-INTERLOCK — drained
- V1 portfolio-ready — drained
