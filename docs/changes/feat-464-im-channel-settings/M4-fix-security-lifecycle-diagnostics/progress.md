# M4 — Progress

## R1 — Gateway WS 身份边界与原子 bind

- Context: `/im/ws/gateway` 之前不校验 bearer，任意连接可用同一 `node_id` 覆盖内存 socket 与 credential key；bind 则在四个 repository commit 之间执行 owner guard，两个 owner 可同时通过。
- Decision: WS 入口只接受 bearer token，将认证 owner 注入 `GatewayHandler`；`node.register` 在写 socket/key/DB 前对 durable node owner 做 fail-closed 校验。新增 `BindingStore`，使用独立连接和 `BEGIN IMMEDIATE` 在读取 owner 前抢占写事务，并原子提交 bind/node/profile/default-entry。
- Rationale: 身份必须由传输边界派生而非 frame 自报；bind 的授权检查与写入必须属于同一 transaction owner，进程内锁无法覆盖多个 IM worker。
- Evidence:
  - Tests: `pytest -q tests/im_service/integration/test_gateway_auth_boundary.py tests/im_service/integration/test_bind_atomicity.py tests/im_service/integration/test_account_binding_api.py tests/im_service/contract/test_account_binding_contract.py tests/im_service/unit/test_gateway_handler.py` → 54 passed。
  - Entry: 两个真实注册用户 token 驱动 `/im/ws/gateway`；缺 token 在 node row 创建前 1008，错误 owner 收到 `gateway_owner_mismatch` 后 1008，原 connection owner/key 不变。
  - Frontend State Matrix: N/A（传输与存储边界）。
  - Browser QA: N/A（无 UI 变化）。
  - E2E/Regression: `test_cross_owner_concurrent_bind_has_one_atomic_winner` 用两个独立 SQLite connection 同时 confirm，证明一胜一 409 语义、同 owner 幂等，channel/head/key/removal 密文字节完全不变。
  - Visual/Interaction: N/A。
  - Prototype Comparison: N/A。
- Rollback: 同时回退 WS owner 注入与 `BindingStore`；不可只回退其中一个，否则会分别重新开放 socket takeover 或 bind TOCTOU。
- Commits: C1 `12681ca99`；C2 `8766659d9`。

## R2 — Credential re-entry 与本地 secret 安全写

- Context: 待实施。
- Decision: 待实施。
- Rationale: 待实施。
- Evidence: 待实施。
- Rollback: 待实施。
- Commits: 待实施。

## R3 — Provider preflight、metadata replay 与 activation retry

- Context: 待实施。
- Decision: 待实施。
- Rationale: 待实施。
- Evidence: 待实施。
- Rollback: 待实施。
- Commits: 待实施。

## R4 — Worker 生命周期、背压与真实停用收敛

- Context: 待实施。
- Decision: 待实施。
- Rationale: 待实施。
- Evidence: 待实施。
- Rollback: 待实施。
- Commits: 待实施。

## R5 — 前端 provider registry 真分派

- Context: 待实施。
- Decision: 待实施。
- Rationale: 待实施。
- Evidence: 待实施。
- Rollback: 待实施。
- Commits: 待实施。

## R6 — 独立真实旅程与全门禁

- Context: 待实施。
- Decision: 待实施。
- Rationale: 待实施。
- Evidence: 待实施。
- Rollback: 待实施。
- Commits: 待实施。
