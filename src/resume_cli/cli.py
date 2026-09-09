"""Thin command layer: successful data on stdout, diagnostics on stderr."""

import json
import sys
from pathlib import Path
from typing import Annotated

import typer

from resume_cli import __version__
from resume_cli.domain.errors import ResumeError
from resume_cli.domain.schemas import StrictModel

app = typer.Typer(
    help="读取 PDF 简历，提取结构化信息，并结合岗位描述评分。",
    no_args_is_help=True,
    invoke_without_command=True,
    add_completion=False,
    pretty_exceptions_enable=False,
    rich_markup_mode=None,
)
batch_app = typer.Typer(help="按顺序处理显式指定的 PDF，单份失败后继续。", no_args_is_help=True)
app.add_typer(batch_app, name="batch")

PDFPath = Annotated[Path, typer.Argument(help="本地文本型 PDF 简历路径。")]
MockOption = Annotated[bool, typer.Option("--mock", help="固定虚构数据演示；不调用 AI。")]
OutputOption = Annotated[
    Path | None, typer.Option("--output", help="保存 UTF-8 JSON，不覆盖已有文件。")
]
EvidenceOption = Annotated[
    bool,
    typer.Option(
        "--evidence",
        help="在评分 JSON 中包含简历证据和待核实缺口。",
    ),
]
PDFPaths = Annotated[list[Path], typer.Argument(help="要处理的 PDF 路径；去重后最多 20 份。")]
OCROption = Annotated[bool, typer.Option("--ocr", help="对无文本页执行本地 Tesseract OCR。")]
OCRLanguage = Annotated[
    str, typer.Option("--ocr-lang", help="OCR 语言包，例如 eng 或 eng+chi_sim。")
]
LayoutOption = Annotated[bool, typer.Option("--layout", help="对文本页使用 pypdf 布局提取模式。")]
MOCK_NOTICE = "MOCK：固定演示数据，与当前输入内容无关；未调用 AI。"


@app.callback()
def root(
    version: Annotated[bool, typer.Option("--version", help="显示版本。", is_eager=True)] = False,
) -> None:
    if version:
        typer.echo(__version__)
        raise typer.Exit()


def _fail(exc: ResumeError) -> None:
    typer.echo(f"ERROR [{exc.code}] {exc.message}", err=True)
    raise typer.Exit(exc.exit_code)


def _emit(result: StrictModel, output: Path | None) -> None:
    payload = result.model_dump_json(indent=2) + "\n"
    if output is not None:
        save_json(output, payload)
    typer.echo(payload, nl=False)


@app.command("parse")
def parse_command(
    pdf_path: PDFPath,
    ocr: OCROption = False,
    ocr_lang: OCRLanguage = "eng+chi_sim",
    layout: LayoutOption = False,
    pages: Annotated[
        bool, typer.Option("--pages", help="输出含页码、文本和提取方法的 JSON。")
    ] = False,
) -> None:
    """提取 PDF 文本，不访问模型服务。"""
    try:
        document = parse_document(pdf_path, ocr=ocr, ocr_language=ocr_lang, layout=layout)
        if pages:
            typer.echo(
                json.dumps(
                    {
                        "page_count": len(document.pages),
                        "pages": [
                            {"page": p.number, "text": p.text, "method": p.method}
                            for p in document.pages
                        ],
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
        else:
            typer.echo(document.text)
    except ResumeError as exc:
        _fail(exc)


@app.command("extract")
def extract_command(
    pdf_path: PDFPath,
    mock: MockOption = False,
    output: OutputOption = None,
    ocr: OCROption = False,
    ocr_lang: OCRLanguage = "eng+chi_sim",
    layout: LayoutOption = False,
) -> None:
    """将简历提取为经过校验的 JSON。"""
    try:
        if output is not None:
            check_output_path(output)
        text = parse_document(pdf_path, ocr=ocr, ocr_language=ocr_lang, layout=layout).text
        if mock:
            typer.echo(MOCK_NOTICE, err=True)
        _emit(extract_resume(text, mock=mock), output)
    except ResumeError as exc:
        _fail(exc)


@app.command("score")
def score_command(
    pdf_path: PDFPath,
    jd: Annotated[Path, typer.Option("--jd", help="UTF-8 岗位描述 .txt 文件。")],
    mock: MockOption = False,
    output: OutputOption = None,
    evidence: EvidenceOption = False,
    ocr: OCROption = False,
    ocr_lang: OCRLanguage = "eng+chi_sim",
    layout: LayoutOption = False,
) -> None:
    """使用完整简历与 JD 评分，按 50/30/20 权重本地计算总分。"""
    try:
        if output is not None:
            check_output_path(output)
        jd_text = read_jd(jd)
        document = parse_document(pdf_path, ocr=ocr, ocr_language=ocr_lang, layout=layout)
        if mock:
            typer.echo(MOCK_NOTICE, err=True)
        _emit(
            score_resume(
                document.text, jd_text, mock=mock, include_evidence=evidence, document=document
            ),
            output,
        )
    except ResumeError as exc:
        _fail(exc)


def check_output_path(*args, **kwargs):
    from resume_cli.adapters.storage import check_output_path as impl

    return impl(*args, **kwargs)


def parse_document(*args, **kwargs):
    from resume_cli.adapters.documents import parse_document as impl

    return impl(*args, **kwargs)


def read_jd(*args, **kwargs):
    from resume_cli.adapters.documents import read_jd as impl

    return impl(*args, **kwargs)


def save_json(*args, **kwargs):
    from resume_cli.adapters.storage import save_json as impl

    return impl(*args, **kwargs)


def extract_resume(*args, **kwargs):
    from resume_cli.application.resumes import extract_resume as impl

    return impl(*args, **kwargs)


def score_resume(*args, **kwargs):
    from resume_cli.application.resumes import score_resume as impl

    return impl(*args, **kwargs)


def run_batch(*args, **kwargs):
    from resume_cli.application.batch import run_batch as impl

    return impl(*args, **kwargs)


def _configure_stdio() -> None:
    """Windows consoles and frozen pipes often start as cp1252; JSON and resumes are UTF-8."""
    for stream in (sys.stdout, sys.stderr):
        if stream is None:
            continue
        encoding = (getattr(stream, "encoding", None) or "").lower().replace("-", "")
        if encoding in {"utf8", "utf8sig"}:
            continue
        reconfigure = getattr(stream, "reconfigure", None)
        if not callable(reconfigure):
            continue
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except (OSError, ValueError, AttributeError):
            continue


def main() -> None:
    _configure_stdio()
    app()


def _batch_progress(index: int, total: int, path: Path) -> None:
    typer.echo(f"[{index}/{total}] {path}", err=True)


def _batch_command(
    pdf_paths: list[Path],
    operation: str,
    mock: bool,
    output: Path | None,
    jd: Path | None = None,
    evidence: bool = False,
    ocr: bool = False,
    ocr_lang: str = "eng+chi_sim",
    layout: bool = False,
) -> None:
    try:
        if output is not None:
            check_output_path(output)
        if mock:
            typer.echo(MOCK_NOTICE, err=True)
        report = run_batch(
            pdf_paths,
            operation,
            jd_path=jd,
            mock=mock,
            include_evidence=evidence,
            ocr=ocr,
            ocr_language=ocr_lang,
            layout=layout,
            progress=_batch_progress,
        )
        _emit(report, output)
    except ResumeError as exc:
        _fail(exc)
    if report.failed:
        typer.echo(
            f"BATCH：{report.succeeded} 份成功，{report.failed} 份失败；详情见 JSON。", err=True
        )
        raise typer.Exit(7)


@batch_app.command("extract")
def batch_extract_command(
    pdf_paths: PDFPaths,
    mock: MockOption = False,
    output: OutputOption = None,
    ocr: OCROption = False,
    ocr_lang: OCRLanguage = "eng+chi_sim",
    layout: LayoutOption = False,
) -> None:
    """批量提取简历；部分或全部文件失败时仍返回报告，退出码 7。"""
    _batch_command(pdf_paths, "extract", mock, output, ocr=ocr, ocr_lang=ocr_lang, layout=layout)


@batch_app.command("score")
def batch_score_command(
    pdf_paths: PDFPaths,
    jd: Annotated[Path, typer.Option("--jd", help="所有简历共用的 UTF-8 岗位描述 .txt。")],
    mock: MockOption = False,
    output: OutputOption = None,
    evidence: EvidenceOption = False,
    ocr: OCROption = False,
    ocr_lang: OCRLanguage = "eng+chi_sim",
    layout: LayoutOption = False,
) -> None:
    """使用同一份 JD 批量评分，不排序候选人；可增加 --evidence。"""
    _batch_command(pdf_paths, "score", mock, output, jd, evidence, ocr, ocr_lang, layout)
