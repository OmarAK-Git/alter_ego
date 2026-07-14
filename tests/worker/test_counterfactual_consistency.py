import json
from datetime import datetime
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.database import Base
from core.models import DecisionRecordModel, ProfileArtifactModel
from worker.explainer import (
    LLMProvider,
    build_top_k_counterfactuals,
    generate_explanation,
    reset_explainer_queue_state,
)

CORPUS_PATH = Path(__file__).resolve().parent.parent / "fixtures" / "counterfactual_corpus.json"


def _load_corpus() -> dict:
    with CORPUS_PATH.open(encoding="utf-8") as f:
        return json.load(f)


def _assert_counterfactual_consistency(case: dict) -> None:
    """Harness metric: top-K counterfactuals match largest contributions."""
    k = _load_corpus()["k"]
    contributions = case["contributions"]
    expected = case["expected"]

    cfs = build_top_k_counterfactuals(contributions, k=k)

    assert len(cfs) == expected["count"]
    assert [cf.contribution_id for cf in cfs] == expected["contribution_ids"]
    assert [cf.score_delta for cf in cfs] == expected["score_deltas"]

    contrib_by_id = {c["contribution_id"]: c for c in contributions}
    for cf in cfs:
        orig = contrib_by_id[cf.contribution_id]
        feature_name = orig["feature_name"]
        score = orig["contribution_score"]
        assert feature_name in cf.counterfactual_text
        assert f"{score:.2f}" in cf.counterfactual_text
        assert cf.score_delta == score


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


@pytest.mark.parametrize("case", _load_corpus()["cases"], ids=lambda c: c["id"])
def test_corpus_counterfactual_consistency(case):
    _assert_counterfactual_consistency(case)


def test_build_top_k_counterfactuals_non_list_input():
    cfs = build_top_k_counterfactuals(None, k=3)
    assert cfs == []


def test_generate_explanation_counterfactual_integration(db_session, monkeypatch):
    """Integration: generate_explanation attaches corpus-consistent counterfactuals."""
    reset_explainer_queue_state()
    contributions = _load_corpus()["cases"][0]["contributions"]
    dec = DecisionRecordModel(
        decision_id="dec-cf",
        event_id="evt-cf",
        entity_id="user_1",
        timestamp=datetime.utcnow(),
        score=105.0,
        confidence=0.9,
        profile_version="v-cf",
        scoring_config_version="2.2",
        contributions=contributions,
        is_anomaly=True,
        cohort_used="role1",
        cohort_unsupported=False,
        flags=[],
    )
    prof = ProfileArtifactModel(
        profile_version="v-cf",
        entity_id="user_1",
        entity_type="human",
        created_at=datetime.utcnow(),
        data_window_start=datetime.utcnow(),
        data_window_end=datetime.utcnow(),
        features={},
    )
    db_session.add(dec)
    db_session.add(prof)
    db_session.commit()

    monkeypatch.setattr(
        "worker.explainer.load_scoring_config",
        lambda: {"version": "2.2", "explainer_queue_depth": 4},
    )

    class GoodLLM(LLMProvider):
        def __init__(self):
            super().__init__()
            self.model_id = "test-model"

        def generate(self, prompt, temperature=0.0):
            return json.dumps(
                {
                    "summary_text": "Behavior deviated from baseline.",
                    "claim_objects": [
                        {
                            "contribution_id": "c2",
                            "claim_text": "Geo distance drove the score.",
                            "evidence_binding": ["c2"],
                        }
                    ],
                }
            )

    record = generate_explanation("dec-cf", db_session, provider=GoodLLM())
    expected = build_top_k_counterfactuals(contributions, k=3)

    assert record.validation_status.value == "passed"
    assert len(record.counterfactuals) == len(expected)
    for actual, exp in zip(record.counterfactuals, expected, strict=True):
        assert actual.contribution_id == exp.contribution_id
        assert actual.score_delta == exp.score_delta
        assert actual.counterfactual_text == exp.counterfactual_text
