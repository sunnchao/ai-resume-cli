import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _load():
    path = ROOT / "scripts" / "release_meta.py"
    spec = importlib.util.spec_from_file_location("release_meta", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_package_version_matches_project():
    module = _load()
    assert module.package_version() == "0.6.0"
    assert module.python_wheel_name("0.6.0") == "ai_resume_cli-0.6.0-py3-none-any.whl"
    assert module.python_sdist_name("0.6.0") == "ai_resume_cli-0.6.0.tar.gz"


def test_tag_version_requires_v_prefix():
    module = _load()
    assert module.tag_version("v0.6.0") == "0.6.0"
    assert module.tag_version("refs/tags/v1.2.3") == "1.2.3"
    with pytest.raises(ValueError, match="vX.Y.Z"):
        module.tag_version("0.6.0")
    with pytest.raises(ValueError, match="vX.Y.Z"):
        module.tag_version("v0.6.0-rc.1")


def test_check_tag_rejects_mismatch(tmp_path):
    module = _load()
    root = tmp_path
    (root / "pyproject.toml").write_text('[project]\nversion = "0.6.0"\n', encoding="utf-8")
    init = root / "src" / "resume_cli"
    init.mkdir(parents=True)
    (init / "__init__.py").write_text('__version__ = "0.6.0"\n', encoding="utf-8")
    assert module.check_tag("v0.6.0", root=root) == "0.6.0"
    with pytest.raises(ValueError, match="不一致"):
        module.check_tag("v0.7.0", root=root)


def test_platform_archive_names():
    module = _load()
    assert module.platform_label("linux", "x86_64") == "linux-x86_64"
    assert module.platform_label("darwin", "arm64") == "macos-arm64"
    assert module.platform_label("win32", "AMD64") == "windows-x86_64"
    assert module.archive_name("0.6.0", "linux-x86_64") == "resume-cli-0.6.0-linux-x86_64.tar.gz"
    assert module.archive_name("0.6.0", "windows-x86_64") == "resume-cli-0.6.0-windows-x86_64.zip"


def test_archive_checksums_and_notes(tmp_path):
    module = _load()
    source = tmp_path / "resume-cli"
    nested = source / "_internal"
    nested.mkdir(parents=True)
    (source / "resume-cli").write_text("fake-binary", encoding="utf-8")
    (nested / "lib.txt").write_text("lib", encoding="utf-8")
    dest = tmp_path / "release"
    archive = module.archive_binary(source, dest, version="0.6.0")
    assert archive.name.startswith("resume-cli-0.6.0-")
    assert archive.is_file()

    wheel = dest / module.python_wheel_name("0.6.0")
    wheel.write_bytes(b"wheel")
    checksums = module.write_checksums(dest)
    text = checksums.read_text(encoding="utf-8")
    assert archive.name in text
    assert wheel.name in text
    assert "SHA256SUMS" not in text.split()

    notes = module.changelog_notes(ROOT, "0.6.0")
    assert notes.startswith("# ai-resume-cli 0.6.0")
    assert "PDF 解析保留页码" in notes
