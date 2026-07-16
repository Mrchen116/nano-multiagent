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
- Commits: `c697a8eac`（C1 red tests），`4f759badf`（C2 implementation）。

## R2 — relay error 终态与后续队列恢复

- Context: Round 3 reviewer 留存的真实会话显示 `send_message(to=<不存在的 conversation_id>)` 在 tool call 后一直没有 tool result，IM 可见 agent placeholder 最终被 watchdog 回收；之后同会话用户消息只有 `message.sent`，没有 `relay.accepted`，但 node heartbeat 仍 online，重启 Gateway 才恢复。代码根因是 IM 返回 `type=error` 后，`IMConnectionManager` 只记 `error_ack`，没有结束 `_awaiting_ack_type`、弹出 `_pending_frames[0]` 或完成 `ack_future`。`agent.message` 因此永久占据唯一串行出站队头，run 卡在 `send_message`，后继 lifecycle / streaming frames 全部排在其后；heartbeat 是独立通道，所以节点仍显示 online。
- Decision: IM websocket `serve()` 给所有 handler error 补充原请求 `message_type`。Gateway 把匹配当前 serialized frame 的 error 当 negative ack：弹出该帧、以 `IMFrameRejectedError` 结束调用者、记录 rejected event、继续 flush 下一帧；不相关 error 只记录，不误伤可能并行到达的 heartbeat。连接不因业务拒绝断开。
- Rationale: 每次只允许一个 ack-bound frame 在途，原 request type 是足够且不会跨 heartbeat 误配的 correlation key。业务拒绝属于该 frame 的显式 terminal，而不是 transport failure；transport 断开仍保留既有 retry 队头语义。
- Evidence:
  - Tests: IM websocket protocol、rejected-frame queue recovery、既有 downstream-error keepalive、成功 agent-message ack 与 handler invalid-source 共 `6 passed in 0.71s`；新 regression 证明 rejected `agent.message` waiter 失败后 `node.report` 自动成为下一在途帧并 ack，pending queue 清空。
  - Entry: ephemeral IM `:63546` + Gateway `wt-refactor-463-M6-81129` + deterministic Anthropic SSE LLM。原帧为 `agent.message {to: conversation:missing-m6, text: M6BAD7F3A}`；真实 session tool result 为 `IM rejected agent.message frame (invalid_agent_message): conversation_id not found`，同一 run 随后完成 `ERROR-HANDLED-M6BAD7F3A`。
  - Frontend State Matrix: N/A。
  - Browser QA: N/A；黑盒从 IM public HTTP 入口驱动。
  - E2E/Regression: 同 conversation `6d63a53fca9641cda35c95e81985d430` 的后继 `M6SAME9C2D` completed；新 conversation `8534e98ef4304e7196e30cf7540f8fa1` 的 `M6NEW4B8E` completed。三段 agent reply 均由 IM DB 观测为 completed；node 最后心跳 `2026-07-16T08:42:09.239792Z` 仍 online，IM log 只有 1 次 Gateway websocket accept，证明全程没有 Gateway restart / reconnect。
  - Visual/Interaction: N/A。
  - Prototype Comparison: N/A。
- Rollback: 回退 `bfa2efb9e` 会恢复“error 只记录、pending head 永不结束”的队列毒化行为。
- Commits: `914e15825`（C1 red tests），`bfa2efb9e`（C2 implementation）。

## R3 — permission watchdog 与整体资源收敛

- Context: 待实施。
