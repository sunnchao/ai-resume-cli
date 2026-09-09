import builtins
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from resume_cli.adapters import ocr
from resume_cli.adapters.documents import parse_document
from resume_cli.domain.errors import ResumeError


@pytest.fixture
def fake_engine(monkeypatch):
    monkeypatch.setattr(ocr.shutil, "which", lambda name: "/synthetic/tesseract")
    calls = []
    paths = []

    def run(command, **kwargs):
        calls.append((command, kwargs))
        return SimpleNamespace(
            returncode=0,
            stdout=b"eng\nchi_sim\n" if "--list-langs" in command else b"Python OCR result",
        )

    def render(data, index, path):
        paths.append(path)
        path.write_bytes(b"image bytes")

    monkeypatch.setattr(ocr.subprocess, "run", run)
    monkeypatch.setattr(ocr, "_render", render)
    return calls, paths


def test_ocr_command_is_bounded_shell_free_and_removes_images(fake_engine):
    calls, paths = fake_engine
    assert ocr.ocr_page(b"pdf", 1, "eng+chi_sim") == "Python OCR result"
    command, kwargs = calls[-1]
    assert command[-4:] == ["-l", "eng+chi_sim", "--psm", "3"]
    assert kwargs["timeout"] == 30 and not kwargs.get("shell", False)
    assert not paths[0].exists() and not paths[0].parent.exists()


def test_ocr_missing_engine_and_invalid_language(monkeypatch):
    monkeypatch.setattr(ocr.shutil, "which", lambda name: None)
    with pytest.raises(ResumeError) as caught:
        ocr.ocr_page(b"", 0, "eng")
    assert caught.value.code == "OCR_UNAVAILABLE"
    with pytest.raises(ResumeError) as caught:
        ocr.ocr_page(b"", 0, "eng;echo SECRET")
    assert caught.value.code == "OCR_LANGUAGE_INVALID"


def test_ocr_missing_language(fake_engine):
    with pytest.raises(ResumeError) as caught:
        ocr.ocr_page(b"", 0, "fra")
    assert caught.value.code == "OCR_LANGUAGE_MISSING"


@pytest.mark.parametrize(
    "behavior,code",
    [
        ("timeout", "OCR_TIMEOUT"),
        ("failed", "OCR_FAILED"),
        ("empty", "OCR_EMPTY"),
        ("encoding", "OCR_FAILED"),
    ],
)
def test_ocr_failure_cleanup(fake_engine, monkeypatch, behavior, code):
    _, paths = fake_engine
    previous = ocr.subprocess.run

    def run(command, **kwargs):
        if "--list-langs" in command:
            return previous(command, **kwargs)
        if behavior == "timeout":
            raise subprocess.TimeoutExpired(command, 30)
        return SimpleNamespace(
            returncode=1 if behavior == "failed" else 0,
            stdout=b"\xff" if behavior == "encoding" else b"",
        )

    monkeypatch.setattr(ocr.subprocess, "run", run)
    with pytest.raises(ResumeError) as caught:
        ocr.ocr_page(b"", 0, "eng")
    assert caught.value.code == code
    assert paths and not paths[0].parent.exists()


def test_optional_renderer_missing_has_clear_error(monkeypatch, tmp_path):
    original = builtins.__import__

    def missing(name, *args, **kwargs):
        if name == "pypdfium2":
            raise ImportError("missing")
        return original(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", missing)
    with pytest.raises(ResumeError) as caught:
        ocr._render(b"", 0, tmp_path / "image.png")
    assert caught.value.code == "OCR_DEPENDENCY_MISSING"


@pytest.mark.parametrize("size", [(100_000, 100_000), (float("nan"), 100)])
def test_renderer_rejects_invalid_or_huge_page_before_allocating(monkeypatch, tmp_path, size):
    import sys

    class Page:
        def get_size(self):
            return size

        def render(self, **kwargs):
            pytest.fail("Must reject before allocating a bitmap")

        def close(self):
            pass

    class Document:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def __getitem__(self, index):
            return Page()

    monkeypatch.setitem(
        sys.modules, "pypdfium2", SimpleNamespace(PdfDocument=lambda data: Document())
    )
    with pytest.raises(ResumeError) as caught:
        ocr._render(b"", 0, tmp_path / "page.png")
    assert caught.value.code == "OCR_PAGE_TOO_LARGE"


def test_parser_only_ocr_empty_pages_and_applies_character_limit(make_pdf, monkeypatch):
    from resume_cli.adapters import documents as files

    calls = []

    def recognize(data, index, language):
        calls.append(index)
        return "recognized Python"

    monkeypatch.setattr(files, "ocr_page", recognize)
    path = make_pdf(["NATIVE", None])
    doc = parse_document(path, ocr=True)
    assert calls == [1] and [p.method for p in doc.pages] == ["pdf_text", "ocr"]
    monkeypatch.setattr(files, "MAX_RESUME_CHARS", 10)
    with pytest.raises(ResumeError) as caught:
        parse_document(path, ocr=True)
    assert caught.value.code == "RESUME_TOO_LONG"


@pytest.fixture
def require_real_ocr():
    import importlib.util
    import os

    try:
        if importlib.util.find_spec("pypdfium2") is None:
            raise RuntimeError("OCR extra missing")
        ocr._engine("eng+chi_sim")
    except (RuntimeError, ResumeError) as exc:
        if os.environ.get("RESUME_REQUIRE_OCR") == "1":
            pytest.fail(f"Required OCR prerequisites missing: {exc}")
        pytest.skip("Real OCR requires Tesseract, eng+chi_sim and the OCR extra")


@pytest.mark.ocr
@pytest.mark.parametrize(
    "name,language,tokens",
    [
        ("scan-en.pdf", "eng", ["Python", "React", "PostgreSQL"]),
        ("scan-zh.pdf", "eng+chi_sim", ["Python", "React", "计算机"]),
        ("mixed.pdf", "eng", ["NATIVE_PAGE_ONE", "Python"]),
    ],
)
def test_real_scanned_corpus(require_real_ocr, name, language, tokens):
    document = parse_document(
        Path(__file__).resolve().parents[1] / "examples/corpus" / name,
        ocr=True,
        ocr_language=language,
    )
    for token in tokens:
        # Tesseract can insert spaces between Chinese glyphs. Keep raw OCR text intact.
        assert "".join(token.split()) in "".join(document.text.split())
    if name == "mixed.pdf":
        assert [p.number for p in document.pages] == [1, 2]
        assert [p.method for p in document.pages] == ["pdf_text", "ocr"]
    else:
        assert document.pages[0].method == "ocr"


@pytest.mark.ocr
def test_real_blank_page_is_not_fabricated(require_real_ocr):
    with pytest.raises(ResumeError) as caught:
        parse_document(
            Path(__file__).resolve().parents[1] / "examples/corpus/blank-page.pdf", ocr=True
        )
    assert caught.value.code == "OCR_EMPTY"
