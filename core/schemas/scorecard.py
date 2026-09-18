from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

LOCKED_SCENARIO_IDS: frozenset[str] = frozenset(
    {
        "cap.attributed_s2_s3_s5",
        "cap.drift_vs_point_axes",
        "cap.no_n1_headline",
        "gov.no_knob_without_sweep",
        "gov.anomaly_opens_workflow",
        "gov.integrity_job_sees_decisions",
        "des.production_call_shape",
        "des.no_llm_in_score",
        "des.ngram_mismatch_halts",
        "thr.cmdline_injection_survives",
        "thr.api_key_required",
        "thr.fp_block_sanctuary",
        "use.pipeline_to_triage",
        "use.ui_sends_api_key",
        "use.demo_honesty",
    }
)

REALM_FOR_ID: dict[str, str] = {
    "cap.attributed_s2_s3_s5": "capability",
    "cap.drift_vs_point_axes": "capability",
    "cap.no_n1_headline": "capability",
    "gov.no_knob_without_sweep": "governance",
    "gov.anomaly_opens_workflow": "governance",
    "gov.integrity_job_sees_decisions": "governance",
    "des.production_call_shape": "design",
    "des.no_llm_in_score": "design",
    "des.ngram_mismatch_halts": "design",
    "thr.cmdline_injection_survives": "threat",
    "thr.api_key_required": "threat",
    "thr.fp_block_sanctuary": "threat",
    "use.pipeline_to_triage": "usability",
    "use.ui_sends_api_key": "usability",
    "use.demo_honesty": "usability",
}

PENDING_ALLOWED: frozenset[tuple[str, str]] = frozenset(
    {
        ("cap.attributed_s2_s3_s5", "new_build"),
        ("cap.drift_vs_point_axes", "new_build"),
        ("thr.fp_block_sanctuary", "new_build"),
    }
)


class ScorecardRow(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1"]
    scenario_id: str
    realm: Literal["capability", "governance", "design", "threat", "usability"]
    arm: Literal["old_build", "new_build"]
    status: Literal["pass", "fail", "pending", "error"]
    failure_class: Literal["none", "harness", "scorer", "theater_detector"]
    expected: dict[str, Any]
    observed: dict[str, Any]
    fixture: Literal["deterministic"]
    notes: str = ""

    @field_validator("scenario_id")
    @classmethod
    def _locked_id(cls, value: str) -> str:
        if value not in LOCKED_SCENARIO_IDS:
            raise ValueError(f"unknown scenario_id {value!r}; not in spec §5 set")
        return value

    @model_validator(mode="after")
    def _honesty(self) -> ScorecardRow:
        if REALM_FOR_ID[self.scenario_id] != self.realm:
            raise ValueError(f"realm {self.realm!r} does not match {self.scenario_id}")
        if self.status == "pending" and (self.scenario_id, self.arm) not in PENDING_ALLOWED:
            raise ValueError(
                f"pending illegal for {(self.scenario_id, self.arm)}; "
                "only capability quality new_build and thr.fp_block_sanctuary new_build"
            )
        if self.status in {"pass", "pending"} and self.failure_class != "none":
            raise ValueError("failure_class must be none when status is pass or pending")
        if self.status in {"fail", "error"} and self.failure_class == "none":
            raise ValueError("failure_class is required when status is fail or error")
        return self


def validate_scorecard_row(data: dict[str, Any]) -> ScorecardRow:
    return ScorecardRow.model_validate(data)
