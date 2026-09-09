"""Text-based extraction and scoring; no terminal I/O."""

from typing import TypeVar

from resume_cli.adapters.ai import request_json
from resume_cli.adapters.mock_data import load_assessment, read_fixture
from resume_cli.adapters.prompts import extract_messages, score_messages
from resume_cli.domain.documents import ParsedDocument, TextPage
from resume_cli.domain.schemas import (
    DetailedScoreResult,
    EvidenceScoreAssessment,
    Resume,
    ScoreAssessment,
    ScoreResult,
    StrictModel,
    finalize_evidence_score,
    finalize_score,
)

Model = TypeVar("Model", bound=StrictModel)


def _request(schema: type[Model], messages: list[dict[str, str]], *, mock: bool) -> Model:
    if mock:
        return load_assessment(schema)
    return request_json(schema, messages)


def extract_resume(text: str, *, mock: bool = False) -> Resume:
    return _request(Resume, extract_messages({"resume_text": text}), mock=mock)


def score_resume(
    text: str,
    jd: str,
    *,
    mock: bool = False,
    include_evidence: bool = False,
    document: ParsedDocument | None = None,
) -> ScoreResult | DetailedScoreResult:
    if include_evidence:
        assessment = _request(
            EvidenceScoreAssessment,
            score_messages({"resume_text": text, "jd_text": jd}, include_evidence=True),
            mock=mock,
        )
        source = read_fixture("evidence-resume.txt") if mock else text
        if mock:
            document = ParsedDocument(
                tuple(
                    TextPage(index, page, "text")
                    for index, page in enumerate(source.split("\f"), 1)
                )
            )
            source = document.text
            jd = read_fixture("evidence-jd.txt")
        return finalize_evidence_score(assessment, source, jd, document=document, mock=mock)
    assessment = _request(
        ScoreAssessment,
        score_messages({"resume_text": text, "jd_text": jd}),
        mock=mock,
    )
    return finalize_score(assessment)
