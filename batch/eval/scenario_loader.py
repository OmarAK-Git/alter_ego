from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, ValidationError, field_validator, model_validator

from core.schemas.scorecard import LOCKED_SCENARIO_IDS, REALM_FOR_ID

ALLOWED_THEATER = frozenset(
    {
        "seeded_decision_e2e",
        "n1_headline",
        "unearned_demo_claim",
        "unit_as_e2e",
        "f1_only_usefulness",
        "stage_a_as_fp_win",
        "gt_in_scorer",
        "fake_ingest_api",
        "series_j_fold",
        "auto_resolved_as_precision",
    }
)


class ArmSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected: dict[str, Any]
    fixture: Literal["deterministic"]


class SetupSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")
    call: Literal["run_pipeline"]
    events: Literal["mini", "seed42_s2_s3_s5", "none"]
    notes: str = ""


class ScenarioSpec(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    schema_version: Literal["1"]
    scenario_id: str
    realm: Literal["capability", "governance", "design", "threat", "usability"]
    description: str
    runner: Literal["e2e_kernel"]
    setup: SetupSpec
    arms: dict[str, ArmSpec]
    scorecard_pins: list[str]
    theater_detector: str

    @field_validator("scenario_id")
    @classmethod
    def _id(cls, value: str) -> str:
        if value not in LOCKED_SCENARIO_IDS:
            raise ValueError(value)
        return value

    @field_validator("theater_detector")
    @classmethod
    def _theater(cls, value: str) -> str:
        if value not in ALLOWED_THEATER:
            raise ValueError(value)
        return value

    @model_validator(mode="after")
    def _cross(self) -> ScenarioSpec:
        if REALM_FOR_ID[self.scenario_id] != self.realm:
            raise ValueError("realm mismatch")
        if set(self.arms) != {"old_build", "new_build"}:
            raise ValueError("arms must be exactly old_build and new_build")
        if not self.scorecard_pins:
            raise ValueError("scorecard_pins required")
        return self


def load_scenario(path: Path) -> ScenarioSpec:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    spec = ScenarioSpec.model_validate(data)
    if path.stem != spec.scenario_id:
        raise ValidationError.from_exception_data(
            "ScenarioSpec",
            [
                {
                    "type": "value_error",
                    "loc": ("scenario_id",),
                    "input": spec.scenario_id,
                    "ctx": {
                        "error": (
                            f"filename stem {path.stem!r} != scenario_id {spec.scenario_id!r}"
                        ),
                    },
                }
            ],
        )
    return spec


def load_all_scenarios(directory: Path) -> list[ScenarioSpec]:
    return [load_scenario(p) for p in sorted(directory.glob("*.yaml"))]
