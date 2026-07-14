# Active Context

**Updated:** 2026-07-14

## Current focus

**T3 run:** `.workflow/2026-07-12-v1-portfolio-ready/` — **program drain complete**  
**Active sprint:** S6 (closed)  
**Next runnable:** none — all S0–S6 packets + gates `done`/`wontfix`  
**Phase honesty:** Phases 0–4 = Partial. **Not CALIBRATED.**

## S6 handoff artifacts

| Packet | Artifact | Verifier |
|---|---|---|
| S6.1 | `docs/hardening-sweep-checklist.md` | survives |
| S6.2 | `docs/residual-risk-drift-hypotheses.md` | survives |
| S6.3 | `OPS.md` standing rule (sweep + governance) | survives |
| S6-EXIT-GATE | `results/S6-EXIT-GATE-verifier-result.md` (pytest 121 + ruff + verify_run) | survives |

## Recent fixes (2026-07-14)

- Schema/ORM normalizer default aligned to `1.0-char-3gram-hash-128`
- `RealLLMProvider` Google path: **Vertex AI + ADC only** → default model `gemini-3.5-flash` (Agent Builder / AI Studio API-key path dropped)

## Decisions locked

- Hybrid C S2 residual; S3 knobs v2.2 @ thr=45 unchanged
- S5 Path A: compose-as-IaC; Path B: S5.11 cohort advanced gates deferred
- Autopilot models: implement `composer-2.5`, verify `cursor-grok-4.5-high`
- No weight/threshold change without checklist sweep + governance record

## Resume / operator next

Program queue is drained — no autopilot-runnable packets remain. Remaining items are operator-owned, outside the queue:

1. Human drift research: `docs/residual-risk-drift-hypotheses.md` + optional re-sweep via `docs/hardening-sweep-checklist.md`
2. ~~Empirical S5.7~~ — **done** 2026-07-14 (`docs/llm-determinism-check.md`: 4 unique hashes / 10 runs @ temp=0)
