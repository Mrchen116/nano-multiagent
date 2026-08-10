# bugfix-525-M1: 隔离 self-evolution side-chain 原始输出 — Tasks

> 对齐: ../fix.md（Bugfix lite）

## 目标

self-evolution review 继续真实执行 memory/skill 工具并发布一条结构化
`self_evolution_review`，但 fork 内部的 assistant/tool/turn realtime 事件不再进入父
run 的用户可见投递面；普通 `RunOrigin.BACKGROUND_TASK` run 的结果不受影响。

## 退出标准

- [x] 真实 self-evolution fork 的 raw assistant/tool/turn 输出不发布到父 session event stream。
- [x] memory/skill side effect、父模型、workspace-scoped hook/tool、unattended permission 语义保持不变。
- [x] review 完成后仍只发布一条结构化 `self_evolution_review`。
- [x] 普通 background Agent 的用户可见结果不被全局抑制。

## 测试策略

- 保护的回归风险与可观察 seam: 真实 Kernel turn 触发真实 self-improvement background hook 和真实 fork；从 `Kernel.stream()` 的 session-event seam 观察用户可投递事件，并从 workspace `USER.md` 观察 memory side effect。
- 已有保护与处置: `tests/unit/test_background_hook_fork.py`（keep）、`tests/unit/test_self_improvement_hook.py`（keep）、`tests/unit/platform/hooks/test_realtime_stream_events.py`（keep）、`tests/unit/personal_assistant/test_background_session_events.py`（keep）；这些分别保护继承能力、review 调度、前台 realtime schema、结构化通知消费，不覆盖本次跨 seam 失败原因。
- 落层/目录/marker: `tests/integration/`，marker: 无；需要同时经过 Kernel、background hook、真实 fork、工具执行与 session event hub，这是能暴露坏值继承的最低层。
- 文件归属: 新建 `tests/integration/test_self_evolution_output_visibility.py`；既有 unit 文件各自只拥有单层行为，且 `test_background_hook_fork.py` 已超过 400 行，不继续堆跨模块行为。
- 可选依赖 importorskip: 无。
- 本 milestone 产生的一次性验收证据（收尾删除，不进套件）: 无；固定 fake LLM 驱动的真实 Kernel integration regression 同时作为可重复入口证据。

### 受影响的既有测试处置

| 风险 / 行为 | 既有测试 | 处置 | 理由与保留或替代保护 | 验证 |
|---|---|---|---|---|
| fork 继承父模型、permission、workspace execution scope 和 background origin | `tests/unit/test_background_hook_fork.py::test_fork_inherits_parent_execution_context` | keep | 扩充其断言，明确仅 session-event publisher 被隔离，避免修复误伤既有能力 | focused pytest |
| review 调度后发布结构化通知 | `tests/unit/test_self_improvement_hook.py::TestSessionEventPublish` | keep | 通知由父 background hook context 发布，不应随 fork raw stream 一起被抑制 | focused pytest |
| 普通 realtime hook schema | `tests/unit/platform/hooks/test_realtime_stream_events.py` | keep | 修复只发生在 side-chain HookContext，不改变普通前台/后台 run 的 realtime hook | focused pytest |
| Gateway 消费结构化通知 | `tests/unit/personal_assistant/test_background_session_events.py` | keep | 既有 structured notification consumer 仍是唯一 UI 回显路径 | focused pytest |

前端 UI：N/A。本 milestone 不修改前端或 feat-524 展示设计。

Prototype / Reference Contract：N/A。

## Roadpoints

### R1 — 真实 fork session-event 红测与隔离修复

- 状态: DONE
- 步骤: 用受控两阶段 LLM 让主 turn 正常回答、self-evolution fork 调用真实 memory 后生成 `Saved: ...`；确认当前实现把 raw assistant/tool/turn 发布到 session stream，再在 fork HookContext 最小隔离 session-event publisher。
- 验证: 红测失败点必须是 raw side-chain event 可见；修复后同一测试证明 `USER.md` 已更新、事件流只有主回答和一条 structured notice。

### R2 — 继承不变量与既有测试维护

- 状态: DONE
- 步骤: 更新既有 fork context 断言，确认 model caller、permission requester、workspace scope、background origin 保留，普通 background/realtime 行为无全局过滤。
- 验证: 相关 unit/integration suites 全绿。

### R3 — 比例门禁与 Bugfix lite 证据闭环

- 状态: DONE
- 步骤: 运行 Ruff、diff/doc checks 与比例扩大测试；回填 `progress.md` 和 `fix.md` 修复/验证。
- 验证: 所有计划门禁通过，文档含生产证据 locator、红绿测试与残余风险。
