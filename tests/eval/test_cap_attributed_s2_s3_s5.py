from batch.eval.e2e_kernel import evaluate_scenario


def test_attributed_s2_s3_s5_old_recorded_new_pending(tmp_path):
    rows = {r.arm: r for r in evaluate_scenario("cap.attributed_s2_s3_s5", sqlite_root=tmp_path)}
    old = rows["old_build"]
    new = rows["new_build"]
    assert old.status == "pass"
    assert old.observed["corpus"] == "ci_compact_seed42_shaped"
    for key in ("scenario_2_slow_roll", "scenario_3_subtle", "scenario_5_patient_cycle"):
        cell = old.observed[key]
        assert cell["n"] >= 1
        assert "attributed_tp" in cell
        assert "recall" in cell
        assert cell.get("vacuous_r1") is False
    assert old.observed["f1_treated_as_primary"] is False
    assert new.status == "pending"
    assert new.failure_class == "none"
