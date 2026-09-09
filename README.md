# AI 简历解析 CLI

使用 Python 将本地 PDF 简历转为文本或结构化 JSON，并结合 JD 给出评分与面试问题。**v0.6.0 新增 PDF 页码 / JD 证据定位、可选 OCR、复杂版面样例集及多平台 CI**；保留批量功能和默认单份 JSON。macOS / Linux 容器各 151 项测试通过，覆盖率 96%。详见 [v0.6 迭代说明](docs/ITERATION-0.6.md)、[任务清单](docs/ITERATIONS.md)和[验收记录](docs/VALIDATION.md)。

## 安装与快速演示

要求 Python 3.11+。建议使用 [uv](https://docs.astral.sh/uv/)：

```bash
uv sync --frozen
uv run resume-cli --help
uv run resume-cli parse examples/resume.pdf
uv run resume-cli extract examples/resume.pdf --mock
uv run resume-cli score examples/resume.pdf --jd examples/jd.txt --mock
uv run resume-cli score examples/resume.pdf --jd examples/jd.txt --mock --output result.json
uv run resume-cli score examples/resume.pdf --jd examples/jd.txt --mock --evidence
uv run resume-cli batch extract examples/resume.pdf examples/resume-alt.pdf --mock
uv run resume-cli batch score examples/resume.pdf examples/resume-alt.pdf --jd examples/jd.txt --mock --evidence
```

最后一条命令再次执行会拒绝覆盖 `result.json`；请换一个文件名。JSON 同时输出到 stdout。

也可用标准 Python 环境安装：

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install .
resume-cli --help
```

Windows 激活命令为 `.venv\Scripts\activate`。Windows / Linux 是否经过实际验证见验证记录。

## 技术选型

| 组件 | 用途 |
| --- | --- |
| Python 3.11+ / Typer | 包管理、三个 CLI 命令和帮助 |
| pypdf | PDF 文本与页面读取 |
| pypdfium2 / Pillow / Tesseract（可选） | 无文本页本地 OCR |
| OpenAI Python SDK | Chat Completions API、结构化输出、超时控制 |
| Pydantic v2 | 严格 JSON 字段、类型与评分范围校验 |
| pytest / Ruff | 离线自动测试、代码检查与格式化 |

依赖范围位于 `pyproject.toml`，可复现版本位于 `uv.lock`。ReportLab 只用于开发阶段生成虚构样例，不是运行时依赖。

## 真实 AI 配置

把 `.env.example` 复制成运行目录下的 `.env`，填写自己的 Key 和可用模型：

```dotenv
OPENAI_API_KEY=填写你的密钥
OPENAI_MODEL=填写你的模型ID
# 可选，默认 https://api.openai.com/v1
# OPENAI_BASE_URL=https://你的端点/v1
```

程序只读取当前工作目录的 `.env`；同名 shell 环境变量优先。`parse` 和 `--mock` 不读取模型配置、不访问网络。

```bash
uv run resume-cli extract examples/resume.pdf
uv run resume-cli score examples/resume.pdf --jd examples/jd.txt
```

端点必须支持 `POST /chat/completions` 与 `response_format=json_schema`。不适配仅支持 Responses API 的端点，也不自动切换模型。参考 [OpenAI 结构化输出文档](https://platform.openai.com/docs/guides/structured-outputs)。模型 ID 由配置指定，仓库不假定某个模型已在你的账号开通。

`extract` 与 `score` 各附带 2 条虚构 few-shot 样本，示范缺失值、`null` / `[]`、以及“简历未体现”的写法；当前任务始终在最后一条 user 消息。样本不能替代 Schema 校验，也不能证明真实模型不会幻觉。

每条正常 AI 命令只调用一次；网络错误、429、5xx 最多重试一次，间隔 1 秒。每次请求网络超时设为 30 秒、SDK 自动重试关闭。输出预算 4096 tokens。输入字符限额不是 token 数，需结合模型窗口验证；网络超时也不是整个进程的硬性 61 秒截止时间。

## 命令说明

| 命令 | 输出 | 参数 |
| --- | --- | --- |
| `resume-cli parse <pdf_path>` | 纯文本，或 --pages 的分页 JSON | PDF 路径，可选 --pages |
| `resume-cli extract <pdf_path>` | 简历 JSON | 可选 `--mock`、`--output` |
| `resume-cli score <pdf_path> --jd <jd_path>` | 评分 JSON | 必填 JD，可选 `--mock`、`--output`、`--evidence` |
| `resume-cli batch extract <pdf_paths>...` | 逐文件提取报告 | 可选 `--mock`、`--output` |
| `resume-cli batch score <pdf_paths>... --jd <jd_path>` | 逐文件评分报告 | 必填共用 JD，可选 `--mock`、`--output`、`--evidence` |

根命令和子命令均支持 `--help`，根命令支持 `--version`。也可执行 `python -m resume_cli`。中文和空格路径受支持，空格路径请加引号。

所有单份 / 批量命令均支持 `--ocr`、`--ocr-lang`、`--layout`。启用 OCR 时需安装下面的可选依赖与系统引擎。

成功数据只写 stdout；提示与错误只写 stderr。JSON 可以通过管道传给其他程序：

```bash
uv run resume-cli extract examples/resume.pdf --mock | python3 -m json.tool
```

## 示例输入和输出

`examples/resume.pdf` 与 `examples/resume-alt.pdf` 是虚构简历，均包含中英混排、教育与项目经历；`examples/jd.txt` 是虚构岗位。

提取输出示例：

```json
{
  "name": "陈晨",
  "phone": null,
  "email": "chen@example.com",
  "city": "杭州",
  "education": [
    {"school": "示例大学", "major": "计算机科学", "degree": "本科", "graduation_time": "2024-06"}
  ],
  "skills": ["Python", "React", "PostgreSQL"]
}
```

标量信息缺失为 `null`，列表缺失为 `[]`。所有键必须存在；错误类型、额外字段、非法 JSON 和重复 JSON 键均被拒绝。技能清除空白与完全重复项；不修复猜测性的 JSON 错误。

评分输出包含 `overall_score`、`skill_score`、`experience_score`、`education_score`、`comment` 和 2-3 条 `interview_questions`。完整 mock 输出保存在 `examples/expected-score.json`。

## 评分规则 v1

评分直接读取完整简历文本和 JD，不依赖缺少工作经历字段的提取结果。模型不决定总分：

```text
总分 = 四舍五入（技能分 × 50% + 经验分 × 30% + 教育分 × 20%）
88 / 80 / 70 → 82
```

模型内部返回 JD 三维要求标记，公开 JSON 不包含这些内部字段。JD 完全没有可识别的职责或要求时返回错误；单项未设门槛时按 100 分处理，并在理由中标记“不设门槛”。JD 有要求但简历无证据时不能算作已匹配，理由应写“简历未体现”。所有分数必须为 0-100 的整数，布尔值和数字字符串不算整数。

分数和理由仍受模型判断影响，结构校验不能证明事实准确。首版用于演示与辅助面试准备，不设置自动录用或淘汰门槛。

## 可解释评分（v0.5）

加上 `--evidence` 后，公开 JSON 增加 `skill_evidence`、`experience_evidence`、`education_evidence`、`gaps` 和 `evidence_basis`。每维最多 3 条证据，每条包含 `source: "resume"`、`quote` 和 `relevance`；短引与说明各最多 240 字符。缺口最多 6 条，每条最多 240 字符。

程序会对引文与当前简历做本地比对：仅忽略空白，保留标点、大小写和其他字符；引文必须是原文的连续子串。无法匹配时返回 `AI_EVIDENCE_INVALID`（退出 5），不输出或保存结果。无证据时可返回空数组；未设门槛的维度必须返回空证据数组。

比对通过只说明引文出现在文本中，不保证模型对上下文、否定句、JD 相关性或缺口的判断正确，也不构成简历真实性核验。v0.6 增加的 PDF 页码和 JD 定位规则见下文。

真实请求的 `evidence_basis` 为 `input_resume`；mock 为 `mock_fixture`，引文核对的是包内固定虚构文本与 JD，不能作为当前 PDF 的证据。完整 mock 示例见 `examples/expected-score-evidence.json`。只有显式 `--evidence` 才切换到包含证据的新 Schema 和 few-shot；默认评分请求沿用 v0.4。

### PDF 页码与 JD 定位（v0.6）

详细输出使用 `evidence_schema_version: "2"`。每条证据增加 `jd_quote`、`resume_locations` 和 `jd_location`；缺口通过新增的 `gap_evidence` 对应原有 `gaps` 字符串列表。模型仅返回原文短引，页码和位置由本地程序计算；伪造 JD 引文返回 `AI_JD_EVIDENCE_INVALID`（退出 5）。

位置字段的含义：

- `page`：1 起始的 PDF 物理页码，直接传入纯文本的 Python API 无法验证页码时为 null。
- `method`：pdf_text、pdf_layout、ocr 或 text。
- `line_start / line_end`：1 起始，按本次提取的页内文本或读取的 JD 文本计算。
- `start_char / end_char`：0 起始的 Unicode 字符区间，右端不包含；不是字节偏移或 PDF 坐标。
- 同一短引返回每个匹配页的首次位置；JD 重复短引只返回首次位置；不允许跨页拼接引用。

JD 读取保留前导 / 尾部空白行，移除 BOM 并统一 CRLF，以保证行号可追溯。mock 的页码对应固定虚构页，不是输入 PDF 的页码。OCR 页定位到识别文本，可能包含识别错误或插入空格。

```bash
uv run resume-cli parse examples/corpus/multi-page.pdf --pages
uv run resume-cli score examples/resume.pdf --jd examples/jd.txt --mock --evidence
```

## OCR 与复杂版面（v0.6）

安装 Python 可选依赖：

```bash
uv sync --frozen --extra ocr
# 或在标准虚拟环境中：python -m pip install '.[ocr]'
```

系统需安装 Tesseract 并确保命令在 PATH：macOS 可用 `brew install tesseract`；Ubuntu 可用 `sudo apt-get install tesseract-ocr`；Windows 可用 `choco install tesseract --yes`，必要时将 `C:\Program Files\Tesseract-OCR` 加入 PATH。

语言包可用系统包管理器安装，或使用附带脚本下载固定版本并验证 SHA-256：

```bash
uv run python scripts/install_ocr_languages.py --directory .tessdata
export TESSDATA_PREFIX="$PWD/.tessdata"
uv run --extra ocr resume-cli parse examples/corpus/scan-zh.pdf --ocr --pages
uv run --extra ocr resume-cli parse examples/corpus/mixed.pdf --ocr --ocr-lang eng --pages
uv run resume-cli parse examples/corpus/two-column.pdf --layout
```

Windows PowerShell 设置为 `$env:TESSDATA_PREFIX = (Resolve-Path .tessdata).Path`。默认语言 eng+chi_sim，也可 `--ocr-lang eng`。下载脚本不会覆盖内容不同的既有语言文件；.tessdata 已被 Git 忽略。

OCR 仅作用于无文本页，使用本地 PDFium 以 200 DPI 渲染，再执行 Tesseract；单页最多 1200 万像素，Tesseract 每页最多 30 秒。成功和失败都会清理临时图像，不上传 OCR 图像到云服务。原有文本页跳过 OCR，文字页中嵌入的图片文字暂不识别；空白页仍明确失败。

`--layout` 使用 pypdf 的布局提取模式，保留更多水平位置，但不保证恢复双栏阅读语义、旋转内容或表格结构。样例集位于 [examples/corpus](examples/corpus/README.md)，共 7 份虚构 PDF、11 页；不代表低清、手写或任意复杂扫描件均可准确识别。

## 批量处理（v0.5）

显式传入多份 PDF，按顺序逐份执行。路径解析后去重并保留首次出现的顺序，最多 20 份不同文件；不自动扫描目录、不递归、不并发、不排序候选人。批量评分只读取一次共用 JD。

```bash
uv run resume-cli batch score examples/resume.pdf examples/resume-alt.pdf --jd examples/jd.txt --mock --evidence --output batch-result.json
```

报告包含 `operation`、`mode`、`total`、`succeeded`、`failed` 和 `results`。成功项为 `file / status: success / result`，失败项为 `file / status: error / error`，其中 error 含错误码、提示和该文件的退出码。报告不会保存简历全文；选择证据模式会包含选出的简历引文。

单份失败后继续处理后续文件。**只要有文件失败，仍输出完整 JSON 报告并退出 7**；所有文件成功时退出 0。全局参数、JD、配置或输出路径错误在批处理前失败；全局失败和保存失败时 stdout 为空。进度和 mock 标记只写 stderr。指定 `--output` 会保存与 stdout 完全相同的汇总 JSON，并拒绝覆盖既有文件。

每份正常文件调用一次 AI，临时错误最多一次重试；20 份输入最多 40 次请求。认证、配额等请求错误逐文件记录，首版不会自动暂停整个批次。中断进程不会写出部分报告，也没有断点续跑。执行时请显式列出准备处理的文件。

## mock 的边界

`--mock` 返回包内固定的虚构数据，与当前输入内容无关；依然校验 PDF 和 JD 文件。stderr 会明确标记 MOCK，评分理由也包含 MOCK。批量报告另有 `mode: mock`，证据评分另有 `evidence_basis: mock_fixture`。单份提取 JSON 为保留原题字段没有额外模式标记，保存的提取文件必须结合调用命令识别。

mock 可以验证安装、文件读取、Schema 和输出，不能证明模型提取正确、评分合理或能抵御提示注入。真实 AI 请求失败时不会自动回退到 mock。

## PDF 与文件限制

- 默认读取文本型 PDF，--ocr 可处理无文本扫描页；`.pdf` / `.PDF` 后缀和 `%PDF-` 文件头均需正确。
- PDF 最大 10 MiB、20 页，提取文本最大 20,000 字符；超限拒绝，不截断。
- 任一页既无文本也未成功 OCR 时失败并提示页码；空白页需先移除。
- 拒绝加密、损坏文件；文字页内的图片文字不自动 OCR。
- 双栏、表格、特殊编码不保证语义顺序；建议先检查 `parse` 输出。
- JD 仅支持 UTF-8 / UTF-8 BOM `.txt`，最大 8,000 字符。
- `--output` 父目录必须存在且可写，目标必须不存在。临时文件写入完成后以硬链接排他提交；不支持硬链接的文件系统会返回错误，不采用可能覆盖目标的回退方案。

## 错误码

| 退出码 | 含义 |
| --- | --- |
| 0 | 成功或帮助 |
| 2 | 参数、配置、文件输入、JD 无有效要求 |
| 3 | PDF 无法解析、加密、无页面或页无文本 |
| 4 | AI 网络、认证、拒答或请求失败 |
| 5 | AI JSON、字段、类型、分数、截断等响应错误 |
| 6 | 结果路径或保存失败 |
| 7 | 批处理中有文件失败；stdout 仍有完整 JSON 报告 |

错误示例：`ERROR [PDF_PAGE_NO_TEXT] 第 2 页未提取到文本…`。错误不输出半成品 JSON，不默认展示堆栈，也不回显模型响应或 Key。

OCR 引擎 / 依赖 / 语言包缺失、识别失败、超时或空结果均使用退出码 3；无效 OCR 语言代码使用退出码 2。证据或 JD 引文校验失败使用退出码 5。

## 项目结构

```text
src/resume_cli/
  cli.py          # 命令入口、输出与错误
  files.py        # PDF / JD 读取与文件保存
  documents.py    # 页文本、物理页码与原文位置
  ocr.py          # 可选 PDFium + Tesseract 本地识别
  config.py       # 环境变量与 .env
  ai.py           # API 请求、受控重试、mock
  batch.py        # 顺序批处理、逐项结果、失败汇总
  prompts.py      # 提示词版本与文档数据边界
  schemas.py      # JSON 规则与本地总分
  fixtures/       # 随 wheel 分发的固定 mock 数据
tests/            # 离线文件、Schema、HTTP、CLI 测试
examples/         # 虚构 PDF / JD 与期望输出
scripts/          # 样例生成、真实 API 冒烟、wheel / 二进制构建与校验
docs/             # 迭代任务、验证记录与演示指南
output/pdf/       # 原需求文档快照
```

## 开发与验证

```bash
uv sync --frozen --group dev
uv run pytest --cov=resume_cli
uv run ruff check .
uv run ruff format --check .
uv build
```

### 独立可执行文件

用 PyInstaller 为**当前操作系统和 CPU**打出命令行程序，不需要目标机器安装 Python。不交叉编译。默认是目录分发（`--onedir`）：启动时立即在 stderr 打印 `resume-cli 启动中…`，不先解压整个包。单文件（`--onefile`）每次启动都要解压，会明显变慢，只在需要拷贝单个文件时使用。

```bash
uv sync --frozen --group dev --group binary
uv run python scripts/build_binary.py
uv run python scripts/verify_binary.py
./dist/binary/resume-cli/resume-cli --version
./dist/binary/resume-cli/resume-cli parse examples/resume.pdf
./dist/binary/resume-cli/resume-cli extract examples/resume.pdf --mock
```

也可执行 `scripts/build_binary.sh`。Windows 产物为 `dist/binary/resume-cli/resume-cli.exe`。整个 `dist/binary/resume-cli/` 目录需要一起分发。`dist/` 已忽略，不要把二进制提交进仓库。

默认不打入 OCR extra。若需要把 pypdfium2 / Pillow 打进包，加 `--ocr`；系统仍须自行安装 Tesseract，二进制不会内嵌 OCR 引擎。该产物不能代替 wheel 安装，也不能证明其他 OS 的二进制可用。

### CI 与多平台验证

[GitHub Actions 工作流](.github/workflows/ci.yml)包含：Windows / Ubuntu / macOS × Python 3.11 / 3.12 / 3.13 的 9 个核心作业、3 个 OS 的真实 OCR 作业，以及工作流语法检查。核心作业不安装 OCR extra；OCR 作业使用固定语言数据并要求 OCR 测试实际执行。全过程不需要 AI Key。

推送符合 `vX.Y.Z` 的 Git tag 会触发 [Release 工作流](.github/workflows/release.yml)。tag 必须与 `pyproject.toml` 和 `src/resume_cli/__init__.py` 的版本一致，例如当前代码是 `0.6.0` 时使用 `v0.6.0`。工作流会：

1. 构建并校验 `ai_resume_cli-<version>-py3-none-any.whl` 与 sdist。
2. 在 Ubuntu / macOS / Windows runner 上用 PyInstaller 打当前架构的目录分发二进制，再打成 `resume-cli-<version>-<os>-<arch>.tar.gz` 或 `.zip`。
3. 用虚构样例校验二进制后，把 Python 包、三个平台压缩包和 `SHA256SUMS` 上传到同名 GitHub Release。

独立二进制仍不交叉编译、不含 OCR extra、不内嵌 Tesseract。GitHub-hosted `macos-latest` 当前是 arm64，`ubuntu-latest` / `windows-latest` 当前是 x86_64；不要把某一 runner 的产物写成其他 CPU 已验证。手动运行该工作流只构建并上传 Actions artifact，不会创建 GitHub Release。尚未推送远程仓库时，不要把本机结果写成 GitHub Release 已发布。

```bash
git tag v0.6.0
git push origin v0.6.0
```

核心作业还会构建 wheel，在项目外的全新环境安装并运行命令。可本地复现：

```bash
uv run python scripts/verify_wheel.py dist/ai_resume_cli-0.6.0-py3-none-any.whl
uv run --extra ocr pytest -m ocr
```

已实测 macOS Python 3.11、3.13 和 Linux 容器 Python 3.11。Windows、Python 3.12 及 GitHub 远程矩阵尚未执行；当前无 Git 远程地址，推送后才会触发 CI。详见 [验证记录](docs/VALIDATION.md)。

重新生成样例：`uv run python scripts/generate_examples.py`。生成脚本需要中文 TrueType 字体，可用 `--font /path/to/font.ttf` 指定；已提交的 PDF 嵌入字体，运行 CLI 不需要安装该字体。配置真实 API 后运行 `uv run python scripts/smoke_ai.py`，对两份虚构简历执行提取与评分；加 `--evidence` 验证新增评分证据。它会使用真实 API（产生调用费用），打印结果供人工核对，不自动写结果文件。

## 隐私与已知问题

真实模式会把简历文本和 JD 发送至配置的模型端点，使用 `store=False`；这不能代表供应商没有其他日志或数据保留。默认不保存正文、提示词和原始响应。仅在指定 `--output` 时落盘。`.env`、`private/` 和 `results/` 已忽略，提交任意其他输出路径前仍需检查内容。

已实现功能、测试结果和验证范围以[验证记录](docs/VALIDATION.md)为准。OCR 为无文本页的基础识别；并发、缓存、多供应商适配和 Web UI 未实现。复杂版面、识别错误和证据的语义相关性仍可能影响结果。当前真实模型端点仍出现 HTTP 400，新定位模式的线上响应尚未通过验收。MVP 既有验收与演示材料已获用户确认；本轮没有执行发布。
