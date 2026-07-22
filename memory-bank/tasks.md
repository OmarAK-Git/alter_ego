# Tasks

**Canonical T3 state:** `.workflow/2026-07-19-d4-time-axis/state.json`

## Autopilot

**Active sprint:** SD (D4 time-axis + Series D)  
**Next runnable:** `SD-EXIT-GATE` — **blocked** (operator stop-before-gate)  
**Stop before:** `SD-EXIT-GATE`  
**Design status:** executing; SD0–SD7 done

## In queue

- [x] **SD0** — C2 red-first (seam rewrite; no fix)
- [x] **SD1** — Fix `get_latest_shadow_profile` sim-time axis + audit
- [x] **SD2** — No silent fallback (WARN + flag)
- [x] **SD3** — Future-`created_at` regression
- [x] **SD4** — Dual `promotion_coverage` (N=5) + Series D harness skeleton
- [x] **SD5-REVIEW-GATE** — items 1–5 STOP — **ready_for_review** (ACCEPT-WITH-GAPS)
- [x] **SD6** — Series D sweep (DONE_WITH_CONCERNS; Not CALIBRATED)
- [x] **SD7** — Series D governance
- [ ] **SD-EXIT-GATE** — (**blocked** — operator stop-before-gate)

## Later (operator / separate)

- [ ] Attestation YAML hygiene S6.3 (zero behavioral diff; out of this packet)

## Prior drained

- Series C — `.workflow/2026-07-19-series-c/` EXIT ACCEPT-WITH-GAPS; Not CALIBRATED
- S55 R-INTERLOCK — drained
- V1 portfolio-ready — drained
