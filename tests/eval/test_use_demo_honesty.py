from pathlib import Path

from batch.eval.e2e_kernel import evaluate_scenario
from batch.eval.theater import TheaterContext, run_theater_detector


def test_detector_trips_on_series_a_current_fixture():
    tripped, _ = run_theater_detector(
        "unearned_demo_claim",
        TheaterContext(doc_texts={"x": "Current operating point: Precision: ~0.019 · FP: 3448"}),
    )
    assert tripped is True


def test_live_docs_pass_demo_honesty_both_arms(tmp_path):
    rows = evaluate_scenario("use.demo_honesty", sqlite_root=tmp_path)
    for row in rows:
        assert row.status == "pass"
        assert row.observed["unearned_demo_claim"] is False


def test_readme_and_spec_mark_series_a_archival():
    readme = Path("README.md").read_text(encoding="utf-8")
    spec = Path("docs/SPEC.md").read_text(encoding="utf-8")
    assert "Series I" in readme and "archival" in readme.lower()
    assert "Series I" in spec
