"""
Staged interactive smoke test — pauses between each phase so you can
inspect the UI before data changes.

Run with:
    .venv\\Scripts\\pytest.exe tests/live/test_live_smoke_staged.py -v -s

The -s flag is REQUIRED (disables output capture so input() works).
Keep http://localhost:8000 open in a browser and hit Refresh after each prompt.
"""
import sqlite3
import json
import requests
from datetime import datetime

import pytest

BASE = "http://localhost:8000"
DB_PATH = "alter_ego_calibrate_v2.db"


def api(path, method="GET", **kwargs):
    return requests.request(method, f"{BASE}{path}", **kwargs)


def pause(message: str):
    """Block until the user presses Enter."""
    print(f"\n{'─'*60}")
    print(f"  {message}")
    print(f"{'─'*60}")
    input("  ► Press ENTER to continue to the next stage...\n")


# --------------------------------------------------------------------------- #
#  Fixtures                                                                     #
# --------------------------------------------------------------------------- #

@pytest.fixture(scope="module")
def decision_id():
    """Generate a unique decision ID for this run."""
    return f"staged_smoke_{datetime.utcnow().strftime('%H%M%S%f')}"


@pytest.fixture(scope="module", autouse=True)
def cleanup(decision_id):
    """Always clean up after the test module, even on failure."""
    yield
    con = sqlite3.connect(DB_PATH)
    deleted = 0
    for table in ("decisions", "alert_workflow_state", "explanations"):
        cur = con.execute(f"DELETE FROM {table} WHERE decision_id=?", (decision_id,))
        deleted += cur.rowcount
    con.commit()
    con.close()
    print(f"\n[CLEANUP] Removed {deleted} row(s) for {decision_id}")


# --------------------------------------------------------------------------- #
#  Stage 1 — Verify server is reachable                                        #
# --------------------------------------------------------------------------- #

def test_stage_1_server_up():
    r = api("/api/alerts")
    assert r.status_code == 200, f"Server not reachable at {BASE}"
    count = len(r.json())
    print(f"\n[STAGE 1] Server is UP — {count} active alert(s) currently in queue")
    pause(
        "STAGE 1 COMPLETE\n"
        "  -> Open http://localhost:8000 and confirm the Triage Queue\n"
        "     shows the current alert count before we add a new one."
    )


# --------------------------------------------------------------------------- #
#  Stage 2 — Seed a synthetic anomaly                                          #
# --------------------------------------------------------------------------- #

def test_stage_2_seed_anomaly(decision_id):
    con = sqlite3.connect(DB_PATH)
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
            "evt_staged_smoke",
            "user_staged_demo",
            datetime.utcnow().isoformat(),
            91.3,
            0.94,
            "staged_profile_v1",
            "test",
            json.dumps([
                {
                    "contribution_id": "c1",
                    "feature_name": "login_hour",
                    "raw_value": 3.0,
                    "contribution_score": 48.0,
                    "confidence_weight": 0.95,
                },
                {
                    "contribution_id": "c2",
                    "feature_name": "geolocation",
                    "raw_value": 1.0,
                    "contribution_score": 43.3,
                    "confidence_weight": 0.88,
                },
            ]),
            1,
            "analyst",
            0,
            json.dumps([]),
        ),
    )
    con.commit()
    con.close()

    r = api("/api/alerts")
    ids = [a["decision_id"] for a in r.json()]
    assert decision_id in ids, "Seeded decision not visible in triage queue"

    print(f"\n[STAGE 2] Inserted decision: {decision_id}")
    print("          Entity: user_staged_demo | Score: 91.30 | State: new")
    pause(
        "STAGE 2 COMPLETE — Anomaly seeded into live DB\n"
        "  -> Refresh http://localhost:8000\n"
        "  -> You should see 'user_staged_demo' appear in the Triage Queue\n"
        "     with SCORE 91.30 and state badge: new"
    )


# --------------------------------------------------------------------------- #
#  Stage 3 — Acknowledge                                                       #
# --------------------------------------------------------------------------- #

def test_stage_3_acknowledge(decision_id):
    r = api(f"/api/alerts/{decision_id}/workflow", method="PUT",
            json={"state": "acknowledged"})
    assert r.status_code == 200
    assert r.json()["state"] == "acknowledged"

    print("\n[STAGE 3] State: new -> acknowledged")
    pause(
        "STAGE 3 COMPLETE — Alert acknowledged\n"
        "  -> Refresh http://localhost:8000\n"
        "  -> The state badge on 'user_staged_demo' should now read: acknowledged"
    )


# --------------------------------------------------------------------------- #
#  Stage 4 — Investigate                                                       #
# --------------------------------------------------------------------------- #

def test_stage_4_investigate(decision_id):
    r = api(f"/api/alerts/{decision_id}/workflow", method="PUT",
            json={"state": "investigating", "assignee": "analyst_1"})
    assert r.status_code == 200
    assert r.json()["state"] == "investigating"

    print("\n[STAGE 4] State: acknowledged -> investigating (assignee: analyst_1)")
    print("          Profile builds for user_staged_demo will now be shadow-only")
    pause(
        "STAGE 4 COMPLETE — Under investigation\n"
        "  -> Refresh http://localhost:8000\n"
        "  -> Click 'Review' next to user_staged_demo\n"
        "  -> The detail pane should show State: investigating"
    )


# --------------------------------------------------------------------------- #
#  Stage 5 — Generate explanation                                              #
# --------------------------------------------------------------------------- #

def test_stage_5_explanation(decision_id):
    r = api(f"/api/alerts/{decision_id}/explain", method="POST")
    assert r.status_code == 200

    r2 = api(f"/api/alerts/{decision_id}")
    data = r2.json()
    assert data["explanation"] is not None
    exp = data["explanation"]

    print("\n[STAGE 5] Explanation generated")
    print(f"          Summary : \"{exp['summary_text']}\"")
    print(f"          Claims  : {len(exp['claim_objects'])} item(s)")
    print(f"          CFs     : {len(exp['counterfactuals'])} counterfactual(s)")
    print(f"          Status  : {exp['validation_status']}")
    for cf in exp['counterfactuals']:
        print(f"            - {cf['counterfactual_text']}")
    pause(
        "STAGE 5 COMPLETE — Explanation written to DB\n"
        "  -> In the detail view, click 'Generate' in the right pane\n"
        "     (or hit Refresh if you already have it open)\n"
        "  -> You should see the summary text + counterfactuals appear"
    )


# --------------------------------------------------------------------------- #
#  Stage 6 — Clear the alert                                                  #
# --------------------------------------------------------------------------- #

def test_stage_6_clear(decision_id):
    r = api(f"/api/alerts/{decision_id}/workflow", method="PUT",
            json={"state": "cleared", "clear_reason": "Confirmed false positive - staged demo"})
    assert r.status_code == 200

    r2 = api("/api/alerts")
    ids = [a["decision_id"] for a in r2.json()]
    assert decision_id not in ids, "Cleared alert still visible in triage queue"

    print("\n[STAGE 6] Alert cleared and removed from triage queue")
    pause(
        "STAGE 6 COMPLETE — Alert cleared\n"
        "  -> Refresh http://localhost:8000 (Triage Queue tab)\n"
        "  -> 'user_staged_demo' should now be GONE\n"
        "\n"
        "  All 6 stages complete! Press Enter to run cleanup."
    )
