# M6 — Progress

实现基线：`e05d59c56344f3f45c74474416b16d126198445d`。Baseline focused backend `45 passed`；focused frontend `22 passed`。

## R1 — 公共上行身份与 terminal FIFO

- Context: M5 已在 IM dispatcher 统一要求所有 node-scoped 上行帧携带并匹配注册 node，但 Gateway 的 `agent.config`、`agent.message`、streaming/system 和若干 report/result producer 仍可省略该字段；IM 的 generic error 又只记日志，当前 FIFO head 和 ack waiter 会永久占槽。
- Decision: 在 `_send_frame()` 这个唯一 wire 边界以 reporter 注册 node 覆盖 payload `node_id`；generic protocol error 依据单槽 wire FIFO 终结当前 pending frame，给显式 waiter 设置异常并立即 flush 后继。
- Rationale: sender identity 属于 transport envelope，不应由二十余个业务 producer 各自维护；客户端一次只允许一个未确认 frame，因此没有 request metadata 的旧 server error 也能无歧义对应当前 head。
- Evidence:
  - Tests: C1 两项 regression 先稳定 `2 failed`；C2 后 `pytest -q test_gateway_im_connection_behavior.py test_channel_status_protocol.py test_channel_reconcile.py test_gateway_im_resilience.py test_gateway_im_auth.py` → `47 passed`；focused Ruff → passed。
  - Entry: 公共 `send_json` 入口逐一发送 IM guard 的 21 种业务 frame，最终 websocket JSON 全部为 `node-1`；bad `agent.message` 后 waiter 收到 `bad_payload` 异常且下一 `node.report` 已上 wire。
  - Frontend State Matrix: N/A。
  - Browser QA: N/A。
  - E2E/Regression: `tests/unit/personal_assistant/test_gateway_im_connection_behavior.py::test_every_guarded_upstream_frame_carries_registered_node_identity` 与 `::test_protocol_error_terminally_releases_waiter_and_flushes_next_frame`。
  - Visual/Interaction: N/A。
  - Prototype Comparison: N/A。
- Rollback: 回退 R1 C1/C2/C3 commits；会恢复旧 producer 缺 identity 与 error 卡 FIFO 行为。
- Commits: C1=`cf46a3931`，C2=`560b0f94c`。
