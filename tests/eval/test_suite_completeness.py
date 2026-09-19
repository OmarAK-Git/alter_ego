from pathlib import Path

from batch.eval.scenario_loader import load_all_scenarios
from batch.eval.scorecard import assert_scorecard_complete
from core.schemas.scorecard import LOCKED_SCENARIO_IDS
from tests.eval.helpers import expected_pairs, scorecard_pairs


def test_fifteen_scenario_files_exist_and_stems_match():
    paths = sorted(Path("tests/eval/scenarios").glob("*.yaml"))
    stems = {p.stem for p in paths}
    assert stems == set(LOCKED_SCENARIO_IDS)
    specs = load_all_scenarios(Path("tests/eval/scenarios"))
    assert {s.scenario_id for s in specs} == set(LOCKED_SCENARIO_IDS)


def test_evaluate_all_emits_thirty_rows_and_no_illegal_pending(tmp_path):
    from batch.eval.e2e_kernel import evaluate_all

    rows = evaluate_all(sqlite_root=tmp_path)
    assert scorecard_pairs(rows) == expected_pairs()
    assert_scorecard_complete(rows)
    for row in rows:
        if row.status == "pending":
            assert (row.scenario_id, row.arm) in {
                ("cap.attributed_s2_s3_s5", "new_build"),
                ("cap.drift_vs_point_axes", "new_build"),
                ("thr.fp_block_sanctuary", "new_build"),
            }
        if row.scenario_id == "cap.no_n1_headline":
            assert row.status == "pass"
        if row.scenario_id == "use.demo_honesty":
            assert row.status == "pass"
