# Verification Report: refactor-462

## Summary

| 维度 | 结果 |
|---|---|
| Completeness | 4/4 roadpoints 已落地，但 3 个退出标准行为未满足 |
| Correctness | 6/8 用户场景保持；另有 1 个公开 SDK 兼容回归 |
| Coherence | Partially followed（决策 2 / 5 / 8 存在偏离） |

**Verdict: FAIL. 3 critical issues found. Fix before PR.**

## Scope and Evidence

- Verification mode: `full`
- Review round: `1`
- Verified commit: `226a33c02ac856ab710cdf6cd75922eb0cc6a095`
- Narrow final-aggregate tests: `38 passed in 1.41s`
- Full regression: `pytest -m 'not e2e'` → `3305 passed, 1 skipped, 20 deselected in 278.43s`
- Quality gates: `ruff check .` → passed；`ruff format --check .` → `758 files already formatted`；`git diff --check origin/main...HEAD` → passed
- Read-only behavior probes independently reproduced all three CRITICAL findings below. Their absence from the green suite is a coverage gap, not evidence that the behaviors are correct.

## Completeness

- Tasks: 4/4 roadpoints are marked `DONE` and the structural cutover is present.
- Exit criteria are not actually complete:
  - `tasks.md:9` requires all motivation scenarios, including active append/cancel recovery and prompt refresh at every compaction boundary; CRITICAL-2 and CRITICAL-3 violate those behaviors.
  - `tasks.md:15` requires active append interleaving coverage; the current test stops the fake engine before it emits any residual turn write, so it does not cover the required race.
  - `tasks.md:17` requires final-interface behavior coverage after removing private-map/manager tests; manual/threshold/overflow compaction, restart prompt-seed use, and prompt/file-window refresh no longer have equivalent permanent coverage.
- Spec coverage: stable identity, cold first append, between-turn append, ordinary multi-turn replay, simple as-of fork, typed executor ownership, and old-seam deletion are implemented. Active append reconciliation, manual-compaction prompt refresh, and the documented string `workspace_root` SDK contract are incomplete.
- Prototype / Reference coverage: N/A（本 unit 无前端原型或视觉 reference contract）。

## Correctness

| Requirement / Scenario | 实现位置 | 测试覆盖 | 状态 |
|---|---|---|---|
| CLI 多轮对话与恢复 | `src/agent/sdk/kernel.py:849`, `src/agent/core/session/conversation.py:194`, `src/agent/core/agent/runtime.py:321` | `tests/unit/agent/session/test_conversation_session.py:164` | covered |
| IM/Gateway 多轮对话与重启恢复 | `src/agent/sdk/kernel.py:1012`, `src/agent/core/runs/registry.py:168`, `src/agent/core/session/conversation.py:194` | `tests/unit/personal_assistant/test_session_reuse_regression.py:152`, `tests/e2e/critical_paths/test_restart_session_continuity_critical_path.py:65` | covered |
| 带外追加进入下一轮上下文 | `src/agent/sdk/kernel.py:1503`, `src/agent/core/session/conversation.py:207`, `src/agent/core/session/transcript.py:226` | `tests/contract/test_kernel_sdk_behavior_contract.py:303` | covered（仅两轮之间） |
| 重启后首次操作就是带外追加 | `src/agent/core/session/transcript.py:226`（UNKNOWN tail 从 durable turn 初始化） | `tests/unit/agent/session/test_jsonl_transcript.py:27` | covered |
| 中断或取消后继续会话 | `src/agent/core/session/conversation.py:194`, `src/agent/core/agent/runtime.py:321`, `src/agent/core/agent/runtime.py:593` | `tests/unit/agent/session/test_conversation_session.py:111` 未覆盖 residual write | **deviates — CRITICAL-2** |
| 上下文压缩后透明继续 | `src/agent/core/session/conversation.py:227`, `src/agent/core/agent/runtime.py:1727`, `src/agent/core/agent/loop.py:874` | 只有 planner/loop 与 stale-epoch 片段测试，无最终 aggregate / SDK 三类压缩测试 | covered in code, insufficient durable coverage（WARNING-1） |
| 从指定消息 fork 会话 | `src/agent/core/session/conversation.py:236`, `src/agent/core/session/directory.py:177` | `tests/unit/agent/session/test_conversation_session.py:207` + R4 真栈记录 | covered（边界覆盖不足，见 WARNING-1） |
| 会话内提示稳定且在压缩边界刷新 | `src/agent/core/agent/runtime.py:1715`, `src/agent/core/agent/runtime.py:1727`, `src/agent/core/agent/loop.py:969` | 无 manual compact 后重新读取 AGENTS.md 的永久测试 | **deviates — CRITICAL-3** |

## Coherence

| design 决策 | 遵守? | 代码证据 |
|---|---|---|
| 1. 每 session 一个长期存活 ConversationSession | 是 | `src/agent/core/session/directory.py:35`, `src/agent/core/session/directory.py:88` |
| 2. 五个高层事务隐藏 ordering | 部分 | interface 位于 `src/agent/core/session/conversation.py:194`；active append 未完成 live-state reconciliation（CRITICAL-2） |
| 3. ConversationSession 接管 turn state，旧多 session runtime maps 退役 | 是 | `src/agent/core/session/conversation.py:24`, `tests/contract/test_session_aggregate_architecture.py:42` |
| 4. 私有 Transcript + lifecycle permit | 是 | `src/agent/core/session/conversation.py:80`, `src/agent/core/session/transcript.py:40` |
| 5. 三类 compaction 共用 commit 并统一 reset 窗口 | 否 | threshold 路径在 `src/agent/core/agent/loop.py:969` 失效快照，manual 路径 `src/agent/core/agent/runtime.py:1727` 成功提交后未执行同一 reset（CRITICAL-3） |
| 6. KernelExecutor 只拥有 loop / Task / TargetToken | 是 | `src/agent/core/runs/executor.py:139`, `src/agent/core/runs/registry.py:108` |
| 7. SessionService / SessionManager 退役 | 是 | `tests/contract/test_session_aggregate_architecture.py:12` |
| 8. SDK / consumer behavior 无增量 | 否 | `Kernel.submit(workspace_root: str | Path)` 接受 `str`，但未归一化（CRITICAL-1） |

### Prototype / Reference Contract

N/A：`design.md` 没有前端原型或 must-match 视觉 reference。

## Issues

### CRITICAL（提 PR 前必须修）

- **CRITICAL-1 — `Kernel.submit()` 破坏公开的 `str | Path` workspace contract。** `src/agent/sdk/kernel.py:1012-1019` 明确接受 `workspace_root: str | Path | None`，但 `src/agent/sdk/kernel.py:1055-1066` 直接把字符串传给 Registry；`src/agent/core/runs/registry.py:199` 构造 `SessionRef` 后，`src/agent/core/session/types.py:39-48` 对字符串调用 `.expanduser()`，同步抛出 `AttributeError: 'str' object has no attribute 'expanduser'`。这与 progress 中“所有 SDK 会话入口已归一化”的记录（`M1-conversation-session/progress.md:77-82`）及 design 决策 8 的 no-SDK-delta 合约冲突。**修复建议：**在 `Kernel.submit` 与其它 path-taking SDK 方法一样，先执行 `Path(workspace_root or self._repo_root).expanduser().resolve()`；增加真实 `build_kernel` 回归，以 `str(root)` create/submit，等待 run terminal 并断言第二轮历史连续，而不是只检查签名或 mock 调用。

- **CRITICAL-2 — active external append 会让当前进程的 live history 永久漏掉随后已持久化的 assistant/tool/recovery，下一轮上下文不完整。** `AgentEngine._run_locked` 在 `src/agent/core/agent/runtime.py:321-322` 捕获 `state.history` 的旧 list；模型 await 期间，`ConversationSession.append_external` 在 `src/agent/core/session/conversation.py:207-216` 重载 transcript 后用新 list 替换 `self._state.history`；active engine 随后仍在 `src/agent/core/agent/runtime.py:593-615` 向旧 list 追加并把这些条目写入 transcript。独立 probe 得到 durable history=`[external, late assistant]`，但 `history_snapshot()` 和下一 turn 所见均只有 `[external]`，直至进程重启才恢复。现有测试 `tests/unit/agent/session/test_conversation_session.py:111-136` 的 blocking engine 在 append 后不写任何 residual message，反而把只剩 external 的错误形态固化为期望。该行为直接违背 design 的 active append epoch protocol（`design.md:326-343`）及 cancel/interrupt continuation 场景。**修复建议：**不要从 foreign thread 在 active turn 中替换 engine 已捕获的 list；在 ConversationSession 内记录 turn 开始时的 external epoch，append 只提交 durable mutation并标记 loaded state stale，turn/recovery 完成后若 epoch 变化则在 owner loop 上卸载/重载完整 reachable history，再释放 turn gate。新增永久回归：active turn 在 external append 后继续持久化 assistant + tool/recovery，下一次真实 submit 的 LLM context 同时包含 external 与所有 residual entries。

- **CRITICAL-3 — manual compaction 成功后不失效 memory/AGENTS.md prompt snapshot，违反“压缩边界刷新”。** `_invalidate_memory_snapshot` 在 `src/agent/core/agent/runtime.py:1715-1725` 才会清 memory snapshot 与 AGENTS.md dedup；threshold/overflow loop 路径在 `src/agent/core/agent/loop.py:969-972` 调用它，但 public `Kernel.compact()` 进入的 manual 路径 `src/agent/core/agent/runtime.py:1727-1858` 成功 commit 后只替换 `file_state`，没有清 `memory_snapshot`。独立真实 SDK probe：首轮读取 `AGENTS.md=MARKER_OLD`，磁盘改为 `MARKER_NEW`，manual compact 成功后下一轮 system prompt 仍含 OLD 且不含 NEW。该实现还证明 design 决策 5 所要求的“三类 compaction 共用一条 commit + window reset”没有真正收口。**修复建议：**把 successful compaction 的 history replacement、memory/file/prompt reset 收口为一个 ConversationSession/engine commit-finalization helper，让 manual/threshold/overflow 都走同一调用点；仅在 durable commit 成功后失效 snapshot。增加真实 Kernel 测试：同一窗口 prompt 冻结，修改 AGENTS.md 后 manual compact，下一轮读取新内容；同时覆盖 threshold 与 overflow，并验证 restart replay。

### WARNING（应该修）

- **WARNING-1 — 删除旧 private-seam 测试后，关键退出场景没有被最终 interface 的永久测试等价接回。** `tasks.md:21-30` 要求 ConversationSession/真实 Kernel 覆盖 manual/threshold/overflow compact、whole/as-of fork、restart PromptSlotSeed、prompt/file window、active residual append；但当前 aggregate 测试只有简单两轮（`tests/unit/agent/session/test_conversation_session.py:164`）、无 residual write 的 active append（`:111`）、简单 as-of fork（`:207`）和 transcript stale epoch（`tests/unit/agent/session/test_jsonl_transcript.py:138`）。`progress.md:81-85` 的 6 个 selected e2e 也没有 compaction/prompt-window 旅程。全量 3305 项通过却未捕获本报告三个 probe，已经实际证明该缺口。**修复建议：**按 `tasks.md` 测试策略，在最低 final-interface 层补齐 durable matrix：三类 compaction + restart、active append residual/recovery、whole/as-of fork 穿越 compaction boundary、两个 Kernel 实例恢复 PromptSlots 并进入真实 system prompt、legacy archive 无 reserved key 的 empty fallback、manual/automatic compaction 后 memory/AGENTS/file-window refresh；临时 e2e 记录不能替代这些回归。

### SUGGESTION（可以修）

- **SUGGESTION-1 — 退役 owner 的注释仍残留，容易误导后续维护。** `src/agent/core/session/jsonl_writer.py:18-19` 仍称 `_session_histories` 无上限，`src/agent/platform/tools/builtins/agent.py:542-547` 仍描述 `_active_run_models`；两者已被本 unit 删除。**建议：**按 `COMMENTING_GUIDE.md` 改为当前 ConversationSession / current-run model owner 的事实，或删除不再提供约束价值的历史注释。
