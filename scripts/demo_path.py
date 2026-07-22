"""Reproducible analyst demo path: seed → triage → explain → contain (simulated).

No live LLM or external API keys required — explainer uses template fallback when
keys are absent. Run against a live server or import helpers in tests.

Usage:
    python scripts/demo_path.py seed          # insert demo alert into configured DB
    python scripts/demo_path.py run           # HTTP walkthrough (server must be up)
    python scripts/demo_path.py seed-and-run  # seed DB then run HTTP chain
    python scripts/demo_path.py cleanup       # remove demo records
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Protocol

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from sqlalchemy.orm import Session  # noqa: E402

from core.database import Base, SessionLocal, engine  # noqa: E402
from core.models import (  # noqa: E402
    AlertWorkflowStateModel,
    ContainmentQueueModel,
    DecisionRecordModel,
    ExplanationRecordModel,
    ProfileArtifactModel,
)

DEMO_DECISION_ID = "demo_path_alert"
DEMO_ENTITY_ID = "user_demo_path"
DEMO_EVENT_ID = "evt_demo_path"
DEMO_PROFILE_VERSION = "demo_profile_v1"

DEMO_CONTRIBUTIONS = [
    {
        "contribution_id": "demo_c1",
        "feature_name": "login_hour",
        "raw_value": 3.0,
        "contribution_score": 45.0,
        "confidence_weight": 0.9,
    },
    {
        "contribution_id": "demo_c2",
        "feature_name": "geolocation",
        "raw_value": 1.0,
        "contribution_score": 43.5,
        "confidence_weight": 0.85,
    },
]


class HttpClient(Protocol):
    def get(self, path: str, **kwargs: Any) -> Any: ...
    def put(self, path: str, **kwargs: Any) -> Any: ...
    def post(self, path: str, **kwargs: Any) -> Any: ...


def seed_demo_alert(
    db: Session,
    *,
    decision_id: str = DEMO_DECISION_ID,
    entity_id: str = DEMO_ENTITY_ID,
    profile_version: str = DEMO_PROFILE_VERSION,
) -> DecisionRecordModel:
    """Insert a high-confidence anomaly decision and matching profile for the explainer."""
    existing = (
        db.query(DecisionRecordModel)
        .filter(DecisionRecordModel.decision_id == decision_id)
        .first()
    )
    if existing:
        return existing

    now = datetime.utcnow()
    dec = DecisionRecordModel(
        decision_id=decision_id,
        event_id=DEMO_EVENT_ID,
        entity_id=entity_id,
        timestamp=now,
        score=88.5,
        confidence=0.92,
        profile_version=profile_version,
        scoring_config_version="2.2",
        contributions=DEMO_CONTRIBUTIONS,
        is_anomaly=True,
        cohort_used="Engineer",
        cohort_unsupported=False,
        flags=[],
    )
    profile = ProfileArtifactModel(
        profile_version=profile_version,
        entity_id=entity_id,
        entity_type="human",
        created_at=now,
        data_window_start=now,
        data_window_end=now,
        features={"total_events": 120, "process_names": {"python.exe": 15, "git.exe": 10}},
    )
    db.add(dec)
    db.add(profile)
    db.commit()
    db.refresh(dec)
    return dec


def cleanup_demo_alert(db: Session, decision_id: str = DEMO_DECISION_ID) -> None:
    """Remove demo-path records (idempotent)."""
    db.query(ExplanationRecordModel).filter(
        ExplanationRecordModel.decision_id == decision_id
    ).delete()
    db.query(ContainmentQueueModel).filter(
        ContainmentQueueModel.decision_id == decision_id
    ).delete()
    db.query(AlertWorkflowStateModel).filter(
        AlertWorkflowStateModel.decision_id == decision_id
    ).delete()
    db.query(DecisionRecordModel).filter(
        DecisionRecordModel.decision_id == decision_id
    ).delete()
    db.query(ProfileArtifactModel).filter(
        ProfileArtifactModel.profile_version == DEMO_PROFILE_VERSION
    ).delete()
    db.commit()


def run_demo_path(
    client: HttpClient,
    *,
    decision_id: str = DEMO_DECISION_ID,
    api_key: str | None = None,
) -> dict[str, Any]:
    """Walk triage → acknowledge → explain → contain via analyst API."""
    headers: dict[str, str] = {}
    if api_key:
        headers["X-API-KEY"] = api_key

    triage = client.get("/api/alerts")
    _assert_ok(triage, "list triage alerts")
    triage_data = _json(triage)
    assert any(a["decision_id"] == decision_id for a in triage_data), (
        f"{decision_id} not visible in triage queue"
    )

    ack = client.put(
        f"/api/alerts/{decision_id}/workflow",
        json={"state": "acknowledged"},
        headers=headers,
    )
    _assert_ok(ack, "acknowledge alert")
    assert _json(ack)["state"] == "acknowledged"

    explain = client.post(f"/api/alerts/{decision_id}/explain", headers=headers)
    _assert_ok(explain, "generate explanation")
    assert _json(explain)["status"] == "success"

    detail = client.get(f"/api/alerts/{decision_id}")
    _assert_ok(detail, "alert detail")
    detail_data = _json(detail)
    assert detail_data["explanation"] is not None
    assert detail_data["explanation"]["summary_text"]

    contain = client.post(f"/api/alerts/{decision_id}/contain", headers=headers)
    _assert_ok(contain, "queue simulated containment")
    assert _json(contain)["status"] == "queued"

    return {
        "decision_id": decision_id,
        "triage_count": len(triage_data),
        "workflow_state": detail_data["state"]["state"],
        "validation_status": detail_data["explanation"]["validation_status"],
        "summary_preview": detail_data["explanation"]["summary_text"][:80],
    }


def _assert_ok(response: Any, step: str) -> None:
    status = getattr(response, "status_code", None)
    if status is None or status >= 400:
        body = getattr(response, "text", response)
        raise RuntimeError(f"Demo path failed at '{step}': HTTP {status} — {body}")


def _json(response: Any) -> Any:
    if hasattr(response, "json"):
        return response.json()
    return json.loads(response.text)


def _requests_client(base_url: str) -> HttpClient:
    import requests

    class _Client:
        def get(self, path: str, **kwargs: Any) -> Any:
            return requests.get(f"{base_url}{path}", timeout=30, **kwargs)

        def put(self, path: str, **kwargs: Any) -> Any:
            return requests.put(f"{base_url}{path}", timeout=30, **kwargs)

        def post(self, path: str, **kwargs: Any) -> Any:
            return requests.post(f"{base_url}{path}", timeout=30, **kwargs)

    return _Client()


def _ensure_tables() -> None:
    Base.metadata.create_all(bind=engine)


def cmd_seed(args: argparse.Namespace) -> int:
    _ensure_tables()
    db = SessionLocal()
    try:
        dec = seed_demo_alert(db, decision_id=args.decision_id)
        print(f"[seed] decision_id={dec.decision_id} entity_id={dec.entity_id} score={dec.score}")
        print(f"       Open http://localhost:8000 and find '{dec.entity_id}' in Triage Queue")
        return 0
    finally:
        db.close()


def cmd_run(args: argparse.Namespace) -> int:
    api_key = args.api_key or os.getenv("API_KEY")
    client = _requests_client(args.base_url)
    try:
        result = run_demo_path(client, decision_id=args.decision_id, api_key=api_key)
    except RuntimeError as exc:
        print(f"[error] {exc}", file=sys.stderr)
        return 1
    print("[ok] demo path complete:")
    for key, value in result.items():
        print(f"     {key}: {value}")
    return 0


def cmd_seed_and_run(args: argparse.Namespace) -> int:
    code = cmd_seed(args)
    if code != 0:
        return code
    return cmd_run(args)


def cmd_cleanup(args: argparse.Namespace) -> int:
    _ensure_tables()
    db = SessionLocal()
    try:
        cleanup_demo_alert(db, decision_id=args.decision_id)
        print(f"[cleanup] removed demo records for {args.decision_id}")
        return 0
    finally:
        db.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="ALTER_EGO analyst demo path")
    parser.add_argument("--decision-id", default=DEMO_DECISION_ID)
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--api-key", default=None, help="X-API-KEY for privileged routes")

    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("seed", help="Seed demo alert into configured database")
    sub.add_parser("run", help="Run HTTP demo chain against live server")
    sub.add_parser("seed-and-run", help="Seed DB then run HTTP chain")
    sub.add_parser("cleanup", help="Remove demo records")

    args = parser.parse_args(argv)
    handlers = {
        "seed": cmd_seed,
        "run": cmd_run,
        "seed-and-run": cmd_seed_and_run,
        "cleanup": cmd_cleanup,
    }
    return handlers[args.command](args)


if __name__ == "__main__":
    raise SystemExit(main())
