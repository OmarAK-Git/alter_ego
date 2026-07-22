# Final Report — D4 Time-Axis Fix (`2026-07-19-d4-time-axis`)

**Closed:** 2026-07-19  
**Exit decision:** **ACCEPT-WITH-GAPS**  
**Gate mode:** chat_gate · **Verifier:** skeptic-verifier (`cursor-grok-4.5-high`)

## Goal

Fix D4 shadow-read time axis (as-of on sim `data_window_end`, not wall `created_at`), make blocked-shadow misses observable, rewrite C2 + regressions, add dual `promotion_coverage` (N=5), then run Series D re-sweep after a hard operator gate.

## Exit verification (fresh, this session)

| Check | Command | Result | Evidence |
|---|---|---|---|
| Tests | `pytest -v --tb=short --ignore=tests/live` | **163 passed**, EXIT=0 | `results/exit-gate-fresh-verify.txt` |
| Lint | `ruff check .` | **All checks passed**, EXIT=0 | `results/SD-EXIT-ruff.txt` |
| Skeptic | adversarial exit review | ACCEPT-WITH-GAPS → gaps remediated → re-verified CLEARED | `results/SD-EXIT-GATE-skeptic-result.md` |

## What shipped (SD0–SD7)

- **SD0/SD1** — C2 rewritten to a wall/sim-time seam (RED evidence `SD0-C2-red.txt`: promoted 0.0 vs shadow 3.0), then `ProfileStore.get_latest_shadow_profile` fixed to filter/order on `data_window_end` with `created_at DESC` as a tie-break only; GREEN (`SD1-C2-green.txt`). Full profile_store query audit (`SD1-profile-store-audit.md`).
- **SD2** — Blocked-shadow miss now observable: WARN + `drift_shadow_fallback:no_shadow` flag via `count_shadow_profiles` (no direct ORM in scorer).
- **SD3** — Regression tests: wall-future `created_at` still found; equal `data_window_end` prefers later `created_at`.
- **SD4** — Dual `promotion_coverage` (`_ever` + `_in_window` N=5) + `serving_profile_missing_days`; Series D harness skeleton.
- **SD5** — Items 1–5 review gate; operator approved continuation.
- **SD6** — Series D sweep (seed 42, v2.2 @ thr=45): **D4 engagement 12840** (Series C = 0); P=0.011 R=0.504; fallback 1084. **Not CALIBRATED.**
- **SD7** — Series D governance + residual-risk + memory-bank; no detection-YAML changes.

## In-gate remediation

The skeptic caught prohibited **C→D "improvement" framing** (constraint: the *only* permitted C→D claim is the D4 engagement count):

1. `docs/scoring-config-governance-series-d.md` — "Honest reading" bullet reworded to Series-D-only recall with an explicit no-delta disclaimer.
2. `docs/residual-risk-drift-hypotheses.md` — the C-vs-D table relabeled (Series C column = "archival, not a baseline"; non-engagement rows tagged "D-only diagnostic"; "Reading" no longer says recall "improved").

Both re-verified **CLEARED** by the skeptic on fresh file read.

## Accepted gaps / residual risks

- **SD5→SD6 operator ACK** is durable only as a `state.json` note ("operator OK continue SD6-SD7") — no standalone ACK artifact. Accepted; operator re-confirmed by invoking SD-EXIT-GATE.
- **Fallback storm:** `fallback_flag_count=1084` fleet-wide (S2 victim path clean at 0) — documented in governance + residual.
- **Not CALIBRATED:** P≈0.011, FP=5432 — engagement success ≠ calibration.
- **Builder `_shadow_builds_during_block`** still filters wall `created_at` — deferred with Series C `shadow_ever=19` evidence; reopen if Series D fallback storm coincides with `active_shadow_count=0`.
- **C2 RED** is historical (cannot re-fail without reverting SD1) — mitigated by green C2 + SD3 regressions + captured red transcript.

## Constraint compliance

- No `config/scoring_config.yaml` changes (verified clean).
- No attestation param changes (code defaults; YAML hygiene deferred to separate S6.3).
- Series D treated as a new baseline; Series C artifacts preserved.

## Baseline of record

`docs/calibration_series_d_metrics.json` (Series D, seed 42, v2.2 @ thr=45) — **Not CALIBRATED**. Only permitted C→D claim: D4 engagement 0 → 12840.
