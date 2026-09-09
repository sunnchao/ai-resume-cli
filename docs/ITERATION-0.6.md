# v0.6.0：证据定位、OCR 与多平台 CI

日期：2026-09-09。Python 3.11+，提示词版本 1.3，详细证据输出版本 2。

## 本轮任务与状态

| ID | 任务 | 完成依据 | 状态 |
| --- | --- | --- | --- |
| T23 | PDF 页码和原文位置 | 每页保留物理页码、文本、提取方法；引文位置在本地计算 | 已完成 |
| T24 | JD 证据与缺口定位 | 匹配 JD 原文短引；返回行号 / 字符范围；缺口逐项对应 JD 引文 | 已完成 |
| T25 | 可选 OCR 与 layout | PDFium + Tesseract；无文本页识别；plain / layout 文本解析 | 已完成 |
| T26 | 复杂版面样例集 | 7 份虚构 PDF，覆盖多页、双栏、表格、扫描、混合与空白页 | 已完成 |
| T27 | 多平台 CI 配置 | 三种 OS × 三个 Python 版本的核心测试；三种 OS 的 OCR 作业；actionlint | 已完成配置与语法校验 |
| T28 | 多平台实测 | macOS Python 3.11 全量 / 3.13 核心；Linux Python 3.11 容器全量 | 已完成本机与容器验证 |
| T29 | GitHub 远程矩阵运行 | 需要将仓库推送到已配置 GitHub 远程 | 未运行：本地没有 Git 远程地址 |
| T30 | 版本 tag 发布构建 | 推送 `vX.Y.Z` 构建 Python 包与 Linux / macOS 本机二进制并上传 GitHub Release | 已完成：`v0.6.0` Release 已发布 |

## 证据定位契约

`score --evidence` 的每条证据增加：

- `jd_quote`：模型给出的 JD 原文连续短引，必须经过本地匹配。
- `resume_locations`：每个匹配页的首次出现位置，含 `page`、`method`、`line_start`、`line_end`、`start_char`、`end_char`。
- `jd_location`：JD 中首次出现的位置，含行号和字符范围。
- 输出根增加 `gap_evidence`，通过 0 起始 `gap_index` 对应已有 `gaps` 字符串列表；每项包含已校验的 JD 短引和位置。
- `evidence_schema_version: "2"` 标识详细输出版本；默认 score JSON 仍兼容。

PDF 页码从 1 开始，指文件中的物理页，不是印刷页码。页内行号基于本次提取文本，JD 行号基于 UTF-8 解码、移除 BOM、统一 CRLF 后保留空白行的文本。字符范围是 Unicode 字符索引，0 起始、右端不包含，不是文件字节偏移或 PDF 坐标框。

匹配只忽略空白，其他字符必须一致；引文不能跨页拼接。重复短引返回各匹配页的首次位置，JD 重复短引只返回首次位置。直接调用 Python API 仅提供字符串时，无法验证物理页码，因此 `page=null`；CLI 会传入真实页结构。

mock 使用固定的两页虚构文本和固定 JD，`evidence_basis=mock_fixture`。其页码不是用户传入文件的页码。引用存在性不代表语义相关性或简历真实性；OCR 引文定位到识别文本，而非图片中的真实字形。

## OCR 与布局范围

所有单份和批量命令均接受 `--ocr`、`--ocr-lang`、`--layout`。默认仍只读取文本层；`--ocr` 对无文本页启用本地识别，默认语言 `eng+chi_sim`。不会上传页面图像到 OCR 云服务。

OCR 使用可选依赖 pypdfium2 / Pillow 与系统 Tesseract：200 DPI 渲染，单页最多 1200 万像素，Tesseract 每页最多 30 秒。临时图像在成功与失败时均清理；识别文本仍受简历总字符限制。空白页识别为空时错误退出。渲染与 PDF 解析不受 Tesseract 的 30 秒计时覆盖。

`--layout` 使用 pypdf 的布局模式，改善双栏和表格的文本排列，但不重建语义表格，也不保证复杂版面的阅读顺序。`parse --pages` 可检查每页实际文字和方法。

## 验证情况

macOS 与 Linux 容器各 151 项测试通过，覆盖率 96%，包括 4 项真实 OCR 场景；macOS Python 3.13 的 147 项核心测试通过。GitHub 工作流通过 actionlint，Windows 和远程矩阵运行尚未发生。详情见 [VALIDATION.md](VALIDATION.md)。

新增定位的真实模型请求仍收到现有端点的 HTTP 400；本轮通过本地规则、mock 与模拟 HTTP 验证定位功能，不宣称新模型响应已通过线上验收。

## 后续范围

文字与图片混排在同一页时，已有文本会使自动 OCR 跳过该页；手写、倾斜纠正、图像区域检测、坐标框定位仍未实现。批量断点恢复、并发、权重配置继续作为后续候选。
