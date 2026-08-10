# Verification Report: refactor-521

> Validation snapshot: `48d19d8a7809805efcb7631e75079cc09daf2eab → 62422c82c093d61633870d2ebed7850346c20b11`

## Summary

Mode: full

Delta range: N/A

Focus issues: N/A

requires_full_verification: false

| 维度 | 结果 |
|---|---|
| Completeness | 1/1 milestone、7/7 退出标准已证明 |
| Correctness | 2/2 requirements、4/4 scenarios covered |
| Coherence | 5/5 关键设计决策遵守 |

All checks passed. Ready for PR.

## Completeness

- Tasks: `M1-typed-ingress-cutover/tasks.md` 中 7/7 项退出标准已勾选，本轮逐项反查实现、永久测试和实际存在的 progress evidence，未发现只勾选但未完成的项。
- Milestone: `refactor-521-M1` 的 typed producer、`RoutedInbound` cutover、legacy authority 删除、分型 delivery target、`web_relay` residual 分类、persistence guard 和要求的验证命令均有实现与证据。
- Spec 覆盖: 本 unit 以 `motivation.md` 作为首文档；两条 requirement 及四个 scenario 均可映射到生产调用链和永久回归测试。
- Canonical contract: 实现保持 `docs/specs/gateway/routing-delivery.md` 的原目标回复、群门控/裸 `/new`/静默契约，保持 `docs/specs/gateway/relay-protocol.md` 和 `docs/specs/im/gateway-relay.md` 的 provider/relay 幂等与恢复契约，也保持 `docs/specs/gateway/external-channels.md` 的外部回复与 shadow 顺序。
- Prototype / Reference 覆盖: N/A。本 unit 没有前端原型或 must-match reference artifact。

### Milestone Exit Criteria

| 退出标准 | 实现 / 测试证据 | 状态 |
|---|---|---|
| callback 只交付带 `InboundIngress` 的 `InboundMessage`；producer/absence/invalid combinations 受保护 | `src/personal_assistant/channels/base.py:9-88,127`; `src/personal_assistant/channels/web_relay_adapter.py:194-211,227-299`; `src/personal_assistant/channels/feishu/adapter.py:399-410,455-491`; `tests/unit/personal_assistant/test_inbound_ingress.py:18-68`; `tests/unit/personal_assistant/test_gateway_web_relay_adapter.py:20-166`; `tests/unit/test_feishu_adapter.py:63-96,231-267` | covered |
| Gateway post-ingress 只传 `RoutedInbound`；shadow 三态受保护 | `src/personal_assistant/gateway/inbound_models.py:14-48,51-137,176-178`; `src/personal_assistant/gateway/inbound_pipeline.py:130-187`; `tests/unit/personal_assistant/test_routed_inbound.py:25-72` | covered |
| native relay / external shadow 分型投影，typed facts/saga 单权威 | `src/personal_assistant/gateway/runtime_delivery/context.py:17-78,359-449`; `src/personal_assistant/gateway/session_run_coordinator.py:1308-1359,1793-1801`; `tests/unit/personal_assistant/test_gateway_relay_lifecycle.py:153-263,673-832` | covered |
| legacy wrapper/module/key/top-level field/旧 ref fields/fallback 全部删除 | `src/personal_assistant/gateway/runtime_protocol.py` 已删除；`tests/contract/test_relay_typed_ingress_contract.py:22-36`; `tests/unit/personal_assistant/test_routed_inbound.py:65-72`; production search 无 `InboundEnvelope`/`RuntimeProtocolFacts`/`__runtime_protocol_facts__`/derive helper 命中 | covered |
| 四处 ingress `web_relay` proxy 改读 typed facts，其余 residual 为合法 identity | `src/personal_assistant/gateway/inbound_pipeline.py:189-208,249-303`; `src/personal_assistant/gateway/runtime_delivery/context.py:374-449`; production residual 仅落在 adapter name/construction、composition/registry/managed guard、scheduler/internal dispatch target 及 persisted outbound reply channel | covered |
| typed containers 不进入 reply/session/DB/public metadata | `src/personal_assistant/gateway/session_keys.py:1588-1659`; `src/personal_assistant/gateway/shadow_saga.py:255-290`; `tests/contract/test_relay_typed_ingress_contract.py:39-76` | covered |
| focused、contract、non-E2E、Ruff 全绿；真栈验收有实施记录 | 本轮独立重跑 focused `196 passed`、contract `150 passed`、non-E2E `3190 passed`、Ruff check/format-check 全绿；`M1-typed-ingress-cutover/progress.md:40-43` 记录隔离 Web/Feishu 验收和资源清理 | covered |

## Correctness

| Requirement / Scenario | 实现位置（file:line） | 测试覆盖 | 状态 |
|---|---|---|---|
| Requirement: 内置 Web IM 消息的路由与回复保持一致 | Web relay 在 adapter 一次构造 `IMRelayIngress` 并以同一 callback 进入 pipeline：`src/personal_assistant/channels/web_relay_adapter.py:194-211,227-299`；会话键与原 reply target 投影保持：`src/personal_assistant/gateway/session_keys.py:1612-1659` | `tests/unit/personal_assistant/test_gateway_web_relay_adapter.py:20-166`; `tests/unit/personal_assistant/test_gateway_relay_lifecycle.py:319-372,503-580` | covered |
| Scenario: 直聊消息仍回复原会话 | `IMRelayTarget` 使用 `message.external_chat_id` 作为 conversation target，lifecycle/report 使用 typed relay/message identity：`src/personal_assistant/gateway/runtime_delivery/context.py:383-395`; `src/personal_assistant/gateway/runtime_delivery/lifecycle.py:31-112` | `tests/unit/test_inbound_pipeline_streaming.py:34-51,84-127`; `tests/unit/personal_assistant/test_gateway_relay_lifecycle.py:503-580,583-636` | covered |
| Scenario: 群聊触发、裸 `/new` 与静默保持一致 | 原 mention/reply/ALWAYS 门控保留，只将 native bare `/new` 条件改为 `im_relay` 且无 external identity：`src/personal_assistant/gateway/inbound_pipeline.py:249-303`；静默/provisional 策略由 typed relay 投影：`src/personal_assistant/gateway/runtime_delivery/context.py:434-449` | `tests/unit/personal_assistant/test_gateway_stop_command.py:310-541`; `tests/unit/personal_assistant/test_gateway_relay_lifecycle.py:999-1170,1214-1289`; `tests/unit/personal_assistant/test_inbound_pipeline_session.py:977-1118` | covered |
| Requirement: 外部 channel 与 shadow 投递保持一致 | Feishu 直聊/群聊产生 provider-stable conversation/event facts：`src/personal_assistant/channels/feishu/adapter.py:399-410,455-491`；pipeline 生成 pending/anchored state：`src/personal_assistant/gateway/inbound_pipeline.py:189-208`；shadow sync/saga 保持幂等锚点和恢复：`src/personal_assistant/gateway/shadow_sync.py:81-240,447-501`; `src/personal_assistant/gateway/shadow_saga.py:221-315` | `tests/unit/test_feishu_adapter.py:63-96,231-267`; `tests/unit/personal_assistant/test_gateway_shadow_sync.py:193-415`; `tests/unit/personal_assistant/test_inbound_pipeline_session.py:215-550` | covered |
| Scenario: 外部消息仍回到原通道原目标，shadow 的用户/过程/终态顺序保持 | external reply context 仍从原 message 显式投影：`src/personal_assistant/gateway/session_keys.py:1644-1659`；anchored/pending external target 不落入 owner-direct：`src/personal_assistant/gateway/runtime_delivery/context.py:383-403`；recovery 按 saga 顺序重建 user anchor 后 reconcile snapshot：`src/personal_assistant/gateway/shadow_sync.py:447-501` | `tests/unit/personal_assistant/test_inbound_pipeline_session.py:215-347,415-550`; `tests/unit/personal_assistant/test_gateway_shadow_sync.py:250-364,451-809,1696-1765`; `tests/unit/personal_assistant/test_gateway_relay_lifecycle.py:673-940` | covered |
| Scenario: 中继断线与重放不产生重复可见结果 | relay adapter 在 callback 前持久化幂等键：`src/personal_assistant/channels/web_relay_adapter.py:202-223`；provider event 以稳定 saga/idempotency key 复用锚点：`src/personal_assistant/gateway/shadow_saga.py:221-315`; `src/personal_assistant/gateway/shadow_sync.py:119-121,195-240,447-501` | `tests/unit/personal_assistant/test_gateway_web_relay_adapter.py:296-368`; `tests/unit/personal_assistant/test_gateway_shadow_sync.py:193-364,1626-1693`; `tests/unit/personal_assistant/test_gateway_stop_command.py:543-625,772-829` | covered |

## Coherence

| design 决策 | 遵守? | 代码证据（file:line） |
|---|---|---|
| 1. 保留单值 channel ingress interface，`InboundMessage.ingress` 始终存在 | 是 | `src/personal_assistant/channels/base.py:51-88,127`; `src/personal_assistant/channels/web_relay_adapter.py:194-211` |
| 2. adapter facts 与 Gateway shadow state 分层拥有 | 是 | adapter-owned types 在 `src/personal_assistant/channels/base.py:9-61`；Gateway-owned state 在 `src/personal_assistant/gateway/inbound_models.py:14-48`；pipeline 在 callback 后组合 `RoutedInbound`：`src/personal_assistant/gateway/inbound_pipeline.py:130-187` |
| 3. `im_relay` transport origin 与 `external_conversation` identity 正交分离 | 是 | `src/personal_assistant/channels/base.py:33-61`; Web native/external-through-IM producer: `src/personal_assistant/channels/web_relay_adapter.py:248-299`; native/external group gate: `src/personal_assistant/gateway/inbound_pipeline.py:280-288` |
| 4. 同一 M1 删除 wrapper、hidden key、fallback 与重复字段 | 是 | `runtime_protocol.py` 删除；`ShadowConversationRef` 只剩两个 required anchor field：`src/personal_assistant/gateway/inbound_models.py:14-28`；deletion contract: `tests/contract/test_relay_typed_ingress_contract.py:22-36` |
| 5. 只删除业务 capability proxy，保留合法 adapter identity | 是 | pipeline/context 已无 `channel_name == "web_relay"` 能力判断；`runtime_delivery/background.py:235,252`、`runtime_delivery/observer.py:232`、`channel_manager.py:410`、`composition.py:349-351,744` 等 residual 分别是 persisted outbound target、managed guard 或 registry identity |

架构自洽性：未发现依赖方向、跨进程边界或平行机制问题。`channels.base` 不依赖 Gateway，Gateway 内部依旧沿 `InboundPipeline → SessionRunCoordinator → RunDeliveryContext` 的现有 owner 链投影；`personal_assistant` 仍只通过 `agent.sdk` 使用内核。未修改 IM wire、SQLite schema、provider contract 或 Web 前端。

### Prototype / Reference Contract

N/A。

## Validation Evidence

- Validated HEAD: `62422c82c093d61633870d2ebed7850346c20b11`；与 `origin/unit/refactor-521` 一致。
- Focused producer/pipeline/shadow/delivery suite: `196 passed in 10.79s`.
- All architecture contracts: `150 passed in 5.85s`.
- Full non-E2E suite: `3190 passed, 28 warnings in 114.10s`；warnings 为 dependency/deprecation 类，无失败。
- Ruff check: `All checks passed!`.
- Ruff format check: `14 files already formatted`.
- Documentation integrity: `219 maintained Markdown sources, 67 required routes`.
- `git diff --check 48d19d8a7809805efcb7631e75079cc09daf2eab..62422c82c093d61633870d2ebed7850346c20b11`: passed.
- Worker isolated-stack evidence: `docs/changes/refactor-521-relay-typed-ingress/M1-typed-ingress-cutover/progress.md:40-43` 记录 Web critical paths `4 passed` 与专用 Feishu probe 通过；本 verifier 不以该记录替代 product reviewer 的独立旅程验收。

## Issues

### CRITICAL（提 PR 前必须修）

None.

### WARNING（提 PR 前必须修）

None.

### SUGGESTION（可以修）

None.
