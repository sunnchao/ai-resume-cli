"""Batch result contracts."""

from typing import Annotated, Literal

from pydantic import Field

from resume_cli.domain.schemas import DetailedScoreResult, Resume, ScoreResult, StrictModel

Operation = Literal["extract", "score"]


class BatchError(StrictModel):
    code: str
    message: str
    exit_code: int


class BatchSuccess(StrictModel):
    file: str
    status: Literal["success"] = "success"
    result: Resume | DetailedScoreResult | ScoreResult


class BatchFailure(StrictModel):
    file: str
    status: Literal["error"] = "error"
    error: BatchError


class BatchReport(StrictModel):
    operation: Operation
    mode: Literal["mock", "ai"]
    total: int
    succeeded: int
    failed: int
    results: list[Annotated[BatchSuccess | BatchFailure, Field(discriminator="status")]]
