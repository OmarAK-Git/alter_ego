from pathlib import Path

from batch.eval.e2e_kernel import evaluate_scenario, scorer_import_guard


def test_scorer_import_guard_on_live_source():
    src = Path("worker/scorer.py").read_text(encoding="utf-8")
    observed = scorer_import_guard(src)
    assert observed["import_llm"] is False
    assert observed["import_explainer"] is False


def test_des_no_llm_in_score_both_arms(tmp_path):
    rows = evaluate_scenario("des.no_llm_in_score", sqlite_root=tmp_path)
    for row in rows:
        assert row.status == "pass"
        assert row.observed["import_llm"] is False
        assert row.observed["import_explainer"] is False
