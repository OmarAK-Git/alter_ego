from sqlalchemy import Column, String, DateTime, Float, Boolean, Integer
from sqlalchemy.dialects.postgresql import JSONB, ARRAY
from pgvector.sqlalchemy import Vector
from core.database import Base
try:
    from core.database import SQLiteVector
except ImportError:
    SQLiteVector = None
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
    VectorType = Vector(768) if (Vector and not SQLiteVector) else (SQLiteVector if SQLiteVector else JSONB)
    
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
    embedding_model_id = Column(String, default="nomic-embed-text", nullable=False)
    embedding_model_version = Column(String, default="1.0", nullable=False)
    embedding_dimensionality = Column(Integer, default=768, nullable=False)
    embedding_input_normalizer_version = Column(String, default="1.0", nullable=False)

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
    flags = Column(JSONB, nullable=False)

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
