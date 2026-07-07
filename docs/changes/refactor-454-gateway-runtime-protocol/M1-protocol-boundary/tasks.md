# refactor-454-M1: protocol-boundary — Tasks

> 对齐: ../design.md v1

## 目标

收口 Gateway/IM runtime protocol 边界，不改变 Web IM relay、shadow metadata、delivery receipt 和 workspace_root 用户可见行为。IM 侧新增 package-local Gateway frame parser；Gateway 侧让 Web relay 入站产生 typed runtime facts；workspace 运行时权威统一为 Gateway local config wins。

## 退出标准

- [ ] Web IM direct/group relay、重复 relay、shadow metadata、delivery receipt 的用户可见行为与 motivation.md 对应场景一致。
- [ ] IM profile workspace 与 Gateway local config 不一致时，runtime 文件读写/heartbeat/cron 仍使用 local workspace。
- [ ] 新增 contract fixture 覆盖 relay/streaming/receipt/external identity 字段。
- [ ] `WebRelayAdapter` 落 `InboundEnvelope(message, protocol)` 或等价 wrapper，runtime delivery facts 从 `protocol` 读取，raw relay metadata 不再被 lifecycle/observer 重新 parse。
- [ ] `reconcile_all_agents()` local-wins 红测补齐。
- [ ] 指定门禁测试全绿：
  `pytest tests/unit/personal_assistant/test_gateway_web_relay_adapter.py tests/unit/personal_assistant/test_gateway_im_config_sync.py tests/unit/personal_assistant/test_gateway_reconcile_on_connect.py tests/unit/personal_assistant/test_gateway_upstream_reporter.py tests/im_service/integration/test_gateway_websocket_api.py`

## 测试策略

- 被测行为（来自退出标准）：
  - IM/Gateway protocol fixtures 能被 IM parser 和 Gateway relay adapter 按同一字段语义消费。
  - relay adapter 输出 typed runtime protocol facts，delivery lifecycle 从 typed facts 读取 relay/shadow/external identity/receipt 字段。
  - `sync_agent()` 与 `reconcile_all_agents()` 都保持 Gateway local workspace 权威。
  - 现有 WS relay/report/receipt integration 行为不变。
- 已有测试在：
  - `tests/im_service/contract/test_gateway_protocol_contract.py`（扩展），覆盖 fixture/schema。
  - `tests/im_service/integration/test_gateway_websocket_api.py`（扩展），覆盖 WS entry 对 typed parser 的兼容行为。
  - `tests/unit/personal_assistant/test_gateway_web_relay_adapter.py`（扩展），覆盖 `InboundEnvelope`/runtime protocol facts 和 dedup。
  - `tests/unit/personal_assistant/test_gateway_relay_lifecycle.py`（扩展），覆盖 lifecycle 读取 typed protocol facts。
  - `tests/unit/personal_assistant/test_gateway_im_config_sync.py`、`tests/unit/personal_assistant/test_gateway_reconcile_on_connect.py`（扩展），覆盖 workspace local-wins。
- 落层/目录/marker：`tests/unit/`、`tests/im_service/contract/`、`tests/im_service/integration/`，marker：无。
- 可选依赖 importorskip：无。
- 本 milestone 产生的一次性验收证据（收尾删除，不进套件）：无。

前端 UI：N/A。本 milestone 不改前端客户端面。

## Roadpoints

### R1 — IM gateway protocol fixture/parser

- 状态: DONE
- 步骤:
  - 扩展 gateway protocol contract/integration 测试，先用 fixture 断言 relay/streaming/receipt/report 字段解析。
  - 新增 `src/IM/ws/gateway_protocol.py`，让 `GatewayHandler` 在 `node.report`、`node.streaming_delta`、`node.delivery_receipt` 路径消费 typed event。
- 验证:
  - `pytest tests/im_service/contract/test_gateway_protocol_contract.py tests/im_service/integration/test_gateway_websocket_api.py`

### R2 — Gateway relay runtime protocol handoff

- 状态: DONE
- 步骤:
  - 新增 Gateway-local `runtime_protocol.py`，表达 external identity、shadow ref、reply target、relay task/runtime facts。
  - 调整 `WebRelayAdapter` 输出 `InboundEnvelope(message, protocol)` 或等价 wrapper，并把 lifecycle delivery facts 从 protocol 读取。
  - 调整 `session_keys.py` / `inbound_pipeline.py` 的 external identity 调用点使用 typed helper，保留现有用户行为。
- 验证:
  - `pytest tests/unit/personal_assistant/test_gateway_web_relay_adapter.py tests/unit/personal_assistant/test_gateway_relay_lifecycle.py`

### R3 — Gateway workspace authority local-wins

- 状态: DONE
- 步骤:
  - 新增 `workspace_authority.py`，统一 `sync_agent()` 与 `reconcile_all_agents()` 的 workspace 解析。
  - 补齐 `reconcile_all_agents()` local-wins 红测，确保 IM mirror workspace 不覆盖 runtime/local config。
- 验证:
  - `pytest tests/unit/personal_assistant/test_gateway_im_config_sync.py tests/unit/personal_assistant/test_gateway_reconcile_on_connect.py`

### Final Gate

- 状态: DOING
- 步骤:
  - 跑派发要求的五文件门禁。
  - 回填本文件状态与 `progress.md` 证据。
- 验证:
  - `pytest tests/unit/personal_assistant/test_gateway_web_relay_adapter.py tests/unit/personal_assistant/test_gateway_im_config_sync.py tests/unit/personal_assistant/test_gateway_reconcile_on_connect.py tests/unit/personal_assistant/test_gateway_upstream_reporter.py tests/im_service/integration/test_gateway_websocket_api.py`
