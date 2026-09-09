import json
from importlib.resources import files

import pytest

from resume_cli.domain.errors import ResumeError
from resume_cli.domain.schemas import (
    DetailedScoreResult,
    EvidenceScoreAssessment,
    Resume,
    ScoreAssessment,
    finalize_evidence_score,
    finalize_score,
    validate_json,
)


def resume_data():
    return json.loads(files("resume_cli").joinpath("fixtures/resume.json").read_text())


def assessment_data():
    return json.loads(files("resume_cli").joinpath("fixtures/score-assessment.json").read_text())


def evidence_data():
    return json.loads(
        files("resume_cli").joinpath("fixtures/evidence-score-assessment.json").read_text()
    )


def evidence_jd():
    return files("resume_cli").joinpath("fixtures/evidence-jd.txt").read_text(encoding="utf-8")


def evidence_resume():
    return files("resume_cli").joinpath("fixtures/evidence-resume.txt").read_text()


def test_nullable_fields_and_empty_lists():
    data = resume_data()
    data.update(name="  ", phone=None, education=[], skills=[])
    result = validate_json(json.dumps(data), Resume)
    assert result.name is None and result.phone is None
    assert result.education == [] and result.skills == []


def test_multiple_education_and_skill_normalization():
    data = resume_data()
    data["education"].append(dict(school=None, major=None, degree="硕士", graduation_time="2026"))
    data["skills"] = [" Python ", "Python", "", "  ", "React"]
    result = validate_json(json.dumps(data), Resume)
    assert len(result.education) == 2
    assert result.education[1].graduation_time == "2026"
    assert result.skills == ["Python", "React"]


@pytest.mark.parametrize(
    "raw", ["not JSON", "```json\n{}\n```", "{} {}", '{"a":1,"a":2}', '{"a":NaN}', '{"a":Infinity}']
)
def test_reject_malformed_json(raw):
    with pytest.raises(ResumeError) as caught:
        validate_json(raw, Resume)
    assert caught.value.code == "AI_JSON_INVALID"


@pytest.mark.parametrize("field,value", [("phone", 123), ("skills", [7]), ("education", None)])
def test_strict_types(field, value):
    data = resume_data()
    data[field] = value
    with pytest.raises(ResumeError) as caught:
        validate_json(json.dumps(data), Resume)
    assert caught.value.exit_code == 5


def test_missing_field_and_extra_private_field():
    data = resume_data()
    del data["email"]
    with pytest.raises(ResumeError, match="email"):
        validate_json(json.dumps(data), Resume)
    data = resume_data()
    data["sensitive-unknown-key"] = "private value"
    with pytest.raises(ResumeError) as caught:
        validate_json(json.dumps(data), Resume)
    assert "sensitive" not in str(caught.value) and "private value" not in str(caught.value)


@pytest.mark.parametrize("value", [-1, 101, True, "80", 80.0])
def test_score_rejects_invalid_integer(value):
    data = assessment_data()
    data["skill_score"] = value
    with pytest.raises(ResumeError, match="skill_score"):
        validate_json(json.dumps(data), ScoreAssessment)


def test_weighted_total_and_half_up():
    result = finalize_score(validate_json(json.dumps(assessment_data()), ScoreAssessment))
    assert result.overall_score == 82
    data = assessment_data()
    data.update(skill_score=1, experience_score=0, education_score=0)
    assert finalize_score(validate_json(json.dumps(data), ScoreAssessment)).overall_score == 1


def test_evidence_is_opt_in_and_preserves_default_contract():
    assessment = validate_json(json.dumps(evidence_data()), EvidenceScoreAssessment)
    default = finalize_score(assessment)
    detailed = finalize_evidence_score(assessment, evidence_resume(), evidence_jd())
    assert "skill_evidence" not in default.model_dump()
    assert isinstance(detailed, DetailedScoreResult)
    assert detailed.skill_evidence[0].source == "resume"
    assert detailed.evidence_basis == "input_resume"
    assert detailed.gaps


def test_evidence_rejects_untrusted_sources_and_long_quotes():
    data = evidence_data()
    data["skill_evidence"][0]["source"] = "jd"
    with pytest.raises(ResumeError):
        validate_json(json.dumps(data), EvidenceScoreAssessment)
    data = evidence_data()
    data["skill_evidence"][0]["quote"] = "x" * 241
    with pytest.raises(ResumeError):
        validate_json(json.dumps(data), EvidenceScoreAssessment)


def test_evidence_quotes_must_be_in_current_resume_and_errors_do_not_leak():
    data = evidence_data()
    data["skill_evidence"][0]["quote"] = "PRIVATE fabricated quote"
    assessment = validate_json(json.dumps(data), EvidenceScoreAssessment)
    with pytest.raises(ResumeError) as caught:
        finalize_evidence_score(assessment, evidence_resume(), evidence_jd())
    assert caught.value.code == "AI_EVIDENCE_INVALID"
    assert caught.value.exit_code == 5
    assert "skill_evidence.0.quote" in str(caught.value)
    assert "PRIVATE" not in str(caught.value)


def test_evidence_only_ignores_whitespace():
    data = evidence_data()
    data["skill_evidence"][0]["quote"] = "技能：Python、\n React、PostgreSQL"
    assessment = validate_json(json.dumps(data), EvidenceScoreAssessment)
    result = finalize_evidence_score(assessment, evidence_resume(), evidence_jd(), mock=True)
    assert result.evidence_basis == "mock_fixture"
    with pytest.raises(ResumeError):
        finalize_evidence_score(
            assessment, evidence_resume().replace("Python", "python"), evidence_jd()
        )


@pytest.mark.parametrize("field, count", [("skill_evidence", 4), ("gaps", 7)])
def test_evidence_array_limits(field, count):
    data = evidence_data()
    data[field] *= count
    with pytest.raises(ResumeError):
        validate_json(json.dumps(data), EvidenceScoreAssessment)


def test_evidence_not_used_for_a_dimension_without_jd_requirements():
    data = evidence_data()
    data["jd_requirements"]["education"] = False
    assessment = validate_json(json.dumps(data), EvidenceScoreAssessment)
    with pytest.raises(ResumeError, match="未设门槛"):
        finalize_evidence_score(assessment, evidence_resume(), evidence_jd())
    data["education_evidence"] = []
    assessment = validate_json(json.dumps(data), EvidenceScoreAssessment)
    result = finalize_evidence_score(assessment, evidence_resume(), evidence_jd())
    assert result.education_score == 100
    assert not result.education_evidence


def test_no_education_requirement_gets_documented_full_marks():
    data = assessment_data()
    data["jd_requirements"]["education"] = False
    data["education_score"] = 0
    result = finalize_score(validate_json(json.dumps(data), ScoreAssessment))
    assert result.education_score == 100
    assert result.overall_score == 88
    assert "教育未设门槛" in result.comment
    assert "jd_requirements" not in result.model_dump()


def test_no_requirements_is_input_error():
    data = assessment_data()
    data["jd_requirements"] = dict(skills=False, experience=False, education=False)
    data["interview_questions"] = []
    with pytest.raises(ResumeError) as caught:
        finalize_score(validate_json(json.dumps(data), ScoreAssessment))
    assert (caught.value.code, caught.value.exit_code) == ("JD_REQUIREMENTS_MISSING", 2)


@pytest.mark.parametrize("questions", [[], ["one"], ["", "two"], ["a", "b", "c", "d"]])
def test_invalid_interview_questions(questions):
    data = assessment_data()
    data["interview_questions"] = questions
    with pytest.raises(ResumeError) as caught:
        finalize_score(validate_json(json.dumps(data), ScoreAssessment))
    assert caught.value.exit_code == 5


def test_blank_comment_rejected():
    data = assessment_data()
    data["comment"] = "  "
    with pytest.raises(ResumeError, match="comment"):
        validate_json(json.dumps(data), ScoreAssessment)
