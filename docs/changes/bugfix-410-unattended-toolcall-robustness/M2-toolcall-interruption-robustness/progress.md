# bugfix-410-M2 — Progress

## 启动澄清记录

- 范围确认（与 orchestrator）：design Milestone 表 M2 行 = runtime.py / core/session/ / core/tools/{registry,base}.py / gateway/inbound_pipeline.py / personal_assistant/main.py / IM/application/relay_watchdog.py / IM tool_call 持久化 / 前端 tool-calls-panel.tsx。不碰 auto_mode_gate（M1）。
- reason_code 链端到端 6 跳已核实（见开工信）。整条链单一 owner = M2。

## R1 — #82 恢复式 finally 覆盖 CancelledError

- Context: bugfix-402 的 eager-recovery 在 try 体末尾、靠 turn_meta.stop_reason 触发。外部 cancel()（gateway run-idle 看门狗）在工具/LLM 的 await 点打断 run 时，CancelledError 穿透、run 回不到迭代边界、不写 turn_meta → `_run_stop_reason=None` 不匹配 `in ("aborted","cancelled")` → 漏补悬空 tool_call + 脏内存缓存留存 → 下条消息 cache-hit 复用脏历史 → 砖化到进程重启（#82 reopen）。
- Decision: 把 recovery 抽成 `_recover_orphaned_tool_calls`，从 try 体移入 stop_reason-**独立**的 `finally`。新增 `except asyncio.CancelledError` 仅置 `_run_cancelled=True` 并 re-raise（保留 cancel 语义）。finally 无条件扫 `all_messages` 未闭合 tool_call。
- Rationale:
  - 无条件扫描不误伤正常完成 run——其 tool_call 都有对应 tool result，orphan 集天然为空、return no-op。
  - 两步保护级别不对等（按 design 必读陷阱）：`invalidate_session_cache` 是 load-bearing 自愈（同步原子 dict pop、无 await），放 finally 最前、任何 I/O await 之前，cancel 传播中也必跑完、无需 shield；`append_tool_call_recovery`+flush 是 out-of-band 加速、做 I/O，cancel 路径走 `asyncio.shield` best-effort，失败由下次 `prepare_transcript_for_run` 兜底。
  - reason 不依赖 turn_meta：cooperative abort→interrupted / cancel→cancelled；无 turn_meta（CancelledError 穿透）合成 interrupted。
- Evidence:
  - Tests: `tests/unit/test_agent_runtime.py -k "recovery or cancellederror"` 6 passed（2 新 CancelledError + 4 既有 abort/cancel/cache-hit/completed 无回归）。broader runtime+session+loop+executor+streaming 424 passed。ruff check + format 通过。
  - Entry: 后端内部恢复路径，真实入口=regression 测 `test_runtime_recovery_on_cancellederror_visible_to_next_run`——复现 #82 reopen 砖块：同进程内 cancelled run 后第二个 run 的 history 含 `is_recovery=True` 的 synthetic tool result（修前 assert False，修后通过）。
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: `tests/unit/test_agent_runtime.py::test_runtime_recovery_on_cancellederror_passthrough` + `::..._visible_to_next_run`（落库回归）
  - Visual/Interaction: N/A
- Rollback: revert C2 commit（finally 重构）→ 回 R1 C1 红测态
- Commits: C1=plan 后第 1 个 test commit, C2=fix(...R1) finally 重构, C3=本段 docs

## R2 — #98 看门狗豁免（Gateway run-idle + IM relay liveness marker）

- Context: 等人工权限决策是合法无事件停顿，但两个 120s 看门狗都判它卡死杀掉——Gateway run-idle（`inbound_pipeline.py:849` 消费事件流）+ IM relay（`relay_watchdog.py` 扫 DB last_event）。用户看权限卡片 >120s 必踩，点 Allow once 回到已死 run（#98）。
- Decision: 两个看门狗机制不同，豁免落地方式不同（决策 1）。
  - **Gateway run-idle**：`_await_terminal_run_async` 见 `permission_request` 置 `awaiting_permission=True`，对下个 `anext` 用 `wait_for(timeout=None)`；见任一后续 target 事件清豁免恢复 120s。
  - **IM relay**：marker 靠 liveness 非存在性（决策 1 + 风险缓解）。新增 `messages.awaiting_permission_at` 列；`append_permission_request` 置 marker、`update_permission_resolution` 末个 pending 才清、`on_message_completed` 终态清；relay 看门狗新增 `permission_crash_threshold_seconds`（默认 600s，独立于 120s），SQL `NOT (awaiting_permission_at IS NOT NULL AND >= permission_cutoff)` 豁免 fresh marker、reap stale marker；IM `_handle_heartbeat` 每跳 `refresh_awaiting_permission_markers(本节点 agent)` touch 时间戳。
- Rationale:
  - `permission_request` 事件已存在（`runtime.py:1320`），零新增噪音、语义精确（决策 1）。
  - 无限等待 + interrupt 兜底（决策 2）：Gateway 用 timeout=None；relay 靠 heartbeat 持续刷新 → Gateway 活着真无限等。
  - marker 三条兜底缺一不可（避免比原 bug 更糟的永久 ghost）：①permission_response 清；②run 终态清；③崩溃兜底——Gateway 崩溃停刷新 → marker stale 超 600s → relay 照常 reap。
- Evidence:
  - Tests: Gateway `test_inbound_pipeline_permission_watchdog.py` 3 passed（豁免不杀 / 真卡死仍杀 / 豁免后再卡仍杀）；relay `test_relay_watchdog.py` 14 passed（含 2 新 fresh-skip/stale-reap）；marker 生命周期 `test_event_bridge.py` 7 passed（置/终态清/resolve清/heartbeat refresh 只动 marked running）。全 IM 套件 297 passed。pipeline 套件 558 passed。
  - Entry: 跨进程行为，真实入口=控制流单测——`_ControlledStreamKernel` 用 asyncio.Queue 驱动真实 `_await_terminal_run_async`（非 stub）跑到 permission_request 后停顿 0.4s（>0.1s idle）断言无 cancel；relay 用真实 sqlite + 真实 SQL 断言 fresh marker 不 reap / stale reap。
  - Frontend State Matrix: pending「等待批准」徽标本身依赖既有 feat-333 permission_request 卡渲染（已存在），R4 补 reason 文案；本 R 不改前端。
  - Browser QA: 延后到 R4（reason 全链 + 前端文案统一做视觉自测）
  - E2E/Regression: `tests/unit/personal_assistant/test_inbound_pipeline_permission_watchdog.py` + `tests/im_service/unit/test_relay_watchdog.py::*permission_marker*` + `tests/im_service/unit/test_event_bridge.py::*permission*/*heartbeat_refresh*`（全落库）
  - Visual/Interaction: N/A（R4 做）
- Rollback: revert R2 的两个 fix commit（Gateway 豁免 + IM relay marker）
- Commits: C1×2（Gateway 红 + relay 红）, C2×2（Gateway 豁免 fix + IM relay/marker fix）, marker 生命周期回归 test, C3=本段 docs

## R3 — #97 终态在飞 tool_call reconcile

- Context: run 异常终止（看门狗超时/崩溃/interrupt）时，已发 tool_start 但未收 tool_end 的 tool_call 永远收不到 `tool_call_completed`（observer 只在 tool_end 发，`main.py:3114`）→ IM 徽标永久转圈（#97）。
- Decision: observer 跟踪 running tool_call（决策 4）。observer 闭包持 `running_tool_calls: dict[run_id, dict[call_id, name]]`，tool_start 记/tool_end 清。新增合成事件 `run_terminal_reconcile`：observer 对该 run 剩余在飞 tool_call 补发 `tool_call_completed` status=failed + reason。pipeline `_emit_terminal_reconcile(run_id, reason)` 在两条终态路径喂该事件——看门狗 TimeoutError→`timed_out`、终态 failed/cancelled（含 stream ended without terminal）→`interrupted`。
- Rationale:
  - 「已拒绝」不走在飞收口（决策 4）：deny 的工具从不进 running（bugfix-367），在 R4 由 registry denied + tool_result ✕ 渲染，不在此路径。
  - 已完成工具 tool_end 时已 pop 出 running 集，reconcile 不碰它们（含 exit≠0 的失败命令保留原终态）。
  - reason 旁路字段（决策 5），不扩 status 枚举——status 仍 failed，前端 R4 读 reason 决定文案。
- Evidence:
  - Tests: observer `test_inbound_pipeline_streaming.py::TestTerminalToolCallReconcile` 3 passed（在飞收口带 reason / 已完成不改写 / interrupted reason）；pipeline `test_inbound_pipeline_permission_watchdog.py` 5 passed（含 2 新 timed_out/interrupted 喂事件断言）。pipeline+streaming 套件 571 passed。
  - Entry: 跨进程 observer→IM，真实入口=用真实 `_build_kernel_event_observer` 闭包跑 tool_start/tool_end/reconcile 序列，捕获真实 `manager.send_json` 的 streaming_delta；pipeline 用真实 `_await_terminal_run_async` 跑看门狗超时/终态 failed，断言真喂 reconcile 事件给 observer。
  - Frontend State Matrix: reason 文案在 R4 做（本 R 后端补发 reason，IM ToolCall 字段未加→reason 暂被 IM 丢弃，R4 补全链）
  - Browser QA: R4 统一做
  - E2E/Regression: 上述两组测试全落库
  - Visual/Interaction: N/A（R4）
- Rollback: revert R3 fix commit
- Commits: C1=observer reconcile 红测, C2=observer 跟踪+pipeline 喂事件 fix, C3=本段 docs
- Note(给 R4): reconcile delta 已带 `reason` 字段，但 IM ToolCall model / 透传 / 前端文案在 R4 补；R3 后 reason 暂在 IM `_parse_tool_call` 处丢弃，R4 接通后端到端贯通。

## R4 — reason_code 全链 + 前端文案

- Context: R3 让 Gateway 补发带 reason 的 tool_call_completed，但 reason 字段尚未端到端贯通——ToolResult/IM ToolCall 无字段、denied 来源（registry block）未盖 reason_code、前端无文案。本 R 接通全链（决策 4/5）。
- Decision: 旁路 reason 字段不扩 status 枚举（决策 5）。链路 7 跳：
  1. `core/types.py` ToolResult 加 `reason_code`；
  2. `registry.py:172` block 收口盖 `reason_code="denied"`（与给模型看的自由文本 reason 并存，决策 4——auto block 与用户 Deny 都走此处）；
  3. `tool_executor.py` except 从 ToolError.details 提取 reason_code 进 ToolResult（+ finally 时长重建保留）；
  4. `loop.py` on_tool_result 事件带 reason_code；
  5. `realtime_stream.py` tool_end SSE 带 reason_code；
  6. `main.py` observer tool_end → tool_call_completed delta 带 reason；
  7. IM: ToolCall model `reason` 字段 + gateway_handler `_parse_tool_call` 解析 + event_types/repositories 序列化+持久化+解析 + REST DTO（`api/routes/messages.py` ToolCallPayload，浏览器自测补，见 design Changelog） + 前端 ToolCall TS + panel REASON_LABEL_KEYS 文案 + i18n。
- Rationale:
  - denied 与自由文本 reason 并存不复用——复用会污染模型可读理由（决策 4）。
  - 前端 denied→已拒绝 / timed_out→执行超时 / interrupted→已中断；未知 reason 不渲染徽标（不显示裸 code）。
  - pending「等待批准」由既有 feat-333 permission_request 卡承担（#98 豁免保住其 live），不在 tool-calls-panel 路径，本 R 不动。
- Evidence:
  - Tests: 后端链路 `test_toolcall_reason_code_chain.py` 2 passed（registry 盖 denied + 自由文本并存 / executor 提取进 ToolResult）；executor/367 回归 19 passed；IM 序列化 `test_event_bridge/ws_event_types/gateway_handler` 71 passed；contract 同步后 127 passed；前端 `tool-calls-panel.test.tsx` 8 passed（含 3 新 reason 徽标参数化 + 1 无徽标）；前端全套 382 passed；tsc clean。broad 后端 1124 passed。
  - Entry: **真实浏览器端到端自测**——seed 一条 agent 消息含 4 个 tool_call（read=completed 无 reason / bash=denied / bash=timed_out / edit=interrupted），起真实 IM（ephemeral 端口 + 隔离 DB），真实登录注入 token，浏览器打开 /chat 展开 tool-calls-panel：徽标渲染 Denied / Timed out / Interrupted（红色），completed 行无徽标；REST API `GET /conversations/{id}/messages` 验证 reason 字段透传（denied/timed_out/interrupted）。
  - Frontend State Matrix: default(completed 无徽标)✓ / running(既有 pulse 不回归)✓ / failed+denied✓ / failed+timed_out✓ / failed+interrupted✓ / empty(0 calls return null 既有)✓ / long content(pre 滚动既有)✓ / mobile 375x812✓ / desktop 1280x720✓ / dark mode(oklch 红配色)✓。
  - Browser QA: URL=http://127.0.0.1:<ephemeral>/chat/conv-vis；路径=登录(token 注入)→打开会话→展开 tool-calls-panel；console 仅 WS reconnect ERR_CONNECTION_REFUSED（headless 时序伪影，REST 全 200，徽标走 REST 历史加载）；network 无失败 REST 请求。
  - E2E/Regression: 后端链路 + IM 序列化 + 前端 vitest 全落库；浏览器自测为一次性视觉证据（截图保留）。
  - Visual/Interaction: `ACCEPTANCE/bugfix-410-m2/r4-reason-badges-desktop.png`（1280x720）+ `r4-reason-badges-mobile.png`（375x812），对照设计 Q4「按原因区分」——三态文案 + 红色徽标，与 completed 行视觉区分明显，两 viewport 无溢出。
- Rollback: revert R4 的两个 fix commit（reason 全链 + REST DTO）
- Commits: C1=reason_code denied 链路起点红测, C2=全链透传+前端文案+contract 同步 fix, REST DTO fix(浏览器自测补), C3=本段 docs
- Design 修订: design Changelog 补 messages.py DTO 文件清单遗漏（仅本 milestone 内，不影响其他 milestone）。
