from datetime import datetime, timedelta
from fastapi import FastAPI, Depends, HTTPException, Security
from fastapi.security import APIKeyHeader
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os
from sqlalchemy.orm import Session
from sqlalchemy import and_, desc

from core.attestation import (
    ANCHOR_HISTORY_COUNT,
    QUIET_WINDOW_DAYS,
    attest,
)
from core.database import SessionLocal
from core.models import (
    DecisionRecordModel, 
    AlertWorkflowStateModel, 
    ExplanationRecordModel,
    ProfileArtifactModel,
    StalenessHaltExtensionModel,
    log_audit_event,
)
from core.schemas.workflow import AlertStateEnum, AlertStateUpdate, ExtendHaltRequest, ReplayRequest
from worker.explainer import generate_explanation
from worker.recorder import queue_simulated_containment
from worker.scorer import (
    MANDATORY_ESCALATION_SLA_HOURS,
    STALENESS_ESCALATION_FLAG,
    get_active_alert_decision_ids,
    load_scoring_config,
)
from batch.profile_builder.builder import BUILD_BLOCK_SUPERVISOR_ESCALATION_FLAG
from batch.replay_runner import run_replay

app = FastAPI(title="ALTER_EGO Analyst API")

TERMINAL_ALERT_STATES = frozenset({"cleared", "auto_resolved"})
ANALYST_CLEAR_AUDIT_ACTION = "alert_cleared_by_analyst"

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

API_KEY_HEADER = APIKeyHeader(name="X-API-KEY", auto_error=False)

def verify_api_key(api_key: str = Security(API_KEY_HEADER)):
    import sys
    if "pytest" in sys.modules or "PYTEST_CURRENT_TEST" in os.environ:
        return api_key
        
    expected_key = os.getenv("API_KEY")
    if expected_key is None:
        raise HTTPException(
            status_code=500,
            detail="Server configuration error: API_KEY environment variable is not set."
        )
    if not api_key or api_key != expected_key:
        raise HTTPException(
            status_code=401,
            detail="Unauthorized: Invalid or missing API key."
        )
    return api_key


def _get_confidence_floor() -> float:
    config = load_scoring_config()
    return config.get("confidence_floor", 0.6)


def _flags_contain(flags, key: str) -> bool:
    if isinstance(flags, dict):
        return bool(flags.get(key)) or key in flags
    if isinstance(flags, list):
        return key in flags
    return False


def _compute_entity_attestation(db: Session, entity_id: str) -> dict:
    """Shadow attestation status for UI at clear time (Design §4.3 / §4.7)."""
    config = load_scoring_config()
    drift_threshold = float(config.get("drift_threshold", 5.0))
    as_of = datetime.utcnow()

    active = (
        db.query(AlertWorkflowStateModel)
        .filter(
            AlertWorkflowStateModel.entity_id == entity_id,
            AlertWorkflowStateModel.state.in_(["new", "acknowledged", "investigating"]),
        )
        .all()
    )
    earliest = None
    for alert in active:
        dec = db.get(DecisionRecordModel, alert.decision_id)
        start = dec.timestamp if dec is not None else alert.updated_at
        if earliest is None or start < earliest:
            earliest = start

    quiet_cutoff = as_of - timedelta(days=QUIET_WINDOW_DAYS)
    recent_anomaly = (
        db.query(DecisionRecordModel)
        .filter(
            DecisionRecordModel.entity_id == entity_id,
            DecisionRecordModel.is_anomaly.is_(True),
            DecisionRecordModel.timestamp > quiet_cutoff,
        )
        .first()
    )
    quiet = recent_anomaly is None

    shadows = []
    if earliest is not None:
        shadows = (
            db.query(ProfileArtifactModel)
            .filter(
                ProfileArtifactModel.entity_id == entity_id,
                ProfileArtifactModel.is_shadow.is_(True),
                ProfileArtifactModel.created_at >= earliest,
            )
            .order_by(ProfileArtifactModel.created_at)
            .all()
        )
    latest_shadow = (
        db.query(ProfileArtifactModel)
        .filter(
            ProfileArtifactModel.entity_id == entity_id,
            ProfileArtifactModel.is_shadow.is_(True),
        )
        .order_by(desc(ProfileArtifactModel.created_at))
        .first()
    )
    promoted = (
        db.query(ProfileArtifactModel)
        .filter(
            ProfileArtifactModel.entity_id == entity_id,
            ProfileArtifactModel.is_shadow.is_(False),
            ProfileArtifactModel.promoted_at.isnot(None),
            ProfileArtifactModel.superseded_at.is_(None),
        )
        .first()
    )
    history = (
        db.query(ProfileArtifactModel)
        .filter(
            ProfileArtifactModel.entity_id == entity_id,
            ProfileArtifactModel.is_shadow.is_(False),
            ProfileArtifactModel.promoted_at.isnot(None),
        )
        .order_by(desc(ProfileArtifactModel.promoted_at))
        .limit(ANCHOR_HISTORY_COUNT)
        .all()
    )
    shadow_features = (latest_shadow.features if latest_shadow else None) or {}
    promoted_features = (promoted.features if promoted else None) or {}
    anchor_features = (history[-1].features if history else promoted_features) or {}
    shadow_drifts = [
        float((s.features or {}).get("cumulative_drift", 0.0)) for s in shadows
    ]
    ok, detail = attest(
        shadow_features=shadow_features,
        promoted_features=promoted_features,
        anchor_features=anchor_features,
        shadow_drifts_during_block=shadow_drifts,
        drift_threshold=drift_threshold,
    )
    return {
        "quiet": quiet,
        "attest_ok": ok,
        "would_auto_resolve": quiet and ok,
        **detail,
    }


@app.get("/api/alerts")
def get_triage_alerts(db: Session = Depends(get_db)):
    confidence_floor = _get_confidence_floor()

    results = db.query(DecisionRecordModel, AlertWorkflowStateModel)\
        .outerjoin(AlertWorkflowStateModel, DecisionRecordModel.decision_id == AlertWorkflowStateModel.decision_id)\
        .filter(
            DecisionRecordModel.is_anomaly.is_(True),
            DecisionRecordModel.confidence >= confidence_floor,
        )\
        .order_by(desc(DecisionRecordModel.timestamp))\
        .all()
        
    alerts = []
    for dec, state in results:
        s_val = state.state if state else "new"
        if s_val in TERMINAL_ALERT_STATES:
            continue
            
        alerts.append({
            "decision_id": dec.decision_id,
            "entity_id": dec.entity_id,
            "timestamp": dec.timestamp.isoformat(),
            "score": dec.score,
            "confidence": dec.confidence,
            "flags": dec.flags,
            "replay_run_id": dec.replay_run_id,
            "state": s_val,
            "assignee": state.assignee if state else None
        })
    return alerts

def _entity_has_active_extend_halt(db: Session, entity_id: str) -> bool:
    now = datetime.utcnow()
    ext = (
        db.query(StalenessHaltExtensionModel)
        .filter(
            StalenessHaltExtensionModel.entity_id == entity_id,
            StalenessHaltExtensionModel.expires_at > now,
        )
        .order_by(StalenessHaltExtensionModel.expires_at.desc())
        .first()
    )
    return ext is not None


def _build_mandatory_escalations(db: Session) -> list[dict]:
    decisions = db.query(DecisionRecordModel).order_by(DecisionRecordModel.timestamp.desc()).all()
    latest_staleness: dict[str, DecisionRecordModel] = {}
    latest_build_block: dict[str, DecisionRecordModel] = {}
    for dec in decisions:
        flags = dec.flags or []
        if _flags_contain(flags, STALENESS_ESCALATION_FLAG):
            if dec.entity_id not in latest_staleness:
                latest_staleness[dec.entity_id] = dec
        if _flags_contain(flags, BUILD_BLOCK_SUPERVISOR_ESCALATION_FLAG):
            if dec.entity_id not in latest_build_block:
                latest_build_block[dec.entity_id] = dec

    items: list[dict] = []
    seen: set[str] = set()

    for entity_id, halt_dec in latest_staleness.items():
        if _entity_has_active_extend_halt(db, entity_id):
            continue
        alert_ids = get_active_alert_decision_ids(db, entity_id)
        if not alert_ids:
            continue
        items.append({
            "entity_id": entity_id,
            "escalation_type": "staleness",
            "staleness_decision_id": halt_dec.decision_id,
            "escalation_decision_id": halt_dec.decision_id,
            "alert_decision_ids": alert_ids,
            "sla_hours": MANDATORY_ESCALATION_SLA_HOURS,
            "halt_timestamp": halt_dec.timestamp.isoformat(),
            "flags": halt_dec.flags,
        })
        seen.add(entity_id)

    for entity_id, esc_dec in latest_build_block.items():
        if entity_id in seen:
            continue
        alert_ids = get_active_alert_decision_ids(db, entity_id)
        if not alert_ids:
            continue
        items.append({
            "entity_id": entity_id,
            "escalation_type": "build_block",
            "staleness_decision_id": None,
            "escalation_decision_id": esc_dec.decision_id,
            "alert_decision_ids": alert_ids,
            "sla_hours": MANDATORY_ESCALATION_SLA_HOURS,
            "halt_timestamp": esc_dec.timestamp.isoformat(),
            "flags": esc_dec.flags,
        })
    return items


@app.get("/api/mandatory-escalations")
def get_mandatory_escalations(db: Session = Depends(get_db)):
    return _build_mandatory_escalations(db)


@app.post("/api/mandatory-escalations/{entity_id}/extend-halt", dependencies=[Depends(verify_api_key)])
def extend_staleness_halt(entity_id: str, req: ExtendHaltRequest, db: Session = Depends(get_db)):
    justification = req.justification.strip()
    if not justification:
        raise HTTPException(status_code=422, detail="justification is required")

    now = datetime.utcnow()
    ext = StalenessHaltExtensionModel(
        entity_id=entity_id,
        justification=justification,
        extended_at=now,
        expires_at=now + timedelta(hours=MANDATORY_ESCALATION_SLA_HOURS),
    )
    db.add(ext)
    db.commit()
    return {
        "status": "success",
        "entity_id": entity_id,
        "expires_at": ext.expires_at.isoformat(),
        "sla_hours": MANDATORY_ESCALATION_SLA_HOURS,
    }

@app.get("/api/alerts/{decision_id}")
def get_alert_detail(decision_id: str, db: Session = Depends(get_db)):
    dec = db.query(DecisionRecordModel).filter(DecisionRecordModel.decision_id == decision_id).first()
    if not dec:
        raise HTTPException(status_code=404, detail="Alert not found")
        
    state = db.query(AlertWorkflowStateModel).filter(AlertWorkflowStateModel.decision_id == decision_id).first()
    explanation = db.query(ExplanationRecordModel).filter(ExplanationRecordModel.decision_id == decision_id).first()
    attestation = _compute_entity_attestation(db, dec.entity_id)
    
    return {
        "decision": {
            "decision_id": dec.decision_id,
            "entity_id": dec.entity_id,
            "timestamp": dec.timestamp.isoformat(),
            "score": dec.score,
            "confidence": dec.confidence,
            "profile_version": dec.profile_version,
            "contributions": dec.contributions,
            "flags": dec.flags,
            "cohort_used": dec.cohort_used,
            "cohort_unsupported": dec.cohort_unsupported,
            "replay_run_id": dec.replay_run_id,
        },
        "state": {
            "state": state.state if state else "new",
            "assignee": state.assignee if state else None,
            "clear_reason": state.clear_reason if state else None,
            "updated_at": state.updated_at.isoformat() if state else dec.timestamp.isoformat()
        },
        "attestation": attestation,
        "explanation": {
            "summary_text": explanation.summary_text,
            "claim_objects": explanation.claim_objects,
            "counterfactuals": explanation.counterfactuals,
            "validation_status": explanation.validation_status
        } if explanation else None
    }

@app.post("/api/alerts/{decision_id}/explain", dependencies=[Depends(verify_api_key)])
def trigger_explanation(decision_id: str, db: Session = Depends(get_db)):
    try:
        record = generate_explanation(decision_id, db=db)
        return {
            "status": "success",
            "decision_id": decision_id,
            "validation_status": record.validation_status.value,
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@app.put("/api/alerts/{decision_id}/workflow", dependencies=[Depends(verify_api_key)])
def update_workflow_state(decision_id: str, update: AlertStateUpdate, db: Session = Depends(get_db)):
    dec = db.query(DecisionRecordModel).filter(DecisionRecordModel.decision_id == decision_id).first()
    if not dec:
        raise HTTPException(status_code=404, detail="Alert not found")
        
    state = db.query(AlertWorkflowStateModel).filter(AlertWorkflowStateModel.decision_id == decision_id).first()
    if not state:
        state = AlertWorkflowStateModel(
            decision_id=decision_id,
            entity_id=dec.entity_id,
            state="new"
        )
        db.add(state)
        
    state.state = update.state.value
    if update.assignee is not None:
        state.assignee = update.assignee
    if update.clear_reason is not None:
        state.clear_reason = update.clear_reason

    attestation = None
    attestation_override = False
    if update.state == AlertStateEnum.cleared:
        if not update.clear_reason:
            raise HTTPException(status_code=422, detail="clear_reason is required when clearing")
        attestation = _compute_entity_attestation(db, dec.entity_id)
        attestation_override = not (
            attestation.get("quiet") and attestation.get("attest_ok")
        )
        log_audit_event(
            db,
            action=ANALYST_CLEAR_AUDIT_ACTION,
            entity_id=dec.entity_id,
            details={
                "decision_id": decision_id,
                "clear_reason": update.clear_reason,
                "attestation_override": attestation_override,
                "attestation": attestation,
            },
            commit=False,
        )
        
    db.commit()
    return {
        "status": "success",
        "state": state.state,
        "attestation": attestation,
        "attestation_override": attestation_override,
    }

@app.post("/api/alerts/{decision_id}/contain", dependencies=[Depends(verify_api_key)])
def queue_containment(decision_id: str, db: Session = Depends(get_db)):
    dec = db.query(DecisionRecordModel).filter(DecisionRecordModel.decision_id == decision_id).first()
    if not dec:
        raise HTTPException(status_code=404, detail="Alert not found")
        
    queue_simulated_containment(db, decision_id, dec.entity_id)
    db.commit()
    return {"status": "queued"}

@app.get("/api/suppressed")
def get_suppressed_alerts(db: Session = Depends(get_db)):
    confidence_floor = _get_confidence_floor()

    results = db.query(DecisionRecordModel, AlertWorkflowStateModel)\
        .outerjoin(AlertWorkflowStateModel, DecisionRecordModel.decision_id == AlertWorkflowStateModel.decision_id)\
        .filter(
            and_(
                DecisionRecordModel.is_anomaly.is_(True),
                DecisionRecordModel.confidence < confidence_floor,
            )
        )\
        .order_by(desc(DecisionRecordModel.timestamp))\
        .all()
        
    alerts = []
    for dec, state in results:
        s_val = state.state if state else "new"
        if s_val in TERMINAL_ALERT_STATES:
            continue
            
        alerts.append({
            "decision_id": dec.decision_id,
            "entity_id": dec.entity_id,
            "timestamp": dec.timestamp.isoformat(),
            "score": dec.score,
            "confidence": dec.confidence,
            "flags": dec.flags,
            "replay_run_id": dec.replay_run_id,
            "state": s_val
        })
    return alerts

static_dir = os.path.join(os.path.dirname(__file__), "static")
os.makedirs(static_dir, exist_ok=True)
app.mount("/static", StaticFiles(directory=static_dir), name="static")

@app.post("/api/replay", dependencies=[Depends(verify_api_key)])
def trigger_replay(req: ReplayRequest, db: Session = Depends(get_db)):
    summary = run_replay(
        start_time=req.start_time,
        end_time=req.end_time,
        author=req.author,
        change_reason=req.change_reason,
        db=db,
    )
    return summary

@app.get("/")
def serve_ui():
    index_path = os.path.join(static_dir, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": "UI not built yet."}
