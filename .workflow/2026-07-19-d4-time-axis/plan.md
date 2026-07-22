# D4 Time-Axis fix + Series D re-sweep — 2026-07-19

**Tier:** T3  
**Canonical state:** `.workflow/2026-07-19-d4-time-axis/state.json`  
**Design:** `docs/superpowers/specs/2026-07-19-d4-time-axis-design.md`  
**Detailed plan:** `docs/superpowers/plans/2026-07-19-d4-time-axis.md`  
**Prior:** `.workflow/2026-07-19-series-c/` (D4 engagement = 0; diagnose `scratch/diagnose_d4_engagement.py`)

## Goal

Fix the shadow-read time axis so D4 actually engages under sim-time eval, make blocked shadow-miss observable, harden C2 + regression tests, redefine `promotion_coverage` (N=5 in-window), then (after hard gate) run Series D as a new baseline.

## Success Criteria

- Fix shadow lookup: as-of on `data_window_end`; secondary `created_at DESC` tie-break; `count_shadow_profiles`
- profile_store audit lists axes; `promoted_at` = builder `as_of`; Series C `shadow_ever=19` evidence for builder deferral
- Blocked miss → WARN + `drift_shadow_fallback:no_shadow` via ProfileStore count
- C2 red-before-green on real seam (distinct versions); future-`created_at` + tie-break regression green
- Dual coverage metrics (`ever` + `in_window` N=5) with serving-profile axis verified
- **Hard gate:** SD0–SD4 + SD5-REVIEW-GATE before SD6
- Series D (post-approval): seed 42, v2.2 @ thr=45; engagement 0→nonzero; governance

## Constraints

- No detection knob / attestation param / YAML writes this packet
- Attestation YAML hygiene = separate S6.3 (zero behavioral diff)
- Series D new baseline; only C→D claim = `drift_source_profile_version` engagement
- UAW T3 GSD-style loop: researcher → implementer → test-runner → skeptic-verifier

## Risks

| Risk | Approval | Mitigation |
|---|---|---|
| Builder still filters block-era shadows by `created_at` | no | SD1 audit lists adjacent seam; follow-on if needed |
| Series D before items 1–5 review | **yes** | SD6 `blocked`; SD5 chat_gate STOP |
| False CALIBRATED from engagement-only | no | Not CALIBRATED default; no illegal C→D P/R |

## Work Packets

| ID | Objective | Write scope | Status |
|---|---|---|---|
| SD0 | C2 seam rewrite + red evidence (no fix) | `tests/worker/test_shadow_drift_under_block.py`, `results/SD0-C2-red.txt` | ready |
| SD1 | Fix shadow lookup time axis + audit | `worker/profile_store.py`, audit md | pending |
| SD2 | No silent fallback (WARN + flag) | `worker/scorer.py`, tests | pending |
| SD3 | Wall-future `created_at` regression | tests | pending |
| SD4 | Dual promotion_coverage N=5 + harness skeleton | `scratch/run_series_d_sweep.py`, metric tests | pending |
| SD5-REVIEW-GATE | Fresh verify + STOP | `results/SD5-items-1-5-summary.md` | pending |
| SD6 | Series D seed-42 sweep | metrics JSON | **blocked** |
| SD7 | Series D governance + residual | docs | **blocked** |
| SD-EXIT-GATE | pytest + ruff + skeptic | results | **blocked** |

## Autopilot (UAW / GSD-style)

| Role | Agent |
|---|---|
| Research | `researcher` |
| Implement | `implementer` |
| Test | `test-runner` |
| Verify | `skeptic-verifier` |

Prefer implement `composer-2.5`, verify `cursor-grok-4.5-high` when dispatching via Task tool.

**Next runnable:** `SD0`  
**Stop before:** `SD6` (requires operator approval after `SD5-REVIEW-GATE`)

## Requirement Traceability

| Req | AC | Packet | Verification |
|---|---|---|---|
| REQ-SIMTIME | Shadow as-of by `data_window_end`; `created_at` tie-break only | SD1 | C2 green + audit |
| REQ-TIEBREAK | Equal `data_window_end` → later `created_at` | SD1, SD3 | unit |
| REQ-PROMAT | `promoted_at` axis verified safe for in-window metric | SD1 audit, SD4 | audit + metric tests |
| REQ-C2SEAM | C2 fails on pre-fix main, passes after; versions differ | SD0→SD1 | red/green evidence files |
| REQ-NOSILENT | WARN + fallback flag; count via ProfileStore | SD2 | unit + log assert |
| REQ-REGRESS | Future wall `created_at` still found | SD3 | unit |
| REQ-COVERAGE | Dual metrics; N=5; Series C cited; missing-profile tracked | SD4 | metric unit tests |
| REQ-GATE | No Series D before review | SD5-REVIEW-GATE | chat_gate |
| REQ-SERIESD | Sweep + engagement nonzero | SD6–SD7 | sweep artifact + skeptic |

## Verification

- Per-packet focused pytest named in packet result
- SD5: focused suite + ruff on touched files
- Exit (post-SD6): `pytest -v --tb=short --ignore=tests/live` + `ruff check .`
- Optional: `python <ultimate-agentic-workflow>/scripts/verify_run.py --run-dir .workflow/2026-07-19-d4-time-axis`
