# bugfix-417-M3: watchdog-liveness — Tasks

> 对齐: ../design.md（决策 2/3/4/5 + 接口与数据流 B + watchdog 重定义伪逻辑）
> 三份 delta-spec: ../specs/kernel/spec.md（ADDED liveness）、../specs/gateway/spec.md（两条 MODIFIED）、../specs/im/spec.md（REMOVED + ADDED + MODIFIED）

## 目标

把 liveness 心跳从三类"活着但安静"窗口（执行静默长工具 / 等 LLM 返回 / parked 等权限决策）实时流入两个 watchdog，二者重定义为 liveness 驱动；超时与卡死区分两种失败态（`tool_timeout`/"执行超时" vs `stalled`/"已中断"）。三类心跳走同一事件类型（`run_heartbeat`）经 kernel.stream 进 Gateway 与 IM，两个 watchdog 零 permission 专用特例真镜像。

## 退出标准

- [ ] R1 工具心跳解缓冲：移除 `_pending_updates`，`execution_event_callback` 经 `run_coroutine_threadsafe` 实时 dispatch `_dispatch_observe("tool_execution_update")`；observe fail-open 保持
- [ ] R2 `realtime_stream` 加 `on_tool_execution_update` publisher → `publish_session_event("run_heartbeat", {run_id, phase, elapsed_ms})`，仅 liveness 不渲染
- [ ] R3 runtime LLM-await ticker + parked-on-permission await-bound ticker：await 前起、返回/异常/resolve 即停，周期发同款 `run_heartbeat` 进 stream
- [ ] R4 Gateway watchdog：移除 `awaiting_permission` 分支（任意 stream 事件含心跳即重置）；idle 路径 `reason` `timed_out`→`stalled`；`_map_kernel_event_to_run_activity` 加 `run_heartbeat` 映射进 IM
- [ ] R4 IM watchdog：加 `run_heartbeat` streaming_delta kind 经 `_emit` 推进 `conversation_events.last_evt`；移除 `awaiting_permission_at` 专用 marker 豁免（统一 liveness）
- [ ] R4 失败态区分：bash 自身 timeout → `tool_timeout`/"执行超时"；watchdog liveness 收尸 → `stalled`/"已中断"；盘点既有 `interrupted` 语义不重叠
- [ ] `python -m pytest`（最窄相关 + 必要广度）全绿，既有 watchdog / streaming / permission 测试不回归

## 测试策略

> 规范见 docs/TESTING_GUIDE.md。

落层：

- **unit**（worker 红测 → 绿）：
  - `tests/unit/test_streaming_tool_executor.py` 扩：心跳更新在 run 期间实时 dispatch（不等 run 结束才 flush），用一个慢 tool + 计数 observe handler 断言"工具结束前已收到 ≥1 个 tool_execution_update"。
  - realtime_stream publisher：`on_tool_execution_update` 收到 phase:running 更新 → publish `run_heartbeat`（断言 event 名 + payload run_id/elapsed_ms）。
  - runtime LLM-await ticker：mock 一个慢 LLM stream（首 chunk 延迟），断言等待期 publisher 收到周期 `run_heartbeat`；stream 返回后 ticker 停。
  - permission await-bound ticker：parked 在 `request_permission`，断言等待期周期 `run_heartbeat`；resolve 后停。
  - Gateway watchdog 重定义：心跳事件重置 idle 计时；移除 permission 特例后，真静默（无心跳）仍在 timeout 后 cancel + `reason="stalled"`；崩溃停心跳仍被收（回归）。
  - IM watchdog 重定义：`run_heartbeat` 推进 `last_evt` 使活跃 run 不被收；移除 `awaiting_permission_at` 后等权限期靠心跳不被误收；真静默 stale 超阈值仍被翻 failed（回归）。
  - 失败态区分：watchdog 收尸 reason=`stalled`、bash 自身 timeout reason=`tool_timeout`，徽标/文案分流。
- **不测**：前端渲染（心跳仅 liveness，前端可忽略）；bash 进程组（M2 已覆盖）。

## 推进顺序（design M3 行 reviewer Rec #3）

R1 → R2 → R3 → R4，不可横切拆分（心跳 liveness 端到端内聚垂直切片）。
