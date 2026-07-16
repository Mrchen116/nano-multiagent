# M8 — Progress

实现基线：`c93063c02cf3049f6cdb9f23a13f870b096ad994`。

## R1 — Wire terminal response ownership

- Context：M7 在 send 前建立 owner，但 ACK/result/error 只接受 `awaiting_result`，导致 transport 已可见而 send coroutine 尚未恢复时唯一响应被消费为 no-op。
- Decision：owner 一旦建立即可按 type/request 接收终态响应；send 返回时若 owner 已被匹配响应释放则正常完成，只有出现不同 owner 才视为状态机错误。
- Evidence：`test_status_result_during_yielding_send_releases_wire_owner`、`test_heartbeat_ack_during_yielding_send_completes_waiter`；最终 wire/liveness suite `6 passed`。

## R2 — Registration and reconnect liveness

- Context：control rejection handler 自行断开后正常 return，`run_forever` 会立刻重连；transport live 但 register send/ACK 无响应时业务 FIFO 可永久冻结。
- Decision：disconnected normal return 统一进入既有 exception/backoff boundary；backoff 只在 register ACK 后重置。新增默认 10 秒 handshake deadline，从 transport connected 起覆盖 register send 与 ACK receive，ACK 后 slow convergence 不再受 deadline 控制。
- Evidence：protocol rejection 首次 reconnect 前 sleep；silent ACK socket 和 yielding register send 都有界断开；30ms convergence 在 10ms 测试 deadline 下仍完成。

## R3 — Removal feedback owner handoff

- Context：offline retry 将 removal id 记为 waiting；节点上线后再次 retry 若返回 generic error，旧 waiting id 未清理，页面同时展示“等待节点”和在线错误。
- Decision：online retry 发起前主动释放 waiting owner；non-offline mutation error 再做 fail-safe 清理。
- Evidence：永久 Vitest 驱动 offline → online → generic error，最终 `alert=1`、waiting notice=0；channels panel/removal focused `15 passed`。

## R4 — Closure gates

- Focused backend：相关 connection/status/reconcile/integration `60 passed`；最终 closure subset `21 passed`。
- Frontend：68 files / `628 passed`；production build 完成；相关 focused `15 passed`。
- Static/contract：Ruff PASS；test naming/size contract `2 passed`；新 backend test 304 行；`git diff --check` PASS。
- Full backend：managed sandbox 首轮 `3466 passed, 1 skipped, 20 deselected`；开放权限后精确复跑原 13 failures，`13 passed`（24.64s），同一实现的分段全量结果闭合为 `3479 passed, 1 skipped, 20 deselected`；本轮新增 6 tests 全绿。
- Verification：`verification.md` Round 6 targeted closure PASS，0 CRITICAL / 0 WARNING / 0 SUGGESTION。
- Delivery：实现、验证与归档材料已就绪，进入 commit / push / PR 发布。
