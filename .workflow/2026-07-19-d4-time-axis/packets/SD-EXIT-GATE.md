# Packet SD-EXIT-GATE — verifier / chat_gate (BLOCKED)

**label:** `sprint:SD|gate`  
**depends_on:** SD7  
**status:** blocked  
**verification_model:** cursor-grok-4.5-high  
**gate_run_mode:** chat_gate

## Objective

Close the run: full pytest (ignore live) + ruff + skeptic. Sync memory-bank. Write `final-report.md`.

## Verify

```bash
PYTHONPATH=. pytest -v --tb=short --ignore=tests/live
ruff check .
```

Optional: `python <ultimate-agentic-workflow>/scripts/verify_run.py --run-dir .workflow/2026-07-19-d4-time-axis`

## Exit decision

`ACCEPT` / `ACCEPT-WITH-GAPS` / `REJECT` with explicit Not CALIBRATED unless evidence earns otherwise.
