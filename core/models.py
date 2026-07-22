from sqlalchemy import Column, String, DateTime, Float, Boolean, Integer
from sqlalchemy.dialects.postgresql import JSONB
from pgvector.sqlalchemy import Vector
from core.database import Base
from core.schemas.profiles import (
    DEFAULT_EMBEDDING_DIMENSIONALITY,
    DEFAULT_EMBEDDING_MODEL_ID,
    DEFAULT_EMBEDDING_MODEL_VERSION,
    DEFAULT_EMBEDDING_INPUT_NORMALIZER_VERSION,
)
try:
    from core.database import SQLiteVector
except ImportError:
    SQLiteVector = None
from dataclasses import dataclass, field
from datetime import datetime

class EventModel(Base):
    __tablename__ = "events"
    event_id = Column(String, primary_key=True)
    timestamp = Column(DateTime, nullable=False)
    event_type = Column(String, nullable=False)
    raw_entity_id = Column(String, nullable=False)
    simulation_partition = Column(String, default="production", nullable=False)
    event_data = Column(JSONB, nullable=False)

class ResolvedEventModel(Base):
    __tablename__ = "resolved_events"
    event_id = Column(String, primary_key=True)
    timestamp = Column(DateTime, nullable=False, index=True)
    event_type = Column(String, nullable=False)
    raw_entity_id = Column(String, nullable=False)
    entity_id = Column(String, nullable=False, index=True)
    entity_type = Column(String, nullable=False)
    resolution_confidence = Column(Float, nullable=False)
    simulation_partition = Column(String, nullable=False, index=True)
    event_data = Column(JSONB, nullable=False)

class ProfileArtifactModel(Base):
    __tablename__ = "profiles"
    # Choose vector type based on environment
    VectorType = Vector(128) if (Vector and not SQLiteVector) else (SQLiteVector if SQLiteVector else JSONB)
    
    profile_version = Column(String, primary_key=True)
    entity_id = Column(String, nullable=False, index=True)
    entity_type = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    data_window_start = Column(DateTime, nullable=False)
    data_window_end = Column(DateTime, nullable=False)
    promoted_at = Column(DateTime, nullable=True)
    superseded_at = Column(DateTime, nullable=True)
    is_shadow = Column(Boolean, default=False, nullable=False)
    features = Column(JSONB, nullable=False)
    embedding = Column(VectorType, nullable=True) # For command_line_embedding_similarity
    embedding_model_id = Column(String, default=DEFAULT_EMBEDDING_MODEL_ID, nullable=False)
    embedding_model_version = Column(String, default=DEFAULT_EMBEDDING_MODEL_VERSION, nullable=False)
    embedding_dimensionality = Column(Integer, default=DEFAULT_EMBEDDING_DIMENSIONALITY, nullable=False)
    embedding_input_normalizer_version = Column(
        String, default=DEFAULT_EMBEDDING_INPUT_NORMALIZER_VERSION, nullable=False
    )

class DecisionRecordModel(Base):
    __tablename__ = "decisions"
    decision_id = Column(String, primary_key=True)
    event_id = Column(String, nullable=False, index=True)
    entity_id = Column(String, nullable=False, index=True)
    timestamp = Column(DateTime, nullable=False)
    score = Column(Float, nullable=False)
    confidence = Column(Float, nullable=False)
    profile_version = Column(String, nullable=False)
    scoring_config_version = Column(String, nullable=False)
    contributions = Column(JSONB, nullable=False)
    is_anomaly = Column(Boolean, nullable=False, index=True)
    cohort_used = Column(String, nullable=False)
    cohort_unsupported = Column(Boolean, nullable=False)
    embedding_model_version = Column(String, nullable=False, default='unknown')
    flags = Column(JSONB, nullable=False)
    replay_run_id = Column(String, nullable=True, index=True)

class ExplanationRecordModel(Base):
    __tablename__ = "explanations"
    decision_id = Column(String, primary_key=True)
    summary_text = Column(String, nullable=False)
    claim_objects = Column(JSONB, nullable=False)
    counterfactuals = Column(JSONB, nullable=False)
    validation_status = Column(String, nullable=False)
    validation_notes = Column(String, nullable=True)
    llm_model_id = Column(String, nullable=False)
    prompt_hash = Column(String, nullable=False)
    response_hash = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

class AuditLogModel(Base):
    __tablename__ = "audit_logs"
    log_id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
    action = Column(String, nullable=False)
    entity_id = Column(String, nullable=True)
    details = Column(JSONB, nullable=False)
    previous_log_hash = Column(String, nullable=True)

    def compute_hash(self) -> str:
        import hashlib
        import json
        
        # Serialize fields deterministically
        details_str = json.dumps(self.details, sort_keys=True) if isinstance(self.details, (dict, list)) else str(self.details)
        timestamp_str = self.timestamp.isoformat() if hasattr(self.timestamp, "isoformat") else str(self.timestamp)
        
        payload = {
            "timestamp": timestamp_str,
            "action": self.action,
            "entity_id": self.entity_id,
            "details": details_str,
            "previous_log_hash": self.previous_log_hash
        }
        serialized = json.dumps(payload, sort_keys=True)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


DECISION_AUDIT_ACTIONS = frozenset({"RECORD_DECISION", "DECISION_RECORDED"})


@dataclass
class AuditChainBreak:
    log_id: int
    reason: str
    expected: str | None = None
    actual: str | None = None


@dataclass
class AuditIntegrityResult:
    ok: bool
    log_count: int
    decision_count: int | None = None
    decision_audit_count: int | None = None
    count_mismatch: bool = False
    count_check_skipped: bool = False
    breaks: list[AuditChainBreak] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "ok": self.ok,
            "log_count": self.log_count,
            "decision_count": self.decision_count,
            "decision_audit_count": self.decision_audit_count,
            "count_mismatch": self.count_mismatch,
            "count_check_skipped": self.count_check_skipped,
            "breaks": [
                {
                    "log_id": b.log_id,
                    "reason": b.reason,
                    "expected": b.expected,
                    "actual": b.actual,
                }
                for b in self.breaks
            ],
        }


def verify_audit_log_chain(
    logs: list[AuditLogModel],
    *,
    decision_count: int | None = None,
) -> AuditIntegrityResult:
    """Walk audit logs in order and verify hash-chain continuity."""
    breaks: list[AuditChainBreak] = []
    expected_prev_hash: str | None = None

    for log in logs:
        if log.previous_log_hash != expected_prev_hash:
            breaks.append(
                AuditChainBreak(
                    log_id=log.log_id,
                    reason="previous_log_hash mismatch",
                    expected=expected_prev_hash,
                    actual=log.previous_log_hash,
                )
            )
        expected_prev_hash = log.compute_hash()

    decision_audit_count = sum(1 for log in logs if log.action in DECISION_AUDIT_ACTIONS)
    count_mismatch = False
    count_check_skipped = decision_count is None or decision_audit_count == 0
    if not count_check_skipped and decision_count is not None:
        count_mismatch = decision_audit_count != decision_count

    ok = not breaks and not count_mismatch
    return AuditIntegrityResult(
        ok=ok,
        log_count=len(logs),
        decision_count=decision_count,
        decision_audit_count=decision_audit_count if decision_audit_count else None,
        count_mismatch=count_mismatch,
        count_check_skipped=count_check_skipped,
        breaks=breaks,
    )


def log_audit_event(
    db,
    action: str,
    entity_id: str | None = None,
    details: dict | None = None,
    *,
    commit: bool = True,
) -> AuditLogModel:
    from sqlalchemy import desc

    if details is None:
        details = {}

    prev_log = db.query(AuditLogModel).order_by(desc(AuditLogModel.log_id)).first()
    prev_hash = prev_log.compute_hash() if prev_log else None

    new_log = AuditLogModel(
        action=action,
        entity_id=entity_id,
        details=details,
        previous_log_hash=prev_hash
    )
    db.add(new_log)
    if commit:
        db.commit()
        db.refresh(new_log)
    return new_log

class EvalGroundTruthModel(Base):
    __tablename__ = "eval_ground_truth"
    event_id = Column(String, primary_key=True)
    is_malicious = Column(Boolean, nullable=False)
    scenario = Column(String, nullable=False)

class ContainmentQueueModel(Base):
    __tablename__ = "containment_queue"
    queue_id = Column(Integer, primary_key=True, autoincrement=True)
    decision_id = Column(String, nullable=False)
    entity_id = Column(String, nullable=False)
    action = Column(String, nullable=False)
    status = Column(String, default="pending", nullable=False)
    queued_at = Column(DateTime, default=datetime.utcnow, nullable=False)

class ScoringConfigModel(Base):
    __tablename__ = "scoring_configs"
    version = Column(String, primary_key=True)
    config_hash = Column(String, nullable=False, unique=True)
    previous_config_hash = Column(String, nullable=True)
    author = Column(String, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
    change_reason = Column(String, nullable=False)
    config_data = Column(JSONB, nullable=False)

class AlertWorkflowStateModel(Base):
    __tablename__ = "alert_workflow_state"
    decision_id = Column(String, primary_key=True)
    entity_id = Column(String, nullable=False, index=True)
    # new | acknowledged | investigating | cleared | auto_resolved
    state = Column(String, nullable=False, default="new")
    assignee = Column(String, nullable=True)
    clear_reason = Column(String, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class StalenessHaltExtensionModel(Base):
    __tablename__ = "staleness_halt_extensions"
    extension_id = Column(Integer, primary_key=True, autoincrement=True)
    entity_id = Column(String, nullable=False, index=True)
    justification = Column(String, nullable=False)
    extended_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    expires_at = Column(DateTime, nullable=False)
