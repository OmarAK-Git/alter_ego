import json
import logging
import re
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from statistics import median

import duckdb
import numpy as np
import yaml
from sqlalchemy import and_, desc, select
from sqlalchemy.orm import Session

from core.database import SessionLocal
from core.models import DecisionRecordModel, ProfileArtifactModel, ResolvedEventModel
from core.schemas.profiles import (
    DEFAULT_EMBEDDING_DIMENSIONALITY,
    DEFAULT_EMBEDDING_MODEL_ID,
    DEFAULT_EMBEDDING_MODEL_VERSION,
)
from core.math_utils import compute_distribution_kl, exponential_decay
from worker.vectorizer import NORMALIZER_VERSION, compute_cosine_distance, vectorize_command_line

logger = logging.getLogger(__name__)

def extract_role(entity_id: str, entity_type: str) -> str:
    if entity_type == "service_account":
        return "service_account"
    match = re.match(r"user_([a-z]+)_", entity_id)
    if match:
        return match.group(1)
    return "unknown"

def parse_duckdb_histogram(hist_data) -> dict:
    """Safely parse DuckDB histogram output into a string-keyed dict."""
    if not hist_data:
        return {}
    if isinstance(hist_data, dict):
        return {str(k): int(v) for k, v in hist_data.items()}
    if isinstance(hist_data, list):
        res = {}
        for item in hist_data:
            if isinstance(item, dict):
                res[str(item.get('key'))] = int(item.get('value', 0))
            elif isinstance(item, tuple) and len(item) == 2:
                res[str(item[0])] = int(item[1])
        return res
    return {}

def build_profiles(db: Session | None = None, drift_compare_n: int = 5, as_of: datetime | None = None) -> int:
    if db is None:
        db_session = SessionLocal()
    else:
        db_session = db
        
    if as_of is None:
        as_of = datetime.utcnow()

    # Load scoring config for weights and thresholds
    config_path = Path("config/scoring_config.yaml")
    with open(config_path, "r") as f:
        config = yaml.safe_load(f)
    
    drift_weights = config.get("drift_weights", {
        "login_hour": 1.0, "geolocation": 1.0, "endpoint_set": 1.0, "process_name": 1.0, "embedding": 2.0
    })
    drift_threshold = config.get("drift_threshold", 45.0)
    history_count = config.get("drift_comparison_history_count", 5)
    half_life = config.get("drift_half_life_days", 7.0)
    laplace_alpha = config.get("laplace_alpha", 1.0)

    # Fix #7 — initialize temp file paths before try block to prevent NameError in finally
    temp_file_hist: Path | None = None
    temp_file_recent: Path | None = None
    try:
        # Check for active alerts in the new workflow state model
        from core.models import AlertWorkflowStateModel
        blocked_entities_stmt = select(AlertWorkflowStateModel.entity_id).where(
            AlertWorkflowStateModel.state.in_(["new", "acknowledged", "investigating"])
        )
        blocked_entities = set(db_session.execute(blocked_entities_stmt).scalars().all())

        window_days = config.get("max_replay_window_days", 30)
        recent_days = config.get("recent_drift_window_days", 3)
        window_start_limit = as_of - timedelta(days=window_days)
        recent_start_limit = as_of - timedelta(days=recent_days)

        # Historical window (for profile content)
        stmt_hist = select(ResolvedEventModel).where(
            and_(
                ResolvedEventModel.simulation_partition == "production",
                ResolvedEventModel.timestamp <= as_of,
                ResolvedEventModel.timestamp >= window_start_limit
            )
        )
        
        # Recent window (for drift detection)
        stmt_recent = select(ResolvedEventModel).where(
            and_(
                ResolvedEventModel.simulation_partition == "production",
                ResolvedEventModel.timestamp <= as_of,
                ResolvedEventModel.timestamp >= recent_start_limit
            )
        )
        
        import time
        t0 = time.time()
        events_hist = db_session.execute(stmt_hist).scalars().all()
        events_recent = db_session.execute(stmt_recent).scalars().all()
        logger.info(f"Fetched {len(events_hist)} hist and {len(events_recent)} recent events in {time.time()-t0:.2f}s")
        
        if not events_hist:
            return 0
            
        temp_file_hist = Path(f"temp_events_hist_{uuid.uuid4().hex}.jsonl")
        temp_file_recent = None
        if events_recent:
            temp_file_recent = Path(f"temp_events_recent_{uuid.uuid4().hex}.jsonl")
        
        t1 = time.time()
        def write_jsonl(path, evts):
            with open(path, "w") as f:
                for e in evts:
                    data = {
                        "event_id": e.event_id,
                        "timestamp": e.timestamp.isoformat(),
                        "entity_id": e.entity_id,
                        "entity_type": e.entity_type,
                        "role": extract_role(e.entity_id, e.entity_type),
                        "action": e.event_data.get("action"),
                        "endpoint_id": e.event_data.get("endpoint_id"),
                        "process_name": e.event_data.get("process_name"),
                        "command_line": e.event_data.get("command_line", ""),
                        "geolocation": e.event_data.get("geolocation"),
                        "hour_of_day": e.timestamp.hour
                    }
                    f.write(json.dumps(data) + "\n")
        
        write_jsonl(temp_file_hist, events_hist)
        if events_recent:
            write_jsonl(temp_file_recent, events_recent)
        logger.info(f"Wrote temp JSONLs in {time.time()-t1:.2f}s")
                
        con = duckdb.connect()
        
        # Fix #6 — exclude blocked entities from cohort histograms so that an
        # attacker's lateral-movement events cannot inflate cohort baselines and
        # suppress alerts for complicit/adjacent accounts.
        blocked_filter = ""
        params = []
        if blocked_entities:
            placeholders = ",".join(["?"] * len(blocked_entities))
            blocked_filter = f"WHERE entity_id NOT IN ({placeholders})"
            params = list(blocked_entities)

        parent_cohort_query = f"SELECT entity_type, histogram(hour_of_day), histogram(endpoint_id), histogram(process_name), histogram(geolocation) FROM read_json_auto('{temp_file_hist}') {blocked_filter} GROUP BY entity_type"
        parent_res = con.execute(parent_cohort_query, params).fetchall()
        parent_cohorts = {row[0]: {"login_hours": parse_duckdb_histogram(row[1]), "endpoints": parse_duckdb_histogram(row[2]), "process_names": parse_duckdb_histogram(row[3]), "geolocations": parse_duckdb_histogram(row[4])} for row in parent_res}

        primary_cohort_query = f"SELECT role, histogram(hour_of_day), histogram(endpoint_id), histogram(process_name), histogram(geolocation) FROM read_json_auto('{temp_file_hist}') {blocked_filter} GROUP BY role"
        primary_res = con.execute(primary_cohort_query, params).fetchall()
        primary_cohorts = {row[0]: {"login_hours": parse_duckdb_histogram(row[1]), "endpoints": parse_duckdb_histogram(row[2]), "process_names": parse_duckdb_histogram(row[3]), "geolocations": parse_duckdb_histogram(row[4])} for row in primary_res}

        global_res = con.execute(f"SELECT histogram(hour_of_day), histogram(endpoint_id), histogram(process_name), histogram(geolocation) FROM read_json_auto('{temp_file_hist}') {blocked_filter}", params).fetchone()
        global_cohort = {"login_hours": parse_duckdb_histogram(global_res[0]), "endpoints": parse_duckdb_histogram(global_res[1]), "process_names": parse_duckdb_histogram(global_res[2]), "geolocations": parse_duckdb_histogram(global_res[3])} if global_res else {"login_hours": {}, "endpoints": {}, "process_names": {}, "geolocations": {}}
        
        # HISTORICAL PROFILE AGGREGATION
        query_hist = f"SELECT entity_id, MAX(entity_type), MAX(role), MIN(CAST(timestamp AS TIMESTAMP)), MAX(CAST(timestamp AS TIMESTAMP)), COUNT(*), histogram(hour_of_day), histogram(endpoint_id), histogram(process_name), histogram(geolocation), list(command_line) FROM read_json_auto('{temp_file_hist}') GROUP BY entity_id"
        result_hist = con.execute(query_hist).fetchall()
        
        # RECENT BEHAVIOR AGGREGATION (for drift)
        if events_recent:
            query_recent = f"SELECT entity_id, histogram(hour_of_day), histogram(endpoint_id), histogram(process_name), histogram(geolocation), list(command_line) FROM read_json_auto('{temp_file_recent}') GROUP BY entity_id"
            result_recent_rows = con.execute(query_recent).fetchall()
            recent_features_map = {row[0]: row[1:] for row in result_recent_rows}
        else:
            recent_features_map = {}
        # Cleanup
        for p in [temp_file_hist, temp_file_recent]:
            if p and p.exists():
                p.unlink()
        
        build_timestamp = datetime.utcnow()
        profile_version_suffix = build_timestamp.strftime('%Y%m%d%H%M%S')
        count = 0
        cohorts = {"primary": primary_cohorts, "parent": parent_cohorts, "terminus": global_cohort}
        
        # Phase 1: Compute Raw Drifts (Recent vs Historical)
        raw_drift_records = []
        for row in result_hist:
            entity_id, entity_type, role, window_start, window_end, total_events, login_hours, endpoints, process_names, geolocations, cmd_lines = row
            total_events = int(total_events)
            
            # 1. Profile Features (30-day window)
            cur_login_hours = parse_duckdb_histogram(login_hours)
            cur_endpoints = parse_duckdb_histogram(endpoints)
            cur_process_names = parse_duckdb_histogram(process_names)
            cur_geolocations = parse_duckdb_histogram(geolocations)
            
            vectors = [vectorize_command_line(cmd) for cmd in cmd_lines if cmd]
            centroid_arr = np.mean(vectors, axis=0) if vectors else None
            if centroid_arr is not None:
                c_norm = np.linalg.norm(centroid_arr)
                if c_norm > 0:
                    centroid_arr = centroid_arr / c_norm

            # 2. Recent Features (3-day window) - ONLY for drift
            recent_row = recent_features_map.get(entity_id)
            if recent_row:
                rec_login_hours, rec_endpoints, rec_process_names, rec_geolocations, rec_cmd_lines = recent_row
                rec_login_hours = parse_duckdb_histogram(rec_login_hours)
                rec_endpoints = parse_duckdb_histogram(rec_endpoints)
                rec_process_names = parse_duckdb_histogram(rec_process_names)
                rec_geolocations = parse_duckdb_histogram(rec_geolocations)
                
                rec_vectors = [vectorize_command_line(cmd) for cmd in rec_cmd_lines if cmd]
                rec_centroid = np.mean(rec_vectors, axis=0) if rec_vectors else None
                if rec_centroid is not None:
                    rc_norm = np.linalg.norm(rec_centroid)
                    if rc_norm > 0:
                        rec_centroid = rec_centroid / rc_norm
            else:
                # No recent activity? Use current 30d as fallback (shouldn't happen if they have hist)
                rec_login_hours, rec_endpoints, rec_process_names, rec_geolocations, rec_centroid = cur_login_hours, cur_endpoints, cur_process_names, cur_geolocations, centroid_arr

            # 3. Retrieve Historical Baseline (Previous Profile)
            prev_clean_stmt = select(ProfileArtifactModel).where(
                and_(
                    ProfileArtifactModel.entity_id == entity_id,
                    ProfileArtifactModel.is_shadow.is_(False),
                    ProfileArtifactModel.promoted_at.isnot(None),
                )
            ).order_by(desc(ProfileArtifactModel.data_window_end)).limit(history_count)
            prev_profiles = db_session.execute(prev_clean_stmt).scalars().all()
            
            _feature_drifts = []
            if prev_profiles:
                deltas = {"login_hour": [], "geolocation": [], "endpoint_set": [], "process_name": [], "embedding": []}
                for prev in prev_profiles:
                    deltas["login_hour"].append(compute_distribution_kl(rec_login_hours, prev.features.get("login_hours", {}), alpha=laplace_alpha))
                    deltas["geolocation"].append(compute_distribution_kl(rec_geolocations, prev.features.get("geolocations", {}), alpha=laplace_alpha))
                    deltas["endpoint_set"].append(compute_distribution_kl(rec_endpoints, prev.features.get("endpoints", {}), alpha=laplace_alpha))
                    deltas["process_name"].append(compute_distribution_kl(rec_process_names, prev.features.get("process_names", {}), alpha=laplace_alpha))
                    
                    if rec_centroid is not None and prev.embedding is not None:
                        deltas["embedding"].append(compute_cosine_distance(rec_centroid, np.array(prev.embedding)))
                
                avg_deltas = {k: float(np.mean(v)) if v else 0.0 for k, v in deltas.items()}
                raw_drift = sum(avg_deltas[k] * drift_weights.get(k, 1.0) for k in avg_deltas)
            else:
                raw_drift = 0.0

            raw_drift_records.append({
                "entity_id": entity_id,
                "entity_type": entity_type,
                "role": role,
                "raw_drift": raw_drift,
                # Store full 30d features in profile
                "features": {
                    "total_events": total_events,
                    "login_hours": cur_login_hours,
                    "geolocations": cur_geolocations,
                    "endpoints": cur_endpoints,
                    "process_names": cur_process_names
                },
                "embedding": centroid_arr.tolist() if centroid_arr is not None else None,
                "window_start": window_start,
                "window_end": window_end
            })

        # Phase 2: Cohort Normalization
        cohort_drifts = {}
        for rec in raw_drift_records:
            cohort_drifts.setdefault(rec["role"], []).append(rec["raw_drift"])
        
        # Fix #4 — MIN_NORM_COHORT guard: single-entity roles get cohort_medians[role]
        # = their own drift, making norm_drift = 0 always — permanently disabling drift
        # detection for privileged solo accounts. Fall back to global cross-role median.
        MIN_NORM_COHORT = 3
        all_drifts_flat = [d for drifts in cohort_drifts.values() for d in drifts]
        global_drift_median = median(all_drifts_flat) if all_drifts_flat else 0.0
        cohort_medians = {
            r: (median(drifts) if len(drifts) >= MIN_NORM_COHORT else global_drift_median)
            for r, drifts in cohort_drifts.items()
        }

        # Phase 3: Update Accumulators and Persist
        for rec in raw_drift_records:
            entity_id = rec["entity_id"]
            raw_drift = rec["raw_drift"]
            norm_drift = raw_drift - cohort_medians.get(rec["role"], 0.0)
            
            # Get latest profile (even if shadow) to find accumulator state
            latest_any = db_session.query(ProfileArtifactModel).filter(
                ProfileArtifactModel.entity_id == entity_id
            ).order_by(desc(ProfileArtifactModel.data_window_end)).first()
            
            prev_accumulator = latest_any.features.get("cumulative_drift", 0.0) if latest_any else 0.0
            time_delta = 0.0
            if latest_any:
                dt = rec["window_end"] - latest_any.data_window_end
                time_delta = dt.total_seconds() / 86400.0 # days
            
            new_accumulator = exponential_decay(prev_accumulator, norm_drift, half_life, time_delta)
            # Ensure it doesn't go negative
            new_accumulator = max(0.0, new_accumulator)
            
            logger.info(f"Entity {entity_id} drift: raw={raw_drift:.2f}, normalized={norm_drift:.2f}, accum={new_accumulator:.2f}")

            features = {
                "total_events": rec["features"]["total_events"],
                "login_hours": rec["features"]["login_hours"],
                "geolocations": rec["features"]["geolocations"],
                "endpoints": rec["features"]["endpoints"],
                "process_names": rec["features"]["process_names"],
                "role": rec["role"],
                "cohort_data": cohorts,
                "cumulative_drift": new_accumulator,
                "normalized_drift": norm_drift
            }
            
            is_shadow_profile = entity_id in blocked_entities
            promoted_at = as_of if not is_shadow_profile else None
            
            if not is_shadow_profile:
                prev_active = db_session.query(ProfileArtifactModel).filter(
                    and_(
                        ProfileArtifactModel.entity_id == entity_id,
                        ProfileArtifactModel.is_shadow.is_(False),
                        ProfileArtifactModel.promoted_at.isnot(None),
                        ProfileArtifactModel.superseded_at.is_(None),
                    )
                ).first()
                if prev_active:
                    prev_active.superseded_at = promoted_at

            # Ensure version uniqueness even within the same second
            profile_version = f"{entity_id}_{profile_version_suffix}_{uuid.uuid4().hex[:8]}"

            db_profile = ProfileArtifactModel(
                profile_version=profile_version,
                entity_id=entity_id,
                entity_type=entity_type,
                created_at=build_timestamp,
                data_window_start=rec["window_start"],
                data_window_end=rec["window_end"],
                promoted_at=promoted_at,
                superseded_at=None,
                is_shadow=is_shadow_profile,
                features=features,
                embedding=rec["embedding"],
                embedding_model_id=DEFAULT_EMBEDDING_MODEL_ID,
                embedding_model_version=DEFAULT_EMBEDDING_MODEL_VERSION,
                embedding_dimensionality=DEFAULT_EMBEDDING_DIMENSIONALITY,
                embedding_input_normalizer_version=NORMALIZER_VERSION
            )
            db_session.add(db_profile)
            
            # Emit Drift Decision if threshold crossed
            if new_accumulator >= drift_threshold:
                decision_id = f"drift_{profile_version}"
                contributions={"cumulative_drift": new_accumulator},
                db_decision = DecisionRecordModel(
                    decision_id=decision_id,
                    event_id="PROFILE_BUILD",
                    entity_id=entity_id,
                    timestamp=build_timestamp,
                    score=new_accumulator,
                    confidence=0.8, # Static confidence for drift engine
                    profile_version=profile_version,
                    scoring_config_version=config.get("version", "unknown"),
                    contributions=contributions,
                    is_anomaly=True,
                    cohort_used=rec["role"],
                    cohort_unsupported=False,
                    flags={"drift_alert": True, "prev_accumulator": prev_accumulator, "norm_drift": norm_drift}
                )
                db_session.add(db_decision)

            count += 1
            
        db_session.commit()
        return count
        
    finally:
        # Fix #7 — null-initialized above; safe even if exception raised before assignment
        for p in [temp_file_hist, temp_file_recent]:
            if p is not None and p.exists():
                p.unlink()
        if db is None:
            db_session.close()
