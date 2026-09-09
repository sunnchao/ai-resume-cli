"""Opt-in real API smoke check using only the committed synthetic examples."""

import argparse
import sys
from pathlib import Path

from resume_cli.adapters.config import Settings
from resume_cli.adapters.documents import parse_document, read_jd
from resume_cli.adapters.prompts import PROMPT_VERSION
from resume_cli.application.resumes import extract_resume, score_resume
from resume_cli.domain.errors import ResumeError

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", action="store_true", help="同时验证新增评分证据与原文校验。")
    args = parser.parse_args()
    try:
        settings = Settings.load()
        print(f"真实 API 验证；模型：{settings.model}；提示词版本：{PROMPT_VERSION}")
        print("以下只使用仓库的虚构样例，最多正常调用 4 次；结果仍需人工核对。")
        jd = read_jd(ROOT / "examples/jd.txt")
        for name in ["resume.pdf", "resume-alt.pdf"]:
            document = parse_document(ROOT / "examples" / name)
            text = document.text
            print(f"\n{name} / extract")
            print(extract_resume(text).model_dump_json(indent=2))
            print(f"\n{name} / score")
            print(
                score_resume(
                    text, jd, include_evidence=args.evidence, document=document
                ).model_dump_json(indent=2)
            )
    except ResumeError as exc:
        print(f"ERROR [{exc.code}] {exc.message}", file=sys.stderr)
        return exc.exit_code
    return 0


if __name__ == "__main__":
    sys.exit(main())
