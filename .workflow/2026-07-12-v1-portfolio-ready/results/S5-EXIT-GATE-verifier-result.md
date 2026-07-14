# S5-EXIT-GATE — verifier result

**Packet:** `S5-EXIT-GATE` (`gate:S5-exit | chat_gate | phase_exit | req:REQ-S5`)
**Run mode:** `chat_gate` — inline in current chat, UI-selected model (Opus 4.8). No mid-loop `skeptic-verifier` / `composer-2.5` dispatched.
**When:** 2026-07-13
**Canonical state:** `.workflow/2026-07-12-v1-portfolio-ready/state.json`

## Verdict: **survives** (gate PASS — S6 unlocked)

Gate passes on fresh evidence, but only *after* catching and fixing a real
cross-packet regression that the per-packet S5.9 verifier missed (it ran only
its focused 7/7 subset, not the full suite). This is exactly what the exit gate
exists to catch.

## Verification (`scope: phase_exit`)

Both required commands run fresh this session (sandbox disabled; PowerShell has
no `tail`, so full output was captured directly):

| Command | Result |
|---|---|
| `python -m pytest -v --tb=short --ignore=tests/live` | **116 passed**, 0 failed, 117 warnings (deprecation-only), exit 0 |
| `python -m ruff check .` | **All checks passed!** exit 0 |

First full-suite run this session was **1 failed, 115 passed** — see regression below.

## Regression caught and fixed at the gate

**Failure:** `tests/test_spec_alignment.py::test_new_confidence_calculation`
`AssertionError: assert 0.2 < 1e-06` — expected confidence `0.8` (formula
`n/(n+k)=40/50`), got `1.0`.

**Root cause (systematic-debugging, not guesswork):** S5.9's
`embedding_metadata_mismatch_halt` (`worker/scorer.py:408-413`) halts scoring
when a profile's embedding metadata disagrees with the shipped runtime
vectorizer contract. The failing decision carried flags
`['embedding_metadata_mismatch_halt',
'embedding_mismatch_embedding_input_normalizer_version:1.0!=1.0-char-3gram-hash-128']`.

The confidence-formula test (authored in S2.4, pre-S5.9) constructs a
hand-built `ProfileArtifact` that inherits the schema default
`DEFAULT_EMBEDDING_INPUT_NORMALIZER_VERSION = "1.0"`
(`core/schemas/profiles.py:8`). S5.9's runtime contract expects the vectorizer
value `NORMALIZER_VERSION = "1.0-char-3gram-hash-128"`
(`worker/vectorizer.py:6`). Mismatch → fail-closed halt → the confidence path
never runs, so `confidence` is the halt sentinel `1.0` instead of `0.8`.

**Not a production bug.** Real profiles are always created by
`batch/profile_builder/builder.py:451`, which sets
`embedding_input_normalizer_version=NORMALIZER_VERSION` explicitly. The stale
`"1.0"` default is only reachable by hand-constructed test profiles. S5.9
*intentionally* treats `"1.0"` as a mismatch value — see
`tests/worker/test_embedding_metadata_mismatch.py:130`
(`test_normalizer_version_mismatch_halts_scoring` passes `"1.0"` as the example
mismatched value). The halt is the correct, fail-closed behavior.

**Fix (minimal, test-only, in gate scope):** updated the stale fixture in
`tests/test_spec_alignment.py` to declare runtime-matching embedding metadata
(`embedding_input_normalizer_version=NORMALIZER_VERSION` on both profiles),
so the test exercises its intended confidence-formula path instead of being
accidentally short-circuited. No product code, schema, or scoring config
touched — no governance-relevant change. Post-fix: full suite 116/116 green.

## Acceptance checklist (from packet)

1. **All S5.1–S5.12 have verifier `survives` evidence under `results/`.** PASS —
   12/12 verifier result files present, each with verdict `survives`
   (S5.1–S5.12; grepped verdict lines).
2. **Fresh pytest (ignore live) green.** PASS — 116 passed after regression fix.
3. **Fresh `ruff check .` clean.** PASS — All checks passed.
4. **Portfolio honesty — Phase 4 / SPEC_V3 §9 gates shipped or explicitly
   Path-B deferred.** PASS —
   - S5.2 Path A: compose-as-IaC recorded (SPEC/docs aligned).
   - S5.11 Path B: §7.3 cohort-prior defer banner present, root SPEC synced.
   - S5.7: `RealLLMProvider` harness on disk; empirical run honestly marked
     "not executed until API keys" (`README.md:66`,
     `docs/llm-determinism-check.md`). Harness exists — requirement met.
   - S4.3 aging/jitter deferral (Path B) surfaced in README Phase 3 row.
5. **No false CALIBRATED / 100% recall claims.** PASS — grep across `*.md`:
   every `CALIBRATED` hit is a negation ("not CALIBRATED") or historical
   context; README badge is `Phase 0-4 Partial | not CALIBRATED`; SPEC.md
   header and README metrics report `P≈0.019, R≈0.817, FP=3448 — not
   CALIBRATED`. "Recall 1.0" appears only as evidence-backed per-scenario
   (S1/S2/S4 slow-roll) metrics from `docs/calibration_final_metrics.json`,
   not as a global/perfect-recall claim.
6. **Write this result file.** DONE.
7. **On pass: packet `status: done` + evidence; S6.* `ready`, clear
   `blocked_by`.** DONE (state.json updated).

## Residual (not verdict-changing; route to S6 hardening)

- **Stale schema default:** `DEFAULT_EMBEDDING_INPUT_NORMALIZER_VERSION = "1.0"`
  (`core/schemas/profiles.py:8`) and the mirrored ORM default
  (`core/models.py:58-59`) do not match the runtime
  `NORMALIZER_VERSION = "1.0-char-3gram-hash-128"`. Any `ProfileArtifact` /
  `ProfileArtifactModel` inserted *without* an explicit normalizer version will
  fail-closed halt at scoring. Production is safe (builder always sets it), and
  fail-closed is the safe direction, but the default is a latent trap. Aligning
  the default belongs in its own change (touches `core/`), not an exit gate —
  recommend tracking under S6 governance/hardening.

## Notes on environment

Shell sandbox was intermittently returning "no exit status" for
non-allowlisted commands this session (same failure mode recorded in the S5.7
verifier result). Verification commands were run with the sandbox disabled via
`python -m pytest` / `python -m ruff` and completed with real exit codes and
full output captured above.
