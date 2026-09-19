# S1-19 review / verify packet

**Task:** `cap.no_n1_headline`
**Claim:** `format_capability_headline` refuses S1/S4-only; both arms pass with `n1_headline_rejected` True; live headline includes S2+S3+S5.

Controller: `pytest tests/eval/test_cap_no_n1_headline.py -v --tb=short` → 3 passed; ruff clean.
