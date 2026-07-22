"""Honest SPEC §6.4 boil-the-frog invariants (Design 1).

Spec: docs/superpowers/specs/2026-07-18-boil-the-frog-invariants-design.md
Residual: docs/residual-risk-drift-hypotheses.md §2.6 / H11

Layer A — scenario shape vs ladder YAML.
Layer B — score path on in-memory sqlite (padding cohort, no tooling rollout).

Expect RED against current generator + production-only builder. No remediation here.
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pytest
import yaml
from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker

from batch.profile_builder.builder import build_profiles
from batch.synthetic.generator import EventGenerator
from core.database import Base
from core.models import DecisionRecordModel, ProfileArtifactModel, ResolvedEventModel
from worker.scorer import process_unscored_events
from worker.vectorizer import compute_cosine_distance, vectorize_command_line

SPEC_PATH = (
    "docs/superpowers/specs/2026-07-18-boil-the-frog-invariants-design.md"
)
LADDER_PATH = (
    Path(__file__).resolve().parent / "fixtures" / "boil_the_frog" / "s2_process_ladder.yaml"
)

# Declared-not-derived (spec §1.1) — judgment calls, not calibrated.
ABSORPTION_MASS_ALPHA = 0.02
DRIFT_EFFECT_SIZE_DELTA = 1.0
ANOMALY_THRESHOLD = 45.0

FIXTURE_ATTACK_DAYS = 7
FIXTURE_BURSTS = 5
FIXTURE_BASELINE_DAYS = 5
PADDING_COUNT = 3  # ≥3 static same-role padders → MIN_NORM_COHORT=3 satisfied


@compiles(JSONB, "sqlite")
def compile_jsonb_sqlite(type_, compiler, **kw):
    return "JSON"


@compiles(ARRAY, "sqlite")
def compile_array_sqlite(type_, compiler, **kw):
    return "JSON"


def _load_ladder() -> dict:
    with open(LADDER_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _spearman(xs: list[float], ys: list[float]) -> float:
    """Spearman rank correlation; ties → average ranks. n≥2 required."""
    n = len(xs)
    if n < 2:
        return 0.0

    def ranks(vals: list[float]) -> list[float]:
        order = sorted(range(n), key=lambda i: vals[i])
        r = [0.0] * n
        i = 0
        while i < n:
            j = i
            while j + 1 < n and vals[order[j + 1]] == vals[order[i]]:
                j += 1
            avg = (i + j) / 2.0 + 1.0
            for k in range(i, j + 1):
                r[order[k]] = avg
            i = j + 1
        return r

    rx, ry = ranks(xs), ranks(ys)
    mx, my = sum(rx) / n, sum(ry) / n
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    denx = math.sqrt(sum((a - mx) ** 2 for a in rx))
    deny = math.sqrt(sum((b - my) ** 2 for b in ry))
    if denx == 0.0 or deny == 0.0:
        return 0.0
    return num / (denx * deny)


def _baseline_centroid(baseline_family: list[str]) -> np.ndarray:
    vecs = [vectorize_command_line(f"{p} --silent") for p in baseline_family]
    c = np.mean(vecs, axis=0)
    n = np.linalg.norm(c)
    return c / n if n > 0 else c


def _day_mean_distances(
    attack_events: list, baseline_centroid: np.ndarray
) -> dict[int, float]:
    by_day: dict[int, list[float]] = {}
    for e in attack_events:
        # inject_scenario_2_slow_roll: step advances one calendar day from start_ts
        # day_index recovered from sorted unique dates among attack events
        day_key = e.timestamp.date()
        cmd = e.event_data.command_line
        d = compute_cosine_distance(vectorize_command_line(cmd), baseline_centroid)
        by_day.setdefault(day_key, []).append(d)
    ordered_dates = sorted(by_day.keys())
    return {
        idx: float(np.mean(by_day[dt]))
        for idx, dt in enumerate(ordered_dates)
    }


# ---------------------------------------------------------------------------
# Layer A
# ---------------------------------------------------------------------------


def test_a3_spec_reference_present():
    assert "SPEC" in __doc__ or "§6.4" in (__doc__ or "")
    assert SPEC_PATH
    assert LADDER_PATH.is_file()


def test_a1_s2_attack_process_names_match_ladder_yaml():
    """A1: every S2 attack process_name ∈ ladder_by_day[day_index]."""
    ladder = _load_ladder()
    ladder_by_day = {int(k): set(v) for k, v in ladder["ladder_by_day"].items()}

    gen = EventGenerator(seed=ladder["seed"])
    start = datetime(2026, 1, 1)
    events, labels = gen.inject_scenario_2_slow_roll([], [], start + timedelta(days=8))
    attack_ids = {lb["event_id"] for lb in labels if lb["scenario"] == "scenario_2_slow_roll"}
    attack_events = sorted(
        [e for e in events if e.event_id in attack_ids], key=lambda e: e.timestamp
    )
    assert len(attack_events) == 35

    ordered_dates = sorted({e.timestamp.date() for e in attack_events})
    date_to_day = {dt: i for i, dt in enumerate(ordered_dates)}

    violations = []
    for e in attack_events:
        day = date_to_day[e.timestamp.date()]
        allowed = ladder_by_day[day]
        name = e.event_data.process_name
        if name not in allowed:
            violations.append((day, name, sorted(allowed)))

    assert not violations, (
        f"A1 FAIL: attack process_names outside ladder_by_day "
        f"(first violations={violations[:5]})"
    )


def test_a2_s2_command_line_ramp_or_fail_sharp():
    """A2: ¬sharp ∧ (Spearman≥0.60 ∨ early/late gap≥0.05); sharp fails unconditionally."""
    ladder = _load_ladder()
    ramp = ladder["ramp"]
    spearman_min = float(ramp["spearman_min"])
    gap_min = float(ramp["early_late_gap_min"])
    sharp_floor = float(ramp["sharp_distance_floor"])

    gen = EventGenerator(seed=ladder["seed"])
    start = datetime(2026, 1, 1)
    events, labels = gen.inject_scenario_2_slow_roll([], [], start + timedelta(days=8))
    attack_ids = {lb["event_id"] for lb in labels if lb["scenario"] == "scenario_2_slow_roll"}
    attack_events = [e for e in events if e.event_id in attack_ids]

    centroid = _baseline_centroid(ladder["baseline_family"])
    d_by_day = _day_mean_distances(attack_events, centroid)
    days = sorted(d_by_day.keys())
    ds = [d_by_day[d] for d in days]
    n_days = len(days)
    win = n_days // 3
    early = ds[:win] if win else ds[:1]
    late = ds[-win:] if win else ds[-1:]

    sharp = min(ds) > sharp_floor
    rho = _spearman([float(d) for d in days], ds)
    gap = float(np.mean(late) - np.mean(early))
    ramp_ok = (rho >= spearman_min) or (gap >= gap_min)

    # Conjunctive: sharp fails the test regardless of ramp_ok.
    assert not sharp and ramp_ok, (
        f"A2 FAIL: sharp={sharp} (min_d={min(ds):.4f} floor={sharp_floor}), "
        f"rho={rho:.4f} (min={spearman_min}), gap={gap:.4f} (min={gap_min}), "
        f"d_by_day={{{', '.join(f'{k}:{v:.3f}' for k, v in d_by_day.items())}}}"
    )


# ---------------------------------------------------------------------------
# Layer B helpers
# ---------------------------------------------------------------------------


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture
def layer_b_meta(db_session):
    """Single shared Layer B pipeline run for B1–B3 (always-on, no skip)."""
    return _run_layer_b_fixture(db_session)


def _process_event(
    event_id: str,
    entity_id: str,
    ts: datetime,
    process_name: str,
    command_line: str,
    partition: str,
    endpoint_id: str = "ep_btf_1",
) -> ResolvedEventModel:
    return ResolvedEventModel(
        event_id=event_id,
        timestamp=ts,
        event_type="process",
        raw_entity_id=entity_id,
        entity_id=entity_id,
        entity_type="human",
        resolution_confidence=1.0,
        simulation_partition=partition,
        event_data={
            "process_name": process_name,
            "command_line": command_line,
            "endpoint_id": endpoint_id,
        },
    )


def _contrib(decision: DecisionRecordModel, name: str) -> float:
    for c in decision.contributions or []:
        if c.get("feature_name") == name:
            return float(c.get("contribution_score", 0.0))
    return 0.0


def _attack_mass(profile: ProfileArtifactModel, c_attack: set[str]) -> float:
    hist = (profile.features or {}).get("process_names") or {}
    total = sum(int(v) for v in hist.values()) or 1
    return sum(int(hist.get(c, 0)) for c in c_attack) / total


def _latest_cum_drift(db, entity_id: str) -> float:
    p = (
        db.query(ProfileArtifactModel)
        .filter(ProfileArtifactModel.entity_id == entity_id)
        .order_by(ProfileArtifactModel.data_window_end.desc())
        .first()
    )
    if not p:
        return 0.0
    return float((p.features or {}).get("cumulative_drift", 0.0) or 0.0)


def _run_layer_b_fixture(db):
    """Build padding cohort + ladder-shaped S2 attacks; return attack event ids + meta."""
    ladder = _load_ladder()
    family = list(ladder["baseline_family"])
    ladder_by_day = {int(k): list(v) for k, v in ladder["ladder_by_day"].items()}
    cmd_by_day = {int(k): v for k, v in ladder["command_line_by_day"].items()}
    attack_id = "user_engineer_attack"
    control_id = "user_engineer_control"
    pad_ids = [f"user_engineer_pad{i}" for i in range(PADDING_COUNT)]
    all_ids = [attack_id, control_id, *pad_ids]

    t0 = datetime(2026, 1, 1, 9, 0, 0)
    n = 0

    def add_benign(entity: str, day: int, burst: int) -> None:
        nonlocal n
        n += 1
        proc = family[(day + burst) % len(family)]
        ts = t0 + timedelta(days=day, hours=burst)
        db.add(
            _process_event(
                f"ben_{entity}_{day}_{burst}",
                entity,
                ts,
                proc,
                f"{proc} --silent",
                "production",
            )
        )

    for day in range(FIXTURE_BASELINE_DAYS):
        for entity in all_ids:
            for burst in range(4):
                add_benign(entity, day, burst)
        db.commit()
        build_profiles(db, as_of=t0 + timedelta(days=day, hours=23))

    attack_start_day = FIXTURE_BASELINE_DAYS
    attack_event_ids: list[str] = []
    c_attack: set[str] = set()

    for step in range(FIXTURE_ATTACK_DAYS):
        day = attack_start_day + step
        for entity in all_ids:
            for burst in range(3):
                add_benign(entity, day, burst)
        procs = ladder_by_day[step]
        cmd_tmpl = cmd_by_day[step]
        for burst in range(FIXTURE_BURSTS):
            eid = f"atk_{step}_{burst}"
            attack_event_ids.append(eid)
            process_name = procs[burst % len(procs)]
            c_attack.add(process_name)
            command_line = cmd_tmpl.format(process=process_name, burst=burst, day=step)
            ts = t0 + timedelta(days=day, hours=10, minutes=burst * 10)
            db.add(
                _process_event(
                    eid,
                    attack_id,
                    ts,
                    process_name,
                    command_line,
                    "eval_scenario_2",
                )
            )
        db.commit()
        build_profiles(db, as_of=t0 + timedelta(days=day, hours=23))
        process_unscored_events(db)

    baseline_set = set(family)
    c_novel = c_attack - baseline_set
    return {
        "attack_id": attack_id,
        "control_id": control_id,
        "attack_event_ids": attack_event_ids,
        "attack_start": t0 + timedelta(days=attack_start_day),
        "c_attack": c_attack,
        "c_novel": c_novel or c_attack,
        "baseline_family": baseline_set,
    }


def _pre_absorption(profile: ProfileArtifactModel | None, c_novel: set[str]) -> float:
    """Return (mass, pre_abs). Novel categories only — in-family names are not 'injected categories'."""
    if not profile:
        return 1.0, False
    mass = _attack_mass(profile, c_novel)
    return mass, mass < ABSORPTION_MASS_ALPHA


def test_b1_day0_attack_scores_below_threshold(db_session, layer_b_meta):
    """B1: day-0 max full score (incl. drift) over attack events < anomaly_threshold."""
    meta = layer_b_meta
    day0 = meta["attack_start"].date()
    day0_ids = {eid for eid in meta["attack_event_ids"] if eid.startswith("atk_0_")}
    decisions = (
        db_session.query(DecisionRecordModel)
        .filter(DecisionRecordModel.event_id.in_(day0_ids))
        .all()
    )
    assert decisions, "expected day-0 attack decisions"
    assert all(d.timestamp.date() == day0 for d in decisions)
    max_score = max(float(d.score) for d in decisions)
    assert max_score < ANOMALY_THRESHOLD, (
        f"B1 FAIL: day-0 max full score={max_score:.2f} >= {ANOMALY_THRESHOLD} "
        f"(scores={[round(float(d.score), 2) for d in decisions]})"
    )


def test_b2_attack_raises_cumulative_drift_vs_control(db_session, layer_b_meta):
    """B2: cum_drift(attack) − cum_drift(control) ≥ δ with padding cohort."""
    meta = layer_b_meta
    d_attack = _latest_cum_drift(db_session, meta["attack_id"])
    d_control = _latest_cum_drift(db_session, meta["control_id"])
    delta = d_attack - d_control
    assert delta >= DRIFT_EFFECT_SIZE_DELTA, (
        f"B2 FAIL: Δ cum_drift={delta:.4f} (attack={d_attack:.4f}, "
        f"control={d_control:.4f}) < δ={DRIFT_EFFECT_SIZE_DELTA}"
    )


def test_b3a_every_tp_is_drift_necessary(db_session, layer_b_meta):
    """B3a: non-vacuous tp_count>0; every attack TP is drift_necessary (attribution)."""
    meta = layer_b_meta
    decisions = (
        db_session.query(DecisionRecordModel)
        .filter(DecisionRecordModel.event_id.in_(meta["attack_event_ids"]))
        .all()
    )
    assert decisions, "expected attack decisions"
    tps = [d for d in decisions if float(d.score) >= ANOMALY_THRESHOLD]
    assert len(tps) > 0, (
        "B3a FAIL: vacuous — zero TPs (detection unproven; see B4). "
        "Silent forall-over-empty must not pass."
    )
    failures = []
    for d in tps:
        drift_c = _contrib(d, "drift_alert")
        if (float(d.score) - drift_c) >= ANOMALY_THRESHOLD:
            failures.append(
                {
                    "event_id": d.event_id,
                    "score": float(d.score),
                    "drift_contrib": drift_c,
                }
            )
    assert not failures, (
        f"B3a FAIL: {len(failures)} attack TP(s) not drift-necessary; "
        f"examples={failures[:5]}"
    )


def test_b3b_containment_no_post_absorption_tps(db_session, layer_b_meta):
    """B3b: every attack TP scored against a profile with M(C_novel)<α.

    Acceptance test for SPEC §5.5: after B4 catch, active-alert build-blocking
    must prevent novel attack mass from entering promoted profiles.
    """
    meta = layer_b_meta
    c_novel = meta["c_novel"]
    decisions = (
        db_session.query(DecisionRecordModel)
        .filter(DecisionRecordModel.event_id.in_(meta["attack_event_ids"]))
        .all()
    )
    tps = [d for d in decisions if float(d.score) >= ANOMALY_THRESHOLD]
    assert len(tps) > 0, "B3b FAIL: vacuous — zero TPs (see B4)"

    failures = []
    for d in tps:
        profile = (
            db_session.query(ProfileArtifactModel)
            .filter(ProfileArtifactModel.profile_version == d.profile_version)
            .one_or_none()
        )
        mass, pre_abs = _pre_absorption(profile, c_novel)
        if not pre_abs:
            failures.append(
                {
                    "event_id": d.event_id,
                    "score": float(d.score),
                    "M": mass,
                    "profile_version": d.profile_version,
                }
            )

    # Also: no *promoted* (non-shadow) profile should cross α after first catch
    promoted_over = []
    for p in (
        db_session.query(ProfileArtifactModel)
        .filter(
            ProfileArtifactModel.entity_id == meta["attack_id"],
            ProfileArtifactModel.is_shadow.is_(False),
            ProfileArtifactModel.promoted_at.isnot(None),
        )
        .all()
    ):
        mass = _attack_mass(p, c_novel)
        if mass >= ABSORPTION_MASS_ALPHA:
            promoted_over.append(
                {
                    "profile_version": p.profile_version,
                    "window_end": str(p.data_window_end),
                    "M": mass,
                }
            )

    assert not failures and not promoted_over, (
        f"B3b FAIL: containment — TP post-absorption={failures[:3]}; "
        f"promoted M≥α={promoted_over[:3]} (§5.5 build-block gap if AlertWorkflow missing)"
    )


def test_b4_eventual_detection_within_fixture_window(db_session, layer_b_meta):
    """B4: ≥1 drift-necessary pre-absorption TP or builder drift DecisionRecord.

    Scoped license: Design 1 fixture (7×5, clean baseline, seed 42) only —
    not a full-sweep generalization without Series B attribution decomposition.
    """
    meta = layer_b_meta
    c_novel = meta["c_novel"]
    decisions = (
        db_session.query(DecisionRecordModel)
        .filter(DecisionRecordModel.event_id.in_(meta["attack_event_ids"]))
        .all()
    )

    honest_fires = 0
    for d in decisions:
        if float(d.score) < ANOMALY_THRESHOLD:
            continue
        drift_c = _contrib(d, "drift_alert")
        if (float(d.score) - drift_c) >= ANOMALY_THRESHOLD:
            continue
        profile = (
            db_session.query(ProfileArtifactModel)
            .filter(ProfileArtifactModel.profile_version == d.profile_version)
            .one_or_none()
        )
        _, pre_abs = _pre_absorption(profile, c_novel)
        if pre_abs:
            honest_fires += 1

    builder_drift = 0
    for d in (
        db_session.query(DecisionRecordModel)
        .filter(DecisionRecordModel.entity_id == meta["attack_id"])
        .all()
    ):
        flags = d.flags or {}
        if isinstance(flags, dict) and flags.get("drift_alert") is True:
            if d.event_id not in meta["attack_event_ids"]:
                builder_drift += 1

    assert honest_fires + builder_drift >= 1, (
        f"B4 FAIL: no drift-necessary pre-absorption TP and no builder drift "
        f"DecisionRecord in fixture window (honest_fires={honest_fires}, "
        f"builder_drift={builder_drift}). Detection of boil-the-frog unproven "
        f"under Design 1 fixture conditions."
    )
