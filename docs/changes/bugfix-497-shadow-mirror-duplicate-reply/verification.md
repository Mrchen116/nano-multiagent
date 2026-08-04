# Verification Report: bugfix-497

> Validation snapshot: `e79b5d1a12204c077188f3646f741c8648d66cc9 → 068340700fb026a67a22d9aff91c3aab2e70ccb2`

## Summary

Mode: full

Delta range: N/A

Focus issues: N/A

requires_full_verification: false

| 维度 | 结果 |
|---|---|
| Completeness | 0/2 milestones fully closed; worker implementation is present, reviewer exits remain unproved |
| Correctness | 8/9 incident scenarios have implementation/test mappings; the required real Feishu journey has no evidence |
| Coherence | 4/6 design decisions followed; terminal retry ownership has two deviations |

Independent checks at the validation snapshot:

- Focused Gateway/IM/protocol regression: `101 passed`.
- Full Python non-E2E suite: `2850 passed`.
- Architecture import contracts: `5 passed`.
- `git diff --check e79b5d1a..068340700`: passed.
- Frontend reducer/build and documentation checks are recorded at this same snapshot in `M2-rich-shadow-recovery/progress.md`; this verifier did not substitute them for the missing product journey.

1 critical issue(s), 4 warning(s) found. Fix before PR.

## Completeness

- Tasks / milestones: **0/2 fully complete**.
  - M1 has durable identity, same-row live/reconcile behavior and permanent regression coverage, but its reviewer-owned `M1-C1` real Feishu online single/multi-bubble journey is still absent (`design.md:241`, `M2-rich-shadow-recovery/progress.md:35-41`).
  - M2 has the rich snapshot store, atomic IM reconcile, canonical browser upsert and broad automated coverage, but reviewer-owned `M2-C1` through `M2-C3` are not demonstrated. The progress record explicitly says the online, fully-offline plus Gateway restart, and mid-run disconnect journeys still require an exclusive real Feishu window (`design.md:242`, `M2-rich-shadow-recovery/progress.md:35-41`).
- Spec coverage at code level: **4/4 requirements mapped**.
  - Online unique rich bubble: stable identity is created before live `turn_start`, and the terminal snapshot reconciles the same IM row (`src/personal_assistant/gateway/runtime_delivery/observer.py:454-584`, `src/IM/infra/repositories/messages.py:447-608`).
  - Fully-offline rich recovery: normalized runtime facts are written to SQLite before the connection gate, and reconnect recovery submits terminal snapshots after the user anchor (`src/personal_assistant/gateway/runtime_delivery/observer.py:454-658`, `src/personal_assistant/gateway/shadow_sync.py:393-447`).
  - Mid-run completion: the same conversation-scoped source identity creates or updates one message while preserving the existing row id and `created_at` (`src/IM/infra/repositories/messages.py:502-569`, `src/IM/ws/user_stream.py:24-51`).
  - Shared external-channel semantics: the store and sync operate on typed external identities rather than Feishu-only fields (`src/personal_assistant/gateway/shadow_saga.py:224-308`, `src/personal_assistant/gateway/shadow_sync.py:78-214`).
- Prototype / reference coverage: N/A. `design.md:116` explicitly says this change does not alter component structure, visual design, copy, or user operations.

## Correctness

| Requirement / Scenario | 实现位置（file:line） | 测试覆盖 | 状态 |
|---|---|---|---|
| 在线：外部 run 产生一条富气泡 | `observer.py:454-584,659-1173`; `messages.py:447-608`; `chat-stream-reducer.ts:190-219` | `test_gateway_shadow_sync.py:633-727`; `test_external_agent_messages_api.py:128-177`; `chat-stream-reducer.test.ts:100-149` | covered at implementation seams; real journey pending |
| 在线：同一 run 产生多条气泡 | `shadow_saga.py:592-623`; `observer.py:457-477,855-946` | `test_gateway_shadow_sync.py:406-468`; existing relay/steer bubble-roll tests | covered at implementation seams; real journey pending |
| 在线：刷新仍是唯一富历史 | `messages.py:447-608`; `messages.py:610-640` and existing history projection | `test_external_agent_messages_api.py:78-126,128-177` | covered |
| 全程离线：外部 channel 仍正常回复 | `session_run_coordinator.py:597-646`; durable write precedes the observer connection gate at `observer.py:454-658` | existing inbound-pipeline external outage coverage plus `test_gateway_shadow_sync.py:537-630` | covered by separate lowest seams; real journey pending |
| 全程离线：恢复后自动补齐完整历史 | `shadow_saga.py:389-562`; `shadow_sync.py:393-447`; `messages.py:447-608` | SQLite reopen/multi-bubble tests in `test_gateway_shadow_sync.py:298-468`; offline API integration `test_external_agent_messages_api.py:78-126` | covered at implementation seams; real journey pending |
| 恢复直接呈现终态，不重演运行 | `messages.py:513-569`; `chat-stream-reducer.ts:190-219` | `test_external_agent_messages_api.py:78-126`; `chat-stream-reducer.test.ts:100-149` | covered |
| 中途断线：补全原 message id | `messages.py:502-569` | `test_external_agent_messages_api.py:128-177` | covered at implementation seam; real journey pending |
| 打开的会话无需刷新即收敛 | `messages.py:599-607`; `user_stream.py:24-63`; `chat-stream-reducer.ts:190-219` | `test_user_stream.py:35-69`; `chat-stream-reducer.test.ts:100-149` | covered at event/reducer seams; browser journey pending |
| 真实飞书在线、全离线、中途断线三旅程 | Feishu typed identity exists in `src/personal_assistant/channels/feishu/adapter.py:360-443`; generic path is above | `tests/unit/test_feishu_adapter.py:73-75` only proves identity mapping; `progress.md:35-41` says the required journey was not run | **missing acceptance evidence** |

## Coherence

| design 决策 | 遵守? | 代码证据（file:line） |
|---|---|---|
| 1. 现有 Gateway saga store 按逻辑气泡增量维护 durable 富快照 | 是 | `src/personal_assistant/gateway/shadow_saga.py:114-134,389-562` |
| 2. `shadow_message_id` 在 live 建泡前产生，不依赖正文或 Kernel message id | 是 | `src/personal_assistant/gateway/shadow_saga.py:592-623,807-811`; `observer.py:454-478,668-701` |
| 3. live 保持流式，terminal snapshot 经有序 ACK 屏障再调和 | 部分 | 正常 `turn_end` 遵守 (`observer.py:1131-1167`)；异常 `run_terminal_reconcile` 未遵守 (`observer.py:596-630,1483-1577`) |
| 4. IM 提供原子 terminal snapshot reconcile 并发布完整 canonical event | 是 | `src/IM/api/routes/messages.py:457-519`; `src/IM/infra/repositories/messages.py:447-608`; `src/IM/infra/repositories/_message_projection.py:82-90` |
| 5. 只恢复 terminal pending，成功 ACK 后本地收口，由唯一 recovery owner 重试 | 部分 | terminal-only / ACK 后 mark 遵守 (`shadow_saga.py:519-562`)；ready 快照在 connected recovery 任务退出后无重新唤醒 (`observer.py:1160-1167`; `connection_ready.py:113-136`) |
| 6. 已写 legacy 历史不迁移，未交付 legacy pending 继续原协议恢复 | 是 | production 新写入关闭在 `composition.py:424-437`; legacy drain 保留在 `shadow_sync.py:443-447` |

Architecture coherence is otherwise preserved: there is no new top-level package or forbidden cross-package import, and the repository import-boundary contracts passed.

### Prototype / Reference Contract

N/A. No frontend prototype or reference artifact is declared.

## Issues

### CRITICAL（提 PR 前必须修）

- **V-C1 — M1/M2 的 reviewer-owned 真实飞书退出标准没有证据，milestone 无法判定完成。** `docs/changes/bugfix-497-shadow-mirror-duplicate-reply/design.md:241-242` 把真实飞书在线、全离线 + Gateway restart、中途断线 + 打开页面无刷新收敛列为 M1-C1 / M2-C1–C3 退出标准；`docs/changes/bugfix-497-shadow-mirror-duplicate-reply/M2-rich-shadow-recovery/progress.md:35-41` 明确记录尚未执行。修复方向：在独占的真实飞书 listener 窗口按 `design.md:212-233` 跑完三旅程，在 unit progress 持久记录 nonce、操作、浏览器结果、历史 API 对账、message id 和清理结果；不能用 mock/API 证据代替。

### WARNING（提 PR 前必须修）

- **V-W1 — normal terminal 的即时 reconcile 失败后，`ready` 快照没有在当前连接上重新交给唯一 recovery owner。** `src/personal_assistant/gateway/runtime_delivery/observer.py:1131-1167` 捕获 reconcile 异常后只写日志；`src/personal_assistant/gateway/connection_ready.py:113-136` 的 retry loop 只在 `on_connected` 启动，一次 `recover_pending()` 成功就退出。如果 HTTP 暂时失败但 WS 保持连接，该快照会一直 `ready` 直到无关的下次重连，偏离 `design.md:118-136` 的自动重试决策。修复方向：给 `ConnectionReadyCoordinator` 的单一 recovery owner 增加可唤醒的 pending 通知，在新 terminal snapshot ready 或即时 reconcile 失败时唤醒它；加一个“首次 PUT 失败、WS 不断线、后续自动成功”测试。
- **V-W2 — abnormal terminal 没有执行 design 要求的 terminal ACK 屏障和 same-id snapshot reconcile。** `src/personal_assistant/gateway/runtime_delivery/observer.py:596-630` 会把 `run_terminal_reconcile` 快照置为 `ready`，但 `src/personal_assistant/gateway/runtime_delivery/observer.py:1483-1577` 只启动 detached tool/completion live send，没有 `send_json_await_ack` 或 `shadow_bubble_reconcile(shadow_snapshot)`。修复方向：将异常工具收尾、terminal ACK 和快照调和收进一个有序 coroutine；无 live message id / ACK 失败时通知 V-W1 的唯一 recovery owner，并增加 interrupted/failed 终态永久回归测试。
- **V-W3 — M2-C5 要求的 owner 和 agent 隔离没有 integration 回归测试。** 实现在 `src/IM/api/routes/messages.py:470-518` 和 `src/IM/infra/repositories/messages.py:470-501` 有校验，但 `tests/im_service/integration/test_external_agent_messages_api.py:180-208` 只断言了“非 external shadow conversation”与“非 terminal status”，没有覆盖其他 owner 或错误 agent。修复方向：扩展该 integration 文件，分别用其他 owner token 和非会话 agent 提交 snapshot，断言请求被拒且消息/事件行数不变。
- **V-W4 — “非 Feishu adapter 缺稳定身份时只继续外部回复、不留任何 shadow 历史”没有端到端的永久 contract test。** `tests/unit/personal_assistant/test_gateway_shadow_sync.py:915-940,969-984` 分别证明 diagnostic 和 Slack 形态的 sync 不发 HTTP，但没有驱动 inbound pipeline 证明 Agent run / provider reply 仍完成，也没有同时断言 conversation/user/Agent/config-boundary 均未写入，未满足 `design.md:242` 的 M2-C3。修复方向：在现有 inbound/shadow owner 测试文件中加一个 Slack-like external adapter 用例，传入缺 provider event identity 的消息，断言 outbound 回复成功、diagnostic 存在，且 saga/IM/boundary 均无写入。

### SUGGESTION（可以修）

None.

# Round 2

> Validation snapshot: `068340700fb026a67a22d9aff91c3aab2e70ccb2 → f1f44a2696460d7bcef85b605353de8c870b8467`

## Summary

Mode: targeted-closure

Delta range: `068340700fb026a67a22d9aff91c3aab2e70ccb2..f1f44a2696460d7bcef85b605353de8c870b8467`

Focus issues: `V-C1`, `V-W1`, `V-W2`, `V-W3`, `V-W4`

Validated issues: `V-W1`, `V-W2`, `V-W3`, `V-W4`

requires_full_verification: false

| Issue | Round 2 result |
|---|---|
| V-C1 | retained as CRITICAL; the required real Feishu journeys still have no durable evidence |
| V-W1 | closed; one wakeable recovery owner retries on the current connection |
| V-W2 | closed; abnormal terminal now orders live terminal ACK before same-id snapshot reconcile |
| V-W3 | closed; integration coverage rejects wrong agent and other owner without message/event writes |
| V-W4 | closed; a Slack-like missing-identity pipeline test proves external reply continuity and no shadow/boundary writes |

Independent checks at the validation snapshot:

- Focused closure regression across recovery, observer, wire liveness, inbound pipeline,
  steer admission, IM integration and Kernel event forwarding: `119 passed`.
- Repository contract suite: `135 passed`.
- Ruff over every source and test file changed by the closure delta: passed.
- `git diff --check 068340700..f1f44a269`: passed.
- The implementation progress records a final full Python non-E2E run
  (`2876 passed, 20 deselected`), frontend suite (`556 tests passed`) and frontend
  production build at this snapshot; targeted closure did not rerun them.

1 critical issue(s), 0 warning(s) and 0 suggestion(s) remain. Fix before PR.

## Targeted Closure

- **V-C1 remains open.** The reviewer-owned M1/M2 exits still require the real Feishu
  online, fully-offline plus Gateway restart, and mid-run IM disconnect journeys in
  `design.md:212-242`. The latest progress explicitly records that this checkout has no
  isolated Feishu channel and that API/mock coverage is not a substitute
  (`M2-rich-shadow-recovery/progress.md:49-55`).
- **V-W1 is closed.** `ConnectionReadyCoordinator` exposes one generation-based wakeup
  and retries transient recovery failure without requiring another WebSocket connection
  (`connection_ready.py:116-143`); observer reconcile failures notify that owner through
  the composed callback (`composition.py:430-448`, `observer.py:410-417,1280-1321`).
  `test_connection_ready_shadow_recovery.py:76-143` covers both retry-after-failure and
  a later ready snapshot on the existing connection.
- **V-W2 is closed.** Abnormal terminal first durably closes in-flight tools and produces
  a ready snapshot (`observer.py:662-694`), then a single coroutine sends tool terminal
  frames, awaits `message_completed` business ACK, and only then reconciles the same
  snapshot (`observer.py:1737-1773`). The offline durable close and online ordered path
  are protected by `test_gateway_shadow_sync.py:1010-1169`.
- **V-W3 is closed.** The integration test now rejects a non-participant Agent and a
  different owner, then verifies both message and conversation-event counts are
  unchanged (`test_external_agent_messages_api.py:211-247`).
- **V-W4 is closed.** A Slack-like inbound without provider event identity completes the
  Agent run and provider reply while issuing no IM HTTP request, leaving no pending saga,
  rich snapshot, legacy output or config boundary, and recording the required diagnostic
  (`test_inbound_pipeline_session.py:221-285`).

## Closure Delta Coherence

- Batched USER steer correlation remains aligned with the active follower list: Kernel
  reports a separate `user_message_count`, the realtime hook forwards it, and the run
  coordinator advances to the last consumed user follower (`agent/loop.py:684-722`,
  `realtime_stream.py:142-164`, `session_run_coordinator.py:1043-1074`). Permanent tests
  cover mixed-origin batches and two-user batches.
- Failed bubble roll does not leave bubble-A transport context attached to bubble B:
  the failure path clears the live message/text markers and wakes recovery while the new
  durable bubble continues recording (`observer.py:394-408,1602-1647`;
  `test_gateway_shadow_sync.py:1249-1348,1727-1823`).
- Pending follower anchor recovery preserves inbound order even when an earlier saga is
  already anchored: recovery enumerates all sagas with missing anchors or ready snapshots
  by saga row order, then reconciles each saga before advancing (`shadow_saga.py:736-753`,
  `shadow_sync.py:399-449`; `test_gateway_shadow_sync.py:211-350`).
- A successful steer roll clears the prior bubble's cached external reply and intermediate
  marker before the next terminal boundary, preventing stale content from being sent again
  (`observer.py:118-139`; `test_gateway_shadow_sync.py:1351-1399`).
- The delta adds no top-level package or forbidden import direction, and the contract suite
  passes; no architecture boundary crossing or duplicate recovery mechanism requires a
  new full verification round.

## Issues

### CRITICAL（提 PR 前必须修）

- **V-C1 — 真实飞书 reviewer 旅程仍无 durable 验收证据。** `design.md:212-242`
  要求从真实飞书分别验证在线唯一富气泡、全程离线加 Gateway restart 后完整恢复、
  中途断线后同 message id 无刷新收敛，并用历史 API 对账字段。最新
  `M2-rich-shadow-recovery/progress.md:49-55` 明确说明当前机器没有隔离飞书 channel，
  因此本轮不能把自动化 seam 证据替代为产品旅程结论。修复方向不变：获得独占真实
  listener 窗口，按 runbook 记录 nonce、浏览器观察、历史 API 对账、message id 与清理结果。

### WARNING（提 PR 前必须修）

None.

### SUGGESTION（可以修）

None.

# Round 3

> Validation snapshot: `f1f44a2696460d7bcef85b605353de8c870b8467 → pending documentation commit`

## Summary

Mode: real-channel acceptance review

Focus issue: `V-C1`

The initial real-channel evidence covers an online run, a fully IM-offline run followed
by a Gateway restart, and an IM disconnect during a 26,031 ms run. Each history/API and
browser-reload check found exactly one terminal rich Agent bubble, not a new plain reply.
The detailed nonce, message identities, observed rich fields and cleanup boundary are in
[`M2-rich-shadow-recovery/evidence/real-feishu-acceptance-20260804.md`](M2-rich-shadow-recovery/evidence/real-feishu-acceptance-20260804.md).

The test agent's explicit empty tool allowlist meant this listener window could not
generate a structured tool event. The real-channel evidence does not claim otherwise;
ordered rich tool recovery remains covered by the permanent automated regression suite
recorded in `M2-rich-shadow-recovery/progress.md`. Independent review verdict: **fail**.

## Issues

### CRITICAL（提 PR 前必须修）

- **V-C1 remains open.** The required real Feishu run still lacks a structured-tool
  multi-bubble journey, so it cannot observe intermediate `token_usage = null`, final
  cumulative usage, ordered tool content or `kernel_message_id` through the actual
  channel. The mid-run case also must first record an already-visible partial Agent row
  and its message id, then prove that same id automatically reaches terminal state after
  IM restoration.

# Round 4

> Validation snapshot: `f1f44a2696460d7bcef85b605353de8c870b8467 → real Feishu closure evidence`

## Summary

Mode: real-channel closure

Focus issue: `V-C1`

**Verdict: pass.** The new isolated real Feishu runs close the product exits:

- A structured `bash` tool appeared in the live Web IM process timeline. A real Feishu
  follower split the run into an intermediate Agent bubble with completed tool/thinking/
  elapsed and `token_usage = null`, then a terminal bubble with 4,453 cumulative tokens
  and its kernel id. Neither bubble had a plain duplicate.
- A page-visible partial Agent row was recorded as
  `098717ccdade45a68f1b90cb069ebfc2` before IM was stopped. Gateway stayed online and
  Feishu received the complete response while IM was offline. Restoring IM on the same
  SQLite database and port automatically reconciled that same row in the already-open
  page to rich terminal content (thinking, 16,126 total tokens, 27,037 ms and kernel id);
  a fresh login/page reload still showed one bubble.
- The full IM-offline journey was rerun with the real `bash` tool enabled. Feishu received
  its terminal tool result before IM recovery; Gateway restarted while IM was still down;
  restoring the same IM database and port reconciled one completed rich Agent row with
  ordered thinking, `bash` at sequence 1, 3,504 total tokens, 15,026 ms and kernel id
  `msg_18d0de01d4dbee81`. The Web IM page showed that terminal snapshot without a running
  replay and still showed the single bubble after reload.

Exact nonces, message ids, API cross-checks and cleanup boundary are in
[`M2-rich-shadow-recovery/evidence/real-feishu-acceptance-20260804.md`](M2-rich-shadow-recovery/evidence/real-feishu-acceptance-20260804.md).

## Issues

### CRITICAL（提 PR 前必须修）

None.
