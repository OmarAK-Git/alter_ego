#!/usr/bin/env python3
"""Empirical LLM determinism check (SPEC §8.4 / SPEC_V3 §9).

Sends the same prompt 10 times at temperature=0 to the pinned non-alias model
configured in worker.explainer.RealLLMProvider, hashes each response, and writes
docs/llm-determinism-check.md with the outcome.

Requires ANTHROPIC_API_KEY, OPENAI_API_KEY, or Vertex ADC
(GOOGLE_CLOUD_PROJECT + `gcloud auth application-default login`).
Optional: GOOGLE_CLOUD_LOCATION (default global), GOOGLE_MODEL_ID
(default gemini-3.5-flash).
"""

from __future__ import annotations

import hashlib
import sys
from datetime import datetime, timezone
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from worker.explainer import RealLLMProvider  # noqa: E402

DEFAULT_PROMPT = (
    "Explain why logging in from a new geolocation at 3 AM is suspicious, "
    "given the user has never done this before. Keep it to two sentences."
)
RUNS = 10
TEMPERATURE = 0.0
DOC_PATH = Path(__file__).resolve().parent.parent / "docs" / "llm-determinism-check.md"

_PINNED_MODELS = (
    "`claude-3-haiku-20240307` (Anthropic), "
    "`gpt-4o-mini` (OpenAI), or "
    "`gemini-3.5-flash` (Vertex AI via ADC)"
)


def _sha256_hex(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _write_how_to_section(f) -> None:
    f.write("## How to re-run\n\n")
    f.write(
        "From the repository root (with `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, or "
        "Vertex ADC configured):\n\n"
    )
    f.write("```bash\n")
    f.write("python scripts/llm_determinism_check.py\n")
    f.write("```\n\n")
    f.write("Provider precedence matches `worker/explainer.py`:\n")
    f.write("1. `ANTHROPIC_API_KEY` -> `claude-3-haiku-20240307`\n")
    f.write("2. `OPENAI_API_KEY` -> `gpt-4o-mini`\n")
    f.write(
        "3. Vertex AI (`GOOGLE_CLOUD_PROJECT` or ADC project) -> "
        "`gemini-3.5-flash` (override with `GOOGLE_MODEL_ID`; location via "
        "`GOOGLE_CLOUD_LOCATION`, default `global`). Requires "
        "`pip install google-auth` and `gcloud auth application-default login`.\n\n"
    )
    f.write("All model IDs are pinned, non-alias identifiers (no `-latest` suffixes).\n\n")
    f.write("## Architecture note (lineage vs provider determinism)\n\n")
    f.write(
        "Regardless of whether this check finds byte-identical outputs, section 8.4 "
        "treats the **immutable explanation lineage record** (prompt, response, model id, "
        "timestamp) as the single authoritative record. The explainer caches by "
        "deviation-object-hash; re-invoking the LLM to verify a prior explanation is "
        "prohibited. Temperature=0 reduces variance but does not guarantee bit-identical "
        "inference across runs.\n"
    )


def _write_not_executed_artifact(_provider: RealLLMProvider) -> None:
    now = datetime.now(timezone.utc).isoformat()
    DOC_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(DOC_PATH, "w", encoding="utf-8") as f:
        f.write("# LLM Determinism Check (section 8.4)\n\n")
        f.write("**Status:** Not executed -- awaiting credentials\n\n")
        f.write(f"**Date:** {now}\n")
        f.write(f"**Pinned model IDs:** {_PINNED_MODELS}\n")
        f.write(f"**Temperature:** {TEMPERATURE}\n")
        f.write(f"**Runs (planned):** {RUNS}\n")
        f.write(f"**Prompt:** `{DEFAULT_PROMPT}`\n\n")
        f.write("## Results\n\n")
        f.write(
            "No empirical run was performed. Set `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, "
            "or configure Vertex ADC (`GOOGLE_CLOUD_PROJECT` + "
            "`gcloud auth application-default login`) and re-run the script to populate "
            "hash results.\n\n"
        )
        f.write("## Conclusion\n\n")
        f.write(
            "**No empirical conclusion.** This artifact documents that the check has not "
            "yet been executed against a live provider.\n\n"
        )
        _write_how_to_section(f)


def _write_executed_artifact(
    provider: RealLLMProvider,
    results: list[dict],
    unique_hashes: set[str],
) -> None:
    now = datetime.now(timezone.utc).isoformat()
    is_deterministic = len(unique_hashes) == 1
    DOC_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(DOC_PATH, "w", encoding="utf-8") as f:
        f.write("# LLM Determinism Check (section 8.4)\n\n")
        f.write("**Status:** Executed\n\n")
        f.write(f"**Date:** {now}\n")
        f.write(f"**Model ID:** {provider.model_id}\n")
        f.write(f"**Provider:** {provider.provider_type}\n")
        if provider.provider_type == "google" and getattr(provider, "google_project", None):
            f.write(
                f"**Vertex project:** `{provider.google_project}` "
                f"(location `{provider.google_location}`)\n"
            )
        f.write(f"**Temperature:** {TEMPERATURE}\n")
        f.write(f"**Prompt:** `{DEFAULT_PROMPT}`\n\n")
        f.write("## Results\n\n")
        f.write("| Run | Output Hash | Output Length |\n")
        f.write("|-----|-------------|---------------|\n")
        for res in results:
            f.write(f"| {res['run']} | `{res['hash']}` | {res['length']} |\n")
        f.write("\n## Conclusion\n\n")
        if is_deterministic:
            f.write(
                "The provider **is** byte-identical deterministic across "
                f"{RUNS} runs at temperature=0 for this prompt.\n"
            )
        else:
            f.write(
                f"The provider **is NOT** byte-identical deterministic. Observed "
                f"{len(unique_hashes)} unique outputs across {RUNS} runs.\n"
            )
            f.write(
                "> **Note**: This confirms the architectural decision in section 8.4: lineage is "
                "the single authoritative record, and the system must not rely on provider "
                "reproducibility.\n"
            )
        f.write("\n")
        _write_how_to_section(f)


def run_determinism_check() -> int:
    provider = RealLLMProvider()

    if not provider.api_key or provider.provider_type is None:
        _write_not_executed_artifact(provider)
        print(
            "ERROR: No LLM credentials configured. Set ANTHROPIC_API_KEY, OPENAI_API_KEY, "
            "or GOOGLE_CLOUD_PROJECT with Application Default Credentials.",
            file=sys.stderr,
        )
        print(f"Wrote honest not-executed artifact to {DOC_PATH}", file=sys.stderr)
        return 1

    print(
        f"Running LLM determinism check for {provider.model_id} "
        f"({provider.provider_type}) at temperature={TEMPERATURE}..."
    )

    results: list[dict] = []
    unique_hashes: set[str] = set()

    for i in range(RUNS):
        response = provider.generate(DEFAULT_PROMPT, temperature=TEMPERATURE)
        resp_hash = _sha256_hex(response)
        unique_hashes.add(resp_hash)
        results.append({"run": i + 1, "hash": resp_hash, "length": len(response)})
        print(f"  run {i + 1}/{RUNS}: hash={resp_hash[:16]}... len={len(response)}")

    is_deterministic = len(unique_hashes) == 1
    _write_executed_artifact(provider, results, unique_hashes)
    print(
        f"Check complete. Is deterministic: {is_deterministic}. "
        f"Results saved to {DOC_PATH}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(run_determinism_check())
