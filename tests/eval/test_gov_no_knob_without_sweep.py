import hashlib
from pathlib import Path

from batch.eval.e2e_kernel import evaluate_scenario
from core.schemas.scorecard import ScorecardRow

YAML_PATH = Path("config/scoring_config.yaml")
BASELINE = Path("tests/eval/fixtures/scoring_config_baseline.sha256")


def test_baseline_hash_file_matches_current_yaml():
    digest = hashlib.sha256(YAML_PATH.read_bytes()).hexdigest()
    assert BASELINE.read_text(encoding="utf-8").strip() == digest


def test_both_arms_pass_when_yaml_matches_baseline(tmp_path):
    rows = evaluate_scenario("gov.no_knob_without_sweep", sqlite_root=tmp_path)
    assert {r.arm for r in rows} == {"old_build", "new_build"}
    for row in rows:
        assert isinstance(row, ScorecardRow)
        assert row.status == "pass"
        assert row.failure_class == "none"
        assert row.observed["knob_diff_unrecorded"] is False
        assert (
            row.observed.get("theater_detector_tripped", False) is False
            or "theater_detector_tripped" not in row.observed
        )
