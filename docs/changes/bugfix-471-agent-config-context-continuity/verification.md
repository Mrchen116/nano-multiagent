## Verification Report: bugfix-471

### Summary

Mode: full  
Delta range: N/A  
Focus issues: N/A  
requires_full_verification: false

| 维度 | 结果 |
|---|---|
| Completeness | 10/10 tasks complete；23/23 requirements 已映射实现 |
| Correctness | 23/23 requirements covered；关键 scenario 均有长期回归测试或协议/集成测试覆盖 |
| Coherence | Followed |

验证对象：`958f2d87841edc5272416b917977b24fad55a408`

## Completeness

### Task completion

M1 与 M2 的 `tasks.md` 中所有退出标准及 roadpoint task 均已勾选：**10/10 complete**。

### Requirement and scenario implementation map

| 范围 | 覆盖证据 |
|---|---|
| 同一 Kernel session 的完整 runtime replacement、恢复、幂等与 fork | `src/agent/sdk/runtime.py:20-109`、`src/agent/sdk/kernel.py:897-1121`、`src/agent/core/session/conversation.py:290-326`；`tests/integration/test_session_run_coordinator_real_kernel.py` 覆盖 transcript 延续、restart、identity canonicalization 与 fork。 |
| PromptSlots 与产品 runtime 的单点投影 | `src/personal_assistant/gateway/session_composition.py:38-66`；`tests/unit/personal_assistant/test_session_run_coordinator_admission.py:488-536` 覆盖 model、skills、tools、features 与同 session reconfigure。 |
| active run / steer 配置冻结 | `src/personal_assistant/gateway/session_run_coordinator.py:191-239,392-431,718-808`；`tests/unit/personal_assistant/test_session_run_coordinator_admission.py:540-575`。 |
| binding 保留、runtime baseline、原子边界 intent | `src/personal_assistant/gateway/session_binder.py:203-395`、`src/personal_assistant/gateway/session_keys.py:494-535,632-700`；admission regression 覆盖 legacy baseline 与 anchor-first 写入。 |
| durable outbox、ACK、重试与 quarantine | `src/personal_assistant/gateway/boundary_outbox.py`；`tests/unit/personal_assistant/test_gateway_boundary_delivery.py:43-206`。 |
| external channel shadow saga 与 outage 后补写 | `src/personal_assistant/gateway/inbound_pipeline.py:149-192`、`src/personal_assistant/gateway/shadow_saga.py:161-324`；`tests/unit/personal_assistant/test_session_run_coordinator_admission.py:100-162` 与 shadow-sync regressions。 |
| IM durable boundary、owner/anchor 校验、ACK 与 user event replay | `src/IM/infra/repositories.py:3223-3465`、`src/IM/ws/gateway_handler.py:1461-1505`；gateway protocol contract 与 IM messages integration tests。 |
| typed timeline、message-cursor pagination 与 fork re-anchor | `src/IM/application/web_im_service.py:274-466`、`src/IM/infra/repositories.py:3294-3311`；IM message API integration tests。 |
| Web timeline merge、live/reconnect/older prepend、非消息 divider | `src/IM/frontend/src/features/chat/chat-stream-reducer.ts:27-84,172-236`、`src/IM/frontend/src/features/chat/chat-workspace-page.tsx:114-170,582-584`、`src/IM/frontend/src/features/chat/components/message-pane.tsx:562-581,669-675`；对应 reducer、workspace integration 与 message-pane component regressions。 |

### Prototype / Reference Contract

`M2-cache-boundary/tasks.md:51-59` 将全部 must-match 项投影到退出标准与 owner；`M2-cache-boundary/progress.md` 的 Prototype Comparison 和以下可复查仓内 evidence 覆盖固定文案、anchor 前位置、1440/1280/375、reconnect、older prepend、fork，以及 sidebar/message/composer 未改版：

- `M2-cache-boundary/evidence/r3-chat-1440.png`
- `M2-cache-boundary/evidence/r3-chat-1280.png`
- `M2-cache-boundary/evidence/r3-chat-375.png`
- `M2-cache-boundary/evidence/r3-reconnect-375.png`
- `M2-cache-boundary/evidence/r3-older-prepend-1440.png`
- `M2-cache-boundary/evidence/r3-fork-1440.png`
- `M2-cache-boundary/evidence/r3-browser-timeline.json`

代码同时保证 divider 是独立 timeline item、而非 `MessageBubble`，且 anchor 未加载时不孤立渲染（`message-pane.tsx:562-581`）。

## Correctness

### Requirement coverage

- Kernel delta 的 runtime replacement、read identity、fork runtime，以及 PromptSlots 两项 requirement，均由 SDK 的 typed `SessionRuntimeConfig` / `SessionRuntimeIdentity`、Kernel API 与 transcript replacement 实现，并由 real-kernel integration regressions 覆盖。
- Gateway delta 的 capability/model routing、active-run freezing、binding persistence、boundary eventual delivery、relay protocol 与 external shadow saga requirement，均由 coordinator admission lock、persistent binding/outbox、ACK dispatcher 和 saga 实现，并由 unit/integration/contract tests 覆盖。
- IM delta 的 agent configuration state、typed non-message timeline、pagination、fork、gateway ACK 和 owner-scoped replay requirement，均由 repository transaction、timeline service、gateway websocket handler 与 user-event mechanism 实现，并由 IM integration/contract tests 覆盖。
- Web UX delta 的 divider 文案、位置、非消息语义，以及 REST/live/reconnect/prepend stable merge requirement，均由 typed `TimelineItem` reducer 和 `MessagePane` union rendering 实现，并有 Vitest regression source 覆盖。

本轮执行结果：

```text
PYTHONPATH=src pytest -q \
  tests/integration/test_session_run_coordinator_real_kernel.py \
  tests/unit/personal_assistant/test_session_run_coordinator_admission.py \
  tests/unit/personal_assistant/test_gateway_boundary_outbox.py \
  tests/unit/personal_assistant/test_gateway_shadow_sync.py \
  tests/im_service/contract/test_gateway_protocol_contract.py \
  tests/im_service/integration/test_messages_api.py
60 passed, 1 skipped, 7 warnings

PYTHONPATH=src pytest -q \
  tests/contract/test_agent_sdk_surface_guard.py \
  tests/contract/test_no_hardcoded_workspace_dirname.py \
  tests/im_service/contract/test_events_contract.py
7 passed

PYTHONPATH=src pytest -m 'not e2e'
3667 passed, 1 skipped, 20 deselected, 21 warnings
```

前端测试源与仓内历史验证 evidence 均存在；本 verifier worktree 未安装前端依赖，执行 `npm test -- --run ...` 因 `vitest: command not found` 退出 127，故未将 progress 中的 Vitest/build 通过记录表述为本轮复跑结果。

## Coherence

1. **完整 runtime 的原子替换**遵守 design 决策 1/2：`ConversationSession.replace_runtime()` 以 lifecycle permit 和 turn gate 串行，先持久化再失效内存状态（`src/agent/core/session/conversation.py:290-326`）；coordinator 仅在新 run admission 中调用 replacement（`src/personal_assistant/gateway/session_run_coordinator.py:392-431,718-808`）。
2. **SDK 作为 runtime identity 单一所有者**遵守 design 决策 3：canonicalization 位于 `src/agent/sdk/runtime.py:57-109`，Gateway 使用 SDK identity，而没有维护重复 fingerprint 字段清单。
3. **actual-applied runtime 与 boundary intent 的同事务持久化**遵守 design 决策 4/6：`src/personal_assistant/gateway/session_keys.py:632-700` 用单一 SQLite transaction 更新 baseline 并插入 outbox；outbox 仅在 durable ACK 后删除。
4. **非消息 timeline divider**遵守 design 决策 5：IM 写入 `conversation_events` 而非 `messages`（`src/IM/infra/repositories.py:3352-3465`），前端按 typed union 渲染（`message-pane.tsx:562-581`）。
5. **fork 复制并重锚既有 boundary**遵守 design 决策 7：`src/IM/application/web_im_service.py:301-466` 与 `src/IM/infra/repositories.py:3294-3311` 使用 source-to-target mapping，不因 fork 新建配置边界。
6. **外部 shadow saga**遵守 design 决策 8：`src/personal_assistant/gateway/shadow_saga.py:161-245` 只接受稳定 external event identity，不以 chat id、metadata 或文本 hash 伪造 identity；outage 不阻塞业务回复。
7. 架构边界符合 `SPEC.md` / `AGENTS.md`：产品仅经 `agent.sdk` 调用 Kernel，IM 未 import Agent 或 Gateway；Gateway 与 IM 通过既有 HTTP/WebSocket 边界协作，不直读对方持久化文件或 workspace。

## Issues

### WARNING

1. **`ruff format --check` 未通过，存在 CI 交付风险。**
   - Evidence: `src/agent/sdk/runtime.py:1-109` 是静态检查中唯一被报告为 `Would reformat` 的文件；`ruff check` 已通过。
   - Fix: 提交 PR 前执行 `ruff format src/agent/sdk/runtime.py`，随后重新运行 `ruff format --check src/agent/sdk/runtime.py`。项目 CI 包含 format 检查，Python 测试通过不代表 CI 必然通过。

### CRITICAL

None.

### SUGGESTION

None.

## Verdict

No critical issues. 1 warning(s) to consider. Ready for PR (with noted improvements).
