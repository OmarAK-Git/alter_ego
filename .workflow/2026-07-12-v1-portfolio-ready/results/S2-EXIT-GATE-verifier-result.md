# S2-EXIT-GATE — Sprint Close Verifier Result

**Verdict: `survives`**

**Invocation:** `/gsd-autopilot-loop S2-EXIT-GATE` (chat_gate / `verification.scope: phase_exit`)
**Run:** 2026-07-13, UI-selected Opus inline + fresh-context skeptic-verifier (`cursor-grok-4.5-high`, readonly)

## Claim under test

> All S2 packets (S2.1–S2.8) are genuinely `done` with real evidence; the fixes are honest
> (no fake CALIBRATED claims, no overstated recall, no silent spec forks); S2 is safe to close
> so S3 can be unlocked.

## Evidence gathered (fresh, 2026-07-13)

### pytest — PASS

```
python -m pytest -v --tb=short --ignore=tests/live
=> 69 passed, 40 warnings in 3.42s
```

### ruff — PASS

```
python -m ruff check .
=> All checks passed!
```

### Fresh-context skeptic-verifier — `survives`

Adversarial review spot-checked source (not just result docs) for each packet:

| Packet | Confirmation |
|---|---|
| S2.1 | `collide::`/`split::` → conf `0.3` (`worker/resolver.py:33-40`); scorer flag `:263-264`; asserts in `tests/worker/test_resolution_confidence_flags.py` (soft path mismatch vs state.json label, evidence real) |
| S2.2 | `tests/worker/test_evidence_binding.py:121-160` reconstructs Σ contributions vs `decision.score`; damped path forces `sum > cap` |
| S2.3 | `compute_decision_id` hashes `scorer_algorithm_version` + `embedding_model_version` (`worker/scorer.py:28-51`, `:455-460`); `DecisionRecord.embedding_model_version` at `core/schemas/decisions.py:28` |
| S2.4 | YAML `confidence_k: 10.0`; `n/(n+confidence_k)` at `worker/scorer.py:428-429`; `tests/worker/test_confidence.py` |
| S2.5 | Fork Path B: SPEC_V3 embeds `cohort_data`; independent frozen artifacts deferred (`docs/SPEC_V3.md`) |
| S2.6 | Scorer hard-zeros volume + `volume_delta_deferred` (`worker/scorer.py:376-380`); README deferred footnote; YAML weight reserved w/ defer comment |
| S2.7 | Fork Path B deferral banner (`docs/SPEC.md:174`); root↔docs SPEC byte-identical (sha `446e3c0cd918ca7f`); no `lifecycle_state` in worker/batch |
| S2.8 | No `decay_lambdas` in YAML; inventory 28/0/7/0 in `OPS.md` / `progress.md`; §6.8 notes removal |

## Residual honesty debt (non-decisive for S2 close — owned by S3.5)

1. `docs/phase2-audit-result.md:4` still says `CALIBRATED (Audit Grade)` and claims `decay_lambdas` implemented — historical audit; **S3.5** owns the scrub.
2. SPEC §6.8 title/body still say "Calibrated Parameters (Audit Grade)" while header correctly says Phase 2A / S2 recall 0.0 — known S0→**S3.5** debt, not a silent S2 fork.
3. `README.md:66` Phase 1 row stale ("geo not profiled… containment queue manual") vs S1.2/S1.3 — portfolio-facing drift, not S2 write-scope.
4. `core/schemas/config.py` lacks `confidence_k` typed field (runtime reads raw YAML dict) — noted in S2.4.

No S2 weight/threshold gaming found; config stays v2.2 operating point.

## Recommendation

Mark **S2-EXIT-GATE** `done`. Set **active_sprint** to **S3**. Mark **S3.1** `ready` (first S3 packet).
Carry residuals #1/#2 explicitly into **S3.5** (SPEC/phase2 honesty scrub).
