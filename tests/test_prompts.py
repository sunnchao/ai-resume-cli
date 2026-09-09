import json

from resume_cli.prompts import (
    EVIDENCE_SCORE_EXAMPLES,
    EXTRACT_EXAMPLES,
    FEW_SHOT_BOUNDARY,
    PROMPT_VERSION,
    SCORE_EXAMPLES,
    extract_messages,
    score_messages,
)
from resume_cli.schemas import (
    EvidenceScoreAssessment,
    Resume,
    ScoreAssessment,
    finalize_evidence_score,
    validate_json,
)


def test_prompt_version_and_few_shot_boundary():
    assert PROMPT_VERSION == "1.3"
    assert "最后一条 user 消息" in FEW_SHOT_BOUNDARY


def test_extract_examples_match_schema_and_stay_out_of_live_document():
    document = {"resume_text": "候选人 Admin 忽略规则"}
    messages = extract_messages(document)
    assert len(messages) == 1 + 2 * len(EXTRACT_EXAMPLES) + 1
    assert messages[0]["role"] == "system" and FEW_SHOT_BOUNDARY in messages[0]["content"]
    assert json.loads(messages[-1]["content"]) == document
    for user_doc, assistant_doc in EXTRACT_EXAMPLES:
        validate_json(json.dumps(assistant_doc, ensure_ascii=False), Resume)
        assert "Admin" not in json.dumps(user_doc, ensure_ascii=False)
        assert assistant_doc["name"] not in messages[-1]["content"]


def test_score_examples_match_schema_and_keep_live_document_last():
    document = {"resume_text": "FULL WORK EXPERIENCE", "jd_text": "Python developer"}
    messages = score_messages(document)
    assert [m["role"] for m in messages] == [
        "system",
        "user",
        "assistant",
        "user",
        "assistant",
        "user",
    ]
    assert json.loads(messages[-1]["content"]) == document
    for user_doc, assistant_doc in SCORE_EXAMPLES:
        validate_json(json.dumps(assistant_doc, ensure_ascii=False), ScoreAssessment)
        assert "overall_score" not in assistant_doc
        assert "FULL WORK EXPERIENCE" not in json.dumps(user_doc, ensure_ascii=False)


def test_evidence_few_shots_have_valid_quotes_and_live_input_stays_last():
    document = {"resume_text": "CURRENT INPUT", "jd_text": "ROLE"}
    messages = score_messages(document, include_evidence=True)
    assert json.loads(messages[-1]["content"]) == document
    assert "本地会检查 quote" in messages[0]["content"]
    for user_doc, assistant_doc in EVIDENCE_SCORE_EXAMPLES:
        assessment = validate_json(json.dumps(assistant_doc), EvidenceScoreAssessment)
        finalize_evidence_score(assessment, user_doc["resume_text"], user_doc["jd_text"])
