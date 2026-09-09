"""Build a standalone resume-cli executable for the current platform."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DIST = ROOT / "dist" / "binary"


def binary_name(name: str) -> str:
    return f"{name}.exe" if os.name == "nt" else name


def artifact_path(dist: Path, name: str, *, onefile: bool) -> Path:
    filename = binary_name(name)
    return dist / filename if onefile else dist / name / filename


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--name", default="resume-cli", help="可执行文件名，不含扩展名。")
    parser.add_argument(
        "--dist",
        type=Path,
        default=DEFAULT_DIST,
        help="输出目录，默认 dist/binary。",
    )
    parser.add_argument(
        "--ocr",
        action="store_true",
        help="打包可选 OCR 的 Python 依赖；系统仍需安装 Tesseract。",
    )
    parser.add_argument(
        "--onefile",
        action="store_true",
        help="打成单文件。每次启动都要解压，会明显变慢；默认使用目录分发。",
    )
    args = parser.parse_args()

    try:
        import PyInstaller.__main__  # noqa: F401
    except ImportError:
        print(
            "未安装 PyInstaller。请执行：uv sync --frozen --group dev --group binary",
            file=sys.stderr,
        )
        return 2

    dist = args.dist.resolve()
    work = ROOT / "build" / "pyinstaller"
    dist.mkdir(parents=True, exist_ok=True)
    work.mkdir(parents=True, exist_ok=True)

    previous = dist / args.name
    if previous.is_file():
        previous.unlink()
    elif previous.is_dir():
        shutil.rmtree(previous)

    data_sep = ";" if os.name == "nt" else ":"
    fixtures = ROOT / "src" / "resume_cli" / "fixtures"
    command = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--console",
        "--name",
        args.name,
        "--paths",
        str(ROOT / "src"),
        "--distpath",
        str(dist),
        "--workpath",
        str(work),
        "--specpath",
        str(work),
        "--collect-submodules",
        "resume_cli",
        "--collect-data",
        "resume_cli",
        "--add-data",
        f"{fixtures}{data_sep}resume_cli/fixtures",
        "--collect-all",
        "pydantic",
        "--copy-metadata",
        "openai",
        "--copy-metadata",
        "pydantic",
        "--copy-metadata",
        "httpx",
        "--copy-metadata",
        "typer",
        "--copy-metadata",
        "certifi",
        "--hidden-import",
        "resume_cli.cli",
        "--hidden-import",
        "certifi",
        "--hidden-import",
        "typer",
        "--hidden-import",
        "dotenv",
        "--onefile" if args.onefile else "--onedir",
    ]
    if args.ocr:
        command.extend(
            [
                "--collect-all",
                "pypdfium2",
                "--hidden-import",
                "PIL",
                "--hidden-import",
                "PIL.Image",
            ]
        )
    command.append(str(ROOT / "src" / "resume_cli" / "__main__.py"))

    print(" ".join(command))
    subprocess.run(command, check=True, cwd=ROOT)

    produced = artifact_path(dist, args.name, onefile=args.onefile)
    if not produced.is_file():
        print(f"未找到产物：{produced}", file=sys.stderr)
        return 1
    produced.chmod(produced.stat().st_mode | 0o111)
    print(f"binary={produced}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
