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

- Context: TODO。
- Decision: TODO。
- Rationale: TODO。
- Evidence:
  - Tests: TODO。
  - Entry: TODO。
  - Frontend State Matrix: N/A。
  - Browser QA: N/A。
  - E2E/Regression: TODO。
  - Visual/Interaction: N/A。
  - Prototype Comparison: N/A。
- Rollback: TODO。
- Commits: TODO。

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
