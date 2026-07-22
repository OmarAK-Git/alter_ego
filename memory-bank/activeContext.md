# Active Context

**Updated:** 2026-07-19

## Current focus

**T3:** `.workflow/2026-07-19-d4-time-axis/` — **CLOSED** 2026-07-19; SD0–SD7 + SD-EXIT-GATE complete  
**Design:** `docs/superpowers/specs/2026-07-19-d4-time-axis-design.md`  
**Plan:** `docs/superpowers/plans/2026-07-19-d4-time-axis.md`  
**Gate:** `SD-EXIT-GATE` — **ACCEPT-WITH-GAPS** (skeptic `cursor-grok-4.5-high`; pytest **163 passed**, ruff clean). In-gate fix: scrubbed prohibited C→D recall/P/R "improvement" framing from governance + residual docs (re-verified CLEARED). See `results/SD-EXIT-GATE-skeptic-result.md`.  
**Next:** none in this run — Series D is the current baseline (Not CALIBRATED).

## SD0–SD7 landed

- Shadow as-of on `data_window_end`; `created_at DESC` tie-break only
- Blocked miss: WARN + `drift_shadow_fallback:no_shadow` via `count_shadow_profiles`
- C2 red→green + wall-future/tie-break regressions
- Dual `promotion_coverage` (ever + in_window N=5)
- Series D sweep: D4 engagement **12840** (vs Series C **0**); S2 R=**0.714**; **Not CALIBRATED**
- Governance: `docs/scoring-config-governance-series-d.md`

## Run status

**SD-EXIT-GATE closed 2026-07-19** — ACCEPT-WITH-GAPS. Accepted residual: SD5→SD6 operator ACK durable only as `state.json` note; fallback storm (1084); P≈0.011/FP=5432 (Not CALIBRATED).

## Current baseline

**Series D:** `docs/calibration_series_d_metrics.json` — Not CALIBRATED. Only permitted C→D claim: D4 engagement 0→12840.

## Out of this packet

Attestation YAML hygiene — separate S6.3; acceptance = zero behavioral diff.
