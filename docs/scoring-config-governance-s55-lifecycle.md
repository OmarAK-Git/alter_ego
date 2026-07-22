# Scoring-config governance — §5.5 lifecycle × shadow-signal (S55, 2026-07-18)

**Packet:** `.workflow/2026-07-18-s55-alert-lifecycle/`  
**Status:** Declared-not-derived params recorded as **code defaults**. **No** `config/scoring_config.yaml` detection weight/threshold edits this cycle. Series C sweep **deferred**.

## Design authority

- Spec: `docs/superpowers/specs/2026-07-18-s55-blocking-scope-and-alert-lifecycle-design.md` (**APPROVED** operator 2026-07-18)
- S6.3: this record documents new semantic keys + D5 enqueue upgrade without writing knobs to YAML until Series C elects promotion.

## Declared parameters (code defaults in `core/attestation.py`)

| Parameter | Value | Anchor |
|---|---|---|
| `quiet_window_days` | 3 | = `recent_drift_window_days` |
| `min_dwell_builds` | 2 | ≥2 build cycles for one full shadow delta |
| `alpha_prod` | 0.02 | = Design 1 `α` |
| `alpha_anchor` | 0.05 | 2.5× `alpha_prod` over anchor horizon |
| `anchor_history_count` | 5 | = `drift_comparison_history_count` |
| peak-drift bound | `drift_threshold` (5.0 from YAML) | existing key; no new number |
| SLA | `max_profile_build_block_days` (30) | existing S5.6 key; **semantics upgraded** observe→mandatory-review enqueue (D5) |

## Semantic changes (non-knob)

| Change | Location |
|---|---|
| `AlertStateEnum.auto_resolved` | `core/schemas/workflow.py` |
| QUIET∧ATTEST auto-resolution of `new` rows | `batch/profile_builder/builder.py` |
| Drift-row refresh hygiene (D1) | `builder._refresh_or_open_drift_alert` |
| Shadow-signal `drift_alert` under block (D4) | `worker/scorer.py` + `ProfileStore.get_latest_shadow_profile` |
| D5 mandatory-review enqueue | builder escalation flags + `web/api.py` `_build_mandatory_escalations` |
| Attestation at analyst clear + override audit | `web/api.py` `update_workflow_state` |

## Untouched detection knobs

`config/scoring_config.yaml` v2.2 @ `anomaly_threshold=45`, `drift_threshold=5.0`, `features.drift_alert.weight=100.0` — **unchanged**.

## Series C

First post-design sweep establishes Series C baseline. B→C cross-series FP/P/R comparisons prohibited (same rule as A→B). Tracked as follow-on under this T3 run's EXIT notes.
