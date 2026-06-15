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

（待补）

## R4 — reason_code 全链 + 前端文案

（待补）
