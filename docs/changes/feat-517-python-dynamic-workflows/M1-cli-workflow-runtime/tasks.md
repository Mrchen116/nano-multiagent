# feat-517-M1: CLI Python Workflow runtime — Tasks

> 对齐: ../design.md（2026-08-10 Gate 2 Approved）

## 目标

让 `coding_cli` 在启用精确名 `Workflow` 工具时，能够按可信人工 opt-in 生成并批准受限 Python 编排脚本，后台执行、查询、控制、恢复、保存并收到一次终态通知；同时稳定 M2 所依赖的 SDK、事件 metadata 与后台返回 carrier。

## 退出标准

- [ ] Python AST policy、primitives、并发顺序、状态机与 chained-v2 resume 在纯逻辑测试中固定。
- [ ] `Workflow` prompt/schema、启动审批、后台 manager、child adapter、saved/worktree 与一次通知接线完成。
- [ ] `RunOrigin.HUMAN/WORKFLOW`、`BackgroundReturnInfo`、`ToolResult.event_metadata` 和五个 Workflow SDK 方法为稳定公开契约。
- [ ] active/idle/terminal-continuation/`/stop` held-flush 均让 XML 与 sidecar 同命运且 FIFO/exact-once。
- [ ] CLI 默认启用（配置可禁用），支持 `/workflows`、`/effort ultracode`、named/save/control 与后台 child permission 长驻消费。
- [ ] M1 pure/unit/contract/CLI integration、ruff/format/diff-check 通过；真实 Luna 一 Agent lifecycle 留给 reviewer。

## 测试策略

- 保护的回归风险与可观察 seam: 受限 Python 只获得编排能力；run 终态只由顶层控制流决定；并发 admission/resume 可重放；工具开关决定 prompt/schema/reminder/commands；SDK/事件/通知 sidecar 可由产品稳定消费；CLI 在父轮结束后仍可处理 child permission。
- 已有保护与处置: 扩展 provider mapper、tool registry/approval、runs/background tasks、SDK boundary 与 CLI command/runtime owner；Workflow compiler/state 没有既有 owner，按行为新建 `tests/unit/agent/core/workflows/`；跨模块 launch/notification/CLI 新建语义 owner `tests/integration/agent/workflows/` 与 `tests/integration/coding_cli/`。
- 落层/目录/marker: `tests/unit/agent/core/workflows/`、`tests/unit/agent/platform/`、`tests/integration/agent/workflows/`、`tests/integration/coding_cli/`、`tests/contract/`，marker: 无；真实 LLM 只由 reviewer 在 `tests/e2e/`/手工旅程执行。
- 文件归属: 纯状态与编译新建行为名文件；已有 provider/tool/background/SDK/CLI seam 扩展其现有 owner，避免 milestone 名测试文件。
- 可选依赖 importorskip: 无；`jsonschema` 作为 runtime dependency。
- 本 milestone 产生的一次性验收证据（收尾删除，不进套件）: 无；Luna/LLM Proxy 请求 locator 由 reviewer 补入 progress。

### 受影响的既有测试处置

| 风险 / 行为 | 既有测试 | 处置 | 理由与保留或替代保护 | 验证 |
|---|---|---|---|---|
| Run origin 与 pending/stranded/held 搬运 | `tests/unit/agent/core/test_runs_registry_pending.py`、`tests/unit/agent/core/test_agent_loop.py` | rewrite-merge | 原文本不丢风险仍在；把 sidecar 作为同一 carrier 断言，不另测内部队列实现 | focused pytest |
| 后台 registry terminal/通知 | `tests/unit/agent/core/test_background_tasks.py`、`tests/unit/agent/platform/test_background_task_wiring.py` | rewrite-merge | 保留 bash/subagent killed 语义，叠加 Workflow stopped 与 atomic claim、XML/sidecar | focused pytest |
| 工具执行/批准/事件 | `tests/unit/agent/core/test_toolcall_approval_chain.py`、`tests/unit/agent/platform/test_auto_mode_gate_hook.py`、`tests/unit/agent/platform/test_realtime_stream_hook.py` | rewrite-merge | 在既有公开事件 seam 增 decision callback 与 event_metadata | focused pytest |
| provider request mapping | `tests/unit/agent/platform/test_anthropic_mapper.py`、`test_openai_compat_mapper.py` | rewrite-merge | 保留 leading system 语义，新增 `turn_system` 原位 mapping golden | focused pytest |
| SDK 精确表面/所有权/产品边界 | `tests/contract/test_agent_sdk_boundary_contract.py`、`tests/contract/test_package_import_boundaries.py` | rewrite-merge | 公开名单必须加入 SDK-owned Workflow DTO 与方法且不放宽边界 | contract pytest |
| CLI 现有会话/权限/斜杠命令 | `tests/unit/coding_cli/test_commands.py`、`tests/unit/coding_cli/test_product.py`、CLI runtime tests | rewrite-merge | 从用户命令与 stream seam 覆盖新增能力，保留原命令语义 | focused + integration pytest |
| 既有工具/schema/背景 Agent 行为 | 其余 targeted agent/coding_cli tests | keep | 新能力不能改变未启用会话、bash/subagent 和普通 CLI 旅程 | M1 regression set |

UI 状态矩阵：N/A（M1 无前端改动）。

Prototype / Reference Contract：`prototype.html` 的 must-match Web 状态归 M2；M1 只提供 may-adapt 的 presenter 字段集合、machine correlation 与后台 sidecar，不产出浏览器证据。

## Roadpoints

### R1 — 稳定共享公开契约与后台 carrier

- 状态: DONE
- 步骤: 先为 RunOrigin、Background STOPPED/WORKFLOW、notification projection/claim、PendingMessage/RunRecord sidecar、ToolResult event metadata 与 SDK DTO 表面写红测，再实现最小字段和搬运链。
- 验证: core/platform/SDK focused tests + contract tests。

### R2 — 实现受限 Python compiler、primitives 与 resume 状态

- 状态: DONE
- 步骤: 以纯 fake child 写 AST/meta/policy、checkpoint、parallel/pipeline/limits、ordinal、whole-run 终态与 chained-v2 prefix 红测，再实现 `agent.core.workflows`。
- 验证: `tests/unit/agent/core/workflows/`。

### R3 — 接入 platform manager、Workflow 工具与持久化

- 状态: DOING
- 步骤: 为 tool schema/prompt、permission callback、store/journal/snapshot、child adapter/structured output、saved/worktree/background stop/notification 写红测并实现。
- 验证: platform focused tests + `tests/integration/agent/workflows/`。

### R4 — 接入 turn activation、provider golden 与 SDK 管理方法

- 状态: TODO
- 步骤: 固定四态 request、HUMAN/WORKFLOW、共享预算、build args、五个 SDK query/control/save/list 方法及关闭生命周期。
- 验证: provider/unit + SDK/contract + Kernel integration。

### R5 — 完成 coding_cli 产品旅程

- 状态: TODO
- 步骤: 默认工具/config disable、human typed origin、`/workflows`/control/save/named、`/effort ultracode` 与 parent stream 长驻 child permission consumer。
- 验证: CLI unit/integration，TTY 控制由纯输入 seam，非 TTY 走真实命令入口。

### R6 — M1 回归、静态门禁与交付记录

- 状态: TODO
- 步骤: 跑 M1 regression、全量非 E2E（待并行 M2 collection 恢复）、ruff/format/docs/diff；更新 progress 并只提交 M1 paths。
- 验证: design runbook 中 worker 门禁；Luna lifecycle 标记 reviewer pending。
