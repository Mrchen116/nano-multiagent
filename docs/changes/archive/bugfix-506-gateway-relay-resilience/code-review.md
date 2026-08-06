# bugfix-506: Code Review

## Review scope

- Base: `0e79d9b4a264703807c25f25ec121a8b000c5f11`
- Head: implementation worktree before commit
- Review mode: `full`
- Included commits: None; implementation was uncommitted when review began.
- Included uncommitted files: IM streaming protocol/EventBridge/event repository; Gateway connection-ready, runtime observer and IM connection; their focused tests; this unit documentation and canonical-spec updates.

## Round 1

- Result: Changes required; four findings均经独立 verifier 确认。
- Findings:
  1. 后台 profile reconciliation 固化旧版本快照且重连任务可重叠，旧任务可能在新 `config.sync` 后回滚 Agent 配置。
  2. 节点绑定 HTTP 仍被 `on_connected` 同步等待，会在注册 ACK 后占住 WebSocket receive owner。
  3. delta 幂等检查、正文更新与 event 落库分属独立事务；两次提交之间失败会让重传重复正文。
  4. 每个带键 delta 都扫描 `conversation_events` JSON，历史增长后会拉长业务 ACK。
- Resolutions:
  1. reconciliation 改为单飞 generation worker，并在发布前重新读取 `ConfigSyncClient.latest_profile_version`。
  2. 节点绑定改为独立后台 task；outbox 在注册后立即开始 drain。
  3. IM 在同一 SQLite transaction 内写 marker、正文和 delta event；失败回滚三者，notify 只在 commit 后发生。
  4. 增加 `message_delta_idempotency(message_id, idempotency_key)` 复合主键表；首次升级时从旧 event payload 一次性回填，热路径不再扫描 JSON。
- Tests after fixes: 聚焦回归 95 passed；扩大 `tests/im_service/unit tests/unit/personal_assistant` 1092 passed；Ruff check、format check、docs-check 和 `git diff --check` 通过。

## Closure

- Follow-up mode: `closure`
- Findings closed: 4 / 4；四项均由独立 closure verifier 确认关闭。
- Remaining findings: None
- Final result: Passed

## Final base check

- Delivery base: `ee5f657b754642569d64685b064e960ed66dfff1` (`origin/main`).
- The 16 commits added after the original review affect the separate bugfix-505/507 units, IM agent-settings documentation, and its frontend; they do not overlap this unit's Gateway relay, IM event, or canonical-spec paths. The closure review and user acceptance remain applicable after rebasing.
