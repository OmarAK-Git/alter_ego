# LLM Determinism Check (section 8.4)

**Status:** Executed

**Date:** 2026-07-14T05:23:04.323147+00:00
**Model ID:** gemini-3.5-flash
**Provider:** google
**Vertex project:** `gdg-yorku` (location `global`)
**Temperature:** 0.0
**Prompt:** `Explain why logging in from a new geolocation at 3 AM is suspicious, given the user has never done this before. Keep it to two sentences.`

## Results

| Run | Output Hash | Output Length |
|-----|-------------|---------------|
| 1 | `1d36a7d8512a0c09565baa5b647b3118f687df905a629fecd92e99236a0345cc` | 392 |
| 2 | `193efce25e18adf0dc1f8b852ab376904b2d4cb3043323052a481f8d49ec050c` | 318 |
| 3 | `401e9cc75db9ac344986bd73903271e96a6a65660e42446c6691356a39084c1b` | 403 |
| 4 | `1d36a7d8512a0c09565baa5b647b3118f687df905a629fecd92e99236a0345cc` | 392 |
| 5 | `401e9cc75db9ac344986bd73903271e96a6a65660e42446c6691356a39084c1b` | 403 |
| 6 | `1d36a7d8512a0c09565baa5b647b3118f687df905a629fecd92e99236a0345cc` | 392 |
| 7 | `6a5f24487d9872de24dcd63d466baa0dce14d337592a517aa863f9845f6b4b59` | 316 |
| 8 | `401e9cc75db9ac344986bd73903271e96a6a65660e42446c6691356a39084c1b` | 403 |
| 9 | `1d36a7d8512a0c09565baa5b647b3118f687df905a629fecd92e99236a0345cc` | 392 |
| 10 | `1d36a7d8512a0c09565baa5b647b3118f687df905a629fecd92e99236a0345cc` | 392 |

## Conclusion

The provider **is NOT** byte-identical deterministic. Observed 4 unique outputs across 10 runs.
> **Note**: This confirms the architectural decision in section 8.4: lineage is the single authoritative record, and the system must not rely on provider reproducibility.

## How to re-run

From the repository root (with `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, or Vertex ADC configured):

```bash
python scripts/llm_determinism_check.py
```

Provider precedence matches `worker/explainer.py`:
1. `ANTHROPIC_API_KEY` -> `claude-3-haiku-20240307`
2. `OPENAI_API_KEY` -> `gpt-4o-mini`
3. Vertex AI (`GOOGLE_CLOUD_PROJECT` or ADC project) -> `gemini-3.5-flash` (override with `GOOGLE_MODEL_ID`; location via `GOOGLE_CLOUD_LOCATION`, default `global`). Requires `pip install google-auth` and `gcloud auth application-default login`.

All model IDs are pinned, non-alias identifiers (no `-latest` suffixes).

## Architecture note (lineage vs provider determinism)

Regardless of whether this check finds byte-identical outputs, section 8.4 treats the **immutable explanation lineage record** (prompt, response, model id, timestamp) as the single authoritative record. The explainer caches by deviation-object-hash; re-invoking the LLM to verify a prior explanation is prohibited. Temperature=0 reduces variance but does not guarantee bit-identical inference across runs.
