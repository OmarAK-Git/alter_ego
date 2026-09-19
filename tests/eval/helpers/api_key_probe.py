"""Isolated API-key probe. MUST NOT import pytest."""
from __future__ import annotations

import json
import os
import sys

from fastapi.testclient import TestClient


def main() -> int:
    if "pytest" in sys.modules:
        print(json.dumps({"error": "pytest_in_sys_modules"}))
        return 2
    os.environ.setdefault("API_KEY", "kernel-secret")
    from web.api import app

    client = TestClient(app)
    path = "/api/alerts/dec_probe/workflow"
    missing = client.put(path, json={"state": "acknowledged"})
    wrong = client.put(
        path,
        json={"state": "acknowledged"},
        headers={"X-API-KEY": "not-the-key"},
    )
    print(
        json.dumps(
            {
                "missing_status": missing.status_code,
                "wrong_status": wrong.status_code,
                "pytest_loaded": "pytest" in sys.modules,
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
