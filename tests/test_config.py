import pytest

from resume_cli.config import Settings
from resume_cli.errors import ResumeError


def test_missing_config():
    with pytest.raises(ResumeError) as caught:
        Settings.load()
    assert caught.value.code == "CONFIG_MISSING"
    assert "OPENAI_API_KEY" in str(caught.value)
    assert "OPENAI_MODEL" in str(caught.value)


def test_dotenv_environment_precedence_and_no_secret_repr(tmp_path, monkeypatch):
    (tmp_path / ".env").write_text("OPENAI_API_KEY=private-key\nOPENAI_MODEL=file-model\n")
    monkeypatch.setenv("OPENAI_MODEL", "shell-model")
    settings = Settings.load()
    assert settings.model == "shell-model"
    assert settings.api_key == "private-key"
    assert "private-key" not in repr(settings)
    assert settings.base_url == "https://api.openai.com/v1"


@pytest.mark.parametrize(
    "url",
    [
        "not a url",
        "file:///tmp/a",
        "https://user:secret@host/v1",
        "https://host/v1?key=secret",
        "https://host:invalid/v1",
        "https://host:99999/v1",
    ],
)
def test_bad_endpoint_does_not_echo_secret(monkeypatch, url):
    monkeypatch.setenv("OPENAI_API_KEY", "key")
    monkeypatch.setenv("OPENAI_MODEL", "model")
    monkeypatch.setenv("OPENAI_BASE_URL", url)
    with pytest.raises(ResumeError) as caught:
        Settings.load()
    assert caught.value.code == "CONFIG_URL_INVALID"
    assert "secret" not in str(caught.value)


def test_does_not_load_parent_dotenv(tmp_path, monkeypatch):
    (tmp_path / ".env").write_text("OPENAI_API_KEY=key\nOPENAI_MODEL=parent-model\n")
    child = tmp_path / "child"
    child.mkdir()
    monkeypatch.chdir(child)
    with pytest.raises(ResumeError, match="OPENAI_API_KEY"):
        Settings.load()
