import yaml
import hashlib
import math
import json
import uuid
import numpy as np
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import select, desc, and_, func
from pathlib import Path

from core.database import SessionLocal
from core.models import ResolvedEventModel, ProfileArtifactModel, DecisionRecordModel
from core.schemas.events import ResolvedEvent, Event
from core.schemas.profiles import ProfileArtifact
from core.schemas.decisions import DecisionRecord, FeatureContribution
from worker.recorder import record_decision
from worker.profile_store import ProfileStore
from core.math_utils import get_laplace_prob, compute_kl_divergence
from worker.vectorizer import vectorize_command_line, compute_cosine_distance

# Caching for performance
_COHORT_MEMBERS_CACHE = {}
_NOVELTY_FRACTION_CACHE = {}

# Feature to DB field mapping for cohort novelty check
FEATURE_FIELD_MAP = {
    "login_hours": "hour",
    "geolocations": "geolocation",
    "endpoints": "endpoint_id",
    "process_names": "process_name"
}

def _get_cohort_members(db: Session, role: str, entity_type: str) -> list[str]:
    """Returns all entity IDs belonging to a specific cohort."""
    cache_key = (role, entity_type)
    if cache_key in _COHORT_MEMBERS_CACHE:
        return _COHORT_MEMBERS_CACHE[cache_key]
        
    # SQLite/Postgres compatible JSON extract
    stmt = select(ProfileArtifactModel.entity_id).where(
        and_(
            ProfileArtifactModel.entity_type == entity_type,
            func.json_extract(ProfileArtifactModel.features, '$.role') == role,
            ProfileArtifactModel.promoted_at != None
        )
    ).distinct()
    members = db.execute(stmt).scalars().all()
    _COHORT_MEMBERS_CACHE[cache_key] = members
    return members

def _get_novelty_fraction(db: Session, members: list[str], feature_name: str, value: str, window_days: int, current_ts: datetime) -> float:
    """Calculates what fraction of the cohort has exhibited this novel value in the window."""
    if not members: return 0.0
    # Window start date (rounded to hour to allow caching across close events)
    window_start = (current_ts - timedelta(days=window_days)).replace(minute=0, second=0, microsecond=0)
    role = "unknown" # Could pass this in for better cache key
    cache_key = (feature_name, value, tuple(sorted(members)), window_start)
    if cache_key in _NOVELTY_FRACTION_CACHE:
        return _NOVELTY_FRACTION_CACHE[cache_key]

    field = FEATURE_FIELD_MAP.get(feature_name)
    if not field: return 0.0
    
    # Base statement
    stmt = select(func.count(ResolvedEventModel.entity_id.distinct())).where(
        and_(
            ResolvedEventModel.entity_id.in_(members),
            ResolvedEventModel.timestamp >= window_start
        )
    )
    
    if field == "hour":
        stmt = stmt.where(func.strftime('%H', ResolvedEventModel.timestamp) == f"{int(value):02d}")
    else:
        # JSONB field check
        stmt = stmt.where(func.json_extract(ResolvedEventModel.event_data, f'$.{field}') == value)
        
    count = db.execute(stmt).scalar() or 0
    fraction = count / len(members)
    logger.debug(f"Novelty fraction for {feature_name}={value}: {count}/{len(members)} = {fraction}")
    _NOVELTY_FRACTION_CACHE[cache_key] = fraction
    return fraction

import logging
logger = logging.getLogger(__name__)


def load_scoring_config() -> dict:
    config_path = Path(__file__).parent.parent / "config" / "scoring_config.yaml"
    if not config_path.exists():
        return {"anomaly_threshold": 45.0, "version": "2.1", "features": {}}
    with open(config_path, "r") as f:
        return yaml.safe_load(f)

def _get_cohort_histogram(feature_name: str, profile: ProfileArtifact) -> tuple[dict, str]:
    features = profile.features
    cohort_data = features.get("cohort_data", {})
    local_hist = features.get(feature_name, {})
    if sum(local_hist.values()) >= 20: return local_hist, "local"
    role = features.get("role", "unknown")
    entity_type = profile.entity_type
    primary_hist = cohort_data.get("primary", {}).get(role, {}).get(feature_name, {})
    if sum(primary_hist.values()) >= 100: return primary_hist, "role_cohort"
    return cohort_data.get("terminus", {}).get(feature_name, {}), "terminus"

def compute_periodicity(db: Session, entity_id: str, event_time: datetime, window_minutes: int = 60) -> tuple[float, int]:
    stmt = select(ResolvedEventModel.timestamp).where(
        and_(ResolvedEventModel.entity_id == entity_id, ResolvedEventModel.timestamp < event_time, ResolvedEventModel.timestamp >= event_time - timedelta(minutes=window_minutes))
    ).order_by(ResolvedEventModel.timestamp)
    ts_list = db.execute(stmt).scalars().all()
    count = len(ts_list)
    if count < 2: return 0.0, count
    intervals = [(ts_list[i+1] - ts_list[i]).total_seconds() for i in range(len(ts_list)-1)]
    mean_int = sum(intervals) / len(intervals)
    if mean_int < 1.0: return 0.0, count
    cv = (math.sqrt(sum((x - mean_int)**2 for x in intervals) / len(intervals))) / mean_int
    return max(0.0, 1.0 - (cv / 0.3)), count

def score_event(db: Session, resolved_event: ResolvedEvent, profile: ProfileArtifact, config: dict) -> DecisionRecord:
    contributions = []
    features_config = config.get("features", {})
    alpha = config.get("laplace_alpha", 1.0)
    max_contrib = config.get("contribution_scale_max", 20.0)
    
    def get_event_field(field: str, default: str = "unknown") -> str:
        data = resolved_event.event_data
        if hasattr(data, field): return str(getattr(data, field))
        if isinstance(data, dict): return str(data.get(field, default))
        return default

    flags = []
    cohort_gate_config = config.get("cohort_gating_constants", {})
    max_changed_fraction = cohort_gate_config.get("max_changed_fraction", 0.2)
    min_cohort_size = cohort_gate_config.get("min_cohort_size", 10)
    gate_window = config.get("cohort_gate_window_days", 7)

    # Staleness Circuit Breaker (§9)
    max_staleness = config.get("max_profile_staleness_days", 14)
    time_since_profile = (resolved_event.timestamp - profile.data_window_end).total_seconds() / 86400.0
    if time_since_profile > max_staleness:
        flags.append("staleness_halt")
        # For staleness halt, we emit a zero-score record with the halt flag
        decision_id = hashlib.sha256(f"{resolved_event.event_id}HALT".encode('utf-8')).hexdigest()
        return DecisionRecord(
            decision_id=decision_id, event_id=resolved_event.event_id, entity_id=resolved_event.entity_id,
            timestamp=datetime.utcnow(), score=0.0, confidence=1.0,
            profile_version=profile.profile_version, scoring_config_version=str(config.get('version', '2.1')),
            contributions=[], is_anomaly=False, cohort_used="none", cohort_unsupported=True, flags=flags
        )

    def get_rarity_score(val, hist, vocab_size, weight_key, feature_name, baseline_bits=0):
        prob = get_laplace_prob(hist.get(val, 0), sum(hist.values()), vocab_size, alpha=alpha)
        rarity = -math.log2(prob) if prob > 0 else 0
        centered = max(0.0, rarity - baseline_bits)
        
        # Cohort Novelty Gate (§6.7)
        suppressed = False
        if centered > 0: # Novel behavior
            role = profile.features.get("role", "unknown")
            members = _get_cohort_members(db, role, resolved_event.entity_type)
            if len(members) >= min_cohort_size:
                fraction = _get_novelty_fraction(db, members, feature_name, val, gate_window, resolved_event.timestamp)
                if fraction > max_changed_fraction:
                    suppressed = True
                    flags.append(f"novelty_suppressed_{weight_key}")
                else:
                    logger.debug(f"Novelty {feature_name}={val} fraction {fraction} <= {max_changed_fraction}")
            else:
                # Small cohort - cannot suppress but flag for higher confidence requirement
                if role != "unknown":
                    flags.append(f"cohort_too_small_{weight_key}")

        weight = features_config.get(weight_key, {}).get("weight", 1.0)
        raw_weighted = centered * 0.5 * weight
        score = 0.0 if suppressed else min(max_contrib, raw_weighted)
        
        if not suppressed and raw_weighted > max_contrib: 
            flags.append(f"cap_hit_{weight_key}")
        return score, weight, (0.0 if suppressed else centered)

    # Features
    s1, _, c1 = get_rarity_score(str(resolved_event.timestamp.hour), _get_cohort_histogram("login_hours", profile)[0], 24, "login_hour_rarity", "login_hours", 10.0)
    s2, _, c2 = get_rarity_score(get_event_field("geolocation"), _get_cohort_histogram("geolocations", profile)[0], 100, "geolocation_rarity", "geolocations", 10.0)
    s3, _, c3 = get_rarity_score(get_event_field("endpoint_id"), _get_cohort_histogram("endpoints", profile)[0], 50, "endpoint_set_rarity", "endpoints", 10.0)
    s4, _, c4 = get_rarity_score(get_event_field("process_name"), _get_cohort_histogram("process_names", profile)[0], 1000, "process_name_rarity", "process_names", 10.0)
    
    # Embedding (Deterministic Vectorizer)
    cmd_line = get_event_field("command_line", "")
    event_vec = vectorize_command_line(cmd_line)
    
    # Get profile centroid. If none, distance is 1.0 (maximal novelty)
    profile_vec = np.array(profile.embedding) if profile.embedding else None
    
    if profile_vec is not None and len(profile_vec) == len(event_vec):
        dist = compute_cosine_distance(event_vec, profile_vec)
    else:
        dist = 0.0 # Suppress vector-distance contribution for cold-start events per Finding 2
        flags.append("cold_start_embedding_suppressed")
        
    weight_emb = features_config.get("command_line_embedding_similarity", {}).get("weight", 5.0)
    # Scale distance: 0.02 is the noise floor. 0.02 -> 0.1 delta produces a meaningful score.
    # (dist - 0.02) * 500.0 * weight_emb aligns with previous mock intensity (0.05 -> 15.0 pts at weight 1.0)
    raw_emb = (dist - 0.50) * 50.0 * weight_emb if dist > 0.50 else 0.0
    score_emb = min(max_contrib, raw_emb)
    if raw_emb > max_contrib: flags.append("cap_hit_embedding")

    # Periodicity
    score_period = 0.0; dev_period = 0.0; n_period = 0
    if resolved_event.entity_type == "service_account":
        dev_period, n_period = compute_periodicity(db, resolved_event.entity_id, resolved_event.timestamp)
        weight_period = features_config.get("service_account_execution_frequency_deviation", {}).get("weight", 5.0)
        raw_period = dev_period * 5.0 * weight_period
        score_period = min(max_contrib, raw_period)
        if raw_period > max_contrib: flags.append("cap_hit_periodicity")

    # Volume
    v_base = profile.features.get("total_events", 1) / 168.0
    v_delta = max(0.0, (1 - v_base) / max(1.0, v_base))
    weight_vol = features_config.get("total_volume_delta", {}).get("weight", 1.0)
    raw_vol = v_delta * 1.0 * weight_vol
    score_vol = min(10.0, raw_vol)

    # Drift Engine (§6.8)
    drift_accum = profile.features.get("cumulative_drift", 0.0)
    drift_threshold = config.get("drift_threshold", 45.0)
    weight_drift = features_config.get("drift_alert", {}).get("weight", 5.0)
    # If drift crossed threshold, add a heavy weight. Add dead-zone for low-level noise.
    score_drift = 0.0
    if drift_accum >= drift_threshold:
        score_drift = weight_drift
    elif drift_accum > (0.5 * drift_threshold):
        # Linear scale from 50% to 100% of threshold
        scale = (drift_accum - 0.5 * drift_threshold) / (0.5 * drift_threshold)
        score_drift = scale * weight_drift

    # Aggregation
    raw_total = s1 + s2 + s3 + s4 + score_emb + score_period + score_vol + score_drift
    
    contributions = [
        FeatureContribution(contribution_id=f"feat_hour_{uuid.uuid4().hex[:8]}", feature_name="login_hour_rarity", raw_value=c1, contribution_score=s1, confidence_weight=0.9),
        FeatureContribution(contribution_id=f"feat_geo_{uuid.uuid4().hex[:8]}", feature_name="geolocation_rarity", raw_value=c2, contribution_score=s2, confidence_weight=0.9),
        FeatureContribution(contribution_id=f"feat_end_{uuid.uuid4().hex[:8]}", feature_name="endpoint_set_rarity", raw_value=c3, contribution_score=s3, confidence_weight=0.9),
        FeatureContribution(contribution_id=f"feat_proc_{uuid.uuid4().hex[:8]}", feature_name="process_name_rarity", raw_value=c4, contribution_score=s4, confidence_weight=0.9),
        FeatureContribution(contribution_id=f"feat_embed_{uuid.uuid4().hex[:8]}", feature_name="command_line_embedding_similarity", raw_value=float(dist), contribution_score=score_emb, confidence_weight=0.7),
        FeatureContribution(contribution_id=f"feat_vol_{uuid.uuid4().hex[:8]}", feature_name="total_volume_delta", raw_value=v_delta, contribution_score=score_vol, confidence_weight=0.6),
        FeatureContribution(contribution_id=f"feat_drift_{uuid.uuid4().hex[:8]}", feature_name="drift_alert", raw_value=float(drift_accum), contribution_score=score_drift, confidence_weight=0.8)
    ]
    if resolved_event.entity_type == "service_account":
        contributions.append(FeatureContribution(contribution_id=f"feat_period_{uuid.uuid4().hex[:8]}", feature_name="service_account_execution_frequency_deviation", raw_value=dev_period, contribution_score=score_period, confidence_weight=0.8 if n_period >= 5 else 0.1))

    conf_sum = sum(abs(c.contribution_score) * c.confidence_weight for c in contributions)
    weight_sum = sum(abs(c.contribution_score) for c in contributions)
    decision_confidence = conf_sum / weight_sum if weight_sum > 0 else 1.0
    
    # Confidence-Gated Damping
    threshold = config.get("anomaly_threshold", 45.0)
    if decision_confidence < config.get("confidence_floor", 0.6):
        total_score = min(threshold - 5.0, raw_total)
        flags.append("low_confidence_damping_applied")
    else:
        total_score = raw_total

    is_anomaly = total_score >= threshold
    if is_anomaly:
        logger.info(f"ANOMALY DETECTED: entity={resolved_event.entity_id} score={total_score:.2f} conf={decision_confidence:.2f}")
        for c in contributions:
            logger.info(f"  - {c.feature_name}: raw={c.raw_value:.2f} score={c.contribution_score:.2f}")
        flags.append("simulated_containment_queued")
    
    decision_id = hashlib.sha256(f"{resolved_event.event_id}{profile.profile_version}{str(config.get('version', '2.1'))}".encode('utf-8')).hexdigest()
    
    return DecisionRecord(
        decision_id=decision_id, event_id=resolved_event.event_id, entity_id=resolved_event.entity_id,
        timestamp=datetime.utcnow(), score=total_score, confidence=decision_confidence,
        profile_version=profile.profile_version, scoring_config_version=str(config.get('version', '2.1')),
        contributions=contributions, is_anomaly=is_anomaly,
        cohort_used=_get_cohort_histogram("process_names", profile)[1], 
        cohort_unsupported=(_get_cohort_histogram("process_names", profile)[1] == "terminus"),
        flags=flags
    )

def process_unscored_events(db: Session | None = None) -> int:
    if db is None: db_session = SessionLocal()
    else: db_session = db
    config = load_scoring_config()
    profile_store = ProfileStore(db_session)
    count = 0
    try:
        stmt = select(ResolvedEventModel).outerjoin(DecisionRecordModel, ResolvedEventModel.event_id == DecisionRecordModel.event_id).where(DecisionRecordModel.decision_id == None).order_by(ResolvedEventModel.timestamp)
        for db_event in db_session.execute(stmt).scalars().all():
            profile = profile_store.get_active_profile(db_event.entity_id, db_event.timestamp)
            if not profile: continue
            resolved_event = ResolvedEvent(
                event_id=db_event.event_id, timestamp=db_event.timestamp, event_type=db_event.event_type,
                raw_entity_id=db_event.raw_entity_id, entity_id=db_event.entity_id,
                entity_type=db_event.entity_type, resolution_confidence=db_event.resolution_confidence,
                simulation_partition=db_event.simulation_partition, event_data=json.loads(db_event.event_data) if isinstance(db_event.event_data, str) else db_event.event_data
            )
            decision = score_event(db_session, resolved_event, profile, config)
            record_decision(decision, db_session)
            count += 1
    finally:
        if db is None: db_session.close()
    return count
