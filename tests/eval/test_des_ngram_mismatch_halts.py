from batch.eval.e2e_kernel import evaluate_scenario
from worker.scorer import EMBEDDING_METADATA_MISMATCH_FLAG


def test_nomic_metadata_halts_both_arms(tmp_path):
    rows = evaluate_scenario("des.ngram_mismatch_halts", sqlite_root=tmp_path)
    for row in rows:
        assert row.status == "pass"
        assert row.observed["halt_score"] == 0.0
        assert row.observed["halt_flag"] == EMBEDDING_METADATA_MISMATCH_FLAG
