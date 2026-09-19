# S1-20 implement / review / verify packet

**Task:** GitHub Actions + suite completeness
**Plan:** Task 20 (~2831–2993)
**Claim:** GHA owns the 15-ID deterministic suite. `evaluate_all` emits 30 rows. CLI `--assert-complete` exits 0. pending only on the three allowed triples. `tests/live` stays skipped.

## Controller
```
pytest tests/eval/test_suite_completeness.py -v --tb=short
ruff check batch/eval/e2e_kernel.py tests/eval/test_suite_completeness.py tests/eval/test_e2e_kernel.py
```

CLI (slow): `python -m batch.eval.e2e_kernel --scorecard-out artifacts/eval-kernel-scorecard.jsonl --assert-complete` exit 0.

## Commit
`Give GitHub Actions ownership of the 15-ID eval kernel suite`
