import yaml
import hashlib
import math
import json
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import select, desc
from pathlib import Path

from core.database import SessionLocal
from core.models import ResolvedEventModel, ProfileArtifactModel, DecisionRecordModel
from core.schemas.events import ResolvedEvent, Event
from core.schemas.profiles import ProfileArtifact
from core.schemas.decisions import DecisionRecord, FeatureContribution
from worker.recorder import record_decision
from core.math_utils import get_laplace_prob

def load_scoring_config() -> dict:
    config_path = Path(__file__).parent.parent / "config" / "scoring_config.yaml"
    with open(config_path, "r") as f:
        return yaml.safe_load(f)

def _get_cohort_histogram(feature_name: str, profile: ProfileArtifact) -> tuple[dict, str]:
    """Implements the 4-tier cohort fallback chain"""
    features = profile.features
    cohort_data = features.get("cohort_data", {})
    
    # Tier 1: Entity Local
    local_hist = features.get(feature_name, {})
    if sum(local_hist.values()) >= 10:
        return local_hist, "local"
        
    role = features.get("role", "unknown")
    entity_type = profile.entity_type
    
    # Tier 2: Primary Cohort (Role)
    primary_hist = cohort_data.get("primary", {}).get(role, {}).get(feature_name, {})
    if sum(primary_hist.values()) >= 100:
        return primary_hist, "primary"
        
    # Tier 3: Parent Cohort (Entity Type)
    parent_hist = cohort_data.get("parent", {}).get(entity_type, {}).get(feature_name, {})
    if sum(parent_hist.values()) >= 500:
        return parent_hist, "parent"
        
    # Tier 4: Global Terminus
    terminus_hist = cohort_data.get("terminus", {}).get(feature_name, {})
    return terminus_hist, "terminus"

def score_event(resolved_event: ResolvedEvent, profile: ProfileArtifact, config: dict) -> DecisionRecord:
    contributions = []
    total_score = 0.0
    flags = []
    
    features_config = config.get("features", {})
    
    def add_categorical_feature(feat_key: str, event_val: str, vocab_size: int, config_name: str):
        nonlocal total_score
        hist, source = _get_cohort_histogram(feat_key, profile)
        if source == "terminus" and "cohort_unsupported" not in flags:
            flags.append("cohort_unsupported")
            
        total_count = sum(hist.values())
        count = hist.get(event_val, 0)
        
        prob = get_laplace_prob(count, total_count, vocab_size)
        # Point scoring: info content -log2(P)
        raw_val = -math.log2(prob) if prob > 0 else 0
        
        weight = features_config.get(config_name, {}).get("weight", 1.0)
        score = raw_val * weight
        
        # elevated confidence floor if cohort unsupported
        conf = 1.0 if source == "local" else (0.8 if source in ["primary", "parent"] else 0.5)
        
        total_score += score
        contributions.append(FeatureContribution(
            feature_name=config_name, 
            raw_value=raw_val, 
            contribution_score=score, 
            confidence_weight=conf
        ))

    # 1. login_hour_rarity
    hour = str(resolved_event.timestamp.hour)
    add_categorical_feature("login_hours", hour, 24, "login_hour_rarity")

    # 2. endpoint_set_rarity
    if hasattr(resolved_event.event_data, 'endpoint_id'):
        endpoint = resolved_event.event_data.endpoint_id
        add_categorical_feature("endpoints", endpoint, 500, "endpoint_set_rarity")

    # 3. process_name_rarity
    if resolved_event.event_type == "process" and hasattr(resolved_event.event_data, 'process_name'):
        process = resolved_event.event_data.process_name
        add_categorical_feature("process_names", process, 1000, "process_name_rarity")

    # 4. command_line_embedding_similarity (Mock)
    if resolved_event.event_type == "process" and hasattr(resolved_event.event_data, 'command_line'):
        # Mock embedding distance since Phase 0.5 is not built
        cosine_dist = 0.1 
        weight = features_config.get("command_line_embedding_similarity", {}).get("weight", 2.0)
        score = cosine_dist * 50.0 * weight
        total_score += score
        contributions.append(FeatureContribution(feature_name="command_line_embedding_similarity", raw_value=cosine_dist, contribution_score=score, confidence_weight=1.0))

    # 5. service_account_execution_frequency_deviation
    if resolved_event.entity_type == "service_account" and resolved_event.event_type == "process":
        deviation = 0.2
        weight = features_config.get("service_account_execution_frequency_deviation", {}).get("weight", 2.0)
        score = deviation * 20.0 * weight
        total_score += score
        contributions.append(FeatureContribution(feature_name="service_account_execution_frequency_deviation", raw_value=deviation, contribution_score=score, confidence_weight=1.0))

    # 6. Cumulative Drift (Additive)
    drift = profile.features.get("cumulative_drift", 0.0)
    if drift > 0:
        weight = features_config.get("cumulative_drift", {}).get("weight", 5.0)
        score = drift * weight
        total_score += score
        contributions.append(FeatureContribution(feature_name="cumulative_drift", raw_value=drift, contribution_score=score, confidence_weight=1.0))

    threshold = config.get("anomaly_threshold", 75.0)
    is_anomaly = total_score >= threshold
    
    scoring_config_version = str(config.get("version", "1.0"))
    
    raw_id = f"{resolved_event.event_id}{profile.profile_version}{scoring_config_version}".encode('utf-8')
    decision_id = hashlib.sha256(raw_id).hexdigest()
    
    return DecisionRecord(
        decision_id=decision_id,
        event_id=resolved_event.event_id,
        entity_id=resolved_event.entity_id,
        timestamp=datetime.utcnow(),
        score=total_score,
        confidence=1.0,
        profile_version=profile.profile_version,
        scoring_config_version=scoring_config_version,
        contributions=contributions,
        is_anomaly=is_anomaly,
        flags=flags
    )

def process_unscored_events(db: Session | None = None) -> int:
    if db is None:
        db_session = SessionLocal()
    else:
        db_session = db
        
    config = load_scoring_config()
    count = 0
    try:
        stmt = select(ResolvedEventModel).outerjoin(
            DecisionRecordModel, ResolvedEventModel.event_id == DecisionRecordModel.event_id
        ).where(DecisionRecordModel.decision_id == None)
        
        events_to_score = db_session.execute(stmt).scalars().all()
        
        for db_event in events_to_score:
            prof_stmt = select(ProfileArtifactModel).where(
                ProfileArtifactModel.entity_id == db_event.entity_id
            ).order_by(desc(ProfileArtifactModel.created_at)).limit(1)
            
            db_profile = db_session.execute(prof_stmt).scalar_one_or_none()
            if not db_profile:
                continue
                
            event_data_dict = json.loads(db_event.event_data) if isinstance(db_event.event_data, str) else db_event.event_data

            event_obj = Event(
                event_id=db_event.event_id,
                timestamp=db_event.timestamp,
                event_type=db_event.event_type,
                raw_entity_id=db_event.raw_entity_id,
                simulation_partition=db_event.simulation_partition,
                event_data=event_data_dict
            )

            resolved_event = ResolvedEvent(
                event_id=db_event.event_id,
                timestamp=db_event.timestamp,
                event_type=db_event.event_type,
                raw_entity_id=db_event.raw_entity_id,
                entity_id=db_event.entity_id,
                entity_type=db_event.entity_type,
                resolution_confidence=db_event.resolution_confidence,
                simulation_partition=db_event.simulation_partition,
                event_data=event_obj.event_data
            )
            
            profile = ProfileArtifact(
                entity_id=db_profile.entity_id,
                entity_type=db_profile.entity_type,
                profile_version=db_profile.profile_version,
                created_at=db_profile.created_at,
                data_window_start=db_profile.data_window_start,
                data_window_end=db_profile.data_window_end,
                features=db_profile.features,
                embedding=db_profile.embedding,
                embedding_model_id=db_profile.embedding_model_id,
                embedding_model_version=db_profile.embedding_model_version,
                embedding_dimensionality=db_profile.embedding_dimensionality
            )
            
            decision = score_event(resolved_event, profile, config)
            record_decision(decision, db_session)
            count += 1
            
    finally:
        if db is None:
            db_session.close()
            
    return count

if __name__ == "__main__":
    count = process_unscored_events()
    print(f"Scored {count} events.")
