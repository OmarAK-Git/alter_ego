from pathlib import Path

import pytest
from pydantic import ValidationError

from batch.eval.scenario_loader import load_scenario

SCENARIO_DIR = Path("tests/eval/scenarios")


def test_filename_stem_must_equal_scenario_id(tmp_path):
    p = tmp_path / "des.no_llm_in_score.yaml"
    p.write_text(
        """
schema_version: "1"
scenario_id: des.production_call_shape
realm: design
description: stem mismatch
runner: e2e_kernel
setup:
  call: run_pipeline
  events: mini
arms:
  old_build: {expected: {stages_complete: true}, fixture: deterministic}
  new_build: {expected: {stages_complete: true}, fixture: deterministic}
scorecard_pins: [stages_complete]
theater_detector: unit_as_e2e
""",
        encoding="utf-8",
    )
    with pytest.raises(ValidationError):
        load_scenario(p)


def test_runner_must_be_e2e_kernel(tmp_path):
    p = tmp_path / "des.production_call_shape.yaml"
    p.write_text(
        """
schema_version: "1"
scenario_id: des.production_call_shape
realm: design
description: wrong runner
runner: demo_path
setup:
  call: run_pipeline
  events: mini
arms:
  old_build: {expected: {stages_complete: true}, fixture: deterministic}
  new_build: {expected: {stages_complete: true}, fixture: deterministic}
scorecard_pins: [stages_complete]
theater_detector: unit_as_e2e
""",
        encoding="utf-8",
    )
    with pytest.raises(ValidationError):
        load_scenario(p)


def test_skip_flag_field_is_rejected(tmp_path):
    p = tmp_path / "des.production_call_shape.yaml"
    p.write_text(
        """
schema_version: "1"
scenario_id: des.production_call_shape
realm: design
description: skip flags are illegal
runner: e2e_kernel
skip: true
setup:
  call: run_pipeline
  events: mini
arms:
  old_build: {expected: {stages_complete: true}, fixture: deterministic}
  new_build: {expected: {stages_complete: true}, fixture: deterministic}
scorecard_pins: [stages_complete]
theater_detector: unit_as_e2e
""",
        encoding="utf-8",
    )
    with pytest.raises(ValidationError):
        load_scenario(p)


def test_load_des_production_call_shape_from_tree():
    spec = load_scenario(SCENARIO_DIR / "des.production_call_shape.yaml")
    assert spec.scenario_id == "des.production_call_shape"
    assert spec.runner == "e2e_kernel"
    assert spec.theater_detector == "unit_as_e2e"
    assert set(spec.arms) == {"old_build", "new_build"}
