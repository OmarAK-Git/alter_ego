"""QUIET ∧ ATTEST helpers for §5.5 alert auto-resolution (S55 lifecycle).

Declared-not-derived code defaults — not written to scoring_config.yaml this cycle.
See docs/scoring-config-governance-s55-lifecycle.md and design §4.5 / §6.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

# Design §6 — declared-not-derived (governance record; YAML write deferred).
QUIET_WINDOW_DAYS = 3
MIN_DWELL_BUILDS = 2
ALPHA_PROD = 0.02
ALPHA_ANCHOR = 0.05
ANCHOR_HISTORY_COUNT = 5  # = drift_comparison_history_count

NOVEL_MASS_DIMENSIONS = ("process_names", "endpoints", "geolocations")


def _hist_mass(hist: Mapping[str, Any] | None) -> float:
    if not hist:
        return 0.0
    return float(sum(float(v) for v in hist.values()))


def _dimension_novel_fraction(
    shadow_hist: Mapping[str, Any] | None,
    baseline_hist: Mapping[str, Any] | None,
) -> float:
    """Fraction of shadow mass in categories absent from baseline support."""
    if not shadow_hist:
        return 0.0
    total = _hist_mass(shadow_hist)
    if total <= 0.0:
        return 0.0
    support = set((baseline_hist or {}).keys())
    novel = sum(
        float(v) for k, v in shadow_hist.items() if str(k) not in support
    )
    return novel / total


def novel_mass(
    shadow_features: Mapping[str, Any],
    baseline_features: Mapping[str, Any],
) -> float:
    """M_novel(S, P) = max over categorical dims of novel-mass fraction.

    Dimensions: process_names, endpoints, geolocations (Design §4.5).
    """
    fractions = [
        _dimension_novel_fraction(
            shadow_features.get(dim),  # type: ignore[arg-type]
            baseline_features.get(dim),  # type: ignore[arg-type]
        )
        for dim in NOVEL_MASS_DIMENSIONS
    ]
    return max(fractions) if fractions else 0.0


def peak_drift_ok(
    shadow_drifts_during_block: Sequence[float],
    drift_threshold: float,
) -> bool:
    """Peak (not terminal) cumulative_drift across block-era shadows < threshold."""
    if not shadow_drifts_during_block:
        return True
    return max(float(d) for d in shadow_drifts_during_block) < float(drift_threshold)


def attest(
    *,
    shadow_features: Mapping[str, Any],
    promoted_features: Mapping[str, Any],
    anchor_features: Mapping[str, Any],
    shadow_drifts_during_block: Sequence[float],
    drift_threshold: float,
    alpha_prod: float = ALPHA_PROD,
    alpha_anchor: float = ALPHA_ANCHOR,
) -> tuple[bool, dict[str, Any]]:
    """ATTEST: peak-drift ∧ novel-mass(prod) ∧ novel-mass(anchor)."""
    peak_ok = peak_drift_ok(shadow_drifts_during_block, drift_threshold)
    m_prod = novel_mass(shadow_features, promoted_features)
    m_anchor = novel_mass(shadow_features, anchor_features)
    detail = {
        "peak_drift_ok": peak_ok,
        "peak_drift": (
            max(float(d) for d in shadow_drifts_during_block)
            if shadow_drifts_during_block
            else 0.0
        ),
        "drift_threshold": float(drift_threshold),
        "novel_mass_prod": m_prod,
        "novel_mass_anchor": m_anchor,
        "alpha_prod": alpha_prod,
        "alpha_anchor": alpha_anchor,
    }
    ok = peak_ok and m_prod < alpha_prod and m_anchor < alpha_anchor
    detail["attest_ok"] = ok
    return ok, detail
