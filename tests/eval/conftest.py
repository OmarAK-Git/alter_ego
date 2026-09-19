from __future__ import annotations

import pytest


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "eval_kernel: Sprint 1 E2E kernel row (deterministic, no LLM)",
    )
