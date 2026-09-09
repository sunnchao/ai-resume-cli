"""Run a built resume-cli binary against committed synthetic examples."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def default_binary() -> Path:
    name = "resume-cli.exe" if os.name == "nt" else "resume-cli"
    onedir = ROOT / "dist" / "binary" / "resume-cli" / name
    onefile = ROOT / "dist" / "binary" / name
    return onedir if onedir.is_file() else onefile


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("binary", type=Path, nargs="?", default=None)
    args = parser.parse_args()
    binary = (args.binary or default_binary()).resolve()
    if not binary.is_file():
        print(f"找不到可执行文件：{binary}", file=sys.stderr)
        return 2
    if not os.access(binary, os.X_OK):
        print(f"文件不可执行：{binary}", file=sys.stderr)
        return 2

    first = str(ROOT / "examples/resume.pdf")
    second = str(ROOT / "examples/resume-alt.pdf")
    jd = str(ROOT / "examples/jd.txt")
    cases = [
        (["--version"], 0),
        (["parse", first], 0),
        (["parse", first, "--pages"], 0),
        (["extract", first, "--mock"], 0),
        (["score", first, "--jd", jd, "--mock", "--evidence"], 0),
        (["batch", "score", first, second, "--jd", jd, "--mock", "--evidence"], 0),
        (["batch", "extract", first, "missing.pdf", "--mock"], 7),
    ]
    with tempfile.TemporaryDirectory(prefix="resume-binary-") as directory:
        for command, expected in cases:
            result = subprocess.run(
                [str(binary), *command],
                cwd=directory,
                capture_output=True,
                text=True,
                encoding="utf-8",
            )
            if result.returncode != expected:
                sys.stderr.write(result.stderr)
                print(
                    f"二进制校验失败：{command[0]} code={result.returncode} expected={expected}",
                    file=sys.stderr,
                )
                return 1
            if command[0] == "--version":
                if result.stdout.strip() != "0.6.0":
                    print(f"版本不符：{result.stdout!r}", file=sys.stderr)
                    return 1
                if "启动中" not in result.stderr:
                    print("冻结程序启动时应立即在 stderr 提示。", file=sys.stderr)
                    return 1
            elif command[0] != "parse" or "--pages" in command:
                data = json.loads(result.stdout)
                if command[0] == "score":
                    assert data["skill_evidence"][0]["resume_locations"][0]["page"] == 1
                    assert data["gap_evidence"][0]["jd_location"]["line_start"] == 5
            print(f"PASS {command[0]} exit={expected}")
    print(f"OK {binary}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
