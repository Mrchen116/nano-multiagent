# Verification Report: bugfix-410

> Round: 1 | Branch: unit/bugfix-410 | Date: 2026-06-15

## Summary

| 维度 | 结果 |
|---|---|
| Completeness | 8/8 tasks + 4/4 requirements covered |
| Correctness | 10/10 scenarios covered |
| Coherence | Followed（5 条关键决策全部遵守） |

All checks passed. Ready for PR.

---

## Completeness

### Tasks

**M1（auto-mode-classifier-cc-sync）**：3/3 roadpoints 完成。
**M2（toolcall-interruption-robustness）**：4/4 roadpoints 完成。
Tasks: 8/8 complete（M1-R1/R2/R3 + M2-R1/R2/R3/R4 全标 `[x]`）。

### Spec 覆盖

| Requirement | 实现是否存在 |
|---|---|
| Req#99 分类器 transcript 包含历史工具调用 | `auto_mode_gate.py:408` kernel-format fallback |
| Req#98 等人工权限决策不被 idle 看门狗误杀 | `inbound_pipeline.py:853-892` + `relay_watchdog.py:57-90` |
| Req#82 中断的工具轮不再永久污染会话 | `runtime.py:702-713` + `_recover_orphaned_tool_calls:1037` |
| Req#97 run 异常终止时在飞 tool_call 徽标收口 | `main.py:3133-3632` observer reconcile |

---

## Correctness

| Requirement / Scenario | 实现位置（file:line） | 测试覆盖 | 状态 |
|---|---|---|---|
| **#99** 历史工具调用按时序投影进分类器 prompt | `auto_mode_gate.py:408-423`（kernel-format fallback，读 `LLMMessage.tool_calls`） | `test_auto_mode_gate.py::test_kernel_tool_calls_field_extracted` | covered |
| **#99** 防注入不变量保持（assistant 自由文本/tool_result/cron 不进 transcript） | `auto_mode_gate.py:380-430`（仅 role==user 文本 + tool_use 投影入 transcript） | `test_auto_mode_gate.py::TestBuildTranscriptEntries` 多断言 | covered |
| **#98** 权限卡片等待超 120s 后仍可批准 | `inbound_pipeline.py:859-860`（`timeout=None if awaiting_permission`）；relay `relay_watchdog.py:86-87`（fresh marker 豁免） | `test_inbound_pipeline_permission_watchdog.py::test_permission_pending_exempts_idle_watchdog` + `test_relay_watchdog.py::test_scan_skips_running_message_with_fresh_permission_marker` | covered |
| **#98** 权限未决期间徽标显示「等待批准」 | `gateway_handler.py` + `event_bridge.py` 置 `awaiting_permission_at` marker；前端既有 feat-333 permission_request 卡承担渲染 | `test_event_bridge.py::test_permission_request_sets_marker_and_terminal_clears_it` | covered |
| **#98** 用户拒绝权限 → 徽标收口「已拒绝」 | `registry.py:170-183`（`reason_code="denied"`）→ R4 全链透传 → `tool-calls-panel.tsx:80`（`REASON_LABEL_KEYS.denied`）→ i18n 已拒绝 | `test_toolcall_reason_code_chain.py::test_blocked_tool_carries_reason_code_denied` + `tool-calls-panel.test.tsx::reason=denied` | covered |
| **#82** 工具轮中断后会话仍可继续对话 | `runtime.py:1110`（`invalidate_session_cache` 在 finally 最前）→ 下次 submit cache-miss → `prepare_transcript_for_run` 重修 | `test_agent_runtime.py::test_runtime_recovery_on_cancellederror_visible_to_next_run`（复现砖块 + 修后通过） | covered |
| **#82** 中断的 tool_call 在会话历史里带终态 | `runtime.py:1113-1133`（`append_tool_call_recovery` + flush，shield 保护 CancelledError 路径） | `test_agent_runtime.py::test_runtime_recovery_on_cancellederror_passthrough` | covered |
| **#97** bash 挂死触发看门狗超时 → 徽标「执行超时」 | `inbound_pipeline.py:869`（`_emit_terminal_reconcile(run_id, reason="timed_out")`）→ observer → IM | `test_inbound_pipeline_permission_watchdog.py::test_watchdog_timeout_emits_timed_out_reconcile` | covered |
| **#97** 按原因区分终态文案（执行超时/已拒绝/已中断） | `tool-calls-panel.tsx:79-83`（REASON_LABEL_KEYS 三态）+ `zh.json:365-367`（三文案） | `tool-calls-panel.test.tsx`（三态参数化 + 无 reason 无徽标） | covered |
| **#97** 已完成的工具不被改写 | `main.py:3515`（`tool_end` 时 pop 出 running_tool_calls）→ reconcile 遍历时已不在集合 | `test_inbound_pipeline_streaming.py::TestTerminalToolCallReconcile::test_reconcile_does_not_rewrite_completed_toolcalls` | covered |

---

## Coherence

| design 决策 | 遵守? | 代码证据（file:line） |
|---|---|---|
| 决策 1：看门狗用事件驱动状态切换识别合法等权限（不用周期心跳） | 是 | `inbound_pipeline.py:892`（`awaiting_permission = event_name == "permission_request"`）；relay marker 靠 heartbeat touch（`gateway_handler.py:953`），不是 keepalive 事件 |
| 决策 2：权限等待不设硬上限 + liveness 三条兜底路径齐全 | 是 | `timeout=None`（`:859`）；三路清理：①permission_response（`event_bridge.py:320`）②run 终态（`on_message_completed:244`）③崩溃阈值（`relay_watchdog.py:57-90` stale reap） |
| 决策 3（M3 陷阱）：finally **不依赖 stop_reason** 触发，invalidate 在最前（同步原子 dict pop） | 是 | `_recover_orphaned_tool_calls:1089`（仅用 stop_reason 合成 reason 标签，不用于触发）；`invalidate_session_cache:1110` 在任何 await 之前；CancelledError 路径独立 flag `_run_cancelled:581` | 
| 决策 4：denied 不走在飞 tool_call 收口；reason_code 落点 registry.py:172 | 是 | `registry.py:170-183`（`reason_code="denied"`）；denied 工具不进 running（bugfix-367 保证）；M4 reconcile 只针对 `running_tool_calls` 集合（已 pop 的不碰） |
| 决策 5：旁路 reason 字段，不扩 status 枚举 | 是 | 全链 7 跳均用 `reason` 旁路字段，status 仍 `completed`/`failed`；前端仅在已走非 running 分支后多读 reason（`tool-calls-panel.tsx:95`） |

### 架构自洽性（§4.3）

- 依赖方向：M1/M3 纯 kernel 内部（`core/platform`），M2/M4 跨 kernel→Gateway→IM 均走事件流（`permission_request` SSE + `streaming_delta`），无产品包反向 import `agent.core`/`agent.platform`。
- reason_code 全链走 IM 事件/REST 透传，没有跨进程直接访问 kernel 内存。
- 注释风格符合规范：public API 有 Google 风格 docstring（如 `_recover_orphaned_tool_calls:1046`）；注释写 why/约束而非 what；bugfix-410 issue 号标注一致。

---

## Issues

### CRITICAL（提 PR 前必须修）

无。

### WARNING（应该修）

无。

### SUGGESTION（可以修）

**S1 — M3 orphan reason 合成对 `stop_reason="cancelled"` 产 `"cancelled"`，与 incident Q5 三态（timed_out/interrupted/已拒绝）不完全对齐。**

- 位置：`runtime.py:1100-1101`
- 现状：`run_stop_reason == "cancelled"` → `reason = "cancelled"`，但 incident/design 的对外用户态三类是 `timed_out`/`interrupted`/denied，没有 `"cancelled"` 这个 code。
- 实际影响：M3 的 recovery reason 写入 JSONL，用于 LLM 侧的 synthetic tool_result 文本描述（`append_tool_call_recovery`），不直接驱动前端徽标文案（徽标靠 M4 的 reconcile delta，用 `timed_out`/`interrupted`，走独立路径）。所以这里的 `"cancelled"` 不会出现在前端 REASON_LABEL_KEYS 里导致无文案——但若将来 JSONL recovery 条目的 reason 被其他消费者读到，`"cancelled"` 是一个未在接口段定义的 code。
- 建议：将 `runtime.py:1100-1101` 的 `"cancelled"` → `"interrupted"`（两者语义等价，对齐 REASON_LABEL_KEYS 可识别的 code 集合）。改动一行，风险为零。

**S2 — `test_inbound_pipeline_permission_watchdog.py` 的 `test_watchdog_timeout_emits_timed_out_reconcile` 只断言 `_emit_terminal_reconcile` 被调用了正确 reason，但未 end-to-end 断言 observer 接收到 `tool_call_completed` delta 的内容。**

- 位置：`tests/unit/personal_assistant/test_inbound_pipeline_permission_watchdog.py:161`
- 现状：用 `mock` patch 了 `_emit_terminal_reconcile`，验证调用参数，没有跑 observer 闭包验证 delta payload。
- 影响：`TestTerminalToolCallReconcile`（`test_inbound_pipeline_streaming.py:472`）已单独覆盖 observer reconcile 路径，所以实际覆盖完整，只是在 watchdog 测试里用 mock 而非真实 observer——不是漏洞。
- 建议：可选择在 watchdog 测试里也断言 streaming_delta 的完整 payload，提升覆盖深度；非阻塞。

---

No critical issues. 2 suggestion(s) noted (S1 is a one-liner improvement worth doing; S2 non-blocking). Ready for PR (with noted improvements).
