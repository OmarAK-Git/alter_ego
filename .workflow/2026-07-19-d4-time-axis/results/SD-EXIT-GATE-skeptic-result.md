# SD-EXIT-GATE — Skeptic Verification Result

**Run:** `.workflow/2026-07-19-d4-time-axis/` (D4 shadow-read time-axis fix)
**Verifier:** skeptic-verifier (model `cursor-grok-4.5-high`), chat_gate
**Date:** 2026-07-19
**Verdict:** ACCEPT-WITH-GAPS → **gaps remediated in-gate → re-verified CLEARED**

## Fresh evidence (this session)

| Check | Result | Artifact |
|---|---|---|
| `pytest -v --tb=short --ignore=tests/live` | **163 passed**, EXIT=0 | `results/exit-gate-fresh-verify.txt` (L443–444) |
| `ruff check .` | **All checks passed**, EXIT=0 | `results/SD-EXIT-ruff.txt` |

## Claims that survived adversarial review

- C2 RED→GREEN: `SD0-C2-red.txt` FAIL (promoted 0.0 vs shadow 3.0) → `SD1-C2-green.txt` PASS.
- `get_latest_shadow_profile` as-of on `data_window_end`; `created_at DESC` tie-break only (`worker/profile_store.py:67-71`).
- Blocked-shadow miss observable via `ProfileStore` only (no direct ORM in scorer): WARN + `drift_shadow_fallback:no_shadow` (`worker/scorer.py:574-591`; asserted `test_shadow_drift_under_block.py:264-282`).
- No `config/scoring_config.yaml` changes (git clean).
- Series D metrics honest: `calibrated: false`; INVALID cross-series P/R note.

## Blocking gaps found — and remediated in-gate

1. **Governance prohibited C→D recall framing** — `scoring-config-governance-series-d.md:76` said S2 recall "improved from Series C 0.0 to 0.714". **Fixed:** reworded to Series-D-only framing with explicit no-delta disclaimer. Re-verified **CLEARED**.
2. **Residual C↔D P/R table read as a comparison** — `residual-risk-drift-hypotheses.md` ~L149-160. **Fixed:** Series C column relabeled "archival, not a baseline"; non-engagement rows tagged "(D-only diagnostic)"; "Reading" no longer says recall "improved". Re-verified **CLEARED**.

Re-verification (same skeptic, fresh file read): both files **CLEARED** — only C→D comparison asserted is the D4 engagement count (0 → 12840).

## Accepted residual gaps (recorded, non-blocking)

- **SD5→SD6 operator ACK durability:** approval recorded only as `state.json:173` note ("operator OK continue SD6-SD7"), no separate ACK artifact. Accepted; operator re-confirmed by invoking SD-EXIT-GATE.
- **SD7-governance-result.md:33** self-attestation ("no illegal C→D P/R: Met yes") was inaccurate at SD7 time; the underlying docs are now compliant post-gate, so the assertion holds as of exit.
- **C2 RED is historical** (cannot re-fail without reverting SD1) — mitigated by green C2 + SD3 regressions + red transcript.

## Residual risks (must stay recorded)

1. `fallback_flag_count=1084` fleet-wide `drift_shadow_fallback:no_shadow` (S2 victim path clean at 0) — documented in governance §Honest reading + residual §Status.
2. Builder `_shadow_builds_during_block` still filters wall `created_at` — deferred with Series C `shadow_ever=19` evidence.
3. UI timeline still `created_at` (display-only, out of scope).
4. Precision low (P≈0.011, FP=5432) — **Not CALIBRATED**; engagement ≠ calibration.
