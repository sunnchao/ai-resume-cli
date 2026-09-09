# v0.5.0：评分证据与批量处理

日期：2026-09-09。语言：Python。提示词版本：1.2。

状态：T17-T21 开发与本地验证完成，122 项测试通过，覆盖率 96%；T22 部分通过，第二份真实样例的端点 HTTP 400 尚未定位。已有 MVP 验收仍以用户确认完成为准。

## 本轮目标

用户已确认 v0.4 的真实模型验收、文档一致性修复、演示材料完成。本轮继续实现可解释评分与多文件处理；沿用用户已验证的 Chat Completions 接口和默认评分契约。

## 开发任务

| ID | 任务 | 实现与验收 |
| --- | --- | --- |
| T17 | 可选 `score --evidence` | 单次请求返回三维证据、缺口；默认 JSON 和默认 AI Schema 兼容 |
| T18 | 引文校验与来源标记 | 只忽略空白的子串比对；伪造引文失败；mock 明确标记 `mock_fixture` |
| T19 | `batch extract / score` | 显式多个路径、去重、顺序执行、一次读取 JD、最多 20 份 |
| T20 | 部分失败报告 | 单份失败后继续；统一报告；失败项含错误码；退出 7；支持防覆盖保存 |
| T21 | 自动测试与安装交付 | 扩展测试、更新 README / 示例 / 版本 / lock、构建并验证 wheel |
| T22 | 新增证据真实接口验证 | 仅用两份虚构样例执行；与 v0.4 用户验收分别记录 |

## 验收重点

- 默认 score 的字段保持原样，新增能力不要求旧默认返回包含证据。
- 证据与 few-shot 的 Schema 一致，每维最多 3 条、缺口最多 6 条，每条最多 240 字符。
- 原文中不存在的引文报错，错误提示不回显引文；缺少证据可返回空数组。
- 模型判断为 JD 未要求的维度不得填入匹配证据。
- mock 的引文来源于固定虚构文本，不伪装成当前 PDF 的核验结果。
- 多文件结果保持首次输入顺序；重复路径与符号链接别名不重复处理。
- PDF 失败和 AI 失败不影响后续文件；批次有失败时仍可读取完整报告。
- 全局输入 / 配置 / 输出路径错误在 AI 调用前失败；批量进度不混入 stdout。
- 构建包内包含新增 fixture，项目外可执行 batch 与 evidence。

## 使用示例

```bash
uv run resume-cli score examples/resume.pdf --jd examples/jd.txt --mock --evidence
uv run resume-cli batch extract examples/resume.pdf examples/resume-alt.pdf --mock
uv run resume-cli batch score examples/resume.pdf examples/resume-alt.pdf --jd examples/jd.txt --mock --evidence --output batch-result.json
```

## 边界与取舍

引文存在性校验不能证明语义关联、原文真实性或缺口判断正确；不增加自动淘汰或候选人排序。未加入 PDF 页码、OCR、并发和断点恢复。批次按文件限额控制规模，认证或配额失败逐文件报告；每份最多两次请求。

## 后续候选

| 优先级 | 候选任务 | 可验收结果 |
| --- | --- | --- |
| 高 | PDF 页码与 JD 证据定位 | 证据可定位到原文页码和岗位要求 |
| 高 | OCR 与复杂版面样例集 | 指定扫描 / 双栏样例可解析，失败有明确原因 |
| 中 | 批次断点恢复与失败重试 | 可仅重试失败文件，已有结果不重复付费 |
| 中 | 受控并发与配额暂停 | 并发数可配置，触发配额错误后可停止排队 |
| 中 | 自定义权重与配置文件 | 严格校验权重，输出记录实际评分规则 |
| 中 | CI 与多平台验证 | Windows / Linux / macOS 的基础流程可运行 |

当前实际验证结果见 [VALIDATION.md](VALIDATION.md)；本表仅列候选，不表示已实现或已安排到本轮。
