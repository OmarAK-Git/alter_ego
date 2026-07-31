# Active Context

**Updated:** 2026-07-30

## Current focus

**T3:** `.workflow/2026-07-30-reverse-spec-rfc-remediation/` — **CLOSED** 2026-07-30  
**Plan:** `docs/superpowers/plans/2026-07-30-reverse-spec-rfc-remediation.md`  
**Gate:** `R-EXIT-GATE` — **ACCEPT-WITH-GAPS** (`cursor-grok-4.5-high`; fresh pytest **165**, ruff clean).  
**Final report:** `.workflow/2026-07-30-reverse-spec-rfc-remediation/final-report.md`

## What landed

- **RFC-006 / R1** (`5311d3a`): rename `tests/batch/profile_builder/builder.py` → `test_builder.py` (pure R100 rename).
- **RFC-005 / R2** (`2aaa4e0` + `019487e`): `_stream_events_to_jsonl` with `execution_options(yield_per=chunk_size)`; trailing `chunk_size` defaults to 5000.

## Accepted gap

Session identity-map retention without `expunge` — peak ORM memory still scales with window size even though the Python result list is gone.

## Standing order

**All gates on Grok** (`cursor-grok-4.5-high`, `gate_run_mode: in_session_grok`) until the operator says otherwise. Recorded in `OPS.md`.

## Current baseline

**Series D:** `docs/calibration_series_d_metrics.json` — Not CALIBRATED. Only permitted C→D claim: D4 engagement 0→12840.
