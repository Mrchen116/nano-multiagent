# bugfix-520-M2: bounded-failure-semantics — Tasks

> 对齐: ../design.md（2026-08-10 approved）

## 目标

压缩失败不再以空业务 fallback 替换历史；manual、threshold、overflow 按批准矩阵保持原上下文，automatic 达到安全边界时先给用户固定 assistant 提示再失败，并保留结构化诊断。

## 退出标准

- [ ] manual、threshold、overflow 的 summary/persistence failure 不新增 boundary、不替换可恢复历史。
- [ ] threshold 前两次 summary failure 静默沿用原上下文，第三次熔断；overflow summary failure 立即熔断，manual 不计数。
- [ ] automatic 终止前发送固定 assistant 提示，且提示不写入 kernel transcript；既有飞书 assistant delivery seam 保持绿色。
- [ ] failure tracker 归属稳定 `ConversationSession`，external reload/LRU eviction 不重置，成功 compact 重置。
- [ ] stale、persistence exception、summary failure 分流正确；只有 automatic summary failure 计数。
- [ ] `CompactionError` 通过 RunsRegistry 保留稳定 code/details，普通异常协议不变。

## 测试策略

- 保护的回归风险与可观察 seam: summary 失败伪成功、automatic 无限重试、失败提示晚于 terminal、诊断丢失；分别从 summarizer/loop 行为、public Kernel event + transcript、stable conversation identity、RunRecord terminal 观察。
- 已有保护与处置: 扩展并改写 `tests/unit/test_loop_compact.py`、`tests/unit/agent/session/test_conversation_session.py`、`tests/unit/agent/runs/test_runs_registry_executor.py`、`tests/unit/agent/test_kernel_manual_compact.py`、`tests/integration/test_conversation_compaction_integration.py`；不新建平行测试文件。
- 落层/目录/marker: `tests/unit/` 与 `tests/integration/`，marker: 无；unit 是策略与 carrier 的最低暴露层，integration 才能证明 public Kernel、durable transcript 和事件顺序接线。
- 可选依赖 importorskip: 无。
- 本 milestone 产生的一次性验收证据（收尾删除，不进套件）: 无；public Kernel integration 是可长期运行的真实 SDK 入口 regression。

### 受影响的既有测试处置

| 风险 / 行为 | 既有测试 | 处置 | 理由与保留或替代保护 | 验证 |
|---|---|---|---|---|
| automatic fallback 假成功 | `tests/unit/test_loop_compact.py::test_strict_manual_compaction_never_returns_the_automatic_fallback` 及 loop success tests | rewrite-merge | 删除 strict/fallback 前提，改守所有空/异常均不提交与 bounded retry | focused pytest |
| manual summary/append failure atomicity | `tests/unit/agent/test_kernel_manual_compact.py` | keep | public SDK durable seam 仍是最低层 owner；只更新无 strict 的异常形状 | focused pytest |
| threshold stale/success与 overflow success | `tests/integration/test_conversation_compaction_integration.py` | keep | 在同一 public Kernel owner 增补失败矩阵和事件顺序，不复制成功用例 | focused pytest |
| 任意 assistant 文本投递到飞书 | `tests/unit/personal_assistant/test_external_visible_delivery.py::test_feishu_intermediate_reply_goes_to_external_without_im_manager` | keep | 本 unit 不改 Gateway；既有通用 seam 已保护 fixed text 的外部投递 | focused pytest |
| ordinary run failure protocol | `tests/unit/agent/runs/test_runs_registry_executor.py` | keep + rewrite-merge | 新增 typed compaction 分支同时锁住普通异常仍为 `run_execution_failed` | focused pytest |

前端 UI、状态矩阵、浏览器 QA 与 Prototype / Reference Contract：N/A，本 milestone 不改前端。

## Roadpoints

### R1 — 失败值与会话计数契约

- 状态: DOING
- 步骤: 先为 summarizer 无 fallback、`CompactionError` 序列化和 session-owned tracker 写红测，再补最小 domain 实现。
- 验证: `tests/unit/test_core_errors.py`、`tests/unit/test_loop_compact.py`、`tests/unit/agent/session/test_conversation_session.py` focused tests。

### R2 — threshold bounded retry 与 commit 分流

- 状态: TODO
- 步骤: 用 loop 红测锁定前两次 no-commit/no-summary、第三次 typed failure、成功 reset、stale 不计数、persistence 立即失败。
- 验证: `tests/unit/test_loop_compact.py`。

### R3 — manual/overflow 与 automatic 用户提示

- 状态: TODO
- 步骤: 用 public Kernel 红测覆盖 summary/persistence/overflow 原因、历史 atomicity、assistant-before-failed 与不写 transcript；实现 runtime 三入口收口。
- 验证: `tests/unit/agent/test_kernel_manual_compact.py`、`tests/integration/test_conversation_compaction_integration.py`。

### R4 — terminal 诊断、会话重载持续性与最终门禁

- 状态: TODO
- 步骤: 扩展 RunsRegistry typed error/ordinary error tests，验证 external reload/LRU 持续计数、成功 reset、飞书通用投递 seam 与完整 M2 回归。
- 验证: design runbook 的 M2 focused suite、Ruff、`git diff --check`。
