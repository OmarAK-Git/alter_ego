import hashlib
import math
import json
import time
import logging
from dataclasses import dataclass
import numpy as np
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import select, and_, func, extract, cast, Integer
from pathlib import Path

import yaml

from core.database import SessionLocal
from core.models import (
    AlertWorkflowStateModel,
    DecisionRecordModel,
    ProfileArtifactModel,
    ResolvedEventModel,
)
from core.schemas.events import ResolvedEvent
from core.schemas.profiles import (
    DEFAULT_EMBEDDING_DIMENSIONALITY,
    DEFAULT_EMBEDDING_MODEL_ID,
    DEFAULT_EMBEDDING_MODEL_VERSION,
    ProfileArtifact,
)
from core.schemas.decisions import DecisionRecord, FeatureContribution
from worker.recorder import record_decision
from worker.profile_store import ProfileStore
from core.math_utils import get_laplace_prob
from worker.vectorizer import (
    NORMALIZER_VERSION,
    vectorize_command_line,
    compute_cosine_distance,
)
from worker.resolver import LOW_RESOLUTION_THRESHOLD

# Fix #11 — logger defined before first use
logger = logging.getLogger(__name__)

# Pinned hot-path scorer lineage (SPEC_V3 §6.1 — included in decision_id hash).
SCORER_ALGORITHM_VERSION = "1.0"

# S5.5 — staleness + active-alert mandatory escalation (SPEC §5.7).
ACTIVE_ALERT_STATES = frozenset({"new", "acknowledged", "investigating"})
STALENESS_ESCALATION_FLAG = "staleness_active_alert_escalation"
SENSOR_HEALTH_STALENESS_FLAG = "sensor_health_staleness"
MANDATORY_ESCALATION_SLA_HOURS = 24

# S5.9 — runtime embedding contract (SPEC §5.6 / V3 §9 portfolio gate).
RUNTIME_EMBEDDING_MODEL_ID = DEFAULT_EMBEDDING_MODEL_ID
RUNTIME_EMBEDDING_MODEL_VERSION = DEFAULT_EMBEDDING_MODEL_VERSION
RUNTIME_EMBEDDING_DIMENSIONALITY = DEFAULT_EMBEDDING_DIMENSIONALITY
RUNTIME_EMBEDDING_INPUT_NORMALIZER_VERSION = NORMALIZER_VERSION
EMBEDDING_METADATA_MISMATCH_FLAG = "embedding_metadata_mismatch_halt"


@dataclass(frozen=True)
class EmbeddingMetadataMismatch:
    """Single field mismatch between profile artifact and runtime embedding contract."""

    field: str
    profile_value: str | int
    runtime_value: str | int


def check_profile_embedding_metadata(
    profile: ProfileArtifact,
) -> list[EmbeddingMetadataMismatch]:
    """Compare profile embedding metadata to the shipping runtime vectorizer contract."""
    mismatches: list[EmbeddingMetadataMismatch] = []
    for field, profile_value, runtime_value in (
        ("embedding_model_id", profile.embedding_model_id, RUNTIME_EMBEDDING_MODEL_ID),
        (
            "embedding_model_version",
            profile.embedding_model_version,
            RUNTIME_EMBEDDING_MODEL_VERSION,
        ),
        (
            "embedding_dimensionality",
            profile.embedding_dimensionality,
            RUNTIME_EMBEDDING_DIMENSIONALITY,
        ),
        (
            "embedding_input_normalizer_version",
            profile.embedding_input_normalizer_version,
            RUNTIME_EMBEDDING_INPUT_NORMALIZER_VERSION,
        ),
    ):
        if profile_value != runtime_value:
            mismatches.append(
                EmbeddingMetadataMismatch(field, profile_value, runtime_value)
            )
    if profile.embedding is not None and len(profile.embedding) != RUNTIME_EMBEDDING_DIMENSIONALITY:
        mismatches.append(
            EmbeddingMetadataMismatch(
                "embedding_vector_length",
                len(profile.embedding),
                RUNTIME_EMBEDDING_DIMENSIONALITY,
            )
        )
    return mismatches


def find_active_profiles_with_embedding_mismatch(
    db: Session,
) -> list[tuple[str, list[EmbeddingMetadataMismatch]]]:
    """Return promoted profiles whose embedding metadata disagrees with runtime.

    Callable at scorer startup or from ``process_unscored_events`` for audit logging.
    Per-entity halts are enforced in ``score_event`` via ``check_profile_embedding_metadata``.
    """
    stmt = select(ProfileArtifactModel).where(
        and_(
            ProfileArtifactModel.promoted_at.isnot(None),
            ProfileArtifactModel.superseded_at.is_(None),
        )
    )
    affected: list[tuple[str, list[EmbeddingMetadataMismatch]]] = []
    for model in db.execute(stmt).scalars():
        profile = ProfileArtifact(
            entity_id=model.entity_id,
            entity_type=model.entity_type,
            profile_version=model.profile_version,
            created_at=model.created_at,
            data_window_start=model.data_window_start,
            data_window_end=model.data_window_end,
            promoted_at=model.promoted_at,
            superseded_at=model.superseded_at,
            is_shadow=model.is_shadow,
            features=model.features,
            embedding=model.embedding,
            embedding_model_id=model.embedding_model_id,
            embedding_model_version=model.embedding_model_version,
            embedding_dimensionality=model.embedding_dimensionality,
            embedding_input_normalizer_version=model.embedding_input_normalizer_version,
        )
        mismatches = check_profile_embedding_metadata(profile)
        if mismatches:
            affected.append((model.entity_id, mismatches))
    return affected


def compute_decision_id(
    *,
    event_id: str,
    profile_version: str,
    scoring_config_version: str,
    embedding_model_version: str,
    halt: bool = False,
) -> str:
    """Canonical decision_id = SHA-256 of sorted-key JSON lineage payload."""
    payload: dict[str, str | bool] = {
        "embedding_model_version": embedding_model_version,
        "event_id": event_id,
        "profile_version": profile_version,
        "scorer_algorithm_version": SCORER_ALGORITHM_VERSION,
        "scoring_config_version": scoring_config_version,
    }
    if halt:
        payload["halt"] = True
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

# ---------------------------------------------------------------------------
# Fix #2 — TTL-bounded caches (no more unbounded process-global dicts)
# ---------------------------------------------------------------------------
_COHORT_CACHE_TTL = 300  # seconds

# {(role, entity_type): (members_list, monotonic_ts)}
_COHORT_MEMBERS_CACHE: dict[tuple, tuple[list, float]] = {}

# Fix #2 — novelty fraction cache: bounded FIFO at 2048 entries + per-entry TTL.
# Each value is (fraction: float, insert_ts: float) so stale entries are skipped
# on read. Key uses sha256 of sorted members rather than a raw tuple (avoids
# O(N²) key).
_NOVELTY_FRACTION_CACHE: dict[tuple, tuple[float, float]] = {}
_NOVELTY_CACHE_MAX = 2048
_NOVELTY_CACHE_TTL = 300  # seconds — stale entries are recomputed on next read

# Feature to DB field mapping for cohort novelty check
FEATURE_FIELD_MAP = {
    "login_hours": "hour",
    "geolocations": "geolocation",
    "endpoints": "endpoint_id",
    "process_names": "process_name",
}


def _members_hash(members: list[str]) -> str:
    """SHA-256 of the sorted member list — O(N) key, no quadratic growth."""
    return hashlib.sha256(",".join(sorted(members)).encode()).hexdigest()


def _is_postgresql(db: Session) -> bool:
    """Return True when the bound engine is PostgreSQL."""
    return db.bind.dialect.name == "postgresql"


def _get_cohort_members(db: Session, role: str, entity_type: str) -> list[str]:
    """Returns entity IDs in a cohort, with TTL-bounded caching.

    Role is extracted from the ``features`` JSONB column using a
    dialect-agnostic approach:
      - PostgreSQL: ``features['role'].as_string()``  (JSONB subscript, no json_extract)
      - SQLite:     ``json_extract(features, '$.role')``  (explicitly gated)
    """
    cache_key = (role, entity_type)
    entry = _COHORT_MEMBERS_CACHE.get(cache_key)
    if entry is not None:
        members, ts = entry
        if time.monotonic() - ts < _COHORT_CACHE_TTL:
            return members

    if _is_postgresql(db):
        # PostgreSQL: use native JSONB subscript operator — no json_extract
        stmt = select(ProfileArtifactModel.entity_id).where(
            and_(
                ProfileArtifactModel.entity_type == entity_type,
                ProfileArtifactModel.features["role"].as_string() == role,
                ProfileArtifactModel.promoted_at.isnot(None),
            )
        ).distinct()
    else:
        # SQLite path — json_extract is safe here (explicitly SQLite-only branch)
        stmt = select(ProfileArtifactModel.entity_id).where(
            and_(
                ProfileArtifactModel.entity_type == entity_type,
                func.json_extract(ProfileArtifactModel.features, "$.role") == role,
                ProfileArtifactModel.promoted_at.isnot(None),
            )
        ).distinct()

    members = list(db.execute(stmt).scalars().all())
    _COHORT_MEMBERS_CACHE[cache_key] = (members, time.monotonic())
    return members


def _get_novelty_fraction(
    db: Session,
    members: list[str],
    feature_name: str,
    value: str,
    window_days: int,
    current_ts: datetime,
) -> float:
    """Fraction of the cohort that exhibited this value in the window.

    For non-hour fields (geolocation, endpoint_id, process_name) the lookup
    into ``event_data`` is dialect-dispatched:
      - PostgreSQL: ``event_data['field'].as_string() = value``
      - SQLite:     ``json_extract(event_data, '$.field') = value``
    """
    if not members:
        return 0.0

    window_start = (current_ts - timedelta(days=window_days)).replace(
        minute=0, second=0, microsecond=0
    )
    # Fix #2 — use sha256 digest as key instead of raw sorted tuple
    members_key = _members_hash(members)
    cache_key = (feature_name, value, members_key, window_start)

    cached = _NOVELTY_FRACTION_CACHE.get(cache_key)
    if cached is not None:
        fraction, insert_ts = cached
        if time.monotonic() - insert_ts < _NOVELTY_CACHE_TTL:
            return fraction
        # TTL expired — fall through and recompute

    field = FEATURE_FIELD_MAP.get(feature_name)
    if not field:
        return 0.0

    stmt = select(func.count(ResolvedEventModel.entity_id.distinct())).where(
        and_(
            ResolvedEventModel.entity_id.in_(members),
            ResolvedEventModel.timestamp >= window_start,
        )
    )

    # Dialect-agnostic field extraction
    if field == "hour":
        # extract("hour", ...) works on both SQLite (via strftime) and PostgreSQL
        stmt = stmt.where(
            cast(extract("hour", ResolvedEventModel.timestamp), Integer) == int(value)
        )
    elif _is_postgresql(db):
        # PostgreSQL JSONB subscript operator — no json_extract
        stmt = stmt.where(
            ResolvedEventModel.event_data[field].as_string() == value
        )
    else:
        # SQLite path — json_extract is explicitly gated here
        stmt = stmt.where(
            func.json_extract(ResolvedEventModel.event_data, f"$.{field}") == value
        )

    count = db.execute(stmt).scalar() or 0
    fraction = count / len(members)
    logger.debug(
        f"Novelty fraction {feature_name}={value}: {count}/{len(members)} = {fraction:.3f}"
    )

    # FIFO eviction when cache is full (preserves max size = _NOVELTY_CACHE_MAX)
    if len(_NOVELTY_FRACTION_CACHE) >= _NOVELTY_CACHE_MAX:
        oldest_key = next(iter(_NOVELTY_FRACTION_CACHE))
        del _NOVELTY_FRACTION_CACHE[oldest_key]
    _NOVELTY_FRACTION_CACHE[cache_key] = (fraction, time.monotonic())
    return fraction


def entity_has_active_uncleared_alert(db: Session, entity_id: str) -> bool:
    """Return True when the entity has an uncleared triage alert."""
    return bool(get_active_alert_decision_ids(db, entity_id))


def get_active_alert_decision_ids(db: Session, entity_id: str) -> list[str]:
    """Uncleared alert decision_ids for an entity (new/acknowledged/investigating)."""
    rows = (
        db.query(DecisionRecordModel, AlertWorkflowStateModel)
        .outerjoin(
            AlertWorkflowStateModel,
            DecisionRecordModel.decision_id == AlertWorkflowStateModel.decision_id,
        )
        .filter(
            DecisionRecordModel.entity_id == entity_id,
            DecisionRecordModel.is_anomaly.is_(True),
        )
        .all()
    )
    active_ids: list[str] = []
    for dec, state in rows:
        workflow_state = state.state if state else "new"
        if workflow_state in ACTIVE_ALERT_STATES:
            active_ids.append(dec.decision_id)
    return active_ids


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
    if sum(local_hist.values()) >= 20:
        return local_hist, "local"
    role = features.get("role", "unknown")
    primary_hist = cohort_data.get("primary", {}).get(role, {}).get(feature_name, {})
    if sum(primary_hist.values()) >= 100:
        return primary_hist, "role_cohort"
    return cohort_data.get("terminus", {}).get(feature_name, {}), "terminus"


def compute_periodicity(
    db: Session, entity_id: str, event_time: datetime, window_minutes: int = 60
) -> tuple[float, int]:
    stmt = (
        select(ResolvedEventModel.timestamp)
        .where(
            and_(
                ResolvedEventModel.entity_id == entity_id,
                ResolvedEventModel.timestamp < event_time,
                ResolvedEventModel.timestamp >= event_time - timedelta(minutes=window_minutes),
            )
        )
        .order_by(ResolvedEventModel.timestamp)
    )
    ts_list = db.execute(stmt).scalars().all()
    count = len(ts_list)
    if count < 2:
        return 0.0, count
    intervals = [(ts_list[i + 1] - ts_list[i]).total_seconds() for i in range(len(ts_list) - 1)]
    mean_int = sum(intervals) / len(intervals)
    if mean_int < 1.0:
        return 0.0, count
    cv = (math.sqrt(sum((x - mean_int) ** 2 for x in intervals) / len(intervals))) / mean_int
    return max(0.0, 1.0 - (cv / 0.3)), count


def score_event(db: Session, resolved_event: ResolvedEvent, profile: ProfileArtifact, config: dict) -> DecisionRecord:
    contributions = []
    features_config = config.get("features", {})
    alpha = config.get("laplace_alpha", 1.0)
    max_contrib = config.get("contribution_scale_max", 20.0)

    def get_event_field(field: str, default: str = "unknown") -> str:
        data = resolved_event.event_data
        if hasattr(data, field):
            return str(getattr(data, field))
        if isinstance(data, dict):
            return str(data.get(field, default))
        return default

    flags = []
    if resolved_event.resolution_confidence < LOW_RESOLUTION_THRESHOLD:
        flags.append("low_resolution_confidence")

    # S5.9 — embedding/schema metadata gate (SPEC §5.6): halt before feature scoring.
    embedding_mismatches = check_profile_embedding_metadata(profile)
    if embedding_mismatches:
        flags.append(EMBEDDING_METADATA_MISMATCH_FLAG)
        for mismatch in embedding_mismatches:
            flags.append(
                f"embedding_mismatch_{mismatch.field}:"
                f"{mismatch.profile_value}!={mismatch.runtime_value}"
            )
        decision_id = compute_decision_id(
            event_id=resolved_event.event_id,
            profile_version=profile.profile_version,
            scoring_config_version=str(config.get("version", "2.1")),
            embedding_model_version=profile.embedding_model_version,
            halt=True,
        )
        return DecisionRecord(
            decision_id=decision_id,
            event_id=resolved_event.event_id,
            entity_id=resolved_event.entity_id,
            timestamp=resolved_event.timestamp,
            score=0.0,
            confidence=1.0,
            profile_version=profile.profile_version,
            scoring_config_version=str(config.get("version", "2.1")),
            contributions=[],
            is_anomaly=False,
            cohort_used="none",
            cohort_unsupported=True,
            flags=flags,
            embedding_model_version=profile.embedding_model_version,
        )

    cohort_gate_config = config.get("cohort_gating_constants", {})
    max_changed_fraction = cohort_gate_config.get("max_changed_fraction", 0.2)
    min_cohort_size = cohort_gate_config.get("min_cohort_size", 10)
    gate_window = config.get("cohort_gate_window_days", 7)

    # Staleness Circuit Breaker
    max_staleness = config.get("max_profile_staleness_days", 14)
    time_since_profile = (resolved_event.timestamp - profile.data_window_end).total_seconds() / 86400.0
    if time_since_profile > max_staleness:
        flags.append("staleness_halt")
        flags.append(SENSOR_HEALTH_STALENESS_FLAG)
        if entity_has_active_uncleared_alert(db, resolved_event.entity_id):
            flags.append(STALENESS_ESCALATION_FLAG)
        decision_id = compute_decision_id(
            event_id=resolved_event.event_id,
            profile_version=profile.profile_version,
            scoring_config_version=str(config.get("version", "2.1")),
            embedding_model_version=profile.embedding_model_version,
            halt=True,
        )
        return DecisionRecord(
            decision_id=decision_id,
            event_id=resolved_event.event_id,
            entity_id=resolved_event.entity_id,
            # Fix #9 — use event timestamp, not wall-clock
            timestamp=resolved_event.timestamp,
            score=0.0,
            confidence=1.0,
            profile_version=profile.profile_version,
            scoring_config_version=str(config.get("version", "2.1")),
            contributions=[],
            is_anomaly=False,
            cohort_used="none",
            cohort_unsupported=True,
            flags=flags,
            embedding_model_version=profile.embedding_model_version,
        )

    def get_rarity_score(val, hist, vocab_size, weight_key, feature_name, baseline_bits=0):
        prob = get_laplace_prob(hist.get(val, 0), sum(hist.values()), vocab_size, alpha=alpha)
        rarity = -math.log2(prob) if prob > 0 else 0
        centered = max(0.0, rarity - baseline_bits)

        suppressed = False
        if centered > 0:
            role = profile.features.get("role", "unknown")
            members = _get_cohort_members(db, role, resolved_event.entity_type)
            if len(members) >= min_cohort_size:
                fraction = _get_novelty_fraction(
                    db, members, feature_name, val, gate_window, resolved_event.timestamp
                )
                if fraction > max_changed_fraction:
                    suppressed = True
                    flags.append(f"novelty_suppressed_{weight_key}")
                else:
                    logger.debug(
                        f"Novelty {feature_name}={val} fraction {fraction} <= {max_changed_fraction}"
                    )
            else:
                if role != "unknown":
                    flags.append(f"cohort_too_small_{weight_key}")

        weight = features_config.get(weight_key, {}).get("weight", 1.0)
        raw_weighted = centered * 0.5 * weight
        score = 0.0 if suppressed else min(max_contrib, raw_weighted)
        if not suppressed and raw_weighted > max_contrib:
            flags.append(f"cap_hit_{weight_key}")
        return score, weight, (0.0 if suppressed else centered)

    # --- Feature scores ---
    # Fix #8 — get histogram + fallback level once per feature, track all levels
    hist_login, lvl_login = _get_cohort_histogram("login_hours", profile)
    hist_geo, lvl_geo = _get_cohort_histogram("geolocations", profile)
    hist_end, lvl_end = _get_cohort_histogram("endpoints", profile)
    hist_proc, lvl_proc = _get_cohort_histogram("process_names", profile)

    fallback_levels = [lvl_login, lvl_geo, lvl_end, lvl_proc]
    _level_rank = {"local": 0, "role_cohort": 1, "terminus": 2}
    worst_level = max(fallback_levels, key=lambda level: _level_rank.get(level, 0))

    s1, _, c1 = get_rarity_score(str(resolved_event.timestamp.hour), hist_login, 24, "login_hour_rarity", "login_hours", 10.0)
    s2, _, c2 = get_rarity_score(get_event_field("geolocation"), hist_geo, 100, "geolocation_rarity", "geolocations", 10.0)
    s3, _, c3 = get_rarity_score(get_event_field("endpoint_id"), hist_end, 50, "endpoint_set_rarity", "endpoints", 10.0)
    s4, _, c4 = get_rarity_score(get_event_field("process_name"), hist_proc, 1000, "process_name_rarity", "process_names", 10.0)

    # Embedding
    cmd_line = get_event_field("command_line", "")
    event_vec = vectorize_command_line(cmd_line)
    profile_vec = np.array(profile.embedding) if profile.embedding else None

    if profile_vec is not None and len(profile_vec) == len(event_vec):
        dist = compute_cosine_distance(event_vec, profile_vec)
    else:
        dist = 0.0
        flags.append("cold_start_embedding_suppressed")

    weight_emb = features_config.get("command_line_embedding_similarity", {}).get("weight", 5.0)
    raw_emb = (dist - 0.50) * 50.0 * weight_emb if dist > 0.50 else 0.0
    score_emb = min(max_contrib, raw_emb)
    if raw_emb > max_contrib:
        flags.append("cap_hit_embedding")

    # Periodicity (service accounts only)
    score_period = 0.0
    dev_period = 0.0
    n_period = 0
    if resolved_event.entity_type == "service_account":
        dev_period, n_period = compute_periodicity(db, resolved_event.entity_id, resolved_event.timestamp)
        weight_period = features_config.get("service_account_execution_frequency_deviation", {}).get("weight", 5.0)
        raw_period = dev_period * 5.0 * weight_period
        score_period = min(max_contrib, raw_period)
        if raw_period > max_contrib:
            flags.append("cap_hit_periodicity")

    # total_volume_delta deferred (S2.6): hourly spike formula needs calibrated
    # window counts + baseline; reserved weight in YAML until post-S3 sweep.
    score_vol = 0.0
    v_delta = 0.0
    flags.append("volume_delta_deferred")

    # Fix #5 — proportional drift scoring (replaces binary threshold gate).
    # Intended operating point (threshold=5, weight=100, max_contrib=50):
    #   score_drift = min(50, drift_accum / 5 * 100)
    #   Contribution cap (50) is reached at drift_accum = 2.5
    #   anomaly_threshold (45) is crossed by drift alone at drift_accum ≈ 2.25
    # This is deliberate: a sustained high-drift entity trips the alarm at ~2.25
    # accumulated drift units, well before the 5-unit "full" threshold. The cap
    # and threshold are intentionally asymmetric to give drift early-warning power.
    drift_accum = profile.features.get("cumulative_drift", 0.0)
    drift_threshold = config.get("drift_threshold", 5.0)
    weight_drift = features_config.get("drift_alert", {}).get("weight", 100.0)
    score_drift = 0.0
    if drift_accum > 0 and drift_threshold > 0:
        score_drift = min(max_contrib, (drift_accum / drift_threshold) * weight_drift)

    # Aggregation
    raw_total = s1 + s2 + s3 + s4 + score_emb + score_period + score_vol + score_drift

    def get_contrib_id(feat_name: str, raw_val: float) -> str:
        return hashlib.sha256(
            f"{resolved_event.event_id}{feat_name}{raw_val}".encode()
        ).hexdigest()[:8]

    contributions = [
        FeatureContribution(contribution_id=f"feat_hour_{get_contrib_id('login_hour_rarity', c1)}", feature_name="login_hour_rarity", raw_value=c1, contribution_score=s1, confidence_weight=0.9),
        FeatureContribution(contribution_id=f"feat_geo_{get_contrib_id('geolocation_rarity', c2)}", feature_name="geolocation_rarity", raw_value=c2, contribution_score=s2, confidence_weight=0.9),
        FeatureContribution(contribution_id=f"feat_end_{get_contrib_id('endpoint_set_rarity', c3)}", feature_name="endpoint_set_rarity", raw_value=c3, contribution_score=s3, confidence_weight=0.9),
        FeatureContribution(contribution_id=f"feat_proc_{get_contrib_id('process_name_rarity', c4)}", feature_name="process_name_rarity", raw_value=c4, contribution_score=s4, confidence_weight=0.9),
        FeatureContribution(contribution_id=f"feat_embed_{get_contrib_id('command_line_embedding_similarity', float(dist))}", feature_name="command_line_embedding_similarity", raw_value=float(dist), contribution_score=score_emb, confidence_weight=0.7),
        FeatureContribution(contribution_id=f"feat_vol_{get_contrib_id('total_volume_delta', v_delta)}", feature_name="total_volume_delta", raw_value=v_delta, contribution_score=score_vol, confidence_weight=0.6),
        FeatureContribution(contribution_id=f"feat_drift_{get_contrib_id('drift_alert', float(drift_accum))}", feature_name="drift_alert", raw_value=float(drift_accum), contribution_score=score_drift, confidence_weight=0.8),
    ]
    if resolved_event.entity_type == "service_account":
        contributions.append(
            FeatureContribution(
                contribution_id=f"feat_period_{get_contrib_id('service_account_execution_frequency_deviation', dev_period)}",
                feature_name="service_account_execution_frequency_deviation",
                raw_value=dev_period,
                contribution_score=score_period,
                confidence_weight=0.8 if n_period >= 5 else 0.1,
            )
        )

    n = profile.features.get("total_events")
    if n is None:
        n = sum(profile.features.get("login_hours", {}).values())
    confidence_k = config.get("confidence_k", 10.0)
    decision_confidence = n / (n + confidence_k) if (n + confidence_k) > 0 else 0.0

    threshold = config.get("anomaly_threshold", 45.0)
    confidence_floor = config.get("confidence_floor", 0.6)
    if decision_confidence < confidence_floor:
        total_score = min(threshold - 5.0, raw_total)
        flags.append("low_confidence_damping_applied")
    else:
        total_score = raw_total

    is_anomaly = total_score >= threshold
    if is_anomaly:
        logger.info(
            f"ANOMALY DETECTED: entity={resolved_event.entity_id} "
            f"score={total_score:.2f} conf={decision_confidence:.2f}"
        )
        for c in contributions:
            logger.info(f"  - {c.feature_name}: raw={c.raw_value:.2f} score={c.contribution_score:.2f}")

    containment_threshold = config.get("containment_threshold", 85.0)
    if (
        total_score >= containment_threshold
        and decision_confidence >= confidence_floor
    ):
        flags.append("simulated_containment_queued")

    decision_id = compute_decision_id(
        event_id=resolved_event.event_id,
        profile_version=profile.profile_version,
        scoring_config_version=str(config.get("version", "2.1")),
        embedding_model_version=profile.embedding_model_version,
    )

    return DecisionRecord(
        decision_id=decision_id,
        event_id=resolved_event.event_id,
        entity_id=resolved_event.entity_id,
        # Fix #9 — canonical timestamp is event time, not wall clock
        timestamp=resolved_event.timestamp,
        score=total_score,
        confidence=decision_confidence,
        profile_version=profile.profile_version,
        scoring_config_version=str(config.get("version", "2.1")),
        contributions=contributions,
        is_anomaly=is_anomaly,
        # Fix #8 — report worst fallback level across all rarity features
        cohort_used=worst_level,
        cohort_unsupported=(worst_level == "terminus"),
        flags=flags,
        embedding_model_version=profile.embedding_model_version,
    )


def process_unscored_events(db: Session | None = None) -> int:
    if db is None:
        db_session = SessionLocal()
    else:
        db_session = db
    config = load_scoring_config()
    profile_store = ProfileStore(db_session)
    count = 0
    mismatched_profiles = find_active_profiles_with_embedding_mismatch(db_session)
    if mismatched_profiles:
        for entity_id, mismatches in mismatched_profiles:
            fields = ", ".join(m.field for m in mismatches)
            logger.warning(
                "Embedding metadata mismatch for entity %s (%s); "
                "score_event will halt until profile rebuild",
                entity_id,
                fields,
            )
    try:
        stmt = (
            select(ResolvedEventModel)
            .outerjoin(
                DecisionRecordModel,
                ResolvedEventModel.event_id == DecisionRecordModel.event_id,
            )
            .where(DecisionRecordModel.decision_id.is_(None))
            .order_by(ResolvedEventModel.timestamp)
        )
        # Fix #13 — yield_per(500) avoids materialising full result set in memory
        for db_event in db_session.execute(stmt).yield_per(500):
            db_event = db_event[0]
            profile = profile_store.get_active_profile(db_event.entity_id, db_event.timestamp)
            if not profile:
                continue
            resolved_event = ResolvedEvent(
                event_id=db_event.event_id,
                timestamp=db_event.timestamp,
                event_type=db_event.event_type,
                raw_entity_id=db_event.raw_entity_id,
                entity_id=db_event.entity_id,
                entity_type=db_event.entity_type,
                resolution_confidence=db_event.resolution_confidence,
                simulation_partition=db_event.simulation_partition,
                event_data=(
                    json.loads(db_event.event_data)
                    if isinstance(db_event.event_data, str)
                    else db_event.event_data
                ),
            )
            decision = score_event(db_session, resolved_event, profile, config)
            record_decision(decision, db_session)
            count += 1
    finally:
        if db is None:
            db_session.close()
    return count
