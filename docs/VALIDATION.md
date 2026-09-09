# v0.6.0 验证记录

日期：2026-09-09。代码版本 0.6.0，提示词 1.3，证据结构版本 2。历史记录见 [v0.5 验证](VALIDATION-0.5.md)。用户已确认的 MVP 验收继续保留。

## 实际执行结果

| 环境 / 检查 | 实际结果 |
| --- | --- |
| macOS 15.7.4 / arm64 / Python 3.11.14 | 151 passed，覆盖率 96%，包含真实 OCR；Ruff 通过 |
| macOS / Python 3.13.9 | 147 passed，4 个 OCR 用例按核心模式排除 |
| Linux 容器 / aarch64 / Python 3.11.16 | 151 passed，覆盖率 96%，包含真实 OCR；Ruff 通过 |
| Linux wheel 独立安装 | 版本、parse、parse --pages、extract、带定位的 score、批量和退出码 7 通过 |
| macOS wheel 独立安装 | 使用 uv 创建独立环境后，版本、分页、提取、定位、批量与退出码 7 全部通过 |
| 工作流语法 | actionlint 1.7.12 通过，包含 GitHub 上下文与 shell 检查 |
| 样例视觉检查 | 7 份 PDF 共 11 页已渲染检查；空白负例为故意空白 |
| GitHub Windows / Linux / macOS 矩阵 | 尚未触发：本地仓库无远程地址，不把本机结果当作远程结果 |
| GitHub Release / 版本 tag 构建 | 已配置 `.github/workflows/release.yml`。本地 `actionlint` 1.7.12 通过；`tests/test_release_meta.py` 覆盖 tag 必须为 `vX.Y.Z`、与包装版本一致、平台压缩包命名和 SHA256SUMS。核心作业 `pytest -m "not ocr"` 154 passed。尚未推送远程 tag，不记录 GitHub Release 已成功 |
| macOS arm64 独立二进制 | 默认改为目录分发 `dist/binary/resume-cli/resume-cli`，启动立即在 stderr 提示；`verify_binary.py` 覆盖 --version / parse / extract --mock / score --evidence --mock / batch。Linux / Windows 二进制未构建 |

Linux 实测使用 Docker 官方 `python:3.11-slim` 镜像（此次解析 digest：`sha256:9534e5a8e315485d4061ed659af0fd78a284c015f9b73661b41d6bab25604534`），仅挂载构建后的源码包与固定 OCR 语言数据，没有挂载 .env 或其他简历。

## 测试范围

- 原有文件、配置、AI、JSON、评分、批量与失败隔离回归测试。
- PDF 物理页码、重复引文、多页匹配、跨页拒绝、纯文本页码 null。
- JD BOM / CRLF / 前导空白行、字符偏移、伪造 JD 引文、缺口引用数量对应。
- 文本页不调用 OCR，混合 PDF 仅识别无文本页，OCR 后字符限额仍有效。
- OCR 依赖 / 语言缺失、超时、空结果、子进程失败、编码错误、超大页面拒绝、临时图像清理。
- 英文扫描、中文扫描、混合 PDF 和空白负例均实际执行 Tesseract；并非返回固定 mock 文本。
- 双栏与表格验收检查关键词保留，不宣称语义结构完整还原。

中文识别可能插入字间空格。因此样例的关键词和引文匹配忽略空白，程序保留原始 OCR 文本。最初的精确子串测试将这类空格差异视为失败，已改为符合产品匹配规则的检查，并在 macOS / Linux 上通过。

## 可复现命令

```bash
uv sync --frozen --group dev --extra ocr
uv run --extra ocr ruff check .
uv run --extra ocr ruff format --check .
uv run --extra ocr pytest --cov=resume_cli
actionlint .github/workflows/ci.yml .github/workflows/release.yml
uv build
uv run python scripts/verify_wheel.py dist/ai_resume_cli-0.6.0-py3-none-any.whl
```

完整 OCR 验证前需安装 Tesseract 与 eng / chi_sim。CI 设置 `RESUME_REQUIRE_OCR=1`，若依赖或语言缺失即失败，不能通过跳过测试来伪装 OCR 成功。核心作业用 `pytest -m "not ocr"` 验证无 OCR 依赖时的基本安装。

macOS 的 uv 托管解释器在 `venv.EnvBuilder(with_pip=True)` 启动 ensurepip 时曾异常退出；独立安装验证脚本已改用 uv venv / uv pip install。这项修改只影响安装验证脚本，不影响 CLI 运行。

## 真实模型与外部 CI 的边界

对虚构的 examples/corpus/multi-page.pdf 与示例 JD 进行了新增定位模式真实请求，端点仍返回 HTTP 400。该接口问题延续自 v0.5，不能据此宣称新的详细模型输出已通过线上验收。页码、JD 引文存在性和位置由本地代码验证；模拟 HTTP 与固定 few-shot 已覆盖字段契约。

Windows 尚无本轮实机或远程运行结果；Python 3.12 矩阵配置完成但未在本机执行。推送到用户 GitHub 仓库后，CI 才会触发真实远程矩阵。无实际运行链接时不记录“CI 已绿”。
