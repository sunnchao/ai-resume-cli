"""Public JSON contracts and the private AI scoring assessment."""

import json
from typing import Annotated, Any, Literal, TypeVar

from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    StringConstraints,
    ValidationError,
    field_validator,
)

from resume_cli.documents import ParsedDocument, locate_quote
from resume_cli.errors import ResumeError


def _nullable_text(value: Any) -> Any:
    return value.strip() or None if isinstance(value, str) else value


NullableText = Annotated[str | None, BeforeValidator(_nullable_text)]
NonEmptyText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
Score = Annotated[int, Field(ge=0, le=100)]


class StrictModel(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")


class Education(StrictModel):
    school: NullableText
    major: NullableText
    degree: NullableText
    graduation_time: NullableText


class Resume(StrictModel):
    name: NullableText
    phone: NullableText
    email: NullableText
    city: NullableText
    education: list[Education]
    skills: list[str]

    @field_validator("skills")
    @classmethod
    def clean_skills(cls, value: list[str]) -> list[str]:
        return list(dict.fromkeys(skill.strip() for skill in value if skill.strip()))


class JDRequirements(StrictModel):
    skills: bool
    experience: bool
    education: bool


class ScoreAssessment(StrictModel):
    """Internal flags let local code handle missing JD criteria consistently."""

    jd_requirements: JDRequirements
    skill_score: Score
    experience_score: Score
    education_score: Score
    comment: NonEmptyText
    interview_questions: list[NonEmptyText]


class ScoreResult(StrictModel):
    overall_score: Score
    skill_score: Score
    experience_score: Score
    education_score: Score
    comment: NonEmptyText
    interview_questions: list[NonEmptyText] = Field(min_length=2, max_length=3)


class EvidenceItem(StrictModel):
    source: Literal["resume"]
    quote: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=240)]
    relevance: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=240)
    ]
    jd_quote: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=240)]


EvidenceList = Annotated[list[EvidenceItem], Field(max_length=3)]
GapList = Annotated[
    list[Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=240)]],
    Field(max_length=6),
]


class EvidenceScoreAssessment(ScoreAssessment):
    """Requested only for --evidence, preserving the validated default AI contract."""

    skill_evidence: EvidenceList
    experience_evidence: EvidenceList
    education_evidence: EvidenceList
    gaps: GapList
    gap_jd_quotes: GapList


class TextLocation(StrictModel):
    start_char: Annotated[int, Field(ge=0)]
    end_char: Annotated[int, Field(gt=0)]
    line_start: Annotated[int, Field(ge=1)]
    line_end: Annotated[int, Field(ge=1)]


class ResumeLocation(TextLocation):
    page: Annotated[int | None, Field(ge=1)]
    method: Literal["text", "pdf_text", "pdf_layout", "ocr"]


class LocatedEvidenceItem(EvidenceItem):
    resume_locations: Annotated[list[ResumeLocation], Field(min_length=1)]
    jd_location: TextLocation


class GapEvidence(StrictModel):
    gap_index: Annotated[int, Field(ge=0)]
    jd_quote: NonEmptyText
    jd_location: TextLocation


class DetailedScoreResult(ScoreResult):
    """Optional explainability fields; the default score output stays unchanged."""

    evidence_basis: Literal["input_resume", "mock_fixture"]
    evidence_schema_version: Literal["2"] = "2"
    skill_evidence: Annotated[list[LocatedEvidenceItem], Field(max_length=3)]
    experience_evidence: Annotated[list[LocatedEvidenceItem], Field(max_length=3)]
    education_evidence: Annotated[list[LocatedEvidenceItem], Field(max_length=3)]
    gaps: GapList
    gap_evidence: Annotated[list[GapEvidence], Field(max_length=6)]


Model = TypeVar("Model", bound=StrictModel)


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key")
        result[key] = value
    return result


def _invalid_constant(_: str) -> None:
    raise ValueError("Non-standard JSON constant")


def validate_json(raw: str, schema: type[Model]) -> Model:
    try:
        data = json.loads(raw, object_pairs_hook=_unique_object, parse_constant=_invalid_constant)
    except (ValueError, RecursionError) as exc:
        raise ResumeError(
            "AI_JSON_INVALID", "AI 未返回单个有效 JSON 对象；请重试或检查模型。", 5
        ) from exc
    try:
        return schema.model_validate(data)
    except ValidationError as exc:
        first = exc.errors(include_input=False, include_url=False)[0]
        # Do not echo unknown keys: even a validation path can contain private input.
        known = set(Resume.model_fields) | set(Education.model_fields)
        known |= (
            set(ScoreAssessment.model_fields)
            | set(JDRequirements.model_fields)
            | set(EvidenceItem.model_fields)
            | set(DetailedScoreResult.model_fields)
            | set(EvidenceScoreAssessment.model_fields)
            | set(TextLocation.model_fields)
            | set(ResumeLocation.model_fields)
            | set(LocatedEvidenceItem.model_fields)
            | set(GapEvidence.model_fields)
        )
        location = ".".join(
            str(x) if isinstance(x, int) or x in known else "?" for x in first["loc"]
        )
        raise ResumeError(
            "AI_SCHEMA_INVALID", f"AI 字段校验失败：{location or '根对象'}（{first['type']}）。", 5
        ) from exc


def finalize_score(assessment: ScoreAssessment) -> ScoreResult:
    flags = assessment.jd_requirements
    if not any([flags.skills, flags.experience, flags.education]):
        raise ResumeError("JD_REQUIREMENTS_MISSING", "JD 未包含可识别的职责或任职要求，无法评分。")
    skill = assessment.skill_score if flags.skills else 100
    experience = assessment.experience_score if flags.experience else 100
    education = assessment.education_score if flags.education else 100
    notes = [
        f"{name}未设门槛，此项按满分处理。"
        for name, required in [
            ("技能", flags.skills),
            ("经验", flags.experience),
            ("教育", flags.education),
        ]
        if not required
    ]
    data = {
        # Integer arithmetic implements round-half-up without floating-point surprises.
        "overall_score": (skill * 5 + experience * 3 + education * 2 + 5) // 10,
        "skill_score": skill,
        "experience_score": experience,
        "education_score": education,
        "comment": assessment.comment + (" " + " ".join(notes) if notes else ""),
        "interview_questions": assessment.interview_questions,
    }
    return validate_json(json.dumps(data, ensure_ascii=False), ScoreResult)


def finalize_evidence_score(
    assessment: EvidenceScoreAssessment,
    resume_text: str,
    jd_text: str,
    *,
    document: ParsedDocument | None = None,
    mock: bool = False,
) -> DetailedScoreResult:
    result = finalize_score(assessment)
    document = document or ParsedDocument.from_text(resume_text)
    if document.text != resume_text:
        raise ResumeError("EVIDENCE_DOCUMENT_MISMATCH", "页文本与评分输入不一致，无法定位证据。")
    data = result.model_dump()
    groups = (
        ("skill_evidence", assessment.jd_requirements.skills),
        ("experience_evidence", assessment.jd_requirements.experience),
        ("education_evidence", assessment.jd_requirements.education),
    )
    for field, required in groups:
        items = getattr(assessment, field)
        if not required and items:
            raise ResumeError(
                "AI_EVIDENCE_INVALID", f"{field} 对应的 JD 未设门槛，应返回空数组。", 5
            )
        located = []
        for index, item in enumerate(items):
            matches = []
            for page in document.pages:
                location = locate_quote(page.text, item.quote)
                if location is not None:
                    matches.append({**location, "page": page.number, "method": page.method})
            if not matches:
                raise ResumeError(
                    "AI_EVIDENCE_INVALID",
                    f"{field}.{index}.quote 未在简历原文中找到；请重试，或不使用 --evidence。",
                    5,
                )
            jd_location = locate_quote(jd_text, item.jd_quote)
            if jd_location is None:
                raise ResumeError(
                    "AI_JD_EVIDENCE_INVALID", f"{field}.{index}.jd_quote 未在 JD 原文中找到。", 5
                )
            located.append(
                {**item.model_dump(), "resume_locations": matches, "jd_location": jd_location}
            )
        data[field] = located
    if len(assessment.gap_jd_quotes) != len(assessment.gaps):
        raise ResumeError("AI_JD_EVIDENCE_INVALID", "gap_jd_quotes 必须与 gaps 一一对应。", 5)
    gap_evidence = []
    for index, quote in enumerate(assessment.gap_jd_quotes):
        location = locate_quote(jd_text, quote)
        if location is None:
            raise ResumeError(
                "AI_JD_EVIDENCE_INVALID", f"gap_jd_quotes.{index} 未在 JD 原文中找到。", 5
            )
        gap_evidence.append({"gap_index": index, "jd_quote": quote, "jd_location": location})
    data.update(gaps=assessment.gaps, gap_evidence=gap_evidence)
    data["evidence_basis"] = "mock_fixture" if mock else "input_resume"
    return validate_json(json.dumps(data, ensure_ascii=False), DetailedScoreResult)
