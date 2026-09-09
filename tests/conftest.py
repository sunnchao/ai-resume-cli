import io
import socket
from pathlib import Path

import pytest
from reportlab.pdfgen.canvas import Canvas

PROJECT = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def isolated_environment(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    for key in ["OPENAI_API_KEY", "OPENAI_MODEL", "OPENAI_BASE_URL", "OPENAI_LOG"]:
        monkeypatch.delenv(key, raising=False)

    def forbidden_network(*args, **kwargs):
        raise AssertionError("Offline tests must not access the network")

    monkeypatch.setattr(socket.socket, "connect", forbidden_network)
    monkeypatch.setattr(socket.socket, "connect_ex", forbidden_network)


@pytest.fixture
def make_pdf(tmp_path):
    def create(pages=None, name="resume.pdf"):
        data = io.BytesIO()
        canvas = Canvas(data)
        for text in (
            ["Candidate\nPython React PostgreSQL\nExperience: API project"]
            if pages is None
            else pages
        ):
            if text:
                obj = canvas.beginText(50, 780)
                obj.setFont("Helvetica", 10)
                obj.textLines(text)
                canvas.drawText(obj)
            canvas.showPage()
        canvas.save()
        path = tmp_path / name
        path.write_bytes(data.getvalue())
        return path

    return create


@pytest.fixture
def jd_path(tmp_path):
    path = tmp_path / "jd.txt"
    path.write_text("全栈工程师：Python、React；负责 API 开发；计算机本科。", encoding="utf-8")
    return path
