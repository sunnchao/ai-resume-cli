# PDF / OCR 回归样例集

全部内容由 `scripts/generate_corpus.py` 生成，人物、学校、项目和岗位均为虚构。扫描 PDF 只含页面图像，不含隐藏文本层。样例总计 7 份 PDF、11 页。

| 文件 | 类型 | 预期行为 |
| --- | --- | --- |
| multi-page.pdf | 三页中英混排 | 第 1 页技能、第 2 页项目、第 3 页教育；页码由解析器保留 |
| two-column.pdf | 双栏 | plain / layout 均能提取关键技能，layout 尽量保留水平位置 |
| table.pdf | 技能表格 | 关键技能、年限和项目可提取，不承诺恢复结构化表格 |
| scan-en.pdf | 英文纯扫描 | 默认无文本报错；--ocr --ocr-lang eng 可识别关键技能 |
| scan-zh.pdf | 中文纯扫描 | --ocr --ocr-lang eng+chi_sim 可识别中文与英文关键内容 |
| mixed.pdf | 文本页 + 扫描页 | --ocr 时第 1 页 pdf_text、第 2 页 ocr，物理页序保持 |
| blank-page.pdf | 第 2 页故意为空 | 默认 PDF_PAGE_NO_TEXT；启用 OCR 后 OCR_EMPTY，不补造内容 |

`manifest.json` 记录页数、测试词和负例。关键词核对忽略空白，尤其允许 Tesseract 在汉字间添加空格；保留实际 OCR 输出，不擅自删除文字间空格。测试不使用全篇精确匹配，避免把字体、系统或 Tesseract 的空白排版差异当作识别失败。

```bash
uv run resume-cli parse examples/corpus/multi-page.pdf --pages
uv run resume-cli parse examples/corpus/two-column.pdf --layout
uv run --extra ocr resume-cli parse examples/corpus/mixed.pdf --ocr --ocr-lang eng --pages
```

重新生成需要 OCR extra 中的 PDFium、开发依赖 ReportLab 和中文 TrueType 字体：

```bash
uv run --extra ocr python scripts/generate_corpus.py --font /path/to/chinese-font.ttf
```

本机生成后已渲染全部页面，检查中文、列布局、表格及扫描图像。现有文件可跨平台使用，无需重新生成或安装生成时的字体。

这组样例不覆盖手写、低分辨率、严重倾斜、带水印或复杂嵌套表格，不能据此宣称支持所有扫描件。
