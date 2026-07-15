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

- Context: manifest 解封失败时旧代码从 complete snapshot 中省略该 channel 后仍调用 reconcile，等价于删除；cache key mismatch 更在 `ChannelManager` 构造/startup 阶段抛错，阻止 Gateway 连 IM。legacy cleanup 还会先把含 secret 的主配置复制到普通 backup；export 则写完才 chmod。
- Decision: 新增 fail-closed manifest applier：任一 item key/envelope/open 失败即整份返回 `retryable_failed`，不调用 lifecycle reconcile、不提交 cache/applied head，并为目标 generation 上报 `credential_reentry_required`。foreign-key cache 原字节 0600 quarantine 后开放新的状态 outbox，使 Gateway 可继续连 IM。legacy cleanup/export 统一改用预创建 0600 temp、fsync、atomic replace、目录 fsync 且无 backup 的 sensitive writer。
- Rationale: complete-manifest 协议不能在部分解码后执行；旧密文既不能弱解密也不能覆盖，只能保留证据并向权威控制面请求重新输入。明文文件的权限必须在首次可见前确定。
- Evidence:
  - Tests: `pytest -q tests/unit/personal_assistant/test_channel_credential_recovery.py tests/unit/personal_assistant/test_sensitive_local_config.py tests/unit/personal_assistant/test_channel_manifest_store.py tests/unit/personal_assistant/test_channel_legacy_migration.py` → 12 passed；另 `test_channel_reconcile.py/test_channel_manager.py/test_channel_status_outbox.py/test_gateway_im_resilience_e2e_wrapper.py` → 13 passed。
  - Entry: 单项 wrong key 的 revision 2 返回 retryable failure，revision 1 safe runtime 不 stop、cache/applied head 保持；cache key loss 不调用 opener，旧 cache 字节完整移入 `.credential-reentry.*`，startup 返回 failed recovery snapshot 而非抛错。
  - Frontend State Matrix: error 状态由稳定 `credential_reentry_required`/message 驱动；真实浏览器留 R6。
  - Browser QA: R6 执行真实产品恢复路径。
  - E2E/Regression: legacy CLI 回归确认最终 0600；sensitive writer 故障注入确认 destination 原字节与零 temp/backup plaintext。
  - Visual/Interaction: R6。
  - Prototype Comparison: `#channel-failed` 的稳定原因 contract 已由 wire 状态满足，视觉证据留 R6。
- Rollback: applier、quarantine 与 sensitive writer 必须成组回退；只回退 quarantine 会重新阻断连接，只回退 applier会重新把 desired 误删。
- Commits: C1 `26785d798`；C2 `b5275e125`。

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
