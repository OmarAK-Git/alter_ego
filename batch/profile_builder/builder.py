import os
import json
import duckdb
import re
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import select, desc
from pathlib import Path

from core.database import SessionLocal
from core.models import ResolvedEventModel, ProfileArtifactModel, DecisionRecordModel
from core.schemas.profiles import ProfileArtifact
from core.math_utils import get_laplace_prob, compute_kl_divergence

def extract_role(entity_id: str, entity_type: str) -> str:
    if entity_type == "service_account":
        return "service_account"
    # Expected format: user_engineer_1
    match = re.match(r"user_([a-z]+)_", entity_id)
    if match:
        return match.group(1)
    return "unknown"

def build_profiles(db: Session | None = None, drift_compare_n: int = 5) -> int:
    if db is None:
        db_session = SessionLocal()
    else:
        db_session = db
        
    temp_file = Path("temp_events_for_duckdb.jsonl")
    try:
        # 1. Identify blocked entities (Active-alert profile-build blocking)
        blocked_entities_stmt = select(DecisionRecordModel.entity_id).where(DecisionRecordModel.is_anomaly == True)
        blocked_entities = set(db_session.execute(blocked_entities_stmt).scalars().all())

        # 2. Fetch resolved events excluding simulation partition
        stmt = select(ResolvedEventModel).where(ResolvedEventModel.simulation_partition == False)
        events = db_session.execute(stmt).scalars().all()
        
        if not events:
            return 0
            
        # Write to JSONL for DuckDB, injecting role
        with open(temp_file, "w") as f:
            for e in events:
                if e.entity_id in blocked_entities:
                    continue # Skip active-alert entities
                    
                data = {
                    "event_id": e.event_id,
                    "timestamp": e.timestamp.isoformat(),
                    "entity_id": e.entity_id,
                    "entity_type": e.entity_type,
                    "role": extract_role(e.entity_id, e.entity_type),
                    "action": e.event_data.get("action"),
                    "endpoint_id": e.event_data.get("endpoint_id"),
                    "process_name": e.event_data.get("process_name"),
                    "hour_of_day": e.timestamp.hour
                }
                f.write(json.dumps(data) + "\n")
                
        # 3. DuckDB Aggregation
        con = duckdb.connect()
        
        # --- Cohort Hierarchies ---
        # Parent Cohort (entity_type)
        parent_cohort_query = f"""
        SELECT 
            entity_type,
            histogram(hour_of_day) as hours,
            histogram(endpoint_id) as endpoints,
            histogram(process_name) as processes
        FROM read_json_auto('{temp_file}')
        GROUP BY entity_type
        """
        parent_res = con.execute(parent_cohort_query).fetchall()
        parent_cohorts = {}
        for row in parent_res:
            parent_cohorts[row[0]] = {
                "login_hours": {str(k): int(v) for k, v in row[1].items()} if isinstance(row[1], dict) else {},
                "endpoints": {str(k): int(v) for k, v in row[2].items() if k is not None} if isinstance(row[2], dict) else {},
                "process_names": {str(k): int(v) for k, v in row[3].items() if k is not None} if isinstance(row[3], dict) else {}
            }
            
        # Primary Cohort (role)
        primary_cohort_query = f"""
        SELECT 
            role,
            histogram(hour_of_day) as hours,
            histogram(endpoint_id) as endpoints,
            histogram(process_name) as processes
        FROM read_json_auto('{temp_file}')
        GROUP BY role
        """
        primary_res = con.execute(primary_cohort_query).fetchall()
        primary_cohorts = {}
        for row in primary_res:
            primary_cohorts[row[0]] = {
                "login_hours": {str(k): int(v) for k, v in row[1].items()} if isinstance(row[1], dict) else {},
                "endpoints": {str(k): int(v) for k, v in row[2].items() if k is not None} if isinstance(row[2], dict) else {},
                "process_names": {str(k): int(v) for k, v in row[3].items() if k is not None} if isinstance(row[3], dict) else {}
            }
            
        # Global Terminus Fallback
        global_query = f"""
        SELECT 
            histogram(hour_of_day) as hours,
            histogram(endpoint_id) as endpoints,
            histogram(process_name) as processes
        FROM read_json_auto('{temp_file}')
        """
        global_res = con.execute(global_query).fetchone()
        global_cohort = {
            "login_hours": {str(k): int(v) for k, v in global_res[0].items()} if global_res and isinstance(global_res[0], dict) else {},
            "endpoints": {str(k): int(v) for k, v in global_res[1].items() if k is not None} if global_res and isinstance(global_res[1], dict) else {},
            "process_names": {str(k): int(v) for k, v in global_res[2].items() if k is not None} if global_res and isinstance(global_res[2], dict) else {}
        }
        
        # --- Entity Local Profiles ---
        query = f"""
        SELECT 
            entity_id,
            MAX(entity_type) as entity_type,
            MAX(role) as role,
            MIN(CAST(timestamp AS TIMESTAMP)) as window_start,
            MAX(CAST(timestamp AS TIMESTAMP)) as window_end,
            COUNT(*) as total_events,
            histogram(hour_of_day) as login_hours,
            histogram(endpoint_id) as endpoints,
            histogram(process_name) as process_names
        FROM read_json_auto('{temp_file}')
        GROUP BY entity_id
        """
        
        result = con.execute(query).fetchall()
        
        profile_version = f"v_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
        count = 0
        
        # Save cohort distributions
        cohorts = {
            "primary": primary_cohorts,
            "parent": parent_cohorts,
            "terminus": global_cohort
        }
        
        for row in result:
            entity_id = row[0]
            entity_type = row[1]
            role = row[2]
            window_start = row[3]
            window_end = row[4]
            total_events = int(row[5])
            
            login_hours = {str(k): int(v) for k, v in row[6].items()} if isinstance(row[6], dict) else {}
            endpoints = {str(k): int(v) for k, v in row[7].items() if k is not None} if isinstance(row[7], dict) else {}
            process_names = {str(k): int(v) for k, v in row[8].items() if k is not None} if isinstance(row[8], dict) else {}

            features = {
                "total_events": total_events,
                "login_hours": login_hours,
                "endpoints": endpoints,
                "process_names": process_names,
                "role": role,
                "cohort_data": cohorts # Store for the scorer to do confidence-adaptive fallback
            }
            
            # --- Cumulative Drift Detection (KL-Divergence) ---
            # Fetch last N profiles for this entity to calculate delta against an aggregated baseline
            last_prof_stmt = select(ProfileArtifactModel).where(
                ProfileArtifactModel.entity_id == entity_id
            ).order_by(desc(ProfileArtifactModel.created_at)).limit(drift_compare_n)
            last_profiles = db_session.execute(last_prof_stmt).scalars().all()
            
            drift_score = 0.0
            if last_profiles:
                # Aggregate histograms from last N profiles
                agg_hours = {}
                agg_procs = {}
                for p in last_profiles:
                    p_hours = p.features.get("login_hours", {})
                    p_procs = p.features.get("process_names", {})
                    for k, v in p_hours.items():
                        agg_hours[k] = agg_hours.get(k, 0) + v
                    for k, v in p_procs.items():
                        agg_procs[k] = agg_procs.get(k, 0) + v
                
                # Calculate KL-Divergence between new histograms and aggregated old histograms
                kl_sum = 0.0
                
                def calc_feature_kl(new_hist, old_hist, vocab_size):
                    total_new = sum(new_hist.values())
                    total_old = sum(old_hist.values())
                    if total_new == 0 or total_old == 0:
                        return 0.0
                        
                    kl = 0.0
                    all_keys = set(new_hist.keys()) | set(old_hist.keys())
                    for k in all_keys:
                        p_prob = get_laplace_prob(new_hist.get(k, 0), total_new, vocab_size)
                        q_prob = get_laplace_prob(old_hist.get(k, 0), total_old, vocab_size)
                        kl += compute_kl_divergence(p_prob, q_prob)
                    return kl
                
                # Weight drift contributions
                kl_sum += calc_feature_kl(login_hours, agg_hours, 24) * 0.5
                kl_sum += calc_feature_kl(process_names, agg_procs, 500) * 1.5
                
                drift_score = kl_sum
                
            features["cumulative_drift"] = drift_score
            
            artifact = ProfileArtifact(
                entity_id=entity_id,
                entity_type=entity_type,
                profile_version=profile_version,
                created_at=datetime.utcnow(),
                data_window_start=window_start,
                data_window_end=window_end,
                features=features,
                embedding_model_id="text-embedding-3-small",
                embedding_model_version="1.0",
                embedding_dimensionality=1536
            )
            
            db_profile = ProfileArtifactModel(
                profile_version=f"{artifact.entity_id}_{profile_version}",
                entity_id=artifact.entity_id,
                entity_type=artifact.entity_type,
                created_at=artifact.created_at,
                data_window_start=artifact.data_window_start,
                data_window_end=artifact.data_window_end,
                features=artifact.features,
                embedding_model_id=artifact.embedding_model_id,
                embedding_model_version=artifact.embedding_model_version,
                embedding_dimensionality=artifact.embedding_dimensionality
            )
            db_session.merge(db_profile)
            count += 1
            
        db_session.commit()
        return count
        
    finally:
        if db is None:
            db_session.close()
        if temp_file.exists():
            os.remove(temp_file)

if __name__ == "__main__":
    count = build_profiles()
    print(f"Built {count} profiles.")
