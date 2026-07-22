# Packet SD5-REVIEW-GATE — verifier / chat_gate

**label:** `sprint:SD|gate|items-1-5-stop`  
**depends_on:** SD0, SD1, SD2, SD3, SD4  
**verification_model:** cursor-grok-4.5-high  
**gate_run_mode:** chat_gate

## Objective

Fresh verification of items 1–5. Produce operator-facing summary. **STOP** — do not start SD6.

## Write scope

- `.workflow/2026-07-19-d4-time-axis/results/SD5-items-1-5-summary.md`
- Update `state.json`: SD5-REVIEW-GATE → `ready_for_review` (or `done` after operator ACK); SD6 remains `blocked`
- Result: `results/SD5-REVIEW-GATE-verifier-result.md`

## ACs

1. Fresh:

```bash
PYTHONPATH=. pytest tests/worker/test_shadow_drift_under_block.py tests/batch/test_promotion_coverage_metrics.py -v --tb=short
ruff check worker/profile_store.py worker/scorer.py tests/worker/test_shadow_drift_under_block.py
```

2. Summary lists: C2 red/green evidence paths; profile_store audit verdict; fallback flag name; N=5; confirmation **no YAML writes**; confirmation **Series D not run**.
3. Autopilot must not dispatch SD6 until operator explicitly approves.

## Exit decision

- `ACCEPT` / `ACCEPT-WITH-GAPS` / `REJECT` for items 1–5 only.
- Next packet after approval: SD6.
