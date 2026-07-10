# bugfix-417-M3 — Progress

## 开工记录

- 上下文已读全：design.md（决策 2/3/4/5 + 接口与数据流 B + watchdog 重定义伪逻辑 + M3 推进顺序）、三份 delta-spec（kernel ADDED liveness / gateway 两条 MODIFIED / im REMOVED+ADDED+MODIFIED）、5 个目标文件 + 关联（loop.py LLM 调用点、context.py publish_session_event/request_permission、main.py observer 链路、gateway_handler streaming_delta kinds、event_bridge._emit、relay_watchdog SQL、bash.py timeout 路径）。
- 范围确认：5 文件 + 失败态分流必须的关联点。worktree 从 unit/bugfix-417 HEAD（含 M1 强制 cancel + M2 bash 进程组）切出。
- test_command = `PYTHONPATH=src python -m pytest`；基线全绿（2665 passed）。
- 不变量守住：watchdog 仍收真卡死（心跳由真前进的执行层发，非"Task 存在就 tick"）；串行锁不破；bash 回显不破（C 层 bash_runner 未碰）；崩溃停心跳→两侧 120s 内仍被收。

## R1 — 工具心跳解缓冲（实时 dispatch）

- Context: `tools/registry._emit_execution_update`（registry.py:206）把工具运行期的 `phase:running` 心跳 append 到 `_pending_updates`，跑完才循环 flush（:247）。静默长命令（`sleep 200`）整段运行期 observe 链零事件 → 两个 watchdog 看到"输出静默"误杀（B 层事故链根因之一）。
- Decision: 删 `_pending_updates`；execute 内捕获 `asyncio.get_running_loop()`；`_emit_execution_update`（从 `asyncio.to_thread` 工作线程调）经 `run_coroutine_threadsafe` 把 `_dispatch_observe("tool_execution_update", ...)` 调度回 execute 所在 loop，实时 dispatch。最终 output 更新仍走原 dispatch（不重复发）。observe fail-open 保持，丢心跳退化为"按业务事件判存活"。
- Rationale: 心跳必须由"确实在前进的执行层"发出（design 决策 2/3 不变量）；跨线程→loop 必须 `run_coroutine_threadsafe`（既有约束）。
- Evidence: `tests/unit/test_bugfix_417_tool_heartbeat_realtime.py`（慢工具在 run() 阻塞期断言 observe 链已收到 ≥1 个 tool_execution_update）；`test_streaming_tool_executor.py` + `test_bugfix_367_tool_call_observe_timing.py` 回归 19 passed。

## R2 — realtime_stream 加 on_tool_execution_update publisher

- Context: realtime_stream 只监听 tool_call/tool_result/message_end/turn_end，`tool_execution_update` 无 publisher，R1 的实时心跳到不了 `kernel.stream`。
- Decision: 加 `on_tool_execution_update` handler 注册到 `"tool_execution_update"`；携带 `phase` 的更新 → `publish_session_event("run_heartbeat", {run_id, source:"tool", phase, elapsed_ms})`。仅 liveness 不渲染；最终 output 更新（无 phase，带 output）不 publish（避免噪音）。
- Evidence: `tests/unit/platform/hooks/test_realtime_stream_heartbeat.py`（running→publish / final-output→不 publish / 无 run_id→skip）；`test_realtime_stream_events.py` 回归 8 passed。

## R3 — runtime LLM-await + parked-on-permission await-bound ticker

- Context: 非流式 LLM 等首 chunk、parked 等权限决策两类窗口整段无业务事件。
- Decision: 新建 `agent/core/agent/liveness.py`（core，无 platform 依赖，publisher 经注入端口）：`liveness_ticker`（async ctx manager）/ `_with_liveness_heartbeat`（包 async iterator）/ `_emit_liveness_heartbeats` / publisher 适配器。await 前起、返回/异常/cancel 即停，周期发同款 `run_heartbeat`。
  - loop.py：`async for llm_msg in _with_liveness_heartbeat(stream, publish=session_event_publisher(active_hook_ctx), run_id, source="llm")` 包住 LLM 流消费。
  - runtime.py `_permission_requester`：`asyncio.create_task(_emit_liveness_heartbeats(publish=_broker_publish_adapter(publisher_for_broker), run_id, source="permission"))` 在 await 前起，已有 `finally` 里 cancel+drain。
- Rationale: 三类 liveness 源同一事件类型（`run_heartbeat`）进 `kernel.stream`，两个 watchdog 一视同仁（决策 4）。ticker await-bound→证明 progress 而非 Task 存在（决策 2 不变量）。默认间隔 10s `<<` 120s（决策 3 硬约束）。
- Evidence: `tests/unit/test_bugfix_417_liveness_ticker.py`（8 tests：emit-during-await/stop-after、无 publisher no-op、异常下 teardown、`_with_liveness_heartbeat` 间隙 tick、permission-await 镜像 emit-then-stop-on-resolve）；runtime/loop/permission 回归 34+29 passed。

## R4 — 两 watchdog liveness 重定义 + 失败态区分

- Context: Gateway watchdog 有 `awaiting_permission` 特例分支（inbound_pipeline.py:853/860/892）；IM relay_watchdog 有 `awaiting_permission_at` 专用 marker 豁免（SQL + `permission_crash_threshold_seconds`）；watchdog 收尸用 `reason="timed_out"` 与真·工具超时混淆。
- Decision:
  - Gateway：移除 `awaiting_permission` 分支，任意 stream 事件（含 `run_heartbeat`）即重置 idle；`reason` `timed_out`→`stalled`（决策 5）。observer（main.py）加 `run_heartbeat`→IM `node.streaming_delta` kind=run_heartbeat。`_map_kernel_event_to_run_activity` 加 `run_heartbeat`→`agent.run.heartbeat`。
  - IM：gateway_handler 加 `run_heartbeat` kind→`EventBridge.on_run_heartbeat`（read-only `get_conversation_id` + `_emit` append `run.heartbeat` conversation_events 行，推进 `last_evt`，不改 message content/status）；relay_watchdog 移除 `awaiting_permission_at` 豁免子句 + `permission_crash_threshold_seconds`，统一按 `last_evt` 判存活；node-heartbeat 不再 refresh marker。崩溃停心跳→`last_evt` stale→正常收（决策 4，比旧 600s 更快）。
  - 失败态：bash 自身 timeout 的两处 ToolError 带 `details["reason_code"]="tool_timeout"`（经 StreamingToolExecutor 既有 reason_code 提升链到 tool_end 徽标）；前端 `tool_timeout`→执行超时、`stalled`→已中断（保留旧 `timed_out`/`interrupted` 兼容历史行）。
- 既有 `interrupted` 盘点（决策 5 reviewer Rec #2）：inbound_pipeline 显式 abort/stream-ended 路径仍用 `interrupted`（用户/系统显式打断），与 watchdog liveness 收尸 `stalled` 区分清楚；文案前端都归"已中断"但 reason 常量分开，无孤儿分支。
- Evidence:
  - `test_inbound_pipeline_permission_watchdog.py` 重写（permission 靠心跳存活 / 崩溃停心跳被收 / 真静默被收 reason=stalled / 静默长命令靠心跳存活 / post-decision stall 被收）7 passed。
  - `test_relay_watchdog.py` 重写（fresh heartbeat 不收 / stale heartbeat 收 / 格式对齐）17 passed。
  - `test_event_bridge.py` 新增 `on_run_heartbeat`（append 行不改 message）9 passed；`test_streaming_chain.py` 新增 run_heartbeat kind；`test_inbound_pipeline_streaming.py` 新增 observer 转发；`test_inbound_pipeline_sse.py` map 加 run_heartbeat；`test_tools_bash_task.py` 加 reason_code=tool_timeout 断言。
  - 前端 tsc 无错、vitest chat/v2 PASS(183)。

## 收口验证

- 全测试树：`pytest tests/ --collect-only` 2671 collected 无导入错误；`pytest tests/ -m "not e2e"` 2666 passed / 0 failed / 1 skipped（pre-existing）。
- `ruff check src/ tests/` All checks passed；改动文件 `ruff format --check` 全部 already formatted。
- contract whitelist 行锚点（runtime.py:172→177）随 R3 import 位移已更新。
