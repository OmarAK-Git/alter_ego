"""Unit tests for QUIET∧ATTEST helpers (S55.2)."""

from core.attestation import (
    ALPHA_ANCHOR,
    ALPHA_PROD,
    ANCHOR_HISTORY_COUNT,
    MIN_DWELL_BUILDS,
    QUIET_WINDOW_DAYS,
    novel_mass,
    peak_drift_ok,
    attest,
)


def test_declared_defaults_match_design():
    assert QUIET_WINDOW_DAYS == 3
    assert MIN_DWELL_BUILDS == 2
    assert ALPHA_PROD == 0.02
    assert ALPHA_ANCHOR == 0.05
    assert ANCHOR_HISTORY_COUNT == 5


def test_novel_mass_zero_when_support_covered():
    shadow = {
        "process_names": {"chrome.exe": 90, "outlook.exe": 10},
        "endpoints": {"ep-a": 100},
        "geolocations": {"US": 100},
    }
    baseline = {
        "process_names": {"chrome.exe": 50, "outlook.exe": 40, "slack.exe": 10},
        "endpoints": {"ep-a": 80, "ep-b": 20},
        "geolocations": {"US": 100},
    }
    assert novel_mass(shadow, baseline) == 0.0


def test_novel_mass_max_over_dimensions():
    # 20% novel process mass; endpoints fully novel vs empty support → 1.0 wins.
    shadow = {
        "process_names": {"chrome.exe": 80, "evil.exe": 20},
        "endpoints": {"ep-new": 100},
        "geolocations": {"US": 100},
    }
    baseline = {
        "process_names": {"chrome.exe": 100},
        "endpoints": {},
        "geolocations": {"US": 100},
    }
    assert novel_mass(shadow, baseline) == 1.0


def test_novel_mass_process_fraction_only():
    shadow = {
        "process_names": {"chrome.exe": 80, "evil.exe": 20},
        "endpoints": {"ep-a": 100},
        "geolocations": {"US": 100},
    }
    baseline = {
        "process_names": {"chrome.exe": 100},
        "endpoints": {"ep-a": 100},
        "geolocations": {"US": 100},
    }
    assert abs(novel_mass(shadow, baseline) - 0.2) < 1e-9


def test_peak_drift_ok_strictly_below_threshold():
    assert peak_drift_ok([1.0, 4.9], drift_threshold=5.0) is True
    assert peak_drift_ok([1.0, 5.0], drift_threshold=5.0) is False
    assert peak_drift_ok([], drift_threshold=5.0) is True


def test_attest_requires_all_three_gates():
    shadow = {
        "process_names": {"chrome.exe": 100},
        "endpoints": {"ep-a": 100},
        "geolocations": {"US": 100},
    }
    p0 = dict(shadow)
    anchor = dict(shadow)
    ok, detail = attest(
        shadow_features=shadow,
        promoted_features=p0,
        anchor_features=anchor,
        shadow_drifts_during_block=[1.0, 2.0],
        drift_threshold=5.0,
    )
    assert ok is True
    assert detail["peak_drift_ok"] is True
    assert detail["novel_mass_prod"] < ALPHA_PROD
    assert detail["novel_mass_anchor"] < ALPHA_ANCHOR

    fail, detail_fail = attest(
        shadow_features={
            "process_names": {"evil.exe": 100},
            "endpoints": {"ep-a": 100},
            "geolocations": {"US": 100},
        },
        promoted_features=p0,
        anchor_features=anchor,
        shadow_drifts_during_block=[1.0],
        drift_threshold=5.0,
    )
    assert fail is False
    assert detail_fail["novel_mass_prod"] >= ALPHA_PROD
