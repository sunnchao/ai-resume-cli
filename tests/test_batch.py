import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from resume_cli.application import batch
from resume_cli.application.resumes import extract_resume
from resume_cli.cli import app
from resume_cli.domain.errors import ResumeError

runner = CliRunner()


def test_batch_keeps_order_deduplicates_and_reports_individual_failures(make_pdf, tmp_path):
    first = make_pdf(name="first.pdf")
    last = make_pdf(name="last.PDF")
    missing = tmp_path / "missing.pdf"
    alias = tmp_path / "alias.pdf"
    alias.symlink_to(first)
    report = batch.run_batch([first, missing, first, alias, last], "extract", mock=True)
    assert report.total == 3 and report.succeeded == 2 and report.failed == 1
    assert [r.file for r in report.results] == list(map(str, [first, missing, last]))
    assert report.results[1].error.code == "FILE_NOT_FOUND"
    assert report.results[2].status == "success"
    assert report.mode == "mock"


def test_score_reads_jd_once_and_evidence_is_marked_as_mock(make_pdf, jd_path, monkeypatch):
    real_read = batch.read_jd
    reads = []

    def read(path):
        reads.append(path)
        return real_read(path)

    monkeypatch.setattr(batch, "read_jd", read)
    report = batch.run_batch(
        [make_pdf(name="one.pdf"), make_pdf(name="two.pdf")],
        "score",
        jd_path=jd_path,
        mock=True,
        include_evidence=True,
    )
    assert reads == [jd_path]
    data = json.loads(report.model_dump_json())
    assert data["failed"] == 0
    assert all(row["result"]["evidence_basis"] == "mock_fixture" for row in data["results"])


def test_batch_default_score_preserves_legacy_result(make_pdf, jd_path):
    report = batch.run_batch([make_pdf()], "score", jd_path=jd_path, mock=True)
    assert set(report.results[0].result.model_dump()) == {
        "overall_score",
        "skill_score",
        "experience_score",
        "education_score",
        "comment",
        "interview_questions",
    }


@pytest.mark.parametrize(
    "paths,code", [([], "BATCH_EMPTY"), ([Path(f"{i}.pdf") for i in range(21)], "BATCH_TOO_LARGE")]
)
def test_batch_count_errors_are_global(paths, code):
    with pytest.raises(ResumeError) as caught:
        batch.run_batch(paths, "extract", mock=True)
    assert caught.value.code == code


def test_batch_configuration_and_jd_fail_before_any_processing(make_pdf, jd_path, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("global errors must be checked before processing PDFs")

    pdf = make_pdf()
    monkeypatch.setattr(batch, "parse_document", forbidden)
    with pytest.raises(ResumeError, match="OPENAI_API_KEY"):
        batch.run_batch([pdf], "extract")
    jd_path.write_text(" ")
    with pytest.raises(ResumeError) as caught:
        batch.run_batch([pdf], "score", jd_path=jd_path, mock=True)
    assert caught.value.code == "JD_EMPTY"
    with pytest.raises(ResumeError) as caught:
        batch.run_batch([pdf], "score", mock=True)
    assert caught.value.code == "BATCH_JD_REQUIRED"


def test_batch_continues_after_ai_error(make_pdf, monkeypatch):
    calls = []
    monkeypatch.setattr(batch.Settings, "load", lambda: None)

    def request(text, **kwargs):
        calls.append(text)
        if "FAIL" in text:
            raise ResumeError("AI_REQUEST_FAILED", "AI failed", 4)
        return extract_resume(text, mock=True)

    monkeypatch.setattr(batch, "extract_resume", request)
    report = batch.run_batch(
        [make_pdf(["FAIL"], name="bad.pdf"), make_pdf(name="ok.pdf")], "extract"
    )
    assert len(calls) == 2 and report.failed == 1 and report.succeeded == 1
    assert report.results[0].error.exit_code == 4
    assert report.mode == "ai"


def test_batch_cli_saves_partial_report_and_exits_seven(make_pdf, tmp_path):
    output = tmp_path / "report.json"
    result = runner.invoke(
        app,
        [
            "batch",
            "extract",
            str(make_pdf()),
            "missing.pdf",
            "--mock",
            "--output",
            str(output),
        ],
    )
    assert result.exit_code == 7
    payload = json.loads(result.stdout)
    assert payload["total"] == 2 and payload["failed"] == 1
    assert output.read_bytes() == result.stdout.encode("utf-8")
    assert "[1/2]" in result.stderr and "[2/2]" in result.stderr
    assert "MOCK" in result.stderr


def test_batch_all_failures_are_still_reported():
    result = runner.invoke(app, ["batch", "extract", "missing.pdf", "--mock"])
    assert result.exit_code == 7
    assert json.loads(result.stdout)["succeeded"] == 0


def test_batch_rejects_existing_output_before_calls(make_pdf, tmp_path, monkeypatch):
    from resume_cli import cli

    def forbidden(*args, **kwargs):
        pytest.fail("should not run batch")

    monkeypatch.setattr(cli, "run_batch", forbidden)
    output = tmp_path / "existing.json"
    output.write_text("original")
    result = runner.invoke(app, ["batch", "extract", str(make_pdf()), "--output", str(output)])
    assert result.exit_code == 6 and result.stdout == ""
    assert output.read_text() == "original"


def test_batch_score_cli_supports_evidence(make_pdf, jd_path):
    result = runner.invoke(
        app,
        [
            "batch",
            "score",
            str(make_pdf()),
            "--jd",
            str(jd_path),
            "--evidence",
            "--mock",
        ],
    )
    assert result.exit_code == 0
    assert json.loads(result.stdout)["results"][0]["result"]["skill_evidence"]


@pytest.mark.parametrize("args", [["batch"], ["batch", "extract"], ["batch", "score"]])
def test_batch_help(args):
    assert runner.invoke(app, [*args, "--help"]).exit_code == 0


def test_batch_global_failure_has_empty_stdout():
    result = runner.invoke(app, ["batch", "score", "some.pdf", "--jd", "missing.txt", "--mock"])
    assert result.exit_code == 2 and result.stdout == ""
