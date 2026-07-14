"""Root pytest hooks."""

from __future__ import annotations

import pytest


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--live",
        action="store_true",
        default=False,
        help="Run optional live HTTP smoke tests (binds/uses 127.0.0.1:8000).",
    )


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "live: optional HTTP smoke against localhost:8000 (enable with --live)",
    )


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    if config.getoption("--live"):
        return
    skip_live = pytest.mark.skip(
        reason="live smoke opt-in; re-run with: pytest --live tests/live -v"
    )
    for item in items:
        if item.get_closest_marker("live") is not None:
            item.add_marker(skip_live)
