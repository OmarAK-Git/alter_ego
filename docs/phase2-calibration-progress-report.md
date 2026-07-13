# Phase 2 — Calibration Progress Report

**Date**: 2026-05-10 (original narrative); metrics refreshed 2026-07-13 (S3.1/S3.2 re-sweep)  
**Status**: Phase 2A / closed-with-residual — **not CALIBRATED**  
**Metrics authority:** `docs/calibration_final_metrics.json`, `docs/phase2-s3-operating-point.md`

## 1. Executive Summary
This report documents Phase 2 calibration progress. The evaluation harness and threshold sweeps against all four adversarial scenarios (§10.3) are complete. **Phase 2A is closed with residuals** — high FP and scenario_3_subtle misses — not an audit-grade success.

### Key Metrics Summary (thr=45, S3.1 re-sweep)
| Metric | Baseline (Heuristic) | ALTER_EGO (Current) | Status |
| :--- | :--- | :--- | :--- |
| **Precision** | 0.001 | **0.019** | Residual — high FP |
| **Recall (Global)** | 1.00 | **0.817** | Selective |
| **False Positives** | 10,492 | **3448** | Residual |
| **Scenario 1 Catch** | YES | YES (R=1.0) | — |
| **Scenario 2 Catch** | YES | YES (R=1.0) | Caught after integrity fixes |
| **Scenario 3 Catch** | NO | **Partial** (R=0.667) | 15 FN — residual |
| **Scenario 4 Catch** | NO | YES (R=1.0) | — |

---

## 2. Residual Error Modes

### 2.1 High false-positive rate
**Result**: 3448 FP @ thr=45 (P≈0.019). Dominant error mode; unfiltered triage impractical.

### 2.2 Scenario 3: Subtle insider drift
**Result**: Recall 0.667 (15 FN @ thr=45).  
**Analysis**: Subtle coordinated drift remains the weakest attack class. PR-curve best-F1 at thr=55 (FP=1136, FN=34) is diagnostic only — **not applied** to YAML.

### 2.3 Scenario 2 (historical note)
Prior reports claimed S2 recall 0.0. The S3.1 re-sweep shows **recall 1.0** (35/35) after eval-partition and geo-drift integrity fixes. See `docs/calibration_final_metrics.json`.

---

## 3. Parameter Coverage (§6.8 Alignment)
Core scoring parameters are wired; deferred keys per `memory-bank/progress.md` knob inventory.

| Required by spec | Present? | Value / Note |
| :--- | :--- | :--- |
| **anomaly threshold** | Yes | 45.0 (YAML current; P≈0.019 @ saved sweep) |
| **confidence floor** | Yes | 0.6 |
| **containment threshold** | Yes | 85.0 (auto queue when score ≥ threshold + confidence floor; S1.3) |
| **per-feature weights** | Yes | See `scoring_config.yaml` |
| **decay lambdas** | **Removed** | Stripped S2.8 — never read; use `drift_half_life_days` + `max_profile_staleness_days` |
| **min_cohort_size** | Yes | 10 |
| **min_clean_obs_count** | Config only | **Not read** in production path (defer S5.11) |
| **max_changed_fraction** | Yes | 0.2 |
| **cohort_gate_window** | Yes | 7 days |
| **max_calendar_adj** | Config only | **Not read** (defer S4.6) |
| **gap_correlation_win** | Config only | **Not read** (defer S4.6) |
| **investigation_win** | Config only | **Not read** (defer S4.6) |
| **max_replay_window** | Yes | 30 days |
| **max_profile_block** | Config only | **Not read** (defer S5.6) |
| **age_jitter_hours** | Config only | **Not read** (defer S4.3) |
| **delta metric weights** | Yes | See `drift_weights` in YAML |

---

## 4. Feature Contract Reconciliation
1.  **login_hour_rarity**: Uses **Surprisal (Bits)** via Laplace-smoothed log-probability, centered at 5.0 bits.
2.  **geolocation_rarity**: Center: 7.0 bits; geo histograms + drift KL (S1.2).
3.  **endpoint_set_rarity**: Center: 6.0 bits.
4.  **process_name_rarity**: Center: 9.0 bits.
5.  **command_line_embedding_similarity**: Deterministic char 3-gram 128-d (`alter-ego-ngram-v1`).
6.  **service_account_execution_frequency_deviation**: Interval CV-based.

---

## 5. Scenario Analysis (§10.3)

### [PASS] Scenario 1: Sharp Identity Misuse
- **Result**: Recall 1.0.

### [PASS] Scenario 2: Slow Roll Identity Drift
- **Result**: Recall **1.0** (35/35 @ thr=45).

### [PARTIAL] Scenario 3: Subtle / Coordinated Behavioral Drift
- **Result**: Recall **0.667** (15 FN).

### [PASS] Scenario 4: Service Account Identity Abuse
- **Result**: Recall 1.0.

---

## 6. Verdict & Next Steps
Phase 2 is **closed-with-residual (Phase 2A)** — **not CALIBRATED**. Residual modes documented in `docs/phase2-s3-operating-point.md`. Threshold/weight changes require S3.6 governance + full re-sweep.
