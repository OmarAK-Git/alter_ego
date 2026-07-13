# S0 Sprint-Close — Skeptic-Verifier Result

**Verdict:** `survives`

**Date:** 2026-07-12
**Scope:** Sprint close for S0 (all packets S0.1–S0.5), not a single packet.
**Stance:** Per-packet verifier reports and implementer transcripts treated as unevidenced. All evidence re-gathered by direct read of product docs, `state.json`, and authoritative metrics.

## Claim under test

"S0 sprint is complete and honest enough to unlock S1" — i.e. the overclaim demotion, embedding-narrative lock, YAML-knob inventory, and phase-label alignment are all actually landed in the product docs, backed by surviving verifier evidence, and reflected in canonical state.

## Check 1 — All five verifier results exist and say `survives`

| Packet | File | Verdict line |
|---|---|---|
| S0.1 | `results/S0.1-verifier-result.md` | `## Verdict: survives` (L3) |
| S0.2 | `results/S0.2-verifier-result.md` | `**Verdict:** survives` (L3) |
| S0.3 | `results/S0.3-verifier-result.md` | `**Verdict: survives**` (L3) |
| S0.4 | `results/S0.4-verifier-result.md` | `**Verdict: SURVIVES**` (L3) |
| S0.5 | `results/S0.5-verifier-result.md` | `**Verdict:** survives` (L3) |

All five exist and are `survives`. PASS.

## Check 2 — Independent doc spot-checks (did NOT trust the reports)

- **SPEC.md header** (`docs/SPEC.md:3,6,8`): `Status: Phase 2A — Partial (residual risk; S2 recall 0.0)`; `Version: 2.2 — interim operating point ... (Phase 2 not closed)`; metrics-authority pointer to `progress.md` + `calibration_final_metrics.json` with recall ~0.42 / S1,S3,S4=1.0 / S2=0.0. No `CALIBRATED (Audit Grade)` in header. PASS.
- **phase1-audit Final Status** (`docs/phase1-audit-results.md:13-28`): Phase 1 hardening `CLOSED` (scoped); Phase 2 calibration `Partial (Phase 2A) — not a full calibration pass`; metrics table matches JSON (P=1.0, recall ~0.42 = 5 TP/7 FN, S2=0.0); explicit "does not imply Phase 2 is calibrated". No 100%/perfect-recall claim. PASS.
- **README phase map** (`README.md:62-68`): Phases 0/1/3 `Partial`, 2 `Partial (Phase 2A)` with S2 recall 0.0, 4 `Open`. Status badge `Phase 0-3 Partial | v1 in progress`. PASS.
- **SPEC_V3 embedding narrative** (`docs/SPEC_V3.md:97,213`): shipping = 128-d char 3-gram SHA-256 `alter-ego-ngram-v1`, "not semantic BERT"; both `nomic`/`768` hits are explicitly labeled deferred/abandoned debt with "do not describe nomic as current runtime." Grep for `nomic|768|BERT` returns only these two qualified hits. PASS.
- **progress.md inventory** (`memory-bank/progress.md:172-255`): "Scoring config knob inventory (2026-07-12)" with wired/wire/defer/delete labels, per-knob code-path evidence, and summary counts (25 wired / 5 wire / 5 defer / 2 delete). Load-bearing knobs (`total_volume_delta` always 0, `geolocation_rarity` weight-read but histograms not built, `decay_lambdas.*` orphan) classified consistent with code. PASS.

## Check 3 — state.json S0.* statuses (read file)

`state.json` packets S0.1–S0.5 all `"status": "done"` with `evidence` pointing at their respective verifier-result files (L59–108). `active_sprint: "S0"`. S1.1 is `ready`; all other S1+ `pending` — consistent with "one sprint at a time" and readiness to unlock S1. PASS.

## Attempts to refute (all failed)

1. Re-derived each doc claim from the files themselves rather than the reports — every quantitative claim (recall 0.42, S2 0.0, P=1.0) is faithful to `docs/calibration_final_metrics.json`; no stale numbers.
2. Grepped for lingering overclaims (`CALIBRATED`/`100%`/perfect recall / nomic-as-runtime) in the demoted docs — none in scope; only a `§6.8 Audit Grade` string in SPEC.md that S0.1 explicitly scoped out (header-only), not a sprint-close blocker.
3. Checked state.json didn't silently mark packets done without evidence — each `done` packet carries an evidence pointer to an existing, `survives` verifier file.
4. Checked internal consistency of the knob inventory counts and classifications against code — matches; no gamed/glossed classification found.

## Residual notes (do not block S0, flag for S1+)

- S0 is a docs/inventory-only sprint (no code diff), so the plan's stop-gate `pytest`/`ruff` was not exercised here and remains `pending` in `state.json` verification block; that gate is load-bearing at code-touching sprint closes (S1+), not this one.
- SPEC.md §6.8 still contains legacy `CALIBRATED (Audit Grade)` language. Out of S0.1 scope by design, but it should be reconciled by S3.5 so the body doesn't reintroduce the overclaim the header removed.

## Strongest reason it survives

Every S0 acceptance criterion is verifiable directly in the shipped product docs (not just the reports): the SPEC/README/audit headers all say Phase 2A / Partial with S2 recall 0.0, the embedding narrative is locked to `alter-ego-ngram-v1`/128-d with nomic bounded as debt, the YAML inventory exists with code-backed classifications, and `state.json` marks S0.1–S0.5 `done` with existing `survives` evidence. The docs are mutually consistent and faithful to `calibration_final_metrics.json`. S0 is complete and honest enough to unlock S1.
