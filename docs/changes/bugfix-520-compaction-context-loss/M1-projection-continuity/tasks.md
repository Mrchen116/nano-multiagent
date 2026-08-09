# bugfix-520-M1: projection-continuity — Tasks

> 对齐: ../design.md（2026-08-09 approved）

## 目标

让 compaction 与常规 transcript 加载共享同一份可恢复消息投影，并以一条真实 IM/Gateway/recording-LLM 长青旅程证明含工具历史的 threshold 压缩在当轮和 Gateway 重启后都保持原任务连续。

## 退出标准

- [ ] `load()` 与 `list_event_entries()` 对 latest boundary、active branch 和 `tool_call_recovery` 的解释一致。
- [ ] event adapter 对称保留 durable parent/tool/group/reasoning/parts 字段，正常与恢复 tool pair 均可进入 provider。
- [ ] 新增且只新增一条 fake-LLM critical journey：真实工具执行后触发 threshold 压缩，当轮和 Gateway restart 后都回答原目标。
- [ ] catalog 从 14 条变为 15 条，移除“上下文压缩恢复” backlog；既有 fake-LLM #14/#15 继续绿色。

## 测试策略

- 保护的回归风险与可观察 seam: raw JSONL 经 active/recovery 投影进入 compaction 时丢结构关系；从 `JsonlTranscript.load()` 和 `list_event_entries() -> message_from_turn_entry()` 的可恢复消息及 provider mapping 观察。真进程接线风险从 IM HTTP/WS、recording upstream request、durable compact boundary 与 Gateway restart 后回复观察。
- 已有保护与处置: `tests/unit/test_session_persistence_fidelity.py`（rewrite-merge）和 `tests/e2e/critical_paths/test_agent_config_context_continuity_critical_path.py`（扩展共享 fixture）；新建 `test_context_compaction_continuity_critical_path.py`，因为真压缩/工具/重启是既有旅程未覆盖的独立进程级风险。
- 落层/目录/marker: 字段投影在 `tests/unit/`、marker 无；真进程路径在 `tests/e2e/critical_paths/`、marker `e2e`。前者是最低可定位字段丢失层，后者仅守 IM/Gateway/持久恢复接线。
- 可选依赖 importorskip: 无；fake-LLM 旅程仅使用项目已安装的 httpx/PyYAML 和仓库脚本。
- 本 milestone 产生的一次性验收证据（收尾删除，不进套件）: 无；新增 E2E 本身是半年后仍应运行的永久门禁。

### 受影响的既有测试处置

| 风险 / 行为 | 既有测试 | 处置 | 理由与保留或替代保护 | 验证 |
|---|---|---|---|---|
| Message/JSONL 字段往返 | `tests/unit/test_session_persistence_fidelity.py::_entry_to_message` 及相关 roundtrip | rewrite-merge | 手拼 entry 主动补回缺失字段，改为真实 transcript event projection guard；原始 JSONL 往返断言仍保留 | 运行整文件 |
| fake-LLM 真栈启停与 config 改写 | `test_agent_config_context_continuity_critical_path.py::stub_llm_stack` | rewrite-merge | 泛化为可选 recording script、env 与 context window，但由原 fixture 继续唯一拥有起停 | 跑原配置连续性与 cache 告警旅程 |
| compaction/restart 进程接线 | 无（搜索 `tests/e2e/critical_paths` 的 compaction、restart、tool 路径） | keep | restart 与 tool 分别存在，但没有同一真实会话压缩 seam；新增一个语义归属明确的旅程 | 跑新 E2E |

前端 UI：N/A。本 milestone 是后端 bug-regression，用户入口为 IM HTTP/WebSocket；无原型、浏览器或视觉状态。

## Roadpoints

### R1 — canonical recoverable projection 与字段对称

- 状态: TODO
- 步骤: 先补真实 transcript 双路径语义等价红测，再让 `load()` / event projection 共享 latest-boundary active/recovery materialization，并对称搬运 durable Message 字段。
- 验证: persistence fidelity 整文件；provider mapper 能接受 projected normal/recovery tool pairs。

### R2 — recording fixture 与真进程压缩/重启旅程

- 状态: TODO
- 步骤: 先落会在旧投影上失败的 E2E；新增短状态机 recording fixture，泛化既有 stack fixture 的 script/env/context window，跑通真实工具、threshold compact、继续、Gateway restart、继续。
- 验证: 新 E2E 单独绿色，recording request 与 session JSONL 同时证明有效 summary/boundary。

### R3 — catalog 与 milestone 全门禁

- 状态: TODO
- 步骤: catalog 14→15 并移除 backlog；跑 M1 unit、新旧 fake-LLM journeys、docs-check、Ruff 与 diff check。
- 验证: design Runbook 的 M1 相关命令和长期文档门禁全绿。
