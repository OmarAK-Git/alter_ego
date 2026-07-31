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

## Open gaps / unfinished work

Surface this list when the operator asks about unfinished work (standing request, 2026-07-30). Nothing here is a blocker; all are accepted residuals.

| # | Gap | Source | Notes |
|---|---|---|---|
| 1 | `_stream_events_to_jsonl` never `expunge`s streamed rows, so the Session identity map still accumulates every `ResolvedEventModel` — peak ORM memory still scales with window size | `R-EXIT-GATE-verdict.md` (Grok, ACCEPT-WITH-GAPS) | The RFC-005 fix is real (unbounded Python list is gone), but the "bounded to one chunk" claim is incomplete. Cheapest real follow-up. |
| 2 | Partial temp JSONL files on a mid-stream exception rely on the pre-existing `finally` cleanup block | `R2-code-review.md` note 3 | Pre-existing pattern; the diff does not worsen it. |
| 3 | Chunked-extraction regression proves row completeness across chunk boundaries but cannot prove server-side DB round-trips on sqlite | `R2-code-review.md` note 2 | Would need a Postgres-backed test to close. |
| 4 | `mypy .` reports 65 pre-existing errors repo-wide (untyped defs in `core/`, `worker/`, `batch/`) | R2 follow-up run | None introduced by this run; mypy is not a gate command today. |
| 5 | Attestation YAML hygiene S6.3 | carried from prior run | Acceptance = zero behavioral diff. |
| 6 | Series D is **Not CALIBRATED**; fallback storm (1084), P≈0.011 / FP=5432 | `2026-07-19-d4-time-axis` exit | Only permitted C→D claim is D4 engagement 0→12840. |
| 7 | `scratch/series_c_d4_engagement_run.log` still untracked | working tree | Left deliberately; not a doc. |

## Later (operator / separate)

- [ ] Drift capability expansion (H12–H15) — plan at `docs/superpowers/plans/2026-07-30-drift-detection-capability-expansion.md`, not yet loaded into the loop

## Prior drained

- D4 time-axis + Series D — EXIT ACCEPT-WITH-GAPS; Not CALIBRATED
- Series C — EXIT ACCEPT-WITH-GAPS; Not CALIBRATED
- S55 R-INTERLOCK — drained
- V1 portfolio-ready — drained
