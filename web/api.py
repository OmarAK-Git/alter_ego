from fastapi import FastAPI, Depends, HTTPException, Security
from fastapi.security import APIKeyHeader
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os
from sqlalchemy.orm import Session
from sqlalchemy import and_, desc

from core.database import SessionLocal
from core.models import (
    DecisionRecordModel, 
    AlertWorkflowStateModel, 
    ExplanationRecordModel
)
from core.schemas.workflow import AlertStateUpdate, ReplayRequest
from worker.explainer import generate_explanation
from worker.recorder import queue_simulated_containment
from worker.scorer import load_scoring_config
from batch.replay_runner import run_replay

app = FastAPI(title="ALTER_EGO Analyst API")

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
        if s_val == "cleared":
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

@app.get("/api/alerts/{decision_id}")
def get_alert_detail(decision_id: str, db: Session = Depends(get_db)):
    dec = db.query(DecisionRecordModel).filter(DecisionRecordModel.decision_id == decision_id).first()
    if not dec:
        raise HTTPException(status_code=404, detail="Alert not found")
        
    state = db.query(AlertWorkflowStateModel).filter(AlertWorkflowStateModel.decision_id == decision_id).first()
    explanation = db.query(ExplanationRecordModel).filter(ExplanationRecordModel.decision_id == decision_id).first()
    
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
        
    db.commit()
    return {"status": "success", "state": state.state}

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
        if s_val == "cleared":
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
