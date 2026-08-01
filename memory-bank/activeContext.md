# Active Context

**Updated:** 2026-07-31

## Current focus

**T3:** `.workflow/2026-07-30-drift-capability-expansion/` — **IN PROGRESS**  
**Plan:** `docs/superpowers/plans/2026-07-30-drift-detection-capability-expansion.md`  
**Design:** `docs/superpowers/specs/2026-07-30-drift-detection-capability-expansion-design.md`  
**Sprint report:** `.workflow/2026-07-30-drift-capability-expansion/results/SPRINT-PROGRESS-REPORT.md`

## Strategy (2026-07-31 operator change)

- **Parallel sweeps:** F/G/H start without waiting for E (separate calibrate DBs).
- **Queue deps:** P2-3 does **not** depend on P0-3; P4-3 needs P2-3; P5-4 needs P4-3.
- **Leave local E running** (PID 63516, chunk ~11/22) unless cloud-E confirms takeover.
- **Cloud E branch:** eature/drift-capability-expansion pushed to origin for cloud Series E (2026-07-31).\n- **FINAL-DOCS / DC-EXIT-GATE** wait for E+F+G+H metrics + governance.

## What landed (implementation)

- **Phase 0:** `_resolve_effective_profile` — point-rarity/embedding follow shadow under block
- **Phase 1:** `ot_polling` archetype + build-window cadence CoV drift dimension
- **Phase 2:** `compute_volume_rarity` + `hourly_event_counts` histogram
- **Phase 3:** Fleet `COHORT_DRIFT` decision (`fleet_drift_enabled: false`)
- **Phase 4:** `core/geo_centroids.py` + `geo_velocity_delta`
- **Phase 5:** `signal_family_agreement_count`, `precision_gate_version` (Alembic `i8j9k0l1m2n3`)
- **Phase 6:** `drift_crossing_log` + `match_staged_sequence`

All `enabled` flags in committed `scoring_config.yaml` remain **false**.

## In flight

| Packet | Status | Notes |
|---|---|---|
| **P0-3** Series E | in_progress | chunk ~11/22; checkpoint `2026-01-12`; PID 63516; no metrics yet |
| **P2-3** Series F | starting | chunked sweep queued after progress report |
| **P4-3** Series G | pending | after F |
| **P5-4** Series H | pending | after G |

## Verification baseline

`pytest --ignore=tests/live`: **204 passed** (pre-sweep tree). `ruff check .`: clean.

## Standing order

All gates on Grok until operator overrides.
