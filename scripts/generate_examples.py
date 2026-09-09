"""Generate small, synthetic text-layer PDFs and deterministic mock examples."""

import argparse
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

from resume_cli.ai import extract_resume, score_resume

ROOT = Path(__file__).resolve().parents[1]

SAMPLES = {
    "resume.pdf": (
        "陈晨 | 全栈开发",
        [
            ("样例说明", "本简历所有姓名、学校、经历均为虚构，仅用于程序演示。"),
            ("基本信息", "所在城市：杭州\n邮箱：chen@example.com\n未提供电话。"),
            ("教育经历", "示例大学 | 计算机科学 | 本科\n毕业时间：2024-06"),
            ("技能", "Python、React、PostgreSQL"),
            (
                "工作与项目经历",
                "2024-07 至 2026-06：示例软件工作室，全栈开发工程师。\n"
                "负责内部任务管理应用：使用 Python 编写 API，React 构建任务列表和表单，"
                "PostgreSQL 保存任务与状态。\n编写接口测试，参与服务部署与故障排查。"
                "未提供生产访问规模或大模型 API 项目经历。",
            ),
        ],
    ),
    "resume-alt.pdf": (
        "林语 | Python 开发",
        [
            ("样例说明", "本简历全部资料为虚构，专用于第二组人工验收。"),
            ("基本信息", "所在城市：上海\n邮箱：lin@example.com\n电话：138****0000"),
            (
                "教育经历",
                "示例理工学院 | 软件工程 | 本科 | 2022-06\n"
                "示例科技大学 | 计算机技术 | 硕士 | 2025-06",
            ),
            ("技能", "Python、FastAPI、PostgreSQL、Docker"),
            (
                "项目经历",
                "2025-07 至 2026-06：知识库问答实验项目。\n"
                "使用 Python 编写文件处理和模型 API 调用模块，使用 PostgreSQL 存储业务记录；"
                "用 Docker 部署测试环境，并为网络超时编写异常处理。\n"
                "React 尚在学习中，未提供已交付的 React 页面项目。",
            ),
        ],
    ),
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--font", type=Path, help="可嵌入的中文 TrueType 字体（TTF / TTC）。")
    args = parser.parse_args()
    candidates = (
        [args.font]
        if args.font
        else [
            Path("/System/Library/Fonts/STHeiti Light.ttc"),
            Path("/usr/share/fonts/truetype/arphic/uming.ttc"),
            Path("C:/Windows/Fonts/simhei.ttf"),
        ]
    )
    font = next((path for path in candidates if path.is_file()), None)
    if font is None:
        parser.error("未找到中文字体，请用 --font 指定可嵌入的中文 TTF / TTC 文件。")
    out = ROOT / "examples"
    out.mkdir(exist_ok=True)
    pdfmetrics.registerFont(TTFont("ExampleCJK", str(font), subfontIndex=0))
    body = ParagraphStyle(
        "body",
        fontName="ExampleCJK",
        fontSize=11,
        leading=19,
        wordWrap="CJK",
        textColor=colors.HexColor("#253A49"),
    )
    heading = ParagraphStyle(
        "heading", parent=body, fontSize=13, leading=22, textColor=colors.HexColor("#087F83")
    )
    title_style = ParagraphStyle("title", parent=body, fontSize=24, leading=32)
    for filename, (title, sections) in SAMPLES.items():
        document = SimpleDocTemplate(
            str(out / filename),
            title=title + "（虚构样例）",
            author="resume-cli demo",
            leftMargin=48,
            rightMargin=48,
            topMargin=48,
            bottomMargin=48,
        )
        story = [Paragraph(title, title_style), Spacer(1, 18)]
        for label, content in sections:
            story += [
                Paragraph(label, heading),
                Paragraph(escape(content).replace("\n", "<br/>"), body),
                Spacer(1, 14),
            ]
        document.build(story)
        print(out / filename)
    results = {
        "expected-extract.json": extract_resume("", mock=True),
        "expected-score.json": score_resume("", "", mock=True),
        "expected-score-evidence.json": score_resume("", "", mock=True, include_evidence=True),
    }
    for name, result in results.items():
        (out / name).write_text(result.model_dump_json(indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
