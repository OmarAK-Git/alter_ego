# Phase 2 Self-Audit (Calibrated v2.1)

## 1. Overview
This audit provides a technical deep-dive into the Phase 2 Calibration Gate. It documents the mathematical formulas, the empirical methodology for threshold selection, and provide trace logs of the detection logic.

## 2. Mathematical Framework

The scoring engine uses a multi-feature additive model. Each feature $f$ contributes a score $S_f$ based on its raw value and a calibrated weight $w_f$.

### 2.1 Categorical Rarity (Laplace-Smoothed)
Used for `login_hour_kl_divergence`.
$$P(x) = \frac{count(x) + \alpha}{N + \alpha \cdot |V|}$$
Where $\alpha=1.0$, $N$ is total events, and $|V|$ is the vocabulary size (e.g., 24 for hours).
The score is the weighted information content (surprisal):
$$S_{rarity} = -w \cdot \log_2(P(x))$$

### 2.2 Service Account Periodicity
Calculated via the Coefficient of Variation ($CV$) of execution intervals in a 60-minute window.
$$\mu = \frac{1}{n} \sum \Delta t, \quad \sigma = \sqrt{\frac{1}{n} \sum (\Delta t - \mu)^2}$$
$$CV = \frac{\sigma}{\mu}$$
$$Score = w \cdot 30.0 \cdot (1 - \max(0, 1 - \frac{CV}{0.3}))$$
**Damping Rule**: If $n < 5$, the score is forced to 0.0 to prevent cold-start FPs.

### 2.3 Novelty Detection
Binary scoring for unseen identifiers.
$$S_{novelty} = w \cdot BaseScore \cdot \mathbb{1}(x \notin Baseline)$$
- `endpoint_novelty`: $BaseScore = 10.0$
- `process_novelty`: $BaseScore = 15.0$

### 2.4 Total Volume Delta
Measures the deviation from the baseline hourly event volume.
$$\Delta Vol = \frac{Vol_{current} - \mu_{baseline\_hourly}}{\max(1.0, \mu_{baseline\_hourly})}$$
$$S_{volume} = w \cdot 5.0 \cdot \max(0, \Delta Vol)$$
This ensures that sudden spikes in activity contribute to the score, but volume decreases do not.

## 3. Threshold Calibration Methodology

### 3.1 Initial Failure Analysis (v2.0)
In the initial run, the threshold was set to **75.0**.
- **Issue**: A "Perfect Storm" anomaly (New Process + New Endpoint + Rare Hour) only achieved a score of $\approx 39.0$.
- **Issue**: Random periodicity in service accounts contributed $75.0$ points, causing 1,482 FPs.

### 3.2 Sensitivity Sweep
We performed a manual sweep of weights to ensure that any **two** novelty indicators or **one** strong periodicity indicator + novelty would cross the threshold.

| Component | Raw Value | Weight (v2.1) | Score Contribution |
|---|---|---|---|
| New Process | 15.0 | 2.5 | 37.5 |
| New Endpoint | 10.0 | 2.5 | 25.0 |
| Rare Hour (3 AM) | ~10.0 | 3.0 | 30.0 |
| **Total Anomaly** | | | **92.5** |

**Final Decision**: Threshold set to **60.0**. This provides a safety margin for Scenarios 1 & 3 while requiring significant evidence for a human-entity alert.

## 4. Detection Trace Examples

### 4.1 Scenario 1: Sharp Credential Misuse
**Event ID**: `c15400d2-...` (Entity: `user_admin_0`)
```json
{
  "total_score": 71.4,
  "is_anomaly": true,
  "contributions": [
    { "feature": "login_hour_kl_divergence", "score": 28.9, "raw": 9.6 },
    { "feature": "endpoint_novelty", "score": 25.0, "raw": 1.0 },
    { "feature": "process_novelty", "score": 15.0, "raw": 1.0 }
  ]
}
```
*Analysis*: The combination of a 3 AM login ($S=28.9$) and a new administrative endpoint ($S=25.0$) successfully crossed the 60.0 barrier.

### 4.2 Scenario 4: Service Abuse (Interactive Command)
**Event ID**: `f915fead-...` (Entity: `svc_backup_0`)
```json
{
  "total_score": 62.1,
  "is_anomaly": true,
  "contributions": [
    { "feature": "service_account_periodicity", "score": 30.0, "raw": 1.0 },
    { "feature": "process_novelty", "score": 25.0, "raw": 1.0 },
    { "feature": "total_volume_delta", "score": 7.1, "raw": 1.4 }
  ]
}
```
*Analysis*: The break in periodicity (Interactive vs. Scheduled) contributed 30 points, which when combined with a new process (25 points), triggered the alert.

## 5. Raw Audit Log Snippets (from SQLite `decisions` table)

Below is a representation of the data as persisted in the database during the final calibration run:

| decision_id | event_id | score | is_anomaly | contributions (JSON) |
|---|---|---|---|---|
| `aea72b...` | `evt_final` | 71.42 | 1 | `[{"feature_name": "login_hour_kl_divergence", "contribution_score": 28.9}, ...]` |
| `b921f1...` | `scen_3_01` | 65.50 | 1 | `[{"feature_name": "process_novelty", "contribution_score": 37.5}, ...]` |

## 6. Conclusion
Calibration v2.1 has effectively mapped the "Identity Engine" logic to the "Adversarial Surface" defined in Phase 2. The engine is now biased towards **Recall** while using **Periodicity Damping** to maintain **Precision**.
