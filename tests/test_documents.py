import json
from importlib.resources import files
from pathlib import Path

import pytest
from typer.testing import CliRunner

from resume_cli.cli import app
from resume_cli.documents import ParsedDocument, TextPage, locate_quote
from resume_cli.errors import ResumeError
from resume_cli.files import parse_document, read_jd
from resume_cli.schemas import EvidenceScoreAssessment, finalize_evidence_score, validate_json


def inputs():
    base = files("resume_cli").joinpath("fixtures")
    assessment = validate_json(
        base.joinpath("evidence-score-assessment.json").read_text(encoding="utf-8"),
        EvidenceScoreAssessment,
    )
    text = base.joinpath("evidence-resume.txt").read_text(encoding="utf-8")
    jd = base.joinpath("evidence-jd.txt").read_text(encoding="utf-8")
    pages = ParsedDocument(
        tuple(TextPage(i, t, "pdf_text") for i, t in enumerate(text.split("\f"), 1))
    )
    return assessment, pages, jd


def test_offsets_preserve_original_spacing_and_unicode():
    text = "\n标题\n  Python \n 开发 API。\n"
    quote = "Python 开发"
    location = locate_quote(text, quote)
    assert location == {"start_char": 6, "end_char": 17, "line_start": 3, "line_end": 4}
    original = text[location["start_char"] : location["end_char"]]
    assert "".join(original.split()) == "".join(quote.split())
    assert locate_quote(text, "python") is None
    assert locate_quote(text, " ") is None


def test_pdf_locations_and_jd_gap_locations_are_locally_derived():
    assessment, document, jd = inputs()
    result = finalize_evidence_score(assessment, document.text, jd, document=document)
    assert result.evidence_schema_version == "2"
    assert result.skill_evidence[0].resume_locations[0].page == 1
    assert result.experience_evidence[0].resume_locations[0].page == 2
    assert result.education_evidence[0].resume_locations[0].page == 2
    assert result.skill_evidence[0].jd_location.line_start == 2
    gap = result.gap_evidence[0]
    assert gap.gap_index == 0 and gap.jd_location.line_start == 5
    assert jd[gap.jd_location.start_char : gap.jd_location.end_char] == gap.jd_quote


def test_unknown_page_from_text_is_null_and_repeated_pages_are_reported():
    assessment, document, jd = inputs()
    plain = finalize_evidence_score(assessment, document.text, jd)
    assert plain.skill_evidence[0].resume_locations[0].page is None
    repeated = ParsedDocument((*document.pages, TextPage(3, document.pages[0].text, "ocr")))
    result = finalize_evidence_score(assessment, repeated.text, jd, document=repeated)
    assert [m.page for m in result.skill_evidence[0].resume_locations] == [1, 3]
    assert result.skill_evidence[0].resume_locations[1].method == "ocr"


def test_quotes_cannot_bridge_pdf_pages():
    assessment, document, jd = inputs()
    assessment.skill_evidence[0].quote = document.pages[0].text[-15:] + document.pages[1].text[:15]
    with pytest.raises(ResumeError, match="quote"):
        finalize_evidence_score(assessment, document.text, jd, document=document)


def test_wrong_document_context_fails():
    assessment, document, jd = inputs()
    with pytest.raises(ResumeError) as caught:
        finalize_evidence_score(assessment, "different", jd, document=document)
    assert caught.value.code == "EVIDENCE_DOCUMENT_MISMATCH"


@pytest.mark.parametrize("where", ["evidence", "gap", "count"])
def test_jd_quotes_and_gap_alignment_are_verified_without_echo(where):
    assessment, document, jd = inputs()
    if where == "evidence":
        assessment.skill_evidence[0].jd_quote = "PRIVATE false JD quotation"
    elif where == "gap":
        assessment.gap_jd_quotes[0] = "PRIVATE false gap"
    else:
        assessment.gap_jd_quotes = []
    with pytest.raises(ResumeError) as caught:
        finalize_evidence_score(assessment, document.text, jd, document=document)
    assert caught.value.code == "AI_JD_EVIDENCE_INVALID"
    assert "PRIVATE" not in str(caught.value)


def test_jd_line_numbers_preserve_bom_blank_lines_and_crlf(tmp_path):
    path = tmp_path / "jd.txt"
    path.write_bytes(b"\xef\xbb\xbf\r\n\r\n" + "岗位：Python\r\n".encode())
    jd = read_jd(path)
    assert locate_quote(jd, "Python")["line_start"] == 3


def test_parse_pages_cli_and_no_ocr_on_text_pages(make_pdf, monkeypatch):
    from resume_cli import files as file_module

    def forbidden(*args, **kwargs):
        pytest.fail("Native text pages must not invoke OCR")

    monkeypatch.setattr(file_module, "ocr_page", forbidden)
    path = make_pdf(["PAGE ONE", "PAGE TWO"])
    result = CliRunner().invoke(app, ["parse", str(path), "--pages", "--ocr"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["page_count"] == 2
    assert [p["page"] for p in payload["pages"]] == [1, 2]
    assert {p["method"] for p in payload["pages"]} == {"pdf_text"}


@pytest.mark.parametrize("name", ["multi-page.pdf", "two-column.pdf", "table.pdf"])
def test_complex_native_corpus_tokens_survive_layout(name):
    root = Path(__file__).resolve().parents[1] / "examples/corpus"
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    sample = next(s for s in manifest["samples"] if s["file"] == name)
    for layout in [False, True]:
        document = parse_document(root / name, layout=layout)
        assert len(document.pages) == sample["pages"]
        for token in sample["checks"]:
            assert token in document.text


def test_native_scan_detection(make_pdf):
    root = Path(__file__).resolve().parents[1] / "examples/corpus"
    for name in ["scan-en.pdf", "scan-zh.pdf", "mixed.pdf"]:
        with pytest.raises(ResumeError) as caught:
            parse_document(root / name)
        assert caught.value.code == "PDF_PAGE_NO_TEXT"
