"""Verify an installed wheel in an isolated environment outside the checkout."""

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("wheel", type=Path)
    args = parser.parse_args()
    uv = shutil.which("uv")
    if uv is None:
        parser.error("This validation script requires uv on PATH.")
    root = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory(prefix="resume-wheel-") as directory:
        location = Path(directory)
        subprocess.run(
            [uv, "venv", "--quiet", "--python", sys.executable, str(location / "venv")], check=True
        )
        python = location / "venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        subprocess.run(
            [uv, "pip", "install", "--quiet", "--python", str(python), str(args.wheel.resolve())],
            check=True,
        )
        base = [str(python), "-m", "resume_cli"]
        first = str(root / "examples/resume.pdf")
        second = str(root / "examples/resume-alt.pdf")
        jd = str(root / "examples/jd.txt")
        cases = [
            (["--version"], 0),
            (["parse", first], 0),
            (["parse", first, "--pages"], 0),
            (["extract", first, "--mock"], 0),
            (["score", first, "--jd", jd, "--mock", "--evidence"], 0),
            (["batch", "score", first, second, "--jd", jd, "--mock", "--evidence"], 0),
            (["batch", "extract", first, "missing.pdf", "--mock"], 7),
        ]
        for command, expected in cases:
            result = subprocess.run(
                base + command, cwd=directory, capture_output=True, text=True, encoding="utf-8"
            )
            if result.returncode != expected:
                raise RuntimeError(
                    f"Wheel verification failed: {command[0]}, code={result.returncode}"
                )
            if command[0] not in {"--version", "parse"} or "--pages" in command:
                data = json.loads(result.stdout)
                if command[0] == "score":
                    assert data["skill_evidence"][0]["resume_locations"][0]["page"] == 1
                    assert data["gap_evidence"][0]["jd_location"]["line_start"] == 5
            print(f"PASS {command[0]} exit={expected}")


if __name__ == "__main__":
    main()
