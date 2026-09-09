"""Generate ONLY synthetic PDF regression samples, including real image-only scans."""

import argparse
import io
import json
from pathlib import Path

import pypdfium2 as pdfium
from reportlab.lib.colors import HexColor
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen.canvas import Canvas

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "examples/corpus"
PAGE = (595, 842)


def page(canvas, title, lines, *, x=45, y=710, width=500):
    canvas.setFillColor(HexColor("#142B3E"))
    canvas.setFont("CorpusCJK", 23)
    canvas.drawString(x, y + 55, title)
    canvas.setStrokeColor(HexColor("#087F83"))
    canvas.line(x, y + 35, x + width, y + 35)
    canvas.setFont("CorpusCJK", 14)
    for line in lines:
        canvas.drawString(x, y, line)
        y -= 32


def scan_image(title, lines):
    source = io.BytesIO()
    canvas = Canvas(source, pagesize=PAGE)
    page(canvas, title, lines)
    canvas.save()
    with pdfium.PdfDocument(source.getvalue()) as doc:
        pdf_page = doc[0]
        bitmap = pdf_page.render(scale=3)
        image = bitmap.to_pil().copy()
        bitmap.close()
        pdf_page.close()
        return image


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--font", type=Path, default=Path("/System/Library/Fonts/STHeiti Light.ttc")
    )
    args = parser.parse_args()
    if not args.font.is_file():
        parser.error("请使用 --font 指定中文 TrueType 字体；现有样例无需重新生成。")
    pdfmetrics.registerFont(TTFont("CorpusCJK", str(args.font), subfontIndex=0))
    OUT.mkdir(parents=True, exist_ok=True)

    canvas = Canvas(str(OUT / "multi-page.pdf"), pagesize=PAGE, invariant=1)
    for title, lines in [
        (
            "虚构简历 / Skills",
            ["PAGE_ONE", "技能：Python、React、PostgreSQL", "Email: demo@example.com"],
        ),
        (
            "项目经历 / Experience",
            ["PAGE_TWO", "使用 Python 开发订单 API。", "负责 React 管理页面与单元测试。"],
        ),
        (
            "教育经历 / Education",
            ["PAGE_THREE", "示例大学 | 计算机科学 | 本科", "毕业时间：2024-06"],
        ),
    ]:
        page(canvas, title, lines)
        canvas.showPage()
    canvas.save()

    canvas = Canvas(str(OUT / "two-column.pdf"), pagesize=PAGE, invariant=1)
    page(canvas, "虚构双栏简历", ["Synthetic layout regression sample"])
    page(canvas, "Backend", ["Python", "PostgreSQL", "API development"], x=45, y=520, width=220)
    page(canvas, "Frontend", ["React", "TypeScript", "Component testing"], x=325, y=520, width=220)
    canvas.save()

    canvas = Canvas(str(OUT / "table.pdf"), pagesize=PAGE, invariant=1)
    page(canvas, "虚构项目技能表", ["Synthetic table - all values are fictional"])
    canvas.setFont("CorpusCJK", 13)
    rows = [
        ("Skill", "Experience", "Project"),
        ("Python", "3 years", "Order API"),
        ("React", "2 years", "Admin UI"),
        ("PostgreSQL", "2 years", "Task database"),
    ]
    for index, row in enumerate(rows):
        y = 600 - index * 42
        canvas.setStrokeColor(HexColor("#C5D9DE"))
        canvas.rect(45, y - 14, 500, 42, stroke=1, fill=0)
        for x, text in zip([55, 220, 380], row, strict=True):
            canvas.drawString(x, y, text)
    canvas.save()

    english = scan_image(
        "SYNTHETIC RESUME",
        [
            "SCAN_ENGLISH",
            "Skills: Python React PostgreSQL",
            "Experience: API development",
            "Education: Computer Science degree",
            "All candidate information is fictional.",
        ],
    )
    chinese = scan_image(
        "虚构简历",
        [
            "姓名：示例候选人",
            "技能：Python 和 React",
            "项目：开发订单管理系统",
            "教育：计算机本科",
        ],
    )
    for name, image in [("scan-en.pdf", english), ("scan-zh.pdf", chinese)]:
        canvas = Canvas(str(OUT / name), pagesize=PAGE, invariant=1)
        canvas.drawImage(ImageReader(image), 0, 0, width=PAGE[0], height=PAGE[1])
        canvas.save()
    canvas = Canvas(str(OUT / "mixed.pdf"), pagesize=PAGE, invariant=1)
    page(
        canvas,
        "Mixed synthetic PDF",
        ["NATIVE_PAGE_ONE", "Skills: Python", "Page two is a scanned image."],
    )
    canvas.showPage()
    canvas.drawImage(ImageReader(english), 0, 0, width=PAGE[0], height=PAGE[1])
    canvas.save()
    english.close()
    chinese.close()

    canvas = Canvas(str(OUT / "blank-page.pdf"), pagesize=PAGE, invariant=1)
    page(canvas, "Negative fixture", ["Page two is intentionally blank."])
    canvas.showPage()
    canvas.showPage()
    canvas.save()
    manifest = {
        "synthetic": True,
        "check_normalization": "ignore_whitespace",
        "samples": [
            {
                "file": "multi-page.pdf",
                "pages": 3,
                "checks": ["PAGE_ONE", "PAGE_TWO", "PAGE_THREE"],
            },
            {
                "file": "two-column.pdf",
                "pages": 1,
                "checks": ["Python", "React", "PostgreSQL", "TypeScript"],
            },
            {
                "file": "table.pdf",
                "pages": 1,
                "checks": ["Python", "React", "Order API", "Admin UI"],
            },
            {
                "file": "scan-en.pdf",
                "pages": 1,
                "ocr": "eng",
                "checks": ["Python", "React", "PostgreSQL"],
            },
            {
                "file": "scan-zh.pdf",
                "pages": 1,
                "ocr": "eng+chi_sim",
                "checks": ["Python", "React", "计算机"],
            },
            {
                "file": "mixed.pdf",
                "pages": 2,
                "ocr": "eng",
                "checks": ["NATIVE_PAGE_ONE", "Python"],
            },
            {"file": "blank-page.pdf", "pages": 2, "expected_error": "OCR_EMPTY"},
        ],
    }
    (OUT / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"Created {len(manifest['samples'])} synthetic PDF fixtures.")


if __name__ == "__main__":
    main()
