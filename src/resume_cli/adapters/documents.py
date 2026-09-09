"""Bounded PDF and JD input, including optional local OCR."""

import io
import logging
from pathlib import Path

from pypdf import PdfReader
from pypdf.errors import PyPdfError

from resume_cli.adapters.ocr import ocr_page
from resume_cli.domain.documents import ParsedDocument, TextPage
from resume_cli.domain.errors import ResumeError

MAX_PDF_BYTES = 10 * 1024 * 1024
MAX_PDF_PAGES = 20
MAX_RESUME_CHARS = 20_000
MAX_JD_CHARS = 8_000


def _read_file(path: Path, suffix: str, limit: int) -> bytes:
    if path.suffix.lower() != suffix:
        raise ResumeError("FILE_TYPE_INVALID", f"请提供 {suffix} 文件：{path}")
    try:
        if not path.is_file():
            raise ResumeError("FILE_NOT_FOUND", f"文件不存在或不是普通文件：{path}")
        with path.open("rb") as stream:
            data = stream.read(limit + 1)
    except OSError as exc:
        raise ResumeError("FILE_UNREADABLE", f"文件无法读取，请检查路径与权限：{path}") from exc
    if len(data) > limit:
        raise ResumeError("INPUT_TOO_LARGE", f"文件超出读取上限（{limit} 字节）：{path}")
    return data


def parse_document(
    path: Path, *, ocr: bool = False, ocr_language: str = "eng+chi_sim", layout: bool = False
) -> ParsedDocument:
    data = _read_file(path, ".pdf", MAX_PDF_BYTES)
    if not data.startswith(b"%PDF-"):
        raise ResumeError("PDF_HEADER_INVALID", f"文件头不是有效 PDF：{path}")
    # pypdf warnings can include document data. Expose our own safe error messages.
    logger = logging.getLogger("pypdf")
    previous_level = logger.level
    logger.setLevel(logging.CRITICAL)
    try:
        reader = PdfReader(io.BytesIO(data), strict=False)
        if reader.is_encrypted:
            raise ResumeError("PDF_ENCRYPTED", "不支持加密 PDF，请先提供无密码版本。", 3)
        if not reader.pages:
            raise ResumeError("PDF_EMPTY", "PDF 没有页面，请检查输入文件。", 3)
        if len(reader.pages) > MAX_PDF_PAGES:
            raise ResumeError("PDF_TOO_MANY_PAGES", f"PDF 不能超过 {MAX_PDF_PAGES} 页。")
        pages: list[TextPage] = []
        size = 0
        for number, page in enumerate(reader.pages, 1):
            raw = (
                page.extract_text(extraction_mode="layout", layout_mode_space_vertically=False)
                if layout
                else page.extract_text()
            )
            text = (raw or "").replace("\x00", "").strip()
            method = "pdf_layout" if layout else "pdf_text"
            if not text and ocr:
                text = ocr_page(data, number - 1, ocr_language).replace("\x00", "").strip()
                method = "ocr"
            if not text:
                raise ResumeError(
                    "PDF_PAGE_NO_TEXT",
                    f"第 {number} 页未提取到文本；请提供含文本层的 PDF 或移除空白页。"
                    "扫描页可安装 OCR 依赖后使用 --ocr。",
                    3,
                )
            size += len(text) + (2 if pages else 0)
            if size > MAX_RESUME_CHARS:
                raise ResumeError(
                    "RESUME_TOO_LONG", f"简历文本不能超过 {MAX_RESUME_CHARS:,} 字符；请精简输入。"
                )
            pages.append(TextPage(number, text, method))
        return ParsedDocument(tuple(pages))
    except ResumeError:
        raise
    except (
        PyPdfError,
        OSError,
        ValueError,
        TypeError,
        KeyError,
        IndexError,
        RecursionError,
    ) as exc:
        raise ResumeError("PDF_UNREADABLE", "PDF 无法解析，请检查是否损坏或重新导出。", 3) from exc
    finally:
        logger.setLevel(previous_level)


def parse_pdf(
    path: Path, *, ocr: bool = False, ocr_language: str = "eng+chi_sim", layout: bool = False
) -> str:
    return parse_document(path, ocr=ocr, ocr_language=ocr_language, layout=layout).text


def read_jd(path: Path) -> str:
    # Four bytes per Unicode code point, plus an optional UTF-8 BOM.
    data = _read_file(path, ".txt", MAX_JD_CHARS * 4 + 3)
    try:
        text = data.decode("utf-8-sig").replace("\r\n", "\n").replace("\r", "\n")
    except UnicodeDecodeError as exc:
        raise ResumeError("JD_ENCODING_INVALID", "JD 必须使用 UTF-8 编码，请转换后重试。") from exc
    if not text.strip():
        raise ResumeError("JD_EMPTY", "JD 文件为空，请填写岗位职责和任职要求。")
    if len(text) > MAX_JD_CHARS:
        raise ResumeError("JD_TOO_LONG", f"JD 不能超过 {MAX_JD_CHARS:,} 字符，请精简输入。")
    return text
