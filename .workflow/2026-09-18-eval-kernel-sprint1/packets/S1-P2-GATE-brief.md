# S1-P2-GATE packet

**Type:** phase_exit (capability rows)
**Depends on:** S1-17, S1-18, S1-19 (all verifier ACCEPT)
**Model:** cursor-grok-4.6-high-fast (`in_session_grok`)

## Official commands
```
pytest tests/eval/test_cap_attributed_s2_s3_s5.py tests/eval/test_cap_drift_vs_point_axes.py tests/eval/test_cap_no_n1_headline.py -v --tb=short
ruff check .
```

## Accept if
- Official pytest all pass
- ruff clean
- pending remains only on allowed quality/sanctuary new_build triples; `cap.no_n1_headline` both arms pass
- no usefulness claim; Series I remains calibrated: false
- no scoring_config.yaml edits
