"""Read fixed, fictional package data only for explicitly requested mock mode."""

from importlib.resources import files
from typing import TypeVar

from resume_cli.domain.schemas import (
    EvidenceScoreAssessment,
    Resume,
    ScoreAssessment,
    StrictModel,
    validate_json,
)

Model = TypeVar("Model", bound=StrictModel)


def read_fixture(name: str) -> str:
    return files("resume_cli").joinpath("fixtures", name).read_text(encoding="utf-8")


def load_assessment(schema: type[Model]) -> Model:
    filename = {
        Resume: "resume.json",
        ScoreAssessment: "score-assessment.json",
        EvidenceScoreAssessment: "evidence-score-assessment.json",
    }[schema]
    return validate_json(read_fixture(filename), schema)
