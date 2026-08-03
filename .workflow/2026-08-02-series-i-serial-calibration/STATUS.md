# Series I — STATUS (Phase B additive folds)

**Updated:** 2026-08-03T00:45Z
**Branch:** `series-i-serial-calibration`
**Calibrated:** false

## Fold chain

| # | Step | Agent | Governance | Status |
|---|---|---|---|---|
| 1 | `fold_02_feature_volume` | [bc-29a79b5f](bc-29a79b5f-14e2-47a2-ba14-629b42724baa) | **REJECT** (inert) | done |
| 2 | `fold_06_precision_gate` | [bc-40622c65](bc-40622c65-6172-4d03-9810-81f8d91ad106) | pending | **running** |
| 3 | `fold_05_fleet` | — | — | queued |
| 4 | `fold_07_staged_drift` | — | — | queued |
| 5 | `fold_03_drift_volume` | — | — | deferred last |

### Fold 1 result

`features.total_volume_delta.enabled=true` — **REJECT** (inert vs baseline: F1=0.0132, R=0.462, FP=7995, S1=S4=1.0). No flags accepted yet.

## Archival probes (complete on cloud)

| Lane | Agent | F1 | FP |
|---|---|---:|---:|
| `ws_volume_1` w=1.0 | bc-6d94a41a | 0.0134 | 7870 |
| `ws_volume_5` w=5.0 | bc-78440d47 | 0.0133 | 7920 |
| `ws_volume_15` w=15.0 | bc-32e5935d | 0.0132 | 8010 |
| `ws_fleet` | bc-edff5f1d | 0.0135 | 7840 |
| `ws_staged_drift` | bc-bbc337d7 | 0.0135 | 7840 |

Local solos still running: `ws_feat_volume` (64496), `ws_precision_gate` (89136).

## Next

Await `series_i_fold_06_precision_gate_metrics.json` → governance → dispatch fold 3.
