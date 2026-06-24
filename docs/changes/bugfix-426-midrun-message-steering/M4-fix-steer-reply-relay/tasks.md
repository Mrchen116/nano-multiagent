# bugfix-426-M4: fix-steer-reply-relay (#140) — Tasks

> 对齐: ../design.md（决策 5/6 + 决策 3 收窄；现状分析「#140 缺陷」段；M4 数据流段）

## 目标

run 收尾瞬间 steer 不再分裂出新 run_id：注入消息由同一个 run 续轮消费（决策5），
对插话的回复出现在排于 steer 消息之后的新气泡里、全程流式可见、旧气泡干净收尾（决策6），
不超时、不黑屏、不丢中间事件。决策3 的 continuation 收窄为仅兜异常终止。

## 退出标准

- [ ] 模型末轮无 tool_call、终态提交前一刻 inject → 同一 run_id 续跑（非新 run）、`injected=True`
- [ ] inject 在 `commit_terminal` 之后 → `injected=False`（lost-race，调用方 fallback 新 run）
- [ ] kernel 在 drain 真正消费注入消息处发信号事件（单测断言）
- [ ] 决策3：正常完成路径不再产生 continuation（由决策5 续跑覆盖）；异常终止仍 continuation
- [ ] gateway 收信号 → 收尾旧气泡 A（完成态）+ 开新气泡 B（排在 steer 之后），后续事件流式进 B
- [ ] 新增 e2e 复现 #140（收尾瞬间 steer → 新气泡流式、旧气泡完成态、无 relay-idle 超时）修前红修后绿
- [ ] 全测试树 not-e2e 全绿

## 测试策略

- 被测行为（来自退出标准）：
  1. loop 末轮 re-drain 复检：终态前 inject → 同 run 续轮（不 break）
  2. commit_terminal 后 inject → False
  3. 消费注入消息处发 `pending_injection_consumed` observe 事件（带 run_id）→ realtime_stream 转 `injection_consumed` session 事件
  4. 决策3 收窄：正常完成 terminal-inject 不再 stranded-continuation（已由决策5 续跑吞掉）；异常终止仍 continuation
  5. gateway observer 收 `injection_consumed` → close A + open B 序列
  6. 真端到端 #140 旅程（收尾瞬间 steer）
- 已有测试在：
  - `tests/unit/agent/runs/test_run_control_pending_origin.py`（扩展：commit_terminal）
  - `tests/unit/test_agent_loop.py`（扩展：末轮 re-drain 续跑 + 消费信号）
  - `tests/unit/test_runs_registry.py`（扩展：commit 后 inject=False + 决策3 收窄）
  - `tests/unit/test_realtime_stream_*`（新建/扩展：injection_consumed 转发）
  - gateway observer：定位 main.py observer 现有测试或 inbound_pipeline 测试（扩展）
- 落层/目录/marker：tests/unit/（worker 轨）、tests/e2e/（#140 复现，marker e2e）
- 可选依赖 importorskip：e2e 走真 Gateway 进程（scripts/e2e-up.sh），无新顶层依赖
- 本 milestone 产生的一次性验收证据（收尾删除）：reviewer 轨 e2e 栈截图/log（live 证据，记 progress 不进套件）

前端 UI 状态矩阵：N/A（本 milestone 不改前端代码；气泡 A/B 行为由 gateway→IM 协议帧驱动，IM 前端已有 message_completed/turn_start/message_delta 渲染路径，复用 `_close_old_and_restart` 同款帧序列，无新前端逻辑）。reviewer 轨在真 IM 浏览器观察气泡时序作为 live 验收证据。

## Roadpoints

### R1 — 决策5：loop 末轮 re-drain 续同一 run + commit_terminal 原子化  [DONE]

- 步骤:
  - `RunController` 加 `commit_terminal()` + `terminal_lock`（threading.Lock），加 `is_terminal_committed` / `try_commit_terminal_if_empty()`（持锁：drain 复检为空才 commit、返回是否已 commit）。
  - `loop.py:449` 终止决策处：退出前持终止锁再 drain 一次；非空 → append 进 llm_messages + `continue`（续跑同 run）；为空 → commit_terminal 后 break。
  - `registry.inject_pending_message`：持同一终止锁，已 commit → 返回 False（lost-race，调用方 fallback 新 run）。
- 验证: 红测先证「终态前 inject 被 stranded / inject 在 commit 后仍 True」，实现后转「同 run 续轮 / commit 后 inject=False」。

### R2 — 决策3 收窄：_settle_terminal_pending continuation 仅兜异常终止  [DONE]

- 步骤: 正常完成路径 stranded 已被决策5 续跑吞掉（terminal commit 后 controller 队列空）；确认/调整 `_settle_terminal_pending` 仅在异常终止（cancel/timeout/crash）仍 continuation，正常完成路径 drain 为空 → 自然 no-op。审旧测试 `test_stranded_continuation_follows_injected_origin` 是否仍反映正常路径（若正常路径不再 stranded，改测异常路径）。
- 验证: 正常完成 + 终态前 inject → 同 run 续跑、无第二个 run（决策5 覆盖）；异常终止 + inject → continuation 仍在。

### R3 — 决策6 信号：loop 消费点发 pending_injection_consumed → realtime_stream 转 injection_consumed  [DONE]

- 步骤:
  - `loop.py`：drain_pending 返回非空、append 进上下文后（round-boundary 消费点，含 mid-loop 与末轮 re-drain），`_dispatch_observe_async("pending_injection_consumed", {run_id, ...})`。
  - `realtime_stream.py`：注册 `pending_injection_consumed` handler → `publish_session_event(event="injection_consumed", {run_id})`。
- 验证: 红测断言消费点发出 observe 事件带 run_id；realtime_stream 转出 session 事件 injection_consumed。

### R4 — 决策6 气泡滚动：gateway observer 收 injection_consumed → close A + open B；#140 e2e

- 步骤:
  - `main.py` observer：加 `injection_consumed` 分支，复用 `_close_old_and_restart` 同款序列（message_completed 旧 message_id + turn_start 取新 message_id + 后续 delta 进新气泡）。
  - `inbound_pipeline._await_terminal_run_async`：确认 injection_consumed 事件（run_id 匹配）经 `_kernel_event_observer` 路由（已有 run_id 匹配即转发逻辑）。
  - 新增 e2e：收尾瞬间 steer → 断言新气泡流式、旧气泡完成态、无 relay-idle 超时（修前红修后绿）。
- 验证: e2e 红→绿；reviewer 轨真 IM 栈 live 验证气泡时序 + 无超时。
