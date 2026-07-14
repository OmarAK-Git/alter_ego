# Tasks

**Canonical T3 state:** `.workflow/2026-07-12-v1-portfolio-ready/state.json`

## Autopilot

**Next runnable:** none — program drained (all S0–S6 packets + gates `done`/`wontfix`)  
**Active sprint:** S6 (closed)

## Done

### S0–S4 + gates
- [x] S0–S4 + EXIT-GATEs + HUMAN-DRIFT-RESEARCH

### S5
- [x] S5.1–S5.12
- [x] **S5-EXIT-GATE** — chat_gate PASS; `results/S5-EXIT-GATE-verifier-result.md`

### S6
- [x] S6.1 — `docs/hardening-sweep-checklist.md`
- [x] S6.2 — `docs/residual-risk-drift-hypotheses.md`
- [x] S6.3 — OPS standing rule (sweep + governance)
- [x] Align `DEFAULT_EMBEDDING_INPUT_NORMALIZER_VERSION` with runtime (`1.0-char-3gram-hash-128`)
- [x] Google / Vertex provider path on `RealLLMProvider` (`GOOGLE_API_KEY`)
- [x] **S6-EXIT-GATE** — chat_gate PASS; pytest 121 + ruff clean + verify_run ok; `results/S6-EXIT-GATE-verifier-result.md`

## In queue

- none — program drain complete

## Later (operator)

- [ ] Human drift research → optional new sweep per checklist (`docs/residual-risk-drift-hypotheses.md`)
- [x] Empirical S5.7 LLM determinism — executed 2026-07-14 (Vertex `gemini-3.5-flash`); **not** byte-identical → lineage rule confirmed
