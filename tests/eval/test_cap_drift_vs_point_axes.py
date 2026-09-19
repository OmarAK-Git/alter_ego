from batch.eval.e2e_kernel import evaluate_scenario


def test_axes_split_old_recorded_new_pending(tmp_path):
    rows = {r.arm: r for r in evaluate_scenario("cap.drift_vs_point_axes", sqlite_root=tmp_path)}
    old = rows["old_build"]
    new = rows["new_build"]
    assert old.status == "pass"
    assert old.observed["corpus"] == "ci_compact_seed42_shaped"
    assert "drift_alerts" in old.observed
    assert "point_anomaly_fp" in old.observed
    assert "f1_at_45" in old.observed
    assert old.observed["f1_treated_as_primary"] is False
    assert old.observed["axes_split"] is True
    assert new.status == "pending"
