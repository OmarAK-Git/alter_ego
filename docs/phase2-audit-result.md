# Phase 2 — Calibration & Detection Efficacy Audit

**Date**: 2026-05-10 (original narrative); metrics refreshed 2026-07-13 (S3.1/S3.2 re-sweep)  
**Status**: Phase 2A / closed-with-residual — **not CALIBRATED**  
**Metrics authority:** `docs/calibration_final_metrics.json`, `docs/phase2-s3-operating-point.md`

## 1. Executive Summary
This audit documents the transition from manual heuristic fitting to threshold-driven calibration across all four adversarial scenarios defined in the Spec (§8.3). The system implements a six-feature contract with evidence-bound aggregation and confidence-gated damping. **Phase 2A is closed with residual error modes** — high false-positive rate and scenario_3_subtle misses — not an audit-grade calibration success.

### Key Metrics Summary (thr=45, S3.1 re-sweep)
| Metric | Baseline (Heuristic) | ALTER_EGO (Current) | Status |
| :--- | :--- | :--- | :--- |
| **Precision** | 0.001 | **0.019** | Residual — high FP |
| **Recall (Global)** | 1.00 | **0.817** | Selective |
| **False Positives** | 10,492 | **3448** | Residual — dominant error mode |
| **Scenario 1 Catch** | YES | YES (R=1.0) | — |
| **Scenario 2 Catch** | YES | YES (R=1.0) | Caught after S1/S2 integrity fixes |
| **Scenario 3 Catch** | NO | **Partial** (R=0.667, 15 FN) | Residual risk |
| **Scenario 4 Catch** | NO | YES (R=1.0) | — |

---

## 2. Calibration Methodology
We executed a threshold sweep from [0, 150] in increments of 5 against a synthetic evaluation set spanning 15 simulation days. The saved operating point is **Threshold = 45.0** (matches current `config/scoring_config.yaml`).

### 2.1 Threshold Sweep & Operating Point Selection
- **Rationale**: thr=45 is the YAML interim operating point from the S3.1 integrity re-sweep.
- **Residual risk**: 3448 FP (~98% of positive decisions are benign); scenario_3_subtle recall 0.667 (15 FN). See `docs/phase2-s3-operating-point.md`.

### 2.2 PR Curve Visualization (Data)
The full PR curve dataset is available at: [calibration_pr_curve.json](calibration_pr_curve.json)

---

## 3. Parameter Coverage (§6.8 Alignment)
Core scoring parameters are wired; deferred/unwired keys are listed in `memory-bank/progress.md` §Scoring config knob inventory.

| Parameter | Value | Logic |
| :--- | :--- | :--- |
| `confidence_floor` | 0.6 | Blocks low-evidence alerts from crossing threshold. |
| `contribution_scale_max` | 50.0 | Prevents single-feature runaway FPs. |
| `laplace_alpha` | 1.0 | Smoothes rarity scores for warm-up profiles. |
| `decay_lambdas` | — | **Removed S2.8** — never read; staleness via `max_profile_staleness_days`; drift decay via `drift_half_life_days`. |
| `cohort_gating` | min_size=10 | Falls back to Role/Parent histograms when local data < 20. |

---

## 4. Feature Contract Reconciliation
We have addressed the naming and math drift identified in the previous review:

1.  **login_hour_rarity**: Now uses **Surprisal (Information Content)** via smoothed log-probability, centered by subtracting baseline entropy (5.0 bits).
2.  **geolocation_rarity**: Implemented for auth events; centered at 7.0 bits; geo histograms + drift KL (S1.2).
3.  **endpoint_set_rarity**: Replaced binary novelty with categorical log-likelihood (centered 6.0 bits).
4.  **process_name_rarity**: Replaced binary novelty with categorical log-likelihood (centered 9.0 bits).
5.  **command_line_embedding_similarity**: Deterministic char 3-gram SHA-256 → 128-d unit-norm vector (`alter-ego-ngram-v1`).
6.  **service_account_execution_frequency_deviation**: Implemented using **Coefficient of Variation (CV)** intervals.

---

## 5. Scenario Analysis & Residual Risk

### [PASS] Scenario 1: Sharp Identity Misuse
- **Result**: Recall 1.0.
- **Trace**: User `admin_0` logged in from a new Geo (`RU`) at a rare hour (`03:00`). 
- **Decision**: Score above threshold. **Identity flagged.**

### [PASS] Scenario 2: Slow Roll identity Drift
- **Result**: Recall **1.0** (35/35 @ thr=45).
- **Analysis**: Caught under the S3.1 harness after eval-partition integrity fixes (S1.1), geo drift wiring (S1.2), and related S2 work. Prior narrative claiming R=0.0 is superseded by `docs/calibration_final_metrics.json`.

### [PARTIAL] Scenario 3: Coordinated / Subtle Behavioral Drift
- **Result**: Recall **0.667** (30 TP, 15 FN).
- **Analysis**: Subtle insider drift remains the weakest attack class at thr=45.
- **Remediation**: Feature/threshold work or alternate operating point (PR-curve best-F1 at thr=55 documented but **not applied**).

### [PASS] Scenario 4: Service Account Identity Abuse
- **Result**: Recall 1.0.
- **Analysis**: Backup service account running an interactive shell (`cmd.exe`) triggered both periodicity deviation and process rarity.
- **Decision**: Score above threshold. **Identity flagged.**

---

## 6. Storage & Governance Alignment
- **Database**: Transitioned to SQLAlchemy models with Postgres-native JSONB/ARRAY support.
- **Schema**: Added `cohort_used`, `contribution_id`, and `flags` to `DecisionRecord`.
- **Audit Logs**: All decisions are uniquely hashed using `(event_id + profile_version + config_version)`.

## 7. Verdict
Phase 2 is **closed-with-residual (Phase 2A)** — **not CALIBRATED**. S1/S2/S4 recall 1.0 at thr=45; scenario_3_subtle misses and 3448 FP remain. Full metrics: `docs/calibration_final_metrics.json`; residual modes: `docs/phase2-s3-operating-point.md`.
