import threading
import time
from unittest.mock import patch

import pytest
import requests
import uvicorn

# Module-level mark so default collection skips these unless ``--live``.
pytestmark = pytest.mark.live


def run_server():
    # Run the uvicorn server in a daemon thread on port 8000
    uvicorn.run("web.api:app", host="127.0.0.1", port=8000, log_level="error")


@pytest.fixture(scope="session", autouse=True)
def start_live_server(pytestconfig):
    if not pytestconfig.getoption("--live"):
        pytest.skip(
            "Live smoke tests are opt-in (need :8000). Re-run with: pytest --live tests/live -v"
        )

    thread = threading.Thread(target=run_server, daemon=True)
    thread.start()

    # Wait for the server to become responsive
    url = "http://127.0.0.1:8000/api/alerts"
    for _ in range(50):
        try:
            requests.get(url, timeout=1)
            break
        except requests.exceptions.ConnectionError:
            time.sleep(0.1)
    else:
        pytest.skip(
            "Could not bind/reach 127.0.0.1:8000 "
            "(port busy, reserved, or permission denied). "
            "Stop other uvicorn/demo processes and retry: pytest --live tests/live -v"
        )
    yield


@pytest.fixture(scope="session", autouse=True)
def mock_interactive_input(pytestconfig):
    if not pytestconfig.getoption("--live"):
        yield
        return
    # Stub builtins.input so staged interactive tests run without blocking
    with patch("builtins.input", return_value=""):
        yield
