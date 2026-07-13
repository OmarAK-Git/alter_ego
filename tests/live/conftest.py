import threading
import time
import pytest
import uvicorn
import requests
from unittest.mock import patch

def run_server():
    # Run the uvicorn server in a daemon thread on port 8000
    uvicorn.run("web.api:app", host="127.0.0.1", port=8000, log_level="error")

@pytest.fixture(scope="session", autouse=True)
def start_live_server():
    thread = threading.Thread(target=run_server, daemon=True)
    thread.start()
    
    # Wait for the server to become responsive
    url = "http://127.0.0.1:8000/api/alerts"
    for _ in range(50):
        try:
            requests.get(url)
            break
        except requests.exceptions.ConnectionError:
            time.sleep(0.1)
    yield

@pytest.fixture(scope="session", autouse=True)
def mock_interactive_input():
    # Stub builtins.input so staged interactive tests run automatically without blocking or raising EOFError
    with patch("builtins.input", return_value=""):
        yield
