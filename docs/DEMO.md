# 演示与正式提交指南

用户已确认 v0.4 演示材料完成。本文件保留录屏流程供复用，并补充 v0.5 新命令；公开发布地址尚未登记。以下只使用明确列出的虚构简历。

## 建议演示顺序

1. 说明项目目标：PDF 文本读取、AI 信息提取、JD 匹配评分。
2. 展示 Python 版本与安装，打开 README 的配置说明；不要显示实际 Key。
3. 演示三个命令，以及 JSON 可直接用于管道或保存。
4. 演示缺少文件的错误提示和一次显式 mock。
5. 介绍 `cli.py / files.py / ai.py / schemas.py / prompts.py` 的职责。
6. 展示自动测试结果，并说明 OCR、真实评分不确定性等限制。

## 无 Key 可执行的录屏命令

从项目根目录执行：

```bash
uv sync --frozen
uv run python --version
uv run resume-cli --version
uv run resume-cli --help

uv run resume-cli parse examples/resume.pdf
uv run resume-cli extract examples/resume.pdf --mock
uv run resume-cli score examples/resume.pdf --jd examples/jd.txt --mock

uv run resume-cli extract examples/resume.pdf --mock --output demo-extract.json
uv run resume-cli score examples/resume.pdf --jd examples/jd.txt --mock --output demo-score.json
uv run resume-cli parse missing.pdf

uv run pytest -q
```

`missing.pdf` 命令预期失败，退出码为 2。两个 `demo-*.json` 的文件名应使用尚不存在的路径；再次演示时改名。只在样例路径运行这些命令，避免将真实输出提交仓库。

## 真实 AI 演示

先配置运行目录下的 `.env`，然后执行：

```bash
uv run resume-cli extract examples/resume.pdf
uv run resume-cli score examples/resume.pdf --jd examples/jd.txt
uv run python scripts/smoke_ai.py
```

`--mock` 的固定结果不代表真实模型结果，视频中必须说明模式；如果真实调用失败，应展示清晰错误并明确说明改用 mock，不能暗中替换。

## 提交清单

- [x] MVP 真实模型验收完成（用户确认）。
- [x] MVP 文档一致性与演示材料完成（用户确认）。
- [ ] 检查待提交文件，不包含实际 Key、个人简历和敏感输出。
- [ ] 创建公开 GitHub 仓库并填写实际仓库地址。
- [ ] 登记已有演示材料的实际视频链接。
- [ ] 填写提交者真实姓名和联系方式。

如最终采用其他模型、权重或输入限额，先同步 README、任务文档与测试，再录制最终演示。

## v0.5 新增功能演示

```bash
uv run resume-cli score examples/resume.pdf --jd examples/jd.txt --mock --evidence
uv run resume-cli batch extract examples/resume.pdf examples/resume-alt.pdf --mock
uv run resume-cli batch score examples/resume.pdf examples/resume-alt.pdf --jd examples/jd.txt --mock --evidence
uv run resume-cli batch extract examples/resume.pdf missing.pdf examples/resume-alt.pdf --mock
```

最后一条预期退出 7，JSON 仍包含两份成功结果和一份失败记录；进度在 stderr。
证据演示注意 `evidence_basis=mock_fixture`，不能把固定 mock 引文当作当前文件的核验结果。
真实证据验证可执行 `uv run python scripts/smoke_ai.py --evidence`。

## v0.6 定位、OCR 与样例演示

```bash
uv run resume-cli parse examples/corpus/multi-page.pdf --pages
uv run resume-cli score examples/resume.pdf --jd examples/jd.txt --mock --evidence
uv run resume-cli parse examples/corpus/two-column.pdf --layout
uv run --extra ocr resume-cli parse examples/corpus/scan-zh.pdf --ocr --pages
uv run --extra ocr resume-cli parse examples/corpus/mixed.pdf --ocr --ocr-lang eng --pages
```

先按 README 安装 Tesseract 与所选语言。展示 `resume_locations.page`、JD 的 `line_start` 和 `gap_evidence`，并明确 mock 页码来自固定虚构页。混合 PDF 的 pages 输出应显示第 1 页 pdf_text、第 2 页 ocr。工作流配置可展示，但 Windows 及 GitHub 远程结果须等实际运行后再展示。
