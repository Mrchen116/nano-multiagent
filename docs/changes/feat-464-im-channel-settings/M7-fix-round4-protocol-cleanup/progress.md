# M7 — Progress

实现基线：`fb8308ae8ca6fb980fb748b9fb74140385edb8b5`。Baseline focused backend `37 passed`；focused frontend `13 passed`。

## Scope decision — 旧配置迁移移出 M7

- 用户明确不考虑旧 `config.yaml` 或历史 backup 的后向兼容、自动迁移与清理；原 M7 item 4 已停止且未产生代码/测试改动。
- 本 milestone 的安全边界仅验证 IM 通道页新建/更新不会向 `config.yaml` 写入 App Secret；既有旧配置与历史 backup 为 out-of-scope。

## R1 — Status wire owner 与 coalescing race

- Context: 旧队列用 `PendingFrame.sent` 表示发送状态，但该字段只在 awaited `websocket.send()` 返回后才置 true；send yield 期间新 status 会把正在发送的旧 frame 从 deque 删除，随后旧 result 对着新队首无法关联，FIFO 永久卡住。
- Decision: 将未发送 pending deque 与单一 `BusinessFrameOwner` 分开；flush 在进入 wire send 前先 pop 并建立 `sending` owner，send 成功后只把同 owner 转为 `awaiting_result`。ACK/result/error 直接消费 owner，不再通过可被 coalesce 的 deque 队首猜测。
- Rationale: wire 因果归属必须在第一次可能 yield 前确定；pending queue 只拥有真正未发送 frame，coalescing 因而天然无法触碰 in-flight/sent-unacked frame，也无需堆叠 `sent` flag 分支。
- Evidence:
  - Tests: C1 deterministic await-send-yield regression 稳定失败为只发送 `status-old`；C2 后 status ownership/protocol/connection/resilience focused suite `42 passed`，focused Ruff passed。
  - Entry: 公共 `send_json(channel.status)` 在真实 websocket `send` yield 时并发收到 seq3；seq2 result 只释放 seq2，随后 seq3 上 wire并由自身 result 释放。
  - Frontend State Matrix: N/A。
  - Browser QA: N/A。
  - E2E/Regression: `tests/unit/personal_assistant/test_gateway_status_frame_ownership.py::test_status_coalescing_cannot_remove_frame_after_wire_send_begins`。
  - Visual/Interaction: N/A。
  - Prototype Comparison: N/A。
- Rollback: 回退 R1 C1/C2/C3；会恢复 send yield 期间 active status 被 pending coalesce 删除的竞态。
- Commits: C1=`12e1599d2`，C2=`f81b1499e`，C3=本提交。

## R2 — 断线 incarnation supersede 与 control correlation

- Context: 旧连接一建立即并行发送 register 与业务队首，generic error 只能靠业务 deque 猜测归属；heartbeat 又绕过业务 FIFO 直接写 socket。register/heartbeat 的 error 因而可能弹掉 report/status/message，且断线重排会让旧 runtime incarnation status 抢在新 incarnation 前重放。
- Decision: wire owner 扩展为 `control|business` 两条 lane 共用的单响应槽；register ack 前只允许 control flush，ack 后启动 heartbeat、执行 on-connected convergence 并开放业务。heartbeat 也排入 control lane、使用自身 future；control error 断开当前 socket且不消费业务。断线时 control 终止、业务重排，若 pending 已有同 channel 不同 incarnation status 则把旧 owner 标为 superseded 而不重放。
- Rationale: IM websocket 的响应因果是单槽串行协议；显式 lane 与 owner 能让无 request metadata 的 generic error 仍有唯一归属。register ack gate 同时确保 node identity 被 IM 接受后才发送 node-scoped business；status 的 incarnation supersede 则把重连语义收敛为只恢复当前 runtime。
- Evidence:
  - Tests: C1 two-socket/register/heartbeat regressions 在旧实现稳定失败；C2 focused backend suite（status ownership/control correlation/status protocol/connection behavior/resilience/reconcile callback/channel reconcile/bootstrap）全绿，Ruff 全绿。
  - Entry: 第一条 socket 的 register error 或 heartbeat error 后显式断开；第二条 socket 先只发 register，ack 后按原 FIFO 发送 `node.report`、current `channel.status`、`agent.message`，message waiter 由自身 ack 唤醒。旧 incarnation 的 late result 对新 owner 为 no-op。
  - Frontend State Matrix: N/A。
  - Browser QA: N/A。
  - E2E/Regression: `test_gateway_status_frame_ownership.py::test_disconnect_replays_only_current_status_incarnation`、`test_gateway_control_frame_correlation.py::{test_register_error_never_rejects_buffered_business_fifo,test_heartbeat_error_rejects_only_heartbeat_control_owner}`。
  - Visual/Interaction: N/A。
  - Prototype Comparison: N/A。
- Rollback: 回退 R2 C1/C2/C3；会恢复 register ack 前业务并发、heartbeat 绕过 owner 以及旧 incarnation 重放风险。
- Commits: C1=`b2d5310c4`，C2=`47723f6d1`，C3=本提交。

## R3 — Removal 自动成功清理旧反馈

- Context: TODO。
- Decision: TODO。
- Rationale: TODO。
- Evidence:
  - Tests: TODO。
  - Entry: TODO。
  - Frontend State Matrix: error、waiting、empty、missing resource。
  - Browser QA: 延至 R4。
  - E2E/Regression: TODO。
  - Visual/Interaction: 延至 R4。
  - Prototype Comparison: 延至 R4。
- Rollback: TODO。
- Commits: TODO。

## R4 — Targeted browser 与一次性全量门禁

- Context: TODO。
- Decision: TODO。
- Rationale: TODO。
- Evidence:
  - Tests: TODO。
  - Entry: TODO。
  - Frontend State Matrix: TODO。
  - Browser QA: TODO。
  - E2E/Regression: TODO。
  - Visual/Interaction: TODO。
  - Prototype Comparison: TODO。
- Rollback: TODO。
- Commits: TODO。

Prototype Comparison：
| Reference | Required contract | Actual evidence | Viewport / state | Result | Deviation rationale |
|---|---|---|---|---|---|
| `prototype.html#channel-deleting` | retry error/waiting 只随 receipt 存在 | TODO | desktop / failed→empty | blocked | 等待 R4 |
| `prototype.html#channels-empty` | 收敛后只显示空态，无旧 alert/notice | TODO | desktop / empty | blocked | 等待 R4 |
