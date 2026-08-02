# Active Context

**Updated:** 2026-08-02T20:00Z — Series I T2 campaign restructure

## Current focus

**T2:** Finish Series I campaign via cloud/local split (not individual dimension proofs)
**Workflow:** `.workflow/2026-08-02-series-i-serial-calibration/`
**Branch:** `series-i-serial-calibration` (pushed to origin)
**Calibrated:** false

## Phase

`A_weight_search_split` — cadence continues locally; recall-side weight probes on cloud; flag-only solos local (max 3 writers).

## Cadence Step 2 decision

**Do NOT kill** — `cadence_cov` query n=4160: 71.3% exactly 0.0, 28.7% non-zero (mean 0.28, max 1.0). Series F cadence delta mean 0.288. Operator wait required if reconsidering kill threshold.

## Local lanes (max 3)

| Lane | Status |
|---|---|
| `ws_cadence_2` | running (~day 6 complete; day 7 in progress) |
| `ws_precision_gate` | running (~day 10/21) |
| `ws_feat_volume` | running (~day 10/21) |

## Cloud lanes (pending dispatch)

`ws_volume_1`, `ws_volume_5`, `ws_volume_15`, `ws_staged_drift`, `ws_fleet` — see `CLOUD-I-LAUNCH.md`; partial DBs + checkpoints at sim-day 2026-01-11.

## Aborted

| Lane | Reason |
|---|---|
| `ws_geo_5` | `geo_velocity_delta_last_build` 100% zero in partial DB (n=585); Series G mean=0 |

## Standing order

All gates on Grok Fast; do **not** merge Series I to main. Never claim CALIBRATED.
