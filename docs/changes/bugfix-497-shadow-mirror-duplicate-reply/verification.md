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
