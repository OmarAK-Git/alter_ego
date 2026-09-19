from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

THEATER_DETECTOR_NAMES: frozenset[str] = frozenset(
    {
        "seeded_decision_e2e",
        "n1_headline",
        "unearned_demo_claim",
        "unit_as_e2e",
        "f1_only_usefulness",
        "stage_a_as_fp_win",
        "gt_in_scorer",
        "fake_ingest_api",
        "series_j_fold",
        "auto_resolved_as_precision",
    }
)


@dataclass
class TheaterContext:
    decision_insert_path: str | None = None
    headline_text: str = ""
    doc_texts: dict[str, str] = field(default_factory=dict)
    used_run_pipeline: bool = True
    f1_treated_as_primary: bool = False
    stage_a_cited_as_fp_win: bool = False
    scorer_source: str = ""
    introduces_http_ingest: bool = False
    staffs_series_j: bool = False
    auto_resolved_used_as_fp_down: bool = False


def _n1_headline(ctx: TheaterContext) -> tuple[bool, str]:
    text = ctx.headline_text
    has_s1 = "S1" in text
    has_s4 = "S4" in text
    has_s2 = "S2" in text
    has_s3 = "S3" in text
    has_s5 = "S5" in text
    if (has_s1 or has_s4) and not (has_s2 and has_s3 and has_s5):
        return True, "headline reports S1/S4 without S2+S3+S5 n-attributed catch"
    return False, ""


def _seeded(ctx: TheaterContext) -> tuple[bool, str]:
    if ctx.decision_insert_path or not ctx.used_run_pipeline:
        if ctx.decision_insert_path or ctx.used_run_pipeline is False:
            if ctx.used_run_pipeline:
                return False, ""
            return True, "DecisionRecord INSERT / demo_path counted as E2E"
    return False, ""


def _unit_as_e2e(ctx: TheaterContext) -> tuple[bool, str]:
    if not ctx.used_run_pipeline:
        return True, "row emitted without run_pipeline"
    return False, ""


def _gt(ctx: TheaterContext) -> tuple[bool, str]:
    src = ctx.scorer_source
    if "EvalGroundTruth" in src or "eval_ground_truth" in src or "is_malicious" in src:
        return True, "scorer source reads labels"
    return False, ""


def _fake_ingest(ctx: TheaterContext) -> tuple[bool, str]:
    if ctx.introduces_http_ingest:
        return True, "/api/ingest that is not Event JSONL"
    return False, ""


def _unearned(ctx: TheaterContext) -> tuple[bool, str]:
    joined = "\n".join(ctx.doc_texts.values())
    series_a_current = (
        "0.019" in joined
        or "3448" in joined
        or "P≈0.019" in joined
        or "P~0.019" in joined
        or "Precision:** ~0.019" in joined
        or "Precision: ~0.019" in joined
    )
    archival_marked = "archival" in joined.lower() and "series i" in joined.lower()
    calibrated_claim = (
        "CALIBRATED" in joined
        and "not CALIBRATED" not in joined
        and "not calibrated" not in joined.lower()
    )
    canary_claim = "canary" in joined.lower() and "no-go" not in joined.lower()
    if series_a_current and not archival_marked:
        return True, "Series A cited as current without Series I SoT + archival mark"
    if calibrated_claim or canary_claim:
        return True, "CALIBRATED/canary claimed while Series I is calibrated:false"
    return False, ""


def _flag(name: str, attr: str, msg: str) -> Callable[[TheaterContext], tuple[bool, str]]:
    def _inner(ctx: TheaterContext) -> tuple[bool, str]:
        return (True, msg) if getattr(ctx, attr) else (False, "")

    _inner.__name__ = name
    return _inner


REGISTRY: dict[str, Callable[[TheaterContext], tuple[bool, str]]] = {
    "n1_headline": _n1_headline,
    "seeded_decision_e2e": _seeded,
    "unit_as_e2e": _unit_as_e2e,
    "gt_in_scorer": _gt,
    "fake_ingest_api": _fake_ingest,
    "unearned_demo_claim": _unearned,
    "f1_only_usefulness": _flag("f1", "f1_treated_as_primary", "F1@45 treated as primary"),
    "stage_a_as_fp_win": _flag("sa", "stage_a_cited_as_fp_win", "Stage A cited as thr=45 FP win"),
    "series_j_fold": _flag("sj", "staffs_series_j", "Series J fold staffed"),
    "auto_resolved_as_precision": _flag(
        "ar", "auto_resolved_used_as_fp_down", "auto_resolved used as FP-down"
    ),
}


def run_theater_detector(name: str, ctx: TheaterContext) -> tuple[bool, str]:
    if name not in THEATER_DETECTOR_NAMES:
        raise KeyError(name)
    return REGISTRY[name](ctx)
