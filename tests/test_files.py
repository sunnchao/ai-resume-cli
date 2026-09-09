import os
from pathlib import Path

import pytest
from pypdf import PdfReader, PdfWriter

from resume_cli import files
from resume_cli.errors import ResumeError
from resume_cli.files import check_output_path, parse_pdf, read_jd, save_json


def test_pdf_page_order_and_non_ascii_path(make_pdf):
    pdf = make_pdf(["FIRST PAGE", "SECOND PAGE"], name="简历 带空格.PDF")
    text = parse_pdf(pdf)
    assert text == "FIRST PAGE\n\nSECOND PAGE"
    assert parse_pdf(Path(pdf.name)) == text


@pytest.mark.parametrize(
    ("name", "content", "code", "exit_code"),
    [
        ("fake.pdf", b"not a PDF", "PDF_HEADER_INVALID", 2),
        ("broken.pdf", b"%PDF-1.4\nthis is broken", "PDF_UNREADABLE", 3),
        ("wrong.txt", b"%PDF-1.4", "FILE_TYPE_INVALID", 2),
    ],
)
def test_invalid_files(tmp_path, name, content, code, exit_code):
    path = tmp_path / name
    path.write_bytes(content)
    with pytest.raises(ResumeError) as caught:
        parse_pdf(path)
    assert (caught.value.code, caught.value.exit_code) == (code, exit_code)


def test_missing_and_directory(tmp_path):
    for path in [tmp_path / "absent.pdf", tmp_path / "directory.pdf"]:
        if path.name.startswith("directory"):
            path.mkdir()
        with pytest.raises(ResumeError, match="不存在"):
            parse_pdf(path)


def test_unreadable_file(make_pdf, monkeypatch):
    path = make_pdf()
    monkeypatch.setattr(Path, "open", lambda *a, **kw: (_ for _ in ()).throw(PermissionError()))
    with pytest.raises(ResumeError) as caught:
        parse_pdf(path)
    assert caught.value.code == "FILE_UNREADABLE"


def test_encrypted_pdf(make_pdf, tmp_path):
    writer = PdfWriter()
    writer.append(PdfReader(make_pdf()))
    writer.encrypt("test-password")
    target = tmp_path / "encrypted.pdf"
    writer.write(target)
    with pytest.raises(ResumeError) as caught:
        parse_pdf(target)
    assert caught.value.code == "PDF_ENCRYPTED"


def test_zero_pages(tmp_path):
    target = tmp_path / "zero.pdf"
    PdfWriter().write(target)
    with pytest.raises(ResumeError) as caught:
        parse_pdf(target)
    assert caught.value.code == "PDF_EMPTY"


@pytest.mark.parametrize("pages", [[None], ["valid text", None]])
def test_reject_unread_pages(make_pdf, pages):
    with pytest.raises(ResumeError) as caught:
        parse_pdf(make_pdf(pages))
    assert caught.value.code == "PDF_PAGE_NO_TEXT"
    assert f"第 {len(pages)} 页" in str(caught.value)


def test_pdf_limits(make_pdf, monkeypatch):
    with pytest.raises(ResumeError) as caught:
        parse_pdf(make_pdf(["page"] * 21))
    assert caught.value.code == "PDF_TOO_MANY_PAGES"
    monkeypatch.setattr(files, "MAX_RESUME_CHARS", 5)
    with pytest.raises(ResumeError) as caught:
        parse_pdf(make_pdf(["123", "456"]))
    assert caught.value.code == "RESUME_TOO_LONG"
    monkeypatch.setattr(files, "MAX_PDF_BYTES", 10)
    with pytest.raises(ResumeError) as caught:
        parse_pdf(make_pdf())
    assert caught.value.code == "INPUT_TOO_LARGE"


def test_jd_utf8_bom(jd_path):
    jd_path.write_bytes(b"\xef\xbb\xbf" + "  Python 岗位\n ".encode())
    assert read_jd(jd_path) == "  Python 岗位\n "


@pytest.mark.parametrize(
    ("data", "code"),
    [(b" \t\n", "JD_EMPTY"), (b"\xff\xfe", "JD_ENCODING_INVALID"), (b"a" * 8001, "JD_TOO_LONG")],
)
def test_jd_invalid(jd_path, data, code):
    jd_path.write_bytes(data)
    with pytest.raises(ResumeError) as caught:
        read_jd(jd_path)
    assert caught.value.code == code


def test_output_is_exact_utf8_and_private(tmp_path):
    output = tmp_path / "结果.json"
    content = '{\n  "name": "陈晨"\n}\n'
    save_json(output, content)
    assert output.read_bytes() == content.encode("utf-8")
    assert not list(tmp_path.glob(".resume-cli-*"))
    if os.name == "posix":
        assert output.stat().st_mode & 0o077 == 0
    with pytest.raises(ResumeError) as caught:
        save_json(output, "replacement")
    assert caught.value.code == "OUTPUT_EXISTS"
    assert output.read_text() == content


def test_output_invalid_parent_and_symlink(tmp_path):
    with pytest.raises(ResumeError) as caught:
        check_output_path(tmp_path / "missing" / "result.json")
    assert caught.value.code == "OUTPUT_DIRECTORY_INVALID"
    link = tmp_path / "link.json"
    link.symlink_to(tmp_path / "nonexistent")
    with pytest.raises(ResumeError) as caught:
        save_json(link, "{}")
    assert caught.value.code == "OUTPUT_EXISTS"
    assert link.is_symlink()


def test_output_race_does_not_overwrite(tmp_path, monkeypatch):
    real_link = os.link
    target = tmp_path / "race.json"

    def raced_link(source, dest):
        Path(dest).write_text("other writer")
        return real_link(source, dest)

    monkeypatch.setattr(os, "link", raced_link)
    with pytest.raises(ResumeError) as caught:
        save_json(target, "{}")
    assert caught.value.code == "OUTPUT_EXISTS"
    assert target.read_text() == "other writer"
    assert not list(tmp_path.glob(".resume-cli-*"))


def test_disk_failure_leaves_no_output(tmp_path, monkeypatch):
    def full_disk(*args):
        raise OSError("full disk")

    monkeypatch.setattr(os, "fsync", full_disk)
    target = tmp_path / "result.json"
    with pytest.raises(ResumeError) as caught:
        save_json(target, "{}")
    assert caught.value.code == "OUTPUT_WRITE_FAILED"
    assert not target.exists()
    assert not list(tmp_path.glob(".resume-cli-*"))
