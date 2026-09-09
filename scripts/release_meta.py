"""Version checks and release artifact packaging for GitHub tag builds."""

from __future__ import annotations

import argparse
import hashlib
import platform
import re
import sys
import tarfile
import tomllib
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSION_RE = re.compile(r"^\d+\.\d+\.\d+$")
INIT_VERSION_RE = re.compile(r'^__version__\s*=\s*"([^"]+)"', re.MULTILINE)


def package_version(root: Path = ROOT) -> str:
    data = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    project = data["project"]["version"]
    init_text = (root / "src" / "resume_cli" / "__init__.py").read_text(encoding="utf-8")
    match = INIT_VERSION_RE.search(init_text)
    if match is None:
        raise ValueError("src/resume_cli/__init__.py 缺少 __version__")
    if match.group(1) != project:
        raise ValueError(f"版本不一致：pyproject.toml={project} __init__.py={match.group(1)}")
    if VERSION_RE.fullmatch(project) is None:
        raise ValueError(f"版本号不是 X.Y.Z：{project}")
    return project


def tag_version(tag: str) -> str:
    value = tag.strip()
    if value.startswith("refs/tags/"):
        value = value.removeprefix("refs/tags/")
    if value.startswith("v") and VERSION_RE.fullmatch(value[1:]):
        return value[1:]
    raise ValueError(f"tag 不是 vX.Y.Z：{tag}")


def check_tag(tag: str, root: Path = ROOT) -> str:
    version = package_version(root)
    parsed = tag_version(tag)
    if parsed != version:
        raise ValueError(f"tag 版本 {parsed} 与包装版本 {version} 不一致")
    return version


def platform_label(
    system: str | None = None,
    machine: str | None = None,
) -> str:
    system_name = (system or sys.platform).lower()
    cpu = (machine or platform.machine()).lower()
    if cpu in {"amd64", "x64"}:
        cpu = "x86_64"
    elif cpu in {"aarch64"}:
        cpu = "arm64"
    if system_name.startswith("linux"):
        os_name = "linux"
    elif system_name == "darwin":
        os_name = "macos"
    elif system_name.startswith("win"):
        os_name = "windows"
    else:
        raise ValueError(f"不支持的平台：{system_name}")
    return f"{os_name}-{cpu}"


def archive_name(version: str, label: str | None = None) -> str:
    slug = label or platform_label()
    suffix = ".zip" if slug.startswith("windows") else ".tar.gz"
    return f"resume-cli-{version}-{slug}{suffix}"


def python_wheel_name(version: str) -> str:
    return f"ai_resume_cli-{version}-py3-none-any.whl"


def python_sdist_name(version: str) -> str:
    return f"ai_resume_cli-{version}.tar.gz"


def _copy_file(source: Path, destination: Path) -> Path:
    destination.write_bytes(source.read_bytes())
    return destination


def collect_python(dist: Path, dest: Path, version: str | None = None) -> list[Path]:
    resolved = package_version() if version is None else version
    dest.mkdir(parents=True, exist_ok=True)
    collected: list[Path] = []
    for name in (python_wheel_name(resolved), python_sdist_name(resolved)):
        source = dist / name
        if not source.is_file():
            raise FileNotFoundError(f"缺少 Python 产物：{source}")
        collected.append(_copy_file(source, dest / name))
    return collected


def archive_binary(source: Path, dest: Path, version: str | None = None) -> Path:
    if not source.is_dir():
        raise FileNotFoundError(f"缺少二进制目录：{source}")
    resolved = package_version() if version is None else version
    dest.mkdir(parents=True, exist_ok=True)
    archive = dest / archive_name(resolved)
    if archive.exists():
        archive.unlink()
    if archive.name.endswith(".zip"):
        with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as handle:
            for path in sorted(source.rglob("*")):
                if path.is_file():
                    relative = path.relative_to(source).as_posix()
                    handle.write(path, arcname=f"{source.name}/{relative}")
    else:
        with tarfile.open(archive, "w:gz") as handle:
            handle.add(source, arcname=source.name)
    return archive


def write_checksums(directory: Path) -> Path:
    output = directory / "SHA256SUMS"
    lines: list[str] = []
    for path in sorted(directory.iterdir()):
        if not path.is_file() or path.name == output.name:
            continue
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        lines.append(f"{digest}  {path.name}")
    if not lines:
        raise FileNotFoundError(f"没有可校验的文件：{directory}")
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return output


def changelog_notes(root: Path, version: str) -> str:
    text = (root / "CHANGELOG.md").read_text(encoding="utf-8")
    heading = f"## {version}"
    start = text.find(heading)
    if start < 0:
        body = "本次 tag 构建 wheel / sdist 与当前 runner 本机架构的独立二进制。"
    else:
        rest = text[start:]
        next_heading = rest.find("\n## ", 1)
        body = rest if next_heading < 0 else rest[:next_heading]
        body = body.strip()
    summary = (
        "由版本 tag 触发 GitHub Actions 构建。Python 包可在 3.11+ 安装；"
        "独立二进制按 runner 本机操作系统和 CPU 打包，不交叉编译，"
        "默认目录分发，不含 OCR extra，也不内嵌 Tesseract。"
    )
    return f"# ai-resume-cli {version}\n\n{summary}\n\n{body}\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("version", help="打印 pyproject / __init__ 中的包装版本。")
    check = sub.add_parser("check-tag", help="校验 Git tag 与包装版本一致。")
    check.add_argument("tag")
    sub.add_parser("platform", help="打印当前平台的产物标签。")

    collect = sub.add_parser("collect-python", help="复制 wheel / sdist 到发布目录。")
    collect.add_argument("--dist", type=Path, default=ROOT / "dist")
    collect.add_argument("--dest", type=Path, default=ROOT / "dist" / "release")

    archive = sub.add_parser("archive", help="把目录分发二进制打成版本化压缩包。")
    archive.add_argument("--source", type=Path, default=ROOT / "dist" / "binary" / "resume-cli")
    archive.add_argument("--dest", type=Path, default=ROOT / "dist" / "release")

    checksums = sub.add_parser("checksums", help="为目录中的文件写入 SHA256SUMS。")
    checksums.add_argument("directory", type=Path)

    notes = sub.add_parser("notes", help="根据 CHANGELOG 生成 Release 说明。")
    notes.add_argument("--output", type=Path, required=True)

    args = parser.parse_args()
    try:
        if args.command == "version":
            print(package_version())
        elif args.command == "check-tag":
            print(check_tag(args.tag))
        elif args.command == "platform":
            print(platform_label())
        elif args.command == "collect-python":
            for path in collect_python(args.dist, args.dest):
                print(path)
        elif args.command == "archive":
            print(archive_binary(args.source, args.dest))
        elif args.command == "checksums":
            print(write_checksums(args.directory))
        elif args.command == "notes":
            version = package_version()
            args.output.write_text(changelog_notes(ROOT, version), encoding="utf-8")
            print(args.output)
    except (OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
