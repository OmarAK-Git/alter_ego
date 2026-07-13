"""
Live smoke test — fires real HTTP requests at the running server.
Run with:  .venv\Scripts\pytest.exe tests/live/test_live_smoke.py -v -s

Prerequisites: uvicorn must be running on http://localhost:8000
"""
import requests
from datetime import datetime

BASE = "http://localhost:8000"


def api(path, **kwargs):
    return requests.request(kwargs.pop("method", "GET"), f"{BASE}{path}", **kwargs)


def test_server_is_up():
    r = api("/api/alerts")
    assert r.status_code == 200, f"Server not reachable: {r.text}"
    print(f"\n[OK] /api/alerts responded — {len(r.json())} active alerts")


def test_seed_and_triage_full_lifecycle():
    """
    Seeds a synthetic decision directly into the DB via the running process,
    walks it through the full state machine, and verifies each transition.
    """
    import sqlite3
    import json

    db_path = "alter_ego_calibrate_v2.db"
    decision_id = f"smoke_test_{datetime.utcnow().strftime('%H%M%S%f')}"

    # --- Seed a synthetic anomaly into the live DB ---
    con = sqlite3.connect(db_path)
    con.execute(
        """
        INSERT OR IGNORE INTO decisions
            (decision_id, event_id, entity_id, timestamp, score, confidence,
             profile_version, scoring_config_version, contributions,
             is_anomaly, cohort_used, cohort_unsupported, flags)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            decision_id,
            "evt_smoke",
            "user_smoke_test",
            datetime.utcnow().isoformat(),
            88.5,
            0.92,
            "smoke_profile_v1",
            "test",
            json.dumps([
                {"contribution_id": "c1", "feature_name": "login_hour",
                 "raw_value": 3.0, "contribution_score": 45.0, "confidence_weight": 0.9},
                {"contribution_id": "c2", "feature_name": "geolocation",
                 "raw_value": 1.0, "contribution_score": 43.5, "confidence_weight": 0.85},
            ]),
            1,
            "analyst",
            0,
            json.dumps([]),
        ),
    )
    con.commit()
    con.close()
    print(f"\n[SEED] Inserted decision {decision_id} into live DB")

    # --- Appears in triage queue ---
    r = api("/api/alerts")
    ids = [a["decision_id"] for a in r.json()]
    assert decision_id in ids, "Decision not visible in triage queue"
    print("[OK]   Visible in /api/alerts — state: new")

    # --- Acknowledge ---
    r = api(f"/api/alerts/{decision_id}/workflow", method="PUT",
            json={"state": "acknowledged"})
    assert r.status_code == 200
    assert r.json()["state"] == "acknowledged"
    print("[OK]   Transitioned -> acknowledged")

    # --- Investigate ---
    r = api(f"/api/alerts/{decision_id}/workflow", method="PUT",
            json={"state": "investigating", "assignee": "analyst_1"})
    assert r.status_code == 200
    assert r.json()["state"] == "investigating"
    print("[OK]   Transitioned -> investigating (assignee: analyst_1)")

    # --- Trigger explanation ---
    r = api(f"/api/alerts/{decision_id}/explain", method="POST")
    assert r.status_code == 200
    print("[OK]   Explanation generated")

    # --- Detail view has explanation ---
    r = api(f"/api/alerts/{decision_id}")
    data = r.json()
    assert data["explanation"] is not None
    assert data["explanation"]["summary_text"]
    print(f"[OK]   Detail view — explanation: \"{data['explanation']['summary_text'][:60]}...\"")

    # --- Clear with reason ---
    r = api(f"/api/alerts/{decision_id}/workflow", method="PUT",
            json={"state": "cleared", "clear_reason": "Confirmed false positive — smoke test"})
    assert r.status_code == 200
    print("[OK]   Transitioned -> cleared")

    # --- No longer in triage queue ---
    r = api("/api/alerts")
    ids = [a["decision_id"] for a in r.json()]
    assert decision_id not in ids
    print("[OK]   Removed from /api/alerts triage queue")

    # --- Cleanup ---
    con = sqlite3.connect(db_path)
    con.execute("DELETE FROM decisions WHERE decision_id=?", (decision_id,))
    con.execute("DELETE FROM alert_workflow_state WHERE decision_id=?", (decision_id,))
    con.execute("DELETE FROM explanations WHERE decision_id=?", (decision_id,))
    con.commit()
    con.close()
    print("[CLEAN] Removed smoke test records")
