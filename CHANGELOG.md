# 变更记录

## Unreleased

- Windows 冻结二进制校验改为按字节读取 stderr，并接受控制台代码页；冻结启动提示改为 ASCII `resume-cli starting...`，避免 GitHub Windows runner 按 UTF-8 解码失败。
- 内部模块按 `domain` / `application` / `adapters` 分层；CLI 入口仍是 `resume_cli.cli:main`。公开 JSON、命令与错误码不变。
- 增加当前平台独立二进制打包：`scripts/build_binary.py` / `scripts/build_binary.sh`。默认目录分发到 `dist/binary/resume-cli/`，启动时立即在 stderr 提示，避免单文件每次解压的长等待；`--onefile` 仍可打单文件。不含 OCR extra。`scripts/verify_binary.py` 用虚构样例校验 parse / mock extract / evidence score / batch。
- 增加 tag 触发的 GitHub Release 工作流：推送 `vX.Y.Z`（须与 `pyproject.toml` / `__version__` 一致）后构建 wheel / sdist，并在 Ubuntu / macOS / Windows runner 本机架构打包独立二进制；校验后上传到 GitHub Release，附 SHA256SUMS。不交叉编译，不含 OCR extra，也不把二进制提交进仓库。手动 `workflow_dispatch` 只构建产物、不创建 Release。

## 0.6.0 - 2026-09-09

- PDF 解析保留页码、页文本及提取方式；parse --pages 输出分页 JSON。
- score --evidence 增加 PDF 位置、JD 短引与行号、缺口对应的 JD 证据，详细结构版本升级为 2。
- 支持可选本地 OCR、语言选择与布局模式，覆盖所有单份和批量命令。
- 新增 7 份虚构 PDF 回归样例；真实中英文 OCR、混合文件和空白负例测试通过。
- 新增 GitHub Actions：3 OS × 3 Python 核心矩阵、3 OS OCR、actionlint；固定 action 提交与语言数据摘要。
- macOS / Linux 容器各 151 项测试通过，覆盖率 96%；macOS Python 3.13 核心 147 项通过。
- 远程 CI 与 Windows 实测尚未运行；现有真实模型端点仍返回 HTTP 400，详见 VALIDATION.md。

## 0.5.0 - 2026-09-09

- 增加可选 `score --evidence`，输出三维简历短引、相关性说明、待核实缺口与来源标记。
- 引文在本地与原文比对，模型补造短引时失败；限制条数和长度，mock 明确引用固定虚构文本。
- 增加 `batch extract / score`：显式文件、路径去重、顺序执行、20 份上限、逐项结果与失败报告。
- 批量有失败项时退出 7，仍返回完整 JSON，支持 --output 防覆盖保存。
- 默认单份 JSON、默认评分 Schema 与用户已验证的 Chat Completions 接口保持兼容。
- 122 项离线测试通过，覆盖率 96%，构建与独立安装通过。新增证据真实接口一份成功、一份重复 HTTP 400，详见 VALIDATION.md。

## 0.4 后续改进（本轮保留）

- `extract` / `score` 在 Chat Completions 请求中各附加 2 条虚构 few-shot 样本，约束字段写法并减少补造；当前文档仍只出现在最后一条 user 消息。

## 0.4.0 - 2026-09-09

本地 MVP 已完成；用户随后确认真实模型验收、文档一致性与演示材料完成。外部发布地址未登记。

- 增加 `parse`、`extract`、`score`、帮助与版本查询。
- 实现 PDF / JD 输入检查、严格 JSON 规则、Chat Completions API、受控重试与错误提示。
- 评分使用完整简历文本，按照 50/30/20 在本地计算总分。
- 增加显式 mock 和 UTF-8 JSON 保存，保存时拒绝覆盖既有目标。
- 提供两份嵌入中文字体的虚构简历、JD、期望 JSON、生成与真实 API 冒烟脚本。
- 提供 95 项离线测试，覆盖率 96%，以及任务迭代、验收和演示文档。

0.1 / 0.2 / 0.3 是本轮工作按依赖划分的实现阶段，不代表独立对外发布记录，详见 `docs/ITERATIONS.md`。
