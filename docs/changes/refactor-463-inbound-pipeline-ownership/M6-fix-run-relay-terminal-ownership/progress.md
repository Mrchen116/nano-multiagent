# refactor-463-M6 — Progress

## R1 — public try-steer seam 与唯一 fallback run

- Context: Gateway marker 在 terminal observer 完成前仍表示 active，但真实 Kernel run 已可能 terminal。旧代码调用 `submit(steer=True)`；Kernel 在无法注入时会自行创建新 run，coordinator 随后又把同一输入排入自己的 FIFO，形成 orphan run + 第二次 submit。测试 fake 原先把 lost steer 伪装成“旧 run id + injected=False”，没有模拟 public SDK 的 create-on-fallback 语义。
- Decision: 在 public `agent.sdk.Kernel` 增加 `try_steer()` inject-only seam；返回 `None` 明确保证不创建 run。`submit(steer=True)` 内部复用该 seam 后仍保留“拒绝时创建普通 run”的既有兼容行为。Gateway coordinator 只调用 `try_steer()`，失败后由其唯一 FIFO owner 创建一个 normal run；测试 fake 同步到该 public contract。
- Rationale: normal admission 与 per-session FIFO 属于 Gateway coordinator，Kernel 只回答 active run 能否原子接收 steer。把“尝试注入”和“创建 fallback”拆开后，两层不再同时拥有 fallback run。
- Evidence:
  - Tests: `pytest -q` 覆盖 2 个 public SDK contract、既有 submit-steer compatibility、完整 admission 文件和真实 Kernel integration，共 `11 passed in 1.36s`。
  - Entry: `tests/integration/test_session_run_coordinator_real_kernel.py` 在真实 Kernel terminal、Gateway observer 仍阻塞的确定性窗口发第二条同会话消息；修复前实际产生 3 次 LLM request，修复后只有 2 次且第二条输入只进入一次。
  - Frontend State Matrix: N/A。
  - Browser QA: N/A。
  - E2E/Regression: public contract、controlled coordinator regression 与 real Kernel/coordinator integration 均已落库；真实 IM 产品旅程统一在 R2/R3 执行。
  - Visual/Interaction: N/A。
  - Prototype Comparison: N/A。
- Rollback: 回退 `4f759badf` 恢复 Gateway 调用 `submit(steer=True)`；这会重新引入 terminal window 的 orphan/duplicate run。
- Commits: `c697a8eac`（C1 red tests），`4f759badf`（C2 implementation），`65fa3d1b8`（C3 evidence）。

## R2 — relay error 终态与后续队列恢复

- Context: Round 3 reviewer 留存的真实会话显示 `send_message(to=<不存在的 conversation_id>)` 在 tool call 后一直没有 tool result，IM 可见 agent placeholder 最终被 watchdog 回收；之后同会话用户消息只有 `message.sent`，没有 `relay.accepted`，但 node heartbeat 仍 online，重启 Gateway 才恢复。代码根因是 IM 返回 `type=error` 后，`IMConnectionManager` 只记 `error_ack`，没有结束 `_awaiting_ack_type`、弹出 `_pending_frames[0]` 或完成 `ack_future`。`agent.message` 因此永久占据唯一串行出站队头，run 卡在 `send_message`，后继 lifecycle / streaming frames 全部排在其后；heartbeat 是独立通道，所以节点仍显示 online。
- Decision: IM websocket `serve()` 给所有 handler error 补充原请求 `message_type`。Gateway 把匹配当前 serialized frame 的 error 当 negative ack：弹出该帧、以 `IMFrameRejectedError` 结束调用者、记录 rejected event、继续 flush 下一帧；不相关 error 只记录，不误伤可能并行到达的 heartbeat。连接不因业务拒绝断开。
- Rationale: 每次只允许一个 ack-bound frame 在途，原 request type 是足够且不会跨 heartbeat 误配的 correlation key。业务拒绝属于该 frame 的显式 terminal，而不是 transport failure；transport 断开仍保留既有 retry 队头语义。
- Evidence:
  - Tests: IM websocket protocol、rejected-frame queue recovery、既有 downstream-error keepalive、成功 agent-message ack 与 handler invalid-source 共 `6 passed in 0.71s`；新 regression 证明 rejected `agent.message` waiter 失败后 `node.report` 自动成为下一在途帧并 ack，pending queue 清空。
  - Entry: ephemeral IM `:65132` + Gateway `wt-refactor-463-M6-87178` + 真实 LLM_PROXY 上游 `kimiCoding:K2.6`。模型实际发出 `send_message(to=conversation:missing-m6-real, text=M6TOOLBAD1D3E)`；session tool result 为 `tool execution failed: send_message: IM dispatch failed: IM rejected agent.message frame (invalid_agent_message): conversation_id not found`，同一 run 随后完成 `INVALID-HANDLED-M6TOOLBAD1D3E`。
  - Frontend State Matrix: N/A。
  - Browser QA: N/A；黑盒从 IM public HTTP 入口驱动。
  - E2E/Regression: 同 conversation `aa12bf9d54424f17beb50d4b59b6eca0` 的后继 `M6TOOLSAME2E4F` completed；新 conversation `a993b9126d884ac9b9097bd818a565e7` 的 `M6TOOLNEW3F5A` completed。三段 agent reply 均由 IM DB 观测为 completed；node 心跳从 `08:50:35` 推进到 `08:51:35` 且保持 online，IM log 的 `gateway_ws_connections=1`，证明全程没有 Gateway restart / reconnect。
  - Visual/Interaction: N/A。
  - Prototype Comparison: N/A。
- Rollback: 回退 `bfa2efb9e` 会恢复“error 只记录、pending head 永不结束”的队列毒化行为。
- Commits: `914e15825`（C1 red tests），`bfa2efb9e`（C2 implementation），`81e93a122`（C3 evidence）。

## R3 — permission watchdog 与整体资源收敛

- Context: terminal stream owner 原先对每次 `anext(stream)` 固定使用 run idle timeout。permission request 发出后，run 合法地等待用户任意时长且没有新 stream event，因此会被误判为 idle 并 interrupt；同时 R1 引入 public `try_steer` 后，一个旧 SSE 测试 Kernel fake 没有同步接口，完整门禁暴露出该 contract drift。
- Decision: `_await_terminal_run()` 用命名的 `watchdog_timeout` 持有当前策略：普通运行取配置值，收到 `permission_request` 切为 `None` 完全暂停，收到 `permission_resolved` 恢复配置值。测试同时证明 permission 等待超过 timeout 仍存活、resolved 后再次静默会被回收；旧 fake 补齐 inject-only public seam，不改变生产行为。
- Rationale: permission pending 是明确的外部等待状态，不是 run 无进展；恢复后重新启用同一命名 timeout，仍保留真正 stalled run 的资源收敛。timeout 状态由唯一 terminal stream consumer 驱动，避免另建 timer owner。
- Evidence:
  - Tests: terminal / stop / shutdown / dispatcher focused 回归 `29 passed`；本 milestone 相关 focused suite `138 passed`；修正旧 fake 后 targeted pipeline `6 passed`；最终 `pytest -q -m "not e2e"` 为 `3401 passed, 1 skipped, 20 deselected`。
  - Entry: `tests/unit/personal_assistant/test_session_run_coordinator_terminal.py` 用可控 stream 让 pending permission 等待超过 idle timeout，再 resolve 并验证 timeout 重新生效。
  - Frontend State Matrix: N/A。
  - Browser QA: N/A。
  - E2E/Regression: 在真实 IM + Gateway + LLM 环境执行 `scripts/e2e-critical.sh -q -k stop_aborts_active_run`，结果 `1 passed, 16 deselected in 33.01s`；真实 invalid relay 后同/新会话恢复证据见 R2。隔离栈随后由 `e2e-down.sh` 停止并核对 PID。
  - Visual/Interaction: N/A。
  - Prototype Comparison: N/A。
- Rollback: 回退 `91232958f` 会恢复 permission pending 被 idle watchdog 误杀；回退 `d8c839a55` 只会令旧测试 fake 再次偏离 public SDK contract。
- Commits: `f0d6ff142`（C1 red tests），`91232958f`（C2 implementation），`d8c839a55`（compatibility fake）。
