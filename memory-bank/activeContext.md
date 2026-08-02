# Active Context

**Updated:** 2026-08-02T04:25:00Z — Series I serial calibration **IN PROGRESS**

## Current focus

**T3:** `.workflow/2026-08-02-series-i-serial-calibration/`
**Branch:** `series-i-serial-calibration`
**Phase:** A_weight_search (cadence → volume → geo), then B_serial_folds
**Harness:** `scratch/run_series_i_sweep.py` + `scratch/run_series_i_campaign.py`
**Calibrated:** false

## Baseline (Series E–H @ thr=45)

P≈0.0067 R≈0.4615 F1≈0.0132 TP=54 FP=7995; S1=1 S2≈0.74 S3≈0.11 S4=1 S5=0.60

## Standing order

All gates on Grok Fast (`cursor-grok-4.5-high-fast`); implement via `composer-2.5-fast` until operator overrides. Do **not** merge Series I to main without operator review. Never claim CALIBRATED.
