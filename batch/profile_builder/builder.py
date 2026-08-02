import json
import logging
import math
import os
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

from core.attestation import (
    ANCHOR_HISTORY_COUNT,
    MIN_DWELL_BUILDS,
    QUIET_WINDOW_DAYS,
    attest,
)
from core.database import SessionLocal
from core.models import (
    AlertWorkflowStateModel,
    DecisionRecordModel,
    ProfileArtifactModel,
    ResolvedEventModel,
    log_audit_event,
)
from core.schemas.profiles import (
    DEFAULT_EMBEDDING_DIMENSIONALITY,
    DEFAULT_EMBEDDING_MODEL_ID,
    DEFAULT_EMBEDDING_MODEL_VERSION,
)
from core.geo_centroids import haversine_km, lookup_centroid
from core.math_utils import compute_distribution_kl, exponential_decay
from worker.vectorizer import NORMALIZER_VERSION, compute_cosine_distance, vectorize_command_line

logger = logging.getLogger(__name__)

# S5.6 — max_profile_build_block_days supervisor escalation (SPEC §5.5).
ACTIVE_ALERT_STATES = frozenset({"new", "acknowledged", "investigating"})
BUILD_BLOCK_SUPERVISOR_ESCALATION_FLAG = "profile_build_block_supervisor_escalation"
SUPERVISOR_ESCALATION_SLA_HOURS = 24
AUTO_RESOLVED_AUDIT_ACTION = "alert_auto_resolved"
BUILD_BLOCK_ESCALATION_AUDIT_ACTION = "profile_build_block_mandatory_review"

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


def _block_days_for_entity(
    db_session: Session, alerts: list, as_of: datetime
) -> float:
    """Days since earliest active alert started build-blocking this entity."""
    earliest_start: datetime | None = None
    for alert in alerts:
        dec = db_session.get(DecisionRecordModel, alert.decision_id)
        start = dec.timestamp if dec is not None else alert.updated_at
        if earliest_start is None or start < earliest_start:
            earliest_start = start
    if earliest_start is None:
        return 0.0
    return (as_of - earliest_start).total_seconds() / 86400.0


def _flags_has_drift_alert(flags) -> bool:
    if isinstance(flags, dict):
        return bool(flags.get("drift_alert"))
    if isinstance(flags, list):
        return "drift_alert" in flags
    return False


def _entity_is_quiet(db_session: Session, entity_id: str, as_of: datetime) -> bool:
    """QUIET: no anomaly DecisionRecord for entity within trailing quiet_window_days."""
    cutoff = as_of - timedelta(days=QUIET_WINDOW_DAYS)
    recent = (
        db_session.query(DecisionRecordModel)
        .filter(
            DecisionRecordModel.entity_id == entity_id,
            DecisionRecordModel.is_anomaly.is_(True),
            DecisionRecordModel.timestamp > cutoff,
            DecisionRecordModel.timestamp <= as_of,
        )
        .first()
    )
    return recent is None


def _shadow_builds_during_block(
    db_session: Session, entity_id: str, block_start: datetime
) -> list[ProfileArtifactModel]:
    return (
        db_session.query(ProfileArtifactModel)
        .filter(
            ProfileArtifactModel.entity_id == entity_id,
            ProfileArtifactModel.is_shadow.is_(True),
            ProfileArtifactModel.created_at >= block_start,
        )
        .order_by(ProfileArtifactModel.created_at)
        .all()
    )


def _min_dwell_satisfied(
    db_session: Session, entity_id: str, block_start: datetime
) -> bool:
    shadows = _shadow_builds_during_block(db_session, entity_id, block_start)
    return len(shadows) >= MIN_DWELL_BUILDS


def _get_anchor_features(
    db_session: Session, entity_id: str, history_count: int = ANCHOR_HISTORY_COUNT
) -> dict:
    """Promoted profile features from history_count promotions back (P_{-n})."""
    rows = (
        db_session.query(ProfileArtifactModel)
        .filter(
            ProfileArtifactModel.entity_id == entity_id,
            ProfileArtifactModel.is_shadow.is_(False),
            ProfileArtifactModel.promoted_at.isnot(None),
        )
        .order_by(desc(ProfileArtifactModel.promoted_at))
        .limit(history_count)
        .all()
    )
    if not rows:
        return {}
    # Newest first; anchor is the oldest in the window (P_{-n} or earliest available).
    anchor = rows[-1]
    return anchor.features or {}


def _get_promoted_features(db_session: Session, entity_id: str) -> dict:
    row = (
        db_session.query(ProfileArtifactModel)
        .filter(
            ProfileArtifactModel.entity_id == entity_id,
            ProfileArtifactModel.is_shadow.is_(False),
            ProfileArtifactModel.promoted_at.isnot(None),
            ProfileArtifactModel.superseded_at.is_(None),
        )
        .first()
    )
    return (row.features if row else None) or {}


def _get_latest_shadow_features(db_session: Session, entity_id: str) -> dict:
    row = (
        db_session.query(ProfileArtifactModel)
        .filter(
            ProfileArtifactModel.entity_id == entity_id,
            ProfileArtifactModel.is_shadow.is_(True),
        )
        .order_by(desc(ProfileArtifactModel.created_at))
        .first()
    )
    return (row.features if row else None) or {}


def _refresh_or_open_drift_alert(
    db_session: Session,
    *,
    entity_id: str,
    blocked_entities: set[str],
    decision_id: str,
    build_timestamp: datetime,
    new_accumulator: float,
    profile_version: str,
    config: dict,
    role: str,
    prev_accumulator: float,
    norm_drift: float,
) -> None:
    """D1 hygiene: refresh existing drift-class workflow row when already blocked."""
    existing_drift_row = None
    if entity_id in blocked_entities:
        active_rows = (
            db_session.query(AlertWorkflowStateModel)
            .filter(
                AlertWorkflowStateModel.entity_id == entity_id,
                AlertWorkflowStateModel.state.in_(list(ACTIVE_ALERT_STATES)),
            )
            .all()
        )
        for row in active_rows:
            dec = db_session.get(DecisionRecordModel, row.decision_id)
            if dec is not None and _flags_has_drift_alert(dec.flags):
                existing_drift_row = (row, dec)
                break

    if existing_drift_row is not None:
        row, dec = existing_drift_row
        dec.score = new_accumulator
        dec.contributions = {"cumulative_drift": new_accumulator}
        flags = dict(dec.flags) if isinstance(dec.flags, dict) else {"drift_alert": True}
        flags.update(
            {
                "drift_alert": True,
                "prev_accumulator": prev_accumulator,
                "norm_drift": norm_drift,
                "refreshed_at": build_timestamp.isoformat(),
            }
        )
        dec.flags = flags
        dec.profile_version = profile_version
        row.updated_at = build_timestamp
        return

    contributions = {"cumulative_drift": new_accumulator}
    db_decision = DecisionRecordModel(
        decision_id=decision_id,
        event_id="PROFILE_BUILD",
        entity_id=entity_id,
        timestamp=build_timestamp,
        score=new_accumulator,
        confidence=0.8,
        profile_version=profile_version,
        scoring_config_version=config.get("version", "unknown"),
        contributions=contributions,
        is_anomaly=True,
        cohort_used=role,
        cohort_unsupported=False,
        flags={
            "drift_alert": True,
            "prev_accumulator": prev_accumulator,
            "norm_drift": norm_drift,
        },
    )
    db_session.add(db_decision)
    from worker.recorder import open_active_alert_if_needed

    open_active_alert_if_needed(db_session, decision_id, entity_id)


def _auto_resolve_quiet_attested_alerts(
    db_session: Session,
    blocked_alert_rows: list,
    as_of: datetime,
    drift_threshold: float,
) -> list[str]:
    """D3: entity-level auto-resolve of `new` rows when QUIET ∧ ATTEST ∧ min_dwell."""
    entity_alerts: dict[str, list] = {}
    for row in blocked_alert_rows:
        entity_alerts.setdefault(row.entity_id, []).append(row)

    resolved_entities: list[str] = []
    for entity_id, alerts in entity_alerts.items():
        new_rows = [a for a in alerts if a.state == "new"]
        if not new_rows:
            continue

        block_days_alerts = alerts
        block_start_days = _block_days_for_entity(db_session, block_days_alerts, as_of)
        # Reconstruct block_start from days approximation is brittle; use earliest decision ts.
        earliest: datetime | None = None
        for alert in alerts:
            dec = db_session.get(DecisionRecordModel, alert.decision_id)
            start = dec.timestamp if dec is not None else alert.updated_at
            if earliest is None or start < earliest:
                earliest = start
        if earliest is None:
            continue

        if not _min_dwell_satisfied(db_session, entity_id, earliest):
            continue
        if not _entity_is_quiet(db_session, entity_id, as_of):
            continue

        shadows = _shadow_builds_during_block(db_session, entity_id, earliest)
        shadow_drifts = [
            float((s.features or {}).get("cumulative_drift", 0.0)) for s in shadows
        ]
        shadow_features = _get_latest_shadow_features(db_session, entity_id)
        if not shadow_features and shadows:
            shadow_features = shadows[-1].features or {}
        promoted_features = _get_promoted_features(db_session, entity_id)
        anchor_features = _get_anchor_features(db_session, entity_id)

        ok, detail = attest(
            shadow_features=shadow_features,
            promoted_features=promoted_features,
            anchor_features=anchor_features or promoted_features,
            shadow_drifts_during_block=shadow_drifts,
            drift_threshold=drift_threshold,
        )
        if not ok:
            continue

        for row in new_rows:
            row.state = "auto_resolved"
            row.updated_at = as_of
            row.clear_reason = "auto_resolved:QUIET∧ATTEST"
            log_audit_event(
                db_session,
                action=AUTO_RESOLVED_AUDIT_ACTION,
                entity_id=entity_id,
                details={
                    "decision_id": row.decision_id,
                    "attestation": detail,
                    "block_days": block_start_days,
                },
                commit=False,
            )
        resolved_entities.append(entity_id)
        logger.info(
            "Auto-resolved %d new alert(s) for entity %s (QUIET∧ATTEST)",
            len(new_rows),
            entity_id,
        )
    return resolved_entities


def _emit_build_block_supervisor_escalations(
    db_session: Session,
    blocked_alert_rows: list,
    as_of: datetime,
    max_block_days: int,
    config: dict,
    build_timestamp: datetime,
) -> list[str]:
    """Emit auditable supervisor-escalation decisions for prolonged build blocks (D5)."""
    entity_alerts: dict[str, list] = {}
    for row in blocked_alert_rows:
        entity_alerts.setdefault(row.entity_id, []).append(row)

    escalated: list[str] = []
    for entity_id, alerts in entity_alerts.items():
        block_days = _block_days_for_entity(db_session, alerts, as_of)
        if block_days <= max_block_days:
            continue

        logger.warning(
            "Supervisor escalation: entity %s build-blocked %.1f days (threshold %d)",
            entity_id,
            block_days,
            max_block_days,
        )
        latest_profile = (
            db_session.query(ProfileArtifactModel)
            .filter(ProfileArtifactModel.entity_id == entity_id)
            .order_by(desc(ProfileArtifactModel.data_window_end))
            .first()
        )
        profile_version = latest_profile.profile_version if latest_profile else "NONE"
        decision_id = (
            f"build_block_esc_{entity_id}_{build_timestamp.strftime('%Y%m%d%H%M%S')}"
            f"_{uuid.uuid4().hex[:8]}"
        )
        db_session.add(
            DecisionRecordModel(
                decision_id=decision_id,
                event_id="PROFILE_BUILD",
                entity_id=entity_id,
                timestamp=build_timestamp,
                score=0.0,
                confidence=1.0,
                profile_version=profile_version,
                scoring_config_version=config.get("version", "unknown"),
                contributions={"build_block_days": block_days},
                is_anomaly=False,
                cohort_used="unknown",
                cohort_unsupported=False,
                flags={
                    BUILD_BLOCK_SUPERVISOR_ESCALATION_FLAG: True,
                    "block_days": block_days,
                    "max_profile_build_block_days": max_block_days,
                    "sla_hours": SUPERVISOR_ESCALATION_SLA_HOURS,
                    "mandatory_review": True,
                },
            )
        )
        log_audit_event(
            db_session,
            action=BUILD_BLOCK_ESCALATION_AUDIT_ACTION,
            entity_id=entity_id,
            details={
                "decision_id": decision_id,
                "block_days": block_days,
                "max_profile_build_block_days": max_block_days,
            },
            commit=False,
        )
        escalated.append(entity_id)
    return escalated


_BUILD_EXTRACT_CHUNK_SIZE: int = 5000  # rows per DB round-trip when streaming to temp JSONL (bounds build_profiles memory/disk under volume spikes)


def _dim_weight(drift_weights_cfg: dict, key: str) -> float:
    v = drift_weights_cfg.get(key, 1.0)
    return v.get("weight", 0.0) if isinstance(v, dict) else v


def compute_geo_velocity_delta(
    db: Session, entity_id: str, window_start: datetime, window_end: datetime, min_paired_successes: int = 3
) -> tuple[float, list[str]]:
    """Implied travel speed between successive auth events; delta vs. the entity's
    own max historical implied speed within the window. No cross-entity baseline."""
    stmt = (
        select(ResolvedEventModel.timestamp, ResolvedEventModel.event_data)
        .where(
            and_(
                ResolvedEventModel.entity_id == entity_id,
                ResolvedEventModel.timestamp >= window_start,
                ResolvedEventModel.timestamp < window_end,
            )
        )
        .order_by(ResolvedEventModel.timestamp)
    )
    rows = db.execute(stmt).all()
    auth_rows = [
        (ts, data.get("geolocation")) for ts, data in rows
        if isinstance(data, dict) and data.get("action") == "login" and data.get("geolocation")
    ]
    if len(auth_rows) < min_paired_successes:
        return 0.0, []

    flags: list[str] = []
    speeds_kmh: list[float] = []
    for (t1, g1), (t2, g2) in zip(auth_rows, auth_rows[1:]):
        c1, c2 = lookup_centroid(g1), lookup_centroid(g2)
        if c1 is None or c2 is None:
            flags.append("geo_velocity:no_centroid")
            continue
        hours = max((t2 - t1).total_seconds() / 3600.0, 1e-6)
        dist_km = haversine_km(c1, c2)
        speeds_kmh.append(dist_km / hours)

    if not speeds_kmh:
        return 0.0, list(set(flags))

    max_speed = max(speeds_kmh)
    # Plausible commercial air travel ceiling ~900 km/h; anything well beyond that
    # relative to the entity's own max observed speed this window is the delta signal.
    delta = max(0.0, (max_speed - 900.0) / 900.0) if max_speed > 900.0 else 0.0
    return delta, list(set(flags))


def compute_build_window_cadence_cov(
    db: Session, entity_id: str, window_start: datetime, window_end: datetime, min_events: int = 20
) -> tuple[float, int]:
    """Build-window inter-event interval CoV, same formula as worker.scorer.compute_periodicity,
    applied to any entity_type over the build window instead of a rolling 60-minute lookback."""
    stmt = (
        select(ResolvedEventModel.timestamp)
        .where(
            and_(
                ResolvedEventModel.entity_id == entity_id,
                ResolvedEventModel.timestamp >= window_start,
                ResolvedEventModel.timestamp < window_end,
            )
        )
        .order_by(ResolvedEventModel.timestamp)
    )
    ts_list = db.execute(stmt).scalars().all()
    count = len(ts_list)
    if count < min_events:
        return 0.0, count
    intervals = [(ts_list[i + 1] - ts_list[i]).total_seconds() for i in range(len(ts_list) - 1)]
    mean_int = sum(intervals) / len(intervals)
    if mean_int < 1.0:
        return 0.0, count
    cv = (math.sqrt(sum((x - mean_int) ** 2 for x in intervals) / len(intervals))) / mean_int
    return max(0.0, 1.0 - (cv / 0.3)), count


def match_staged_sequence(
    drift_crossing_log: list[dict], templates: list[list[str]]
) -> tuple[bool, list[str] | None]:
    """Subsequence match: template dims must appear across the log in order,
    not necessarily contiguously or in consecutive builds."""
    seen_in_order: list[str] = []
    for entry in drift_crossing_log:
        for dim in entry.get("dims_crossed", []):
            seen_in_order.append(dim)

    for template in templates:
        idx = 0
        for dim in seen_in_order:
            if idx < len(template) and dim == template[idx]:
                idx += 1
        if idx == len(template):
            return True, template
    return False, None


def _stream_events_to_jsonl(db_session: Session, stmt, path: Path, chunk_size: int) -> int:
    """Stream ResolvedEventModel rows straight to a JSONL file in bounded
    chunks instead of materializing the full result set in Python first."""
    count = 0
    result = db_session.execute(stmt.execution_options(yield_per=chunk_size)).scalars()
    with open(path, "w") as f:
        for e in result:
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
                "hour_of_day": e.timestamp.hour,
            }
            f.write(json.dumps(data) + "\n")
            count += 1
    return count


def build_profiles(
    db: Session | None = None,
    drift_compare_n: int = 5,
    as_of: datetime | None = None,
    chunk_size: int = _BUILD_EXTRACT_CHUNK_SIZE,
    config_override: dict | None = None,
) -> int:
    if db is None:
        db_session = SessionLocal()
    else:
        db_session = db

    if as_of is None:
        as_of = datetime.utcnow()

    if config_override is not None:
        config = config_override
    else:
        # ALTER_EGO_SCORING_CONFIG: per-process YAML for parallel calibration probes.
        override = os.environ.get("ALTER_EGO_SCORING_CONFIG", "").strip()
        config_path = Path(override) if override else Path("config/scoring_config.yaml")
        with open(config_path, "r") as f:
            config = yaml.safe_load(f)

    drift_weights_cfg = config.get("drift_weights", {
        "login_hour": 1.0, "geolocation": 1.0, "endpoint_set": 1.0, "process_name": 1.0, "embedding": 2.0
    })
    drift_threshold = config.get("drift_threshold", 45.0)
    history_count = config.get("drift_comparison_history_count", 5)
    half_life = config.get("drift_half_life_days", 7.0)
    laplace_alpha = config.get("laplace_alpha", 1.0)
    max_profile_build_block_days = config.get("max_profile_build_block_days", 30)
    staged_drift_cfg = config.get("staged_drift", {})

    # Fix #7 — initialize temp file paths before try block to prevent NameError in finally
    temp_file_hist: Path | None = None
    temp_file_recent: Path | None = None
    try:
        # Check for active alerts in the new workflow state model
        blocked_alerts_stmt = select(AlertWorkflowStateModel).where(
            AlertWorkflowStateModel.state.in_(list(ACTIVE_ALERT_STATES))
        )
        blocked_alert_rows = list(db_session.execute(blocked_alerts_stmt).scalars().all())
        blocked_entities = {row.entity_id for row in blocked_alert_rows}

        window_days = config.get("max_replay_window_days", 30)
        recent_days = config.get("recent_drift_window_days", 3)
        window_start_limit = as_of - timedelta(days=window_days)
        recent_start_limit = as_of - timedelta(days=recent_days)

        # Builder-visible partitions (Design 1 §0.2): production always;
        # S2/S3/S5 eval partitions feed hist+recent so boil-the-frog absorption is measurable.
        # S1/S4 remain excluded (sharp / service point attacks).
        builder_partitions = ("production", "eval_scenario_2", "eval_scenario_3", "eval_scenario_5")

        # Historical window (for profile content)
        stmt_hist = select(ResolvedEventModel).where(
            and_(
                ResolvedEventModel.simulation_partition.in_(builder_partitions),
                ResolvedEventModel.timestamp <= as_of,
                ResolvedEventModel.timestamp >= window_start_limit
            )
        )
        
        # Recent window (for drift detection)
        stmt_recent = select(ResolvedEventModel).where(
            and_(
                ResolvedEventModel.simulation_partition.in_(builder_partitions),
                ResolvedEventModel.timestamp <= as_of,
                ResolvedEventModel.timestamp >= recent_start_limit
            )
        )
        
        import time

        temp_file_hist = Path(f"temp_events_hist_{uuid.uuid4().hex}.jsonl")
        t0 = time.time()
        count_hist = _stream_events_to_jsonl(db_session, stmt_hist, temp_file_hist, chunk_size)
        logger.info(f"Streamed {count_hist} hist events to JSONL in {time.time()-t0:.2f}s")

        if count_hist == 0:
            temp_file_hist.unlink(missing_ok=True)
            build_timestamp = datetime.utcnow()
            _auto_resolve_quiet_attested_alerts(
                db_session,
                blocked_alert_rows,
                as_of,
                drift_threshold,
            )
            blocked_alert_rows = list(
                db_session.execute(
                    select(AlertWorkflowStateModel).where(
                        AlertWorkflowStateModel.state.in_(list(ACTIVE_ALERT_STATES))
                    )
                ).scalars().all()
            )
            _emit_build_block_supervisor_escalations(
                db_session,
                blocked_alert_rows,
                as_of,
                max_profile_build_block_days,
                config,
                build_timestamp,
            )
            db_session.commit()
            return 0

        temp_file_recent = Path(f"temp_events_recent_{uuid.uuid4().hex}.jsonl")
        t1 = time.time()
        count_recent = _stream_events_to_jsonl(db_session, stmt_recent, temp_file_recent, chunk_size)
        logger.info(f"Streamed {count_recent} recent events to JSONL in {time.time()-t1:.2f}s")
        if count_recent == 0:
            temp_file_recent.unlink(missing_ok=True)
            temp_file_recent = None
                
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
        if temp_file_recent:
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
            cur_hourly_counts = cur_login_hours

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

            cadence_cfg = drift_weights_cfg.get("cadence", {})
            volume_cfg = drift_weights_cfg.get("total_volume_delta", {})
            geo_velocity_cfg = drift_weights_cfg.get("geo_velocity", {})
            cadence_cov, _ = compute_build_window_cadence_cov(
                db_session, entity_id, window_start, window_end
            )

            avg_deltas: dict[str, float] = {}
            if prev_profiles:
                deltas: dict[str, list[float]] = {
                    "login_hour": [],
                    "geolocation": [],
                    "endpoint_set": [],
                    "process_name": [],
                    "embedding": [],
                }
                if cadence_cfg.get("enabled", False):
                    deltas["cadence"] = []
                if volume_cfg.get("enabled", False):
                    deltas["total_volume_delta"] = []
                if geo_velocity_cfg.get("enabled", False):
                    deltas["geo_velocity"] = []
                for prev in prev_profiles:
                    deltas["login_hour"].append(compute_distribution_kl(rec_login_hours, prev.features.get("login_hours", {}), alpha=laplace_alpha))
                    deltas["geolocation"].append(compute_distribution_kl(rec_geolocations, prev.features.get("geolocations", {}), alpha=laplace_alpha))
                    deltas["endpoint_set"].append(compute_distribution_kl(rec_endpoints, prev.features.get("endpoints", {}), alpha=laplace_alpha))
                    deltas["process_name"].append(compute_distribution_kl(rec_process_names, prev.features.get("process_names", {}), alpha=laplace_alpha))

                    if rec_centroid is not None and prev.embedding is not None:
                        deltas["embedding"].append(compute_cosine_distance(rec_centroid, np.array(prev.embedding)))

                    if cadence_cfg.get("enabled", False):
                        deltas["cadence"].append(cadence_cov)

                    if volume_cfg.get("enabled", False):
                        prev_hourly = prev.features.get("hourly_event_counts", {}) if prev else {}
                        deltas["total_volume_delta"].append(
                            compute_distribution_kl(cur_hourly_counts, prev_hourly, alpha=laplace_alpha)
                        )

                    if geo_velocity_cfg.get("enabled", False):
                        gv_delta, _gv_flags = compute_geo_velocity_delta(
                            db_session, entity_id, window_start, window_end
                        )
                        deltas["geo_velocity"].append(gv_delta)

                avg_deltas = {k: float(np.mean(v)) if v else 0.0 for k, v in deltas.items()}
                raw_drift = sum(avg_deltas[k] * _dim_weight(drift_weights_cfg, k) for k in avg_deltas)
            else:
                raw_drift = 0.0

            raw_drift_records.append({
                "entity_id": entity_id,
                "entity_type": entity_type,
                "role": role,
                "raw_drift": raw_drift,
                "avg_deltas": avg_deltas,
                # Store full 30d features in profile
                "features": {
                    "total_events": total_events,
                    "login_hours": cur_login_hours,
                    "geolocations": cur_geolocations,
                    "endpoints": cur_endpoints,
                    "process_names": cur_process_names,
                    "hourly_event_counts": cur_hourly_counts,
                    "cadence_cov": cadence_cov,
                },
                "embedding": centroid_arr.tolist() if centroid_arr is not None else None,
                "window_start": window_start,
                "window_end": window_end
            })

        # Phase 2: Cohort Normalization
        cohort_gate_config = config.get("cohort_gating_constants", {})
        max_changed_fraction = cohort_gate_config.get("max_changed_fraction", 0.2)
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

        # Phase 2.5 — Fleet-level cohort drift (DEBT-068/075, H2/H7 mitigation).
        # Additive: does not change any individual entity's norm_drift/cumulative_drift.
        fleet_drift_enabled = cohort_gate_config.get("fleet_drift_enabled", False)
        if fleet_drift_enabled:
            fleet_soft_threshold = global_drift_median  # role-relative: above the cross-role median raw_drift
            for role, drifts in cohort_drifts.items():
                if len(drifts) < 3:
                    continue
                changed_count = sum(1 for d in drifts if d > fleet_soft_threshold)
                fraction = changed_count / len(drifts)
                if fraction > max_changed_fraction:
                    decision_id = f"cohort_drift_{role}_{build_timestamp.strftime('%Y%m%d%H%M%S')}"
                    db_session.add(DecisionRecordModel(
                        decision_id=decision_id,
                        event_id="COHORT_DRIFT",
                        entity_id=f"__role__{role}",
                        timestamp=build_timestamp,
                        score=0.0,
                        confidence=1.0,
                        profile_version="NONE",
                        scoring_config_version=config.get("version", "unknown"),
                        contributions=[{"role": role, "changed_fraction": fraction,
                                        "cohort_size": len(drifts), "max_changed_fraction": max_changed_fraction}],
                        is_anomaly=False,
                        cohort_used=role,
                        cohort_unsupported=False,
                        flags=["fleet_cohort_drift"],
                    ))

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

            soft_crossing_threshold = staged_drift_cfg.get("soft_crossing_fraction", 0.5)
            avg_deltas = rec.get("avg_deltas", {})
            dims_crossed = [k for k, v in avg_deltas.items() if v > soft_crossing_threshold]
            prior_log = latest_any.features.get("drift_crossing_log", []) if latest_any else []
            drift_crossing_log = (
                prior_log + [{"build_ts": rec["window_end"].isoformat(), "dims_crossed": dims_crossed}]
            )[-10:]

            matched = False
            if staged_drift_cfg.get("enabled", False):
                matched, _which_template = match_staged_sequence(
                    drift_crossing_log, staged_drift_cfg.get("templates", [])
                )
                if matched:
                    features_staged_bonus = staged_drift_cfg.get("bonus", 1.0)
                    new_accumulator = exponential_decay(
                        prev_accumulator, norm_drift + features_staged_bonus, half_life, time_delta
                    )
                    new_accumulator = max(0.0, new_accumulator)

            logger.info(f"Entity {entity_id} drift: raw={raw_drift:.2f}, normalized={norm_drift:.2f}, accum={new_accumulator:.2f}")

            features = {
                "total_events": rec["features"]["total_events"],
                "login_hours": rec["features"]["login_hours"],
                "geolocations": rec["features"]["geolocations"],
                "endpoints": rec["features"]["endpoints"],
                "process_names": rec["features"]["process_names"],
                "hourly_event_counts": rec["features"]["hourly_event_counts"],
                "cadence_cov": rec["features"]["cadence_cov"],
                "role": rec["role"],
                "cohort_data": cohorts,
                "cumulative_drift": new_accumulator,
                "normalized_drift": norm_drift,
                "drift_crossing_log": drift_crossing_log,
                "staged_match": matched if staged_drift_cfg.get("enabled", False) else None,
            }
            for k, v in rec.get("avg_deltas", {}).items():
                features[f"{k}_delta_last_build"] = v
            
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
            
            # Emit Drift Decision if threshold crossed (D1: refresh if already blocked)
            if new_accumulator >= drift_threshold:
                decision_id = f"drift_{profile_version}"
                _refresh_or_open_drift_alert(
                    db_session,
                    entity_id=entity_id,
                    blocked_entities=blocked_entities,
                    decision_id=decision_id,
                    build_timestamp=build_timestamp,
                    new_accumulator=new_accumulator,
                    profile_version=profile_version,
                    config=config,
                    role=rec["role"],
                    prev_accumulator=prev_accumulator,
                    norm_drift=norm_drift,
                )

            count += 1

        # D3 — auto-resolve new rows when QUIET ∧ ATTEST ∧ min_dwell (entity-level)
        _auto_resolve_quiet_attested_alerts(
            db_session,
            blocked_alert_rows,
            as_of,
            drift_threshold,
        )
        # Re-read active blocks after auto-resolution for SLA escalation.
        blocked_alert_rows = list(
            db_session.execute(
                select(AlertWorkflowStateModel).where(
                    AlertWorkflowStateModel.state.in_(list(ACTIVE_ALERT_STATES))
                )
            ).scalars().all()
        )

        _emit_build_block_supervisor_escalations(
            db_session,
            blocked_alert_rows,
            as_of,
            max_profile_build_block_days,
            config,
            build_timestamp,
        )
        db_session.commit()
        return count
        
    finally:
        # Fix #7 — null-initialized above; safe even if exception raised before assignment
        for p in [temp_file_hist, temp_file_recent]:
            if p is not None and p.exists():
                p.unlink()
        if db is None:
            db_session.close()
