# S1-EXIT-GATE packet

**Type:** run_exit
**Model:** cursor-grok-4.6-high-fast (`in_session_grok`)
**Depends on:** S1-20 (verifier ACCEPT)

## Official commands
```
pytest -v --tb=short --ignore=tests/live
ruff check .
```

## Accept if
- Official commands green (or only the documented P0 residual: `test_precision_gate_disabled_does_not_change_containment_flag` vs Series I `precision_gate.enabled=true` — do not revert YAML)
- 15 IDs / 30 rows; pending only on the three allowed triples
- cap.no_n1_headline + use.demo_honesty both arms pass
- no usefulness claim; Series I calibrated: false
- no scoring_config.yaml edits; no /api/ingest; no Series J

Standing residual from P0: that precision_gate contract test is stale vs shipped YAML. Do not treat it as a Sprint 1 regression.
