import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from resume_cli import cli
from resume_cli.cli import app
from resume_cli.domain.errors import ResumeError

runner = CliRunner()
PROJECT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("command", [[], ["parse"], ["extract"], ["score"]])
def test_help(command):
    result = runner.invoke(app, command + ["--help"])
    assert result.exit_code == 0
    assert "Usage" in result.stdout


def test_version():
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert result.stdout.strip() == "0.6.0"


def test_parse_and_mock_full_flow(make_pdf, jd_path, tmp_path):
    pdf = make_pdf(name="简历 示例.pdf")
    parsed = runner.invoke(app, ["parse", str(pdf)])
    assert parsed.exit_code == 0
    assert "Experience: API project" in parsed.stdout
    assert parsed.stderr == ""
    extracted = runner.invoke(app, ["extract", str(pdf), "--mock"])
    assert extracted.exit_code == 0
    assert json.loads(extracted.stdout)["name"] == "陈晨"
    assert "MOCK" in extracted.stderr and "MOCK" not in extracted.stdout
    target = tmp_path / "结果.json"
    scored = runner.invoke(
        app, ["score", str(pdf), "--jd", str(jd_path), "--mock", "--output", str(target)]
    )
    assert scored.exit_code == 0
    assert json.loads(scored.stdout)["overall_score"] == 82
    assert target.read_bytes() == scored.stdout.encode("utf-8")


def test_score_evidence_is_opt_in(make_pdf, jd_path):
    pdf = make_pdf()
    default = runner.invoke(app, ["score", str(pdf), "--jd", str(jd_path), "--mock"])
    detailed = runner.invoke(app, ["score", str(pdf), "--jd", str(jd_path), "--mock", "--evidence"])
    assert default.exit_code == detailed.exit_code == 0
    assert "skill_evidence" not in json.loads(default.stdout)
    result = json.loads(detailed.stdout)
    assert result["skill_evidence"][0]["source"] == "resume"
    assert result["gaps"]


def test_bad_input_checked_before_ai(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Must validate input before calling AI")

    monkeypatch.setattr(cli, "extract_resume", forbidden)
    result = runner.invoke(app, ["extract", "missing.pdf"])
    assert result.exit_code == 2 and result.stdout == ""
    assert "FILE_NOT_FOUND" in result.stderr


def test_invalid_pdf_even_in_mock(make_pdf):
    result = runner.invoke(app, ["extract", str(make_pdf([None])), "--mock"])
    assert result.exit_code == 3 and result.stdout == ""
    assert "PDF_PAGE_NO_TEXT" in result.stderr


def test_missing_jd_is_usage_error(make_pdf):
    result = runner.invoke(app, ["score", str(make_pdf()), "--mock"])
    assert result.exit_code == 2 and result.stdout == ""
    assert "--jd" in result.stderr


def test_missing_key_does_not_fall_back(make_pdf):
    result = runner.invoke(app, ["extract", str(make_pdf())])
    assert result.exit_code == 2 and result.stdout == ""
    assert "CONFIG_MISSING" in result.stderr and "MOCK：" not in result.stderr


def test_output_preflight_before_paid_request(make_pdf, monkeypatch, tmp_path):
    def forbidden(*args, **kwargs):
        raise AssertionError("Existing output must fail before AI")

    monkeypatch.setattr(cli, "extract_resume", forbidden)
    target = tmp_path / "existing.json"
    target.write_text("original")
    result = runner.invoke(app, ["extract", str(make_pdf()), "--output", str(target)])
    assert result.exit_code == 6 and result.stdout == ""
    assert target.read_text() == "original"


def test_output_failure_has_no_json_stdout(make_pdf, monkeypatch, tmp_path):
    def fail(*args, **kwargs):
        raise ResumeError("OUTPUT_WRITE_FAILED", "disk full", 6)

    monkeypatch.setattr(cli, "save_json", fail)
    result = runner.invoke(
        app, ["extract", str(make_pdf()), "--mock", "--output", str(tmp_path / "out.json")]
    )
    assert result.exit_code == 6 and result.stdout == ""
    assert "OUTPUT_WRITE_FAILED" in result.stderr


def test_committed_chinese_examples_and_expected_outputs():
    for name in ["resume.pdf", "resume-alt.pdf"]:
        result = runner.invoke(app, ["parse", str(PROJECT / "examples" / name)])
        assert result.exit_code == 0
        assert "虚构" in result.stdout
        assert "Python" in result.stdout
    result = runner.invoke(app, ["extract", str(PROJECT / "examples/resume.pdf"), "--mock"])
    expected = json.loads((PROJECT / "examples/expected-extract.json").read_text())
    assert json.loads(result.stdout) == expected
