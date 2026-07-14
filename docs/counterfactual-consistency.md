# Counterfactual Consistency Check (SPEC §10.2 / V3 §9)

**Status:** Satisfied in v1 (S5.10)

Counterfactuals are built deterministically from the top-K feature contributions by `contribution_score`. The LLM never generates counterfactual text; `build_top_k_counterfactuals` in `worker/explainer.py` is the single source of truth.

## Metric

**Counterfactual consistency** (SPEC §10.2): for each explanation, the `counterfactuals` list must:

1. Contain at most K entries (default K=3), ordered by descending `contribution_score`.
2. Bind each entry's `contribution_id` to a real contribution in the decision record.
3. Set `score_delta` equal to that contribution's `contribution_score`.
4. Embed the feature name and formatted score in `counterfactual_text`.

The pytest harness loads `tests/fixtures/counterfactual_corpus.json` and asserts these invariants for normal, fewer-than-K, and empty contribution cases. An integration test verifies `generate_explanation` attaches the same counterfactuals when the LLM path succeeds.

## Corpus cases

| Case ID | Scenario |
|---------|----------|
| `normal_top_k` | Five contributions; top-3 by score |
| `fewer_than_k` | Two contributions; all returned |
| `empty_contributions` | No contributions; empty list |

## How to re-run

From the repository root:

```bash
PYTHONPATH=. pytest tests/worker/test_counterfactual_consistency.py tests/worker/test_explainer.py -v --tb=short
```

Focused corpus harness only:

```bash
PYTHONPATH=. pytest tests/worker/test_counterfactual_consistency.py -v --tb=short
```

Lint:

```bash
ruff check worker/explainer.py tests/worker/test_counterfactual_consistency.py
```

## Architecture note

Counterfactual text is template-generated (`If {feature_name} had been within typical range, the score would have been {score:.2f} lower.`). This keeps counterfactuals auditable and independent of LLM variance. Claims and summary text remain LLM-generated (with validation and template fallback per §8.3).
