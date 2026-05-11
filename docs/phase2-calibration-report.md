# Phase 2 Calibration Report

This report summarizes the empirical results of the ALTER_EGO detection engine calibration across four adversarial scenarios.

## 1. Scenario Recall Analysis
| Scenario | Recall @ Threshold 45 | TP | FN | Analysis |
| :--- | :--- | :--- | :--- | :--- |
| **S1: Sharp Misuse** | 1.00 | 1 | 0 | Caught by Geo/Hour novelty. |
| **S2: Slow Roll** | 0.00 | 0 | 7 | Missed; score 31.5 (below noise floor). |
| **S3: Coordinated** | 1.00 | 3 | 0 | Caught by cohort process novelty. |
| **S4: Service Abuse** | 1.00 | 1 | 0 | Caught by periodicity deviation. |

## 2. Precision/Recall Curve
Threshold sweeps demonstrate a sharp Precision drop below **Threshold 45**.

| Threshold | Precision | Recall | F1 |
| :--- | :--- | :--- | :--- |
| 10 | 0.001 | 1.00 | 0.002 |
| 35 | 0.002 | 1.00 | 0.004 |
| **45** | **1.00** | **0.42** | **0.59** |
| 75 | 1.00 | 0.17 | 0.29 |

## 3. Baseline Comparison
- **Baseline (2-Feature Heuristic)**: Precision 0.001, Recall 1.0. (High noise: 10k+ FPs).
- **ALTER_EGO (6-Feature Gated)**: Precision 1.0, Recall 0.42. (Clean: 0 FPs).

## 4. Operational Configuration
The following operating point is recommended for Phase 3 deployment:
- `anomaly_threshold: 45.0`
- `confidence_floor: 0.6`
- `contribution_scale_max: 20.0`
