from batch.eval.e2e_kernel import evaluate_scenario


def test_sanctuary_old_build_recorded_new_build_pending(tmp_path):
    rows = {r.arm: r for r in evaluate_scenario("thr.fp_block_sanctuary", sqlite_root=tmp_path)}
    old = rows["old_build"]
    new = rows["new_build"]
    assert old.status == "pass"
    assert old.observed["fp_opened_before_ladder"] is True
    assert "attributed_ladder_tp" in old.observed
    assert new.status == "pending"
    assert new.failure_class == "none"
    assert new.observed["stage_b"] == "pending"
