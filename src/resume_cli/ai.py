"""One Chat Completions request per command, with one explicit transient retry."""

import time
from importlib.resources import files
from typing import TypeVar

from resume_cli.config import MAX_OUTPUT_TOKENS, REQUEST_TIMEOUT, RETRY_DELAY, Settings
from resume_cli.documents import ParsedDocument, TextPage
from resume_cli.errors import ResumeError
from resume_cli.prompts import extract_messages, score_messages
from resume_cli.schemas import (
    DetailedScoreResult,
    EvidenceScoreAssessment,
    Resume,
    ScoreAssessment,
    ScoreResult,
    StrictModel,
    finalize_evidence_score,
    finalize_score,
    validate_json,
)

Model = TypeVar("Model", bound=StrictModel)


def _request(schema: type[Model], messages: list[dict[str, str]], *, mock: bool) -> Model:
    if mock:
        filename = {
            Resume: "resume.json",
            ScoreAssessment: "score-assessment.json",
            EvidenceScoreAssessment: "evidence-score-assessment.json",
        }[schema]
        raw = files("resume_cli").joinpath("fixtures", filename).read_text(encoding="utf-8")
        return validate_json(raw, schema)

    from openai import (
        APIConnectionError,
        APIResponseValidationError,
        APIStatusError,
        APITimeoutError,
        OpenAI,
        OpenAIError,
    )

    settings = Settings.load()
    with OpenAI(
        api_key=settings.api_key,
        base_url=settings.base_url,
        timeout=REQUEST_TIMEOUT,
        max_retries=0,
    ) as client:
        for attempt in range(2):
            try:
                response = client.chat.completions.create(
                    model=settings.model,
                    messages=messages,
                    response_format={
                        "type": "json_schema",
                        "json_schema": {
                            "name": schema.__name__,
                            "strict": True,
                            "schema": schema.model_json_schema(),
                        },
                    },
                    max_tokens=MAX_OUTPUT_TOKENS,
                    store=False,
                )
                break
            except (APIConnectionError, APIStatusError) as exc:
                status = exc.status_code if isinstance(exc, APIStatusError) else None
                transient = (
                    isinstance(exc, APIConnectionError)
                    or status == 429
                    or (status is not None and status >= 500)
                )
                if transient and attempt == 0:
                    time.sleep(RETRY_DELAY)
                    continue
                if isinstance(exc, APITimeoutError):
                    message = "AI 请求超时，请稍后重试或检查网络。"
                elif status in {401, 403}:
                    message = f"AI 认证或权限失败（HTTP {status}），请检查 Key 与模型权限。"
                elif status is not None:
                    message = f"AI 请求失败（HTTP {status}），请检查模型、端点、配额或稍后重试。"
                else:
                    message = "无法连接 AI 服务，请检查网络与 OPENAI_BASE_URL。"
                raise ResumeError("AI_REQUEST_FAILED", message, 4) from exc
            except APIResponseValidationError as exc:
                raise ResumeError(
                    "AI_RESPONSE_INVALID", "AI 端点返回了无法解析的响应，请检查接口兼容性。", 5
                ) from exc
            except OpenAIError as exc:
                raise ResumeError(
                    "AI_REQUEST_FAILED", "AI 服务响应异常，请检查接口兼容性。", 4
                ) from exc
            except (TypeError, ValueError, AttributeError) as exc:
                raise ResumeError(
                    "AI_RESPONSE_INVALID", "AI 端点返回了无法解析的响应，请检查接口兼容性。", 5
                ) from exc

    return _parse_chat_completion(response, schema)


def _parse_chat_completion(response: object, schema: type[Model]) -> Model:
    choices = getattr(response, "choices", None)
    if not isinstance(choices, list) or not choices:
        raise ResumeError("AI_RESPONSE_INVALID", "AI 服务未返回有效的 Chat Completions 响应。", 5)
    choice = choices[0]
    message = getattr(choice, "message", None)
    if message is None:
        raise ResumeError("AI_RESPONSE_INVALID", "AI 消息的 content 格式错误。", 5)
    refusal = getattr(message, "refusal", None)
    if isinstance(refusal, str) and refusal:
        raise ResumeError("AI_REFUSAL", "模型拒绝了本次请求，未生成结果。", 4)
    finish_reason = getattr(choice, "finish_reason", None)
    if finish_reason == "length":
        raise ResumeError(
            "AI_INCOMPLETE", "AI 输出未完成或被截断；请精简输入或检查模型输出预算。", 5
        )
    if finish_reason not in {None, "stop"}:
        raise ResumeError("AI_NOT_COMPLETED", "AI 请求没有完成，请稍后重试。", 4)
    raw = getattr(message, "content", None)
    if not isinstance(raw, str):
        raise ResumeError("AI_RESPONSE_INVALID", "AI 消息未包含有效的文本内容。", 5)
    if not raw:
        raise ResumeError("AI_OUTPUT_EMPTY", "AI 未返回 JSON 文本，请检查模型与端点兼容性。", 5)
    return validate_json(raw, schema)


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
        source = (
            files("resume_cli").joinpath("fixtures/evidence-resume.txt").read_text(encoding="utf-8")
            if mock
            else text
        )
        if mock:
            document = ParsedDocument(
                tuple(
                    TextPage(index, page, "text")
                    for index, page in enumerate(source.split("\f"), 1)
                )
            )
            source = document.text
            jd = (
                files("resume_cli").joinpath("fixtures/evidence-jd.txt").read_text(encoding="utf-8")
            )
        return finalize_evidence_score(assessment, source, jd, document=document, mock=mock)
    assessment = _request(
        ScoreAssessment,
        score_messages({"resume_text": text, "jd_text": jd}),
        mock=mock,
    )
    return finalize_score(assessment)
