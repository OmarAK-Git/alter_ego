from pydantic import ValidationError
import pytest

from core.schemas.scorecard import (
    LOCKED_SCENARIO_IDS,
    PENDING_ALLOWED,
    ScorecardRow,
)


REQUIRED_IDS = {
    "cap.attributed_s2_s3_s5",
    "cap.drift_vs_point_axes",
    "cap.no_n1_headline",
    "gov.no_knob_without_sweep",
    "gov.anomaly_opens_workflow",
    "gov.integrity_job_sees_decisions",
    "des.production_call_shape",
    "des.no_llm_in_score",
    "des.ngram_mismatch_halts",
    "thr.cmdline_injection_survives",
    "thr.api_key_required",
    "thr.fp_block_sanctuary",
    "use.pipeline_to_triage",
    "use.ui_sends_api_key",
    "use.demo_honesty",
}


def _row(**overrides):
    base = dict(
        schema_version="1",
        scenario_id="des.no_llm_in_score",
        realm="design",
        arm="old_build",
        status="pass",
        failure_class="none",
        expected={"import_llm": False},
        observed={"import_llm": False},
        fixture="deterministic",
        notes="",
    )
    base.update(overrides)
    return ScorecardRow.model_validate(base)


def test_locked_ids_are_exactly_the_fifteen_from_spec_section_5():
    assert LOCKED_SCENARIO_IDS == frozenset(REQUIRED_IDS)
    assert len(LOCKED_SCENARIO_IDS) == 15
    assert "cap.attributed_s3" not in LOCKED_SCENARIO_IDS
    assert "cap.attributed_s2_s3_s5" in LOCKED_SCENARIO_IDS


def test_extra_field_is_rejected():
    with pytest.raises(ValidationError):
        _row(grade="A")


def test_unknown_scenario_id_is_rejected():
    with pytest.raises(ValidationError):
        _row(scenario_id="cap.attributed_s3", realm="capability")


def test_pending_only_on_allowed_quality_and_sanctuary_new_build():
    assert PENDING_ALLOWED == {
        ("cap.attributed_s2_s3_s5", "new_build"),
        ("cap.drift_vs_point_axes", "new_build"),
        ("thr.fp_block_sanctuary", "new_build"),
    }
    ok = _row(
        scenario_id="cap.attributed_s2_s3_s5",
        realm="capability",
        arm="new_build",
        status="pending",
        failure_class="none",
        expected={"quality": "unclaimed"},
        observed={"quality": "unclaimed"},
    )
    assert ok.status == "pending"
    with pytest.raises(ValidationError):
        _row(status="pending")
    with pytest.raises(ValidationError):
        _row(
            scenario_id="cap.no_n1_headline",
            realm="capability",
            arm="new_build",
            status="pending",
            failure_class="none",
            expected={},
            observed={},
        )


def test_failure_class_none_only_when_pass_or_pending():
    with pytest.raises(ValidationError):
        _row(status="fail", failure_class="none", expected={}, observed={})
    fail = _row(
        status="fail",
        failure_class="theater_detector",
        expected={"ok": True},
        observed={"ok": False},
    )
    assert fail.failure_class == "theater_detector"


def test_fixture_must_be_deterministic():
    with pytest.raises(ValidationError):
        _row(fixture="fake_provider")
