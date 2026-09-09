"""Sequential, bounded batches with an explicit report for every input file."""

from collections.abc import Callable, Sequence
from pathlib import Path

from resume_cli.adapters.config import Settings
from resume_cli.adapters.documents import parse_document, read_jd
from resume_cli.application.resumes import extract_resume, score_resume
from resume_cli.domain.batch import BatchError, BatchFailure, BatchReport, BatchSuccess, Operation
from resume_cli.domain.errors import ResumeError

MAX_BATCH_FILES = 20


def run_batch(
    paths: Sequence[Path],
    operation: Operation,
    *,
    jd_path: Path | None = None,
    mock: bool = False,
    include_evidence: bool = False,
    ocr: bool = False,
    ocr_language: str = "eng+chi_sim",
    layout: bool = False,
    progress: Callable[[int, int, Path], None] | None = None,
) -> BatchReport:
    """Preserve input order, deduplicate paths, and continue after individual errors."""
    if operation not in {"extract", "score"}:
        raise ResumeError("BATCH_OPERATION_INVALID", "批处理仅支持 extract 或 score。")
    if operation == "extract" and (jd_path is not None or include_evidence):
        raise ResumeError("BATCH_OPTIONS_INVALID", "提取批处理不支持 JD 或评分证据选项。")
    unique: dict[Path, Path] = {}
    try:
        for path in paths:
            unique.setdefault(path.resolve(), path)
    except (OSError, RuntimeError) as exc:
        raise ResumeError("BATCH_PATH_INVALID", "无法解析输入路径，请检查路径或符号链接。") from exc
    if not unique:
        raise ResumeError("BATCH_EMPTY", "请至少指定一份 PDF。")
    if len(unique) > MAX_BATCH_FILES:
        raise ResumeError("BATCH_TOO_LARGE", f"一次最多处理 {MAX_BATCH_FILES} 份不同的 PDF。")
    jd = None
    if operation == "score":
        if jd_path is None:
            raise ResumeError("BATCH_JD_REQUIRED", "批量评分必须指定 --jd。")
        jd = read_jd(jd_path)
    if not mock:
        # Shared configuration failures must not produce N identical billable attempts.
        Settings.load()

    results: list[BatchSuccess | BatchFailure] = []
    for index, path in enumerate(unique.values(), 1):
        if progress is not None:
            progress(index, len(unique), path)
        try:
            document = parse_document(path, ocr=ocr, ocr_language=ocr_language, layout=layout)
            if operation == "extract":
                result = extract_resume(document.text, mock=mock)
            else:
                result = score_resume(
                    document.text,
                    jd,
                    mock=mock,
                    include_evidence=include_evidence,
                    document=document,
                )
            results.append(BatchSuccess(file=str(path), result=result))
        except ResumeError as exc:
            results.append(
                BatchFailure(
                    file=str(path),
                    error=BatchError(code=exc.code, message=exc.message, exit_code=exc.exit_code),
                )
            )
    failed = sum(isinstance(item, BatchFailure) for item in results)
    return BatchReport(
        operation=operation,
        mode="mock" if mock else "ai",
        total=len(results),
        succeeded=len(results) - failed,
        failed=failed,
        results=results,
    )
