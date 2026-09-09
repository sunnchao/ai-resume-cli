# AGENTS.md

给在本仓库工作的编码代理使用。人类文档入口仍是 [README.md](README.md)。验收状态以 [docs/VALIDATION.md](docs/VALIDATION.md) 为准，任务边界以 [docs/ITERATIONS.md](docs/ITERATIONS.md) 为准。

当前版本：**0.6.0**。提示词版本：`1.3`。详细证据结构版本：`2`。

## 项目是什么

`ai-resume-cli` 是一个本地 Python CLI：读取 PDF 简历，提取结构化 JSON，并按 JD 给出技能 / 经验 / 教育评分。默认输出单份 JSON；批量、OCR、布局提取和评分证据都是显式开关，不能 silently 改变默认契约。

不要把它做成 Web UI、多供应商自动适配器、目录扫描器或自动录用系统。

## 开始前先读

按任务选读，不要整库重写文档：

| 文件 | 何时读 |
| --- | --- |
| `README.md` | 命令、限制、错误码、隐私边界 |
| `docs/ITERATIONS.md` | 已完成 / 未完成任务，实施决策 |
| `docs/ITERATION-0.6.md` | v0.6 契约（页码、OCR、CI） |
| `docs/VALIDATION.md` | 已实测什么、明确未验证什么 |
| `CHANGELOG.md` | 对外可见行为变更 |
| `pyproject.toml` / `uv.lock` | 依赖与工具版本 |

需求原文快照在 `output/pdf/`。不要把快照里的旧接口描述当成当前实现。

## 环境与命令

Python 3.11+。包管理用 [uv](https://docs.astral.sh/uv/)。不要引入 pipenv / poetry / conda。

```bash
uv sync --frozen --group dev
uv run resume-cli --help
uv run pytest --cov=resume_cli
uv run ruff check .
uv run ruff format --check .
```

带 OCR extra（测试标记 `ocr` 需要系统 Tesseract 与 `eng` / `chi_sim`）：

```bash
uv sync --frozen --group dev --extra ocr
uv run --extra ocr pytest --cov=resume_cli
uv run --extra ocr pytest -m ocr
```

构建与独立安装验证：

```bash
uv build
uv run python scripts/verify_wheel.py dist/ai_resume_cli-0.6.0-py3-none-any.whl
```

当前平台独立二进制（不交叉编译；产物在 `dist/binary/`，已 gitignore）：

```bash
uv sync --frozen --group dev --group binary
uv run python scripts/build_binary.py
uv run python scripts/verify_binary.py
```

默认目录分发（启动快），不含 OCR extra。`--onefile` 会每次解压、启动变慢。`--ocr` 只打包 Python OCR 依赖，不内嵌 Tesseract。不要把二进制提交进仓库，也不要把本机产物写成其他 OS 已验证。GitHub Release 只由 `vX.Y.Z` tag 触发；tag 必须与包装版本一致。未实际跑过远程工作流时，不要把 VALIDATION.md 写成 Release 已发布。

核心作业排除 OCR：`uv run pytest -m "not ocr"`。CI 的 OCR 作业设置 `RESUME_REQUIRE_OCR=1`，缺引擎或语言包必须失败，不能靠 skip 伪装通过。

真实模型冒烟（产生费用，不写结果文件）：

```bash
uv run python scripts/smoke_ai.py
uv run python scripts/smoke_ai.py --evidence
```

无 Key 时预期 `CONFIG_MISSING`（退出码 2）。不要为了“跑通”去提交 `.env` 或真实简历。

## 目录与职责

```text
src/resume_cli/
  cli.py          # Typer 入口；成功 JSON 只写 stdout，诊断只写 stderr
  files.py        # PDF / JD 读取、限额、原子保存
  documents.py    # 页文本、物理页码、行号与字符区间
  ocr.py          # 可选本地 PDFium + Tesseract；仅无文本页
  config.py       # 只读 cwd/.env 与同名环境变量
  ai.py           # Chat Completions、一次瞬时重试、mock
  batch.py        # 显式路径、顺序、去重、失败隔离
  prompts.py      # 提示词、数据边界、few-shot
  schemas.py      # 严格 JSON、本地总分、证据校验
  fixtures/       # 随 wheel 分发的固定 mock
tests/            # 离线测试；默认禁止真实网络
examples/         # 虚构简历 / JD / 期望 JSON / corpus
scripts/          # 样例生成、OCR 语言、冒烟、wheel / 二进制 / tag 发布打包与校验
docs/             # 迭代、验收、演示
.github/workflows/ci.yml
.github/workflows/release.yml  # 推送 vX.Y.Z tag 后构建并上传 GitHub Release
```

改行为时同步最近的模块、测试和 README / CHANGELOG / ITERATIONS。不要只改代码或只改文档。

## 不可破坏的契约

1. **默认兼容。** 无 `--evidence` 的 `score` 公开 JSON 不得新增必填字段。无 `--ocr` / `--layout` 时保持原文本提取路径。
2. **Chat Completions。** 真实请求走 `POST /chat/completions` + `response_format=json_schema`（`strict: true`）。不要改回 Responses API，也不要在失败时自动改用 mock 或其他端点。
3. **数据边界。** 简历和 JD 只出现在最后一条 `user` 消息。few-shot 是虚构样本，禁止把样本姓名、分数、经历套到当前文档。提示词改动后核对 `PROMPT_VERSION`。
4. **本地算分。** 总分 = 四舍五入（技能 50% + 经验 30% + 教育 20%），在 `schemas.finalize_score` 计算。模型不得输出 `overall_score`。JD 无任何可识别要求时失败，不给出分数。
5. **stdout / stderr。** 成功数据只在 stdout；MOCK 标记、进度、错误只在 stderr。错误不输出半成品 JSON，不回显 Key、原文或模型原始响应。
6. **保存。** `--output` 拒绝覆盖已有目标。同目录临时文件 + 硬链接提交；不支持硬链接则明确失败，不要改成“先删再写”。
7. **mock。** `--mock` 返回包内 fixture，与当前 PDF 内容无关。证据模式下 `evidence_basis` 必须是 `mock_fixture`，引文核对的是 fixture 文本，不是输入 PDF。
8. **证据。** `--evidence` 才切换证据 Schema。公开引文必须是原文连续子串（仅忽略空白）。伪造简历引文 → `AI_EVIDENCE_INVALID`；伪造 JD 引文 → `AI_JD_EVIDENCE_INVALID`；均为退出码 5。页码 / 行号 / 字符区间由本地计算，不要让模型编造位置。纯文本 Python API 无法验证页码时 `page` 为 `null`。
9. **批量。** 只接受显式路径，去重保序，最多 20 份，不递归目录、不并发。单份失败继续；有失败则完整 JSON 报告 + 退出码 7。全局参数 / JD / 配置 / 输出路径错误时 stdout 为空。
10. **OCR。** 默认关闭。只处理无文本页；文字页中的图片不自动 OCR。空白页仍失败。临时图像必须清理，OCR 图像不得上传到模型或云服务。
11. **配置。** 只读当前工作目录 `.env`，不向上寻找父目录。`OPENAI_BASE_URL` 必须是无用户名密码、无 query/fragment 的 HTTP(S) URL。
12. **限额。** PDF ≤ 10 MiB、≤ 20 页、提取文本 ≤ 20,000 字符；JD ≤ 8,000 字符。超限拒绝，不截断后继续。

## 编码约定

- 语言：Python 3.11+，包布局 `src/resume_cli`。
- 格式与检查：Ruff，`line-length = 100`，规则 `E,F,I,UP,B`。提交前 `ruff check` 与 `ruff format --check` 必须通过。
- 公开模型用 Pydantic v2 `strict=True, extra="forbid"`。缺失标量为 `null`，缺失列表为 `[]`；拒绝重复 JSON 键和非标准常量。
- 用户可见失败用 `ResumeError(code, message, exit_code)`。消息用中文，短、可操作，且不包含私密输入。
- 保持模块薄：CLI 不解析 PDF；`ai.py` 不读文件系统；OCR 失败不得 silently 退回空文本。
- 依赖加在 `pyproject.toml` 并用 `uv lock` 更新 `uv.lock`。ReportLab 只属于 dev group，不要变成运行时依赖。OCR 可选依赖放在 `[project.optional-dependencies] ocr`。
- 测试默认离线。`tests/conftest.py` 禁止 `socket.connect`。需要 HTTP 时用 `httpx.MockTransport` 包住真实 OpenAI SDK，不要 mock 掉整个 SDK 调用形状。
- 新增 CLI 标志必须有帮助文本、测试，以及 README 命令表更新。

## 测试时注意

- 工作目录会被切到临时目录，并清掉 `OPENAI_*`。需要真实配置的测试自行 `monkeypatch.setenv`。
- 用 `examples/` 与 `examples/corpus/` 的虚构文件，或测试里用 `make_pdf` 生成。不要把真实简历放进仓库。
- 改 Schema / prompt / AI 请求体时，更新 `tests/test_ai.py`、`tests/test_prompts.py`、`tests/test_schemas.py` 中对应断言。
- 改文件限额、OCR 或页码逻辑时覆盖 `tests/test_files.py`、`tests/test_documents.py`、`tests/test_ocr.py`。
- 改批量退出码或报告字段时覆盖 `tests/test_batch.py` 与 CLI 测试。
- 文档里的测试数量、覆盖率、Python 版本必须来自实际命令输出。不要把本机 macOS 结果写成 “GitHub CI 已通过”。Windows 与远程矩阵目前未跑，保持“未验证”。

## 隐私与安全

- 真实模式会把简历文本和 JD 发到配置的模型端点，`store=False`。这不能证明供应商无日志。
- 永远不要提交 `.env`、真实 API Key、真实简历、OCR 语言数据目录 `.tessdata/`、或 `private/` `results/` `tmp/` 下的输出。
- 演示和测试只用 `examples/` 虚构数据。
- 错误路径不得打印请求体、响应原文或 Key。
- 不要添加把本地文件上传到第三方 OCR / 存储的功能。

## 明确不要做的事

- 不要把默认 `score` 改成始终输出证据。
- 不要把 `batch` 改成扫描目录、按分数排序或并行打分。
- 不要在 AI 失败时自动 `--mock`。
- 不要为了兼容去同时打 `/responses` 和 `/chat/completions`。
- 不要放宽硬链接保存策略，或允许覆盖已有 `--output`。
- 不要把 OCR 做成默认行为，或把扫描页失败改成跳过。
- 不要在未实际运行的情况下把 VALIDATION.md 标成 Windows / 远程 CI / 真实模型已通过。当前已知真实端点仍可能 HTTP 400。
- 不要把自定义评分权重、断点续跑、并发、Web UI 塞进当前迭代；那些是 v0.7+ 候选。

## 改完如何验收

最小集：

```bash
uv run pytest --cov=resume_cli
uv run ruff check .
uv run ruff format --check .
```

行为变更再补：相关 CLI 手工命令（优先 `--mock`）、必要时 `uv build` + `scripts/verify_wheel.py`。涉及 OCR 时在已安装 Tesseract 的环境跑 `pytest -m ocr`。涉及 prompt / 证据时不要用 mock 结果宣称真实模型质量。

更新 README / CHANGELOG / ITERATIONS / VALIDATION 中与本次改动冲突的句子。版本号以 `pyproject.toml` 与 `src/resume_cli/__init__.py` 为准，需要 bump 时两处一起改。
