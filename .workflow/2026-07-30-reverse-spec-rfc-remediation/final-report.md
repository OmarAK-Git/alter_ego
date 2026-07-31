# Final report — Reverse-Spec RFC Remediation

**Run:** `.workflow/2026-07-30-reverse-spec-rfc-remediation/`  
**Closed:** 2026-07-30  
**Verdict:** **ACCEPT-WITH-GAPS** (`cursor-grok-4.5-high`)

## Goal

Remediate the two independently-verified RFCs from the `5638f86d…` reverse-spec
review: pytest discovery for the profile-builder test (RFC-006) and bounded
Postgres→JSONL extraction in `build_profiles` (RFC-005).

## Outcome

| Packet | Status | Evidence |
|---|---|---|
| R1 (RFC-006) | done | skeptic survives; commit `5311d3a` |
| R2 (RFC-005) | done | code review 0 blocking; skeptic survives; commits `2aaa4e0`, `019487e` |
| R-EXIT-GATE | done | ACCEPT-WITH-GAPS; fresh pytest **165**, ruff clean |

## Commits

- `5311d3a` — test: fix pytest discovery for profile builder aggregation test
- `2aaa4e0` — fix: stream Postgres extraction to temp JSONL in bounded chunks
- `019487e` — style: annotate `_BUILD_EXTRACT_CHUNK_SIZE` as int per plan interface

Surface: exactly `batch/profile_builder/builder.py`,
`tests/batch/profile_builder/test_builder.py`,
`tests/batch/test_profile_build_snapshot.py`. No scoring-config changes.

## Accepted gap

Session identity-map retention: `yield_per` removes the unbounded Python result
list and DuckDB does not rematerialize the ORM window, but without `expunge`
the Session still accumulates every streamed `ResolvedEventModel`. Peak ORM
memory still scales with window size. The remediation is real (list
materialization is gone); the “one chunk only” memory claim is incomplete.

## Not implemented (by design)

- RFC-001 — rejected (fabricated premise; affirmed at exit gate)
- RFC-002 / RFC-003 — KILL affirmed
- RFC-004 — dropped by citation breaker

## Process note

Gate was briefly blocked when Opus 5 hit an API usage limit. Operator authorized
all future gates on `cursor-grok-4.5-high` (standing order recorded in `OPS.md`).
Gate re-opened and closed on Grok.
