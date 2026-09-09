"""Optional local PDFium + Tesseract OCR, without cloud uploads or shell execution."""

import math
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from resume_cli.errors import ResumeError

OCR_TIMEOUT = 30
OCR_DPI = 200
MAX_RENDER_PIXELS = 12_000_000


def _engine(language: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9_]+(?:\+[A-Za-z0-9_]+)*", language):
        raise ResumeError("OCR_LANGUAGE_INVALID", "OCR 语言应为 eng 或 eng+chi_sim 等语言代码。")
    binary = shutil.which("tesseract")
    if not binary:
        raise ResumeError("OCR_UNAVAILABLE", "未找到 tesseract；请安装 Tesseract 和相应语言包。", 3)
    try:
        info = subprocess.run(
            [binary, "--list-langs"], capture_output=True, timeout=10, check=False
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ResumeError("OCR_UNAVAILABLE", "无法启动 Tesseract，请检查安装。", 3) from exc
    languages = set(info.stdout.decode("utf-8", errors="replace").splitlines())
    if info.returncode != 0 or not set(language.split("+")) <= languages:
        raise ResumeError(
            "OCR_LANGUAGE_MISSING", "Tesseract 缺少所选语言包；请检查 --ocr-lang。", 3
        )
    return binary


def _render(data: bytes, page_index: int, output: Path) -> None:
    try:
        import pypdfium2 as pdfium
    except ImportError as exc:
        raise ResumeError(
            "OCR_DEPENDENCY_MISSING", "请安装 OCR 依赖：uv sync --extra ocr。", 3
        ) from exc
    try:
        with pdfium.PdfDocument(data) as document:
            page = document[page_index]
            try:
                width, height = page.get_size()
                scale = OCR_DPI / 72
                if not (
                    math.isfinite(width) and math.isfinite(height) and width > 0 and height > 0
                ):
                    raise ResumeError("OCR_PAGE_TOO_LARGE", "PDF 页尺寸无效。", 3)
                if math.ceil(width * scale) * math.ceil(height * scale) > MAX_RENDER_PIXELS:
                    raise ResumeError("OCR_PAGE_TOO_LARGE", "OCR 页面超过 1200 万像素渲染上限。", 3)
                bitmap = page.render(scale=scale)
                try:
                    image = bitmap.to_pil()
                    try:
                        image.save(output)
                    finally:
                        image.close()
                finally:
                    bitmap.close()
            finally:
                page.close()
    except ResumeError:
        raise
    except (ImportError, OSError, ValueError, RuntimeError) as exc:
        raise ResumeError("OCR_RENDER_FAILED", "PDF 页面无法渲染为 OCR 图像。", 3) from exc


def ocr_page(data: bytes, page_index: int, language: str) -> str:
    binary = _engine(language)
    try:
        with tempfile.TemporaryDirectory(prefix="resume-ocr-") as folder:
            image_path = Path(folder) / "page.png"
            _render(data, page_index, image_path)
            result = subprocess.run(
                [binary, str(image_path), "stdout", "-l", language, "--psm", "3"],
                capture_output=True,
                timeout=OCR_TIMEOUT,
                check=False,
            )
            if result.returncode != 0:
                raise ResumeError("OCR_FAILED", f"第 {page_index + 1} 页 OCR 失败。", 3)
            text = result.stdout.decode("utf-8", errors="strict").strip()
            if not text:
                raise ResumeError("OCR_EMPTY", f"第 {page_index + 1} 页 OCR 未识别到文字。", 3)
            return text
    except subprocess.TimeoutExpired as exc:
        raise ResumeError(
            "OCR_TIMEOUT", f"第 {page_index + 1} 页 OCR 超过 {OCR_TIMEOUT} 秒。", 3
        ) from exc
    except (OSError, UnicodeError) as exc:
        raise ResumeError("OCR_FAILED", f"第 {page_index + 1} 页 OCR 无法完成。", 3) from exc
