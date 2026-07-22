# SD7 Series D Governance Result

**Date:** 2026-07-19  
**Status:** DONE  
**Calibrated claim:** **NOT CALIBRATED**

## Objective

S6.3 Series D governance record + residual-risk / OPS / memory-bank updates. Detection YAML untouched. SD-EXIT-GATE **not** run (operator stop-before-gate).

## Files written / updated

| Path | Action | Rationale |
|---|---|---|
| `docs/scoring-config-governance-series-d.md` | **created** | S6.3 governance record for Series D baseline |
| `docs/residual-risk-drift-hypotheses.md` | updated | Series D = current baseline; C→D P/R prohibition; §2.7 + H11 |
| `OPS.md` | updated | Brief Series D operational pointer |
| `memory-bank/activeContext.md` | updated | SD0–SD7 complete; EXIT blocked |
| `memory-bank/progress.md` | updated | Series D follow-on section |
| `memory-bank/tasks.md` | updated | SD6/SD7 checked; EXIT blocked |
| `.workflow/2026-07-19-d4-time-axis/state.json` | updated | SD7 → done; EXIT-GATE note |
| `.workflow/README.md` | updated | Status line for d4-time-axis slug |

## AC verification

| AC | Met | Evidence |
|---|---|---|
| Governance states seed 42 / thr 45 / config v2.2 | yes | governance doc §What this sweep covers |
| Dual coverage (ever + in_window N=5) | yes | ever=1.0; in_window=0.413 (376/860) |
| D4 engagement 12840 vs Series C 0 (only C→D claim) | yes | governance + residual §2.7 |
| Not CALIBRATED | yes | all docs |
| SD6 concerns recorded honestly | yes | fallback 1084; P=0.011/FP=5432; S2 R=0.714; S2 blocked |
| Residual: Series D baseline; no illegal C→D P/R | yes | residual §1, §2.7, §5, H11 |
| Attestation YAML hygiene follow-on (not executed) | yes | governance + residual + activeContext |
| No `config/scoring_config.yaml` writes | yes | write scope respected |
| No final-report.md or EXIT gate | yes | not created/run |
| state.json SD7 done; EXIT blocked | yes | state.json |

## Governance headline (Series D only)

| Item | Value |
|---|---|
| Seed / thr / config | 42 / 45 / v2.2 |
| P / R / F1 | 0.011 / 0.504 / 0.021 |
| TP / FP / FN | 59 / 5432 / 58 |
| promotion_coverage_ever | 1.0 (55/55) |
| promotion_coverage_in_window (N=5) | 0.413 (376/860) |
| d4_engagement_count | **12840** (Series C: **0**) |
| fallback_flag_count | **1084** |
| S2 recall | **0.714** (25/35); stays blocked (137 active `new`) |

## Concerns carried forward (from SD6)

1. **Fallback storm:** 1084 global `drift_shadow_fallback:no_shadow` — above SD2 expectation (~0 post-first-shadow).
2. **Precision collapse:** P≈0.011, FP=5432 — topology changed; not a calibration claim.
3. **S2 partial recall:** 0.714 — improved within Series D framing but not full catch; B4 license unchanged.

## Follow-on (open, not SD7 scope)

- **Attestation YAML hygiene** — separate S6.3; promote `core/attestation.py` defaults to YAML; zero behavioral diff.
- **SD-EXIT-GATE** — blocked pending operator approval.

## Verification commands

Docs-only packet — no pytest/ruff run required per operator scope. Authoritative numbers from SD6 sweep (`docs/calibration_series_d_metrics.json`, `.workflow/2026-07-19-d4-time-axis/results/SD6-sweep-result.md`).

## Unresolved

None within SD7 write scope. EXIT gate and attestation YAML hygiene remain operator-gated.
