# Autopilot loop stop report

**Invocation:** `/gsd-autopilot-loop` (no flags — drain runnable)  
**When:** 2026-07-14  
**Canonical state:** `.workflow/2026-07-12-v1-portfolio-ready/state.json`  
(Note: `.workflow/autopilot-queue.json` is not present; packets in `state.json` are the queue — packet mode.)

## Stop condition

**Queue empty / all remaining items done** — the single runnable item this run
was `S6-EXIT-GATE` (chat_gate program closeout). It was drained inline and set
`done` with verifier evidence. No `ready`/`pending`/`retry` packets remain.

## Completed this run

| ID | Evidence | Checks |
|---|---|---|
| S6-EXIT-GATE | `results/S6-EXIT-GATE-verifier-result.md` | pytest **121 passed**, ruff **clean**, `verify_run.py` **ok** |

Gate run mode: `chat_gate` — inline, UI-selected model. No mid-loop
`skeptic-verifier` / `composer-2.5` dispatched (per orchestration rule for
exit gates).

## Blocked / human_needed

None.

## Dependency-waiting

None.

## Next runnable

**None.** All S0–S6 packets + all EXIT-GATEs + HUMAN-DRIFT-RESEARCH are
`done` (S3.3 `wontfix` with reason). Program drain complete.

## Last verified item checks (S6-EXIT-GATE)

- `python -m pytest -v --tb=short --ignore=tests/live` → 121 passed, 0 failed (warnings deprecation-only).
- `python -m ruff check .` → All checks passed.
- `verify_run.py --run-dir .workflow/2026-07-12-v1-portfolio-ready` → ok.
- S6.1–S6.3 verifier evidence present; S6 docs carry explicit "not CALIBRATED" banners (no false claims).
- S5 residual (stale `DEFAULT_EMBEDDING_INPUT_NORMALIZER_VERSION`) resolved — default aligned to `1.0-char-3gram-hash-128`, covered by `tests/test_embedding_defaults.py`.

## Program honesty snapshot

- Phases 0–4 = **Partial. Not CALIBRATED.** Global precision ~1.9%, 3448 FP, 15 S3 FN @ `anomaly_threshold=45`.
- Explicit deferrals: S5.2 Path A (compose-as-IaC), S5.11 Path B (§7.3 cohort gates), S5.7 empirical LLM check pending API keys.

## Operator follow-ons (outside the queue)

1. Human drift research via `docs/residual-risk-drift-hypotheses.md`; re-sweep via `docs/hardening-sweep-checklist.md`.
2. `python scripts/llm_determinism_check.py` with `GOOGLE_API_KEY` (optional `GOOGLE_CLOUD_PROJECT`) for the S5.7 empirical artifact.
