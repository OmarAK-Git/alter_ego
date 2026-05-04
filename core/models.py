from sqlalchemy import Column, String, DateTime, Float, Boolean, Integer
from sqlalchemy.dialects.postgresql import JSONB, ARRAY
from pgvector.sqlalchemy import Vector
from core.database import Base
from datetime import datetime

class EventModel(Base):
    __tablename__ = "events"
    event_id = Column(String, primary_key=True)
    timestamp = Column(DateTime, nullable=False)
    event_type = Column(String, nullable=False)
    raw_entity_id = Column(String, nullable=False)
    simulation_partition = Column(Boolean, default=False, nullable=False)
    event_data = Column(JSONB, nullable=False)

class ResolvedEventModel(Base):
    __tablename__ = "resolved_events"
    event_id = Column(String, primary_key=True)
    timestamp = Column(DateTime, nullable=False)
    event_type = Column(String, nullable=False)
    raw_entity_id = Column(String, nullable=False)
    entity_id = Column(String, nullable=False, index=True)
    entity_type = Column(String, nullable=False)
    resolution_confidence = Column(Float, nullable=False)
    simulation_partition = Column(Boolean, default=False, nullable=False)
    event_data = Column(JSONB, nullable=False)

class ProfileArtifactModel(Base):
    __tablename__ = "profiles"
    profile_version = Column(String, primary_key=True)
    entity_id = Column(String, nullable=False, index=True)
    entity_type = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    data_window_start = Column(DateTime, nullable=False)
    data_window_end = Column(DateTime, nullable=False)
    features = Column(JSONB, nullable=False)
    embedding = Column(Vector(1536), nullable=True) # For command_line_embedding_similarity
    embedding_model_id = Column(String, default="text-embedding-3-small", nullable=False)
    embedding_model_version = Column(String, default="1.0", nullable=False)
    embedding_dimensionality = Column(Integer, default=1536, nullable=False)

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
    flags = Column(ARRAY(String), nullable=False)

class ExplanationRecordModel(Base):
    __tablename__ = "explanations"
    decision_id = Column(String, primary_key=True)
    generated_at = Column(DateTime, nullable=False)
    model_id = Column(String, nullable=False)
    summary = Column(String, nullable=False)
    claims = Column(JSONB, nullable=False)
    counterfactual = Column(String, nullable=True)

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
