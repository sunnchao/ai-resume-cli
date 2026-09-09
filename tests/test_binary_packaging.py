import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load(name: str):
    path = ROOT / "scripts" / name
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_binary_build_script_defaults_to_onedir():
    module = _load("build_binary.py")
    assert module.DEFAULT_DIST == ROOT / "dist" / "binary"
    assert module.binary_name("resume-cli") in {"resume-cli", "resume-cli.exe"}
    onedir = module.artifact_path(module.DEFAULT_DIST, "resume-cli", onefile=False)
    onefile = module.artifact_path(module.DEFAULT_DIST, "resume-cli", onefile=True)
    assert onedir != onefile
    assert onedir.parent.name == "resume-cli"


def test_binary_verify_script_prefers_onedir():
    module = _load("verify_binary.py")
    assert module.ROOT == ROOT
    assert callable(module.default_binary)
    assert module.BOOT_NOTICE == "resume-cli starting..."


def test_binary_verify_decodes_windows_console_bytes():
    module = _load("verify_binary.py")
    # GitHub Windows runners emitted 0x85 (cp1252 ellipsis) on frozen stderr.
    assert module.decode_output(None) == ""
    assert module.decode_output(b"") == ""
    assert module.decode_output(b"resume-cli starting...") == "resume-cli starting..."
    assert "启动中" in module.decode_output("resume-cli 启动中…".encode())
    assert module.decode_output(b"resume-cli \x85") == "resume-cli \u2026"
