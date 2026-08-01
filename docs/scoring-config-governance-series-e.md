# Scoring-config governance — Series E (2026-07-30)

**Plan:** `docs/superpowers/plans/2026-07-30-drift-detection-capability-expansion.md` (Phase 0)  
**Status:** Series E baseline established. **Not CALIBRATED.** Detection knobs **unchanged** (`enabled` flags none for Phase 0).

## What this sweep covers

| Item | Value |
|---|---|
| Seed | 42 |
| Config | v2.2 @ `anomaly_threshold=45.0` |
| Semantics | Same event mix as Series D + Phase 0 shadow-aware point-rarity/embedding baseline |
| Artifact | `scratch/series_e_metrics.json` |
| Harness | `scratch/run_series_e_sweep.py` |
| Knobs changed | **false** |

## Headline (Series E only — do not compare FP/P/R to A/B/C/D)

| Metric @ thr=45 | Value |
|---|---|
| P / R / F1 | 0.0067 / 0.4615 / 0.0132 |
| TP / FP / FN | 54 / 7995 / 63 |
| active_alert_workflow_rows | 6270 |
| blocked_entity_count | 53 |

## Phase 0 isolated effect

| Metric | Series D (archival) | Series E |
|---|---:|---:|
| blocked_entity_count | 51 | 53 |
| active_alert_workflow_rows | 3241 | 6270 |
| point_baseline_shadow_engaged_count | 0 (pre-Phase-0) | 13526 |
| blocked_entity_anomaly_count | — | 8023 |

Phase 0 has no config `enabled` gate — this doc confirms the fix does not shift blocked-entity FP volume unexpectedly before Phase 1+ lands.

## Cross-series rule

Do **not** compare headline FP/P/R to Series A/B/C/D. Series E isolates Phase 0 point-baseline behavior only.

## Standing rule

No production scoring change without recorded sweep + governance sign-off (S6.3).
