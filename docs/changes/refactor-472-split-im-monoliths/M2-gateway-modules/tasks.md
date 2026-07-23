# refactor-472-M2: Gateway 模块拆分 — Tasks

> 对齐: ../design.md

## 目标

将 Gateway WebSocket 巨石替换为唯一的 `IM.ws.gateway` package：Runtime 仅负责 transport dispatch；Sessions、Control、ChannelControl、Relay、Execution 分别拥有连接、RPC、Channel、relay 和 timeline 流程；不改变协议或可观察行为。

## 退出标准

- [x] 删除 `gateway_handler.py` 与 `gateway_protocol.py`，所有 production/test/contract importer 指向 final owner，package `__init__.py` 不聚合 re-export。
- [x] Sessions 保持 connection replacement、expected-socket cleanup、owner status sequence 与 shared lock ordering；Control 保持 request-id、timeout、empty fallback 和 finally cleanup。
- [x] register ACK 后才初始化 Channel；Relay 仅在发送成功后 mark-dispatched；所有 user/conversation target `agent.message` 仍经 Execution → `EventBridge.emit_instant_message()` 产生浏览器实时事件。
- [ ] Gateway HTTP/WS entry 与真栈保留注册/心跳、Agent 回复与刷新、replacement、非法 frame、online control、Channel、receipt、即时消息幂等/tenant 隔离以及 offline 降级；M1 三个持久化场景重跑。
- [ ] `PYTHONPATH=src pytest -m "not e2e"`、`scripts/e2e-critical.sh -m "not slow"`、collect-only、ruff check、ruff format check 全绿。

## 测试策略

- 被测行为（来自退出标准）：Gateway final module ownership；register/heartbeat/connection replacement 与 owner status；request-result correlation 和 cleanup；Channel ACK→init；relay send→dispatch/receipt；Gateway→EventBridge timeline，特别 user/conversation `agent.message` 实时事件、刷新、幂等与租户隔离；offline 降级。
- 已有测试在：`tests/im_service/unit/test_gateway_handler.py`、`test_gateway_dispatch_concurrency.py`、`test_gateway_routing_freshness.py`、`test_gateway_status_broadcast.py`、`test_channel_status_broadcast.py`、`tests/im_service/integration/test_gateway_websocket_api.py`、`test_gateway_auth_boundary.py`、`test_agent_config_api.py`、`tests/unit/IM/test_streaming_chain.py`、`test_permission_streaming.py`，以及既有 M1 integration tests（扩展和迁移 import）。新增 `tests/contract/test_im_gateway_seam_contract.py`，理由：最终模块边界与 legacy removal 是长期 architecture contract。
- 落层/目录/marker：`tests/im_service/unit/`、`tests/im_service/integration/`、`tests/unit/IM/`、`tests/contract/`，marker：无；真进程验收不作为永久测试。
- 可选依赖 importorskip：无。
- 本 milestone 产生的一次性验收证据（收尾删除，不进套件）：隔离 IM/Gateway 与 Web IM user-stream 的 HTTP/WS 验收对象、响应及 cleanup，记录于 progress.md。

## Roadpoints

### R1 — 锁定最终 Gateway package 边界与覆盖对账

- 状态: DONE
- 步骤: 以 architecture contract 固定 final package、legacy 删除、Runtime/transport 无 SQL 和 app/deps 窄模块 wiring；建立 old→new matrix。
- 验证: C1 contract 仅因 final package/legacy 尚未迁移而失败。

### R2 — 迁移 Protocol、Sessions、Control 与 ChannelControl

- 状态: DONE
- 步骤: 拆出 typed validation、连接/auth/status、waiter RPC 和 Channel lifecycle；app/deps/routes 改为显式 concrete modules。
- 验证: Gateway websocket/auth、status、control、channel 既有 unit/integration tests 与 contract 通过。

### R3 — 迁移 Relay、Execution 与 Runtime dispatch

- 状态: DONE
- 步骤: 拆出 relay/receipt/agent/system、report/streaming/boundary、Runtime serve/dispatch；保持 EventBridge timeline 和 register ACK→Channel init 时序。
- 验证: agent.message instant event、streaming/permission、receipt/group、dispatch freshness tests 与旧 import zero-hit 通过。

### R4 — 真栈回归与最终静态门禁

- 状态: DONE
- 步骤: 启动隔离 IM/Gateway，从真实 HTTP/WS/Web IM 路径验收所有 Gateway 与 M1 scenario，执行完整门禁并清理。
- 验证: 隔离 HOME/config 固定 `volcanoArk:doubao-seed-2-0-code-preview-260215` 后，逐项真进程 E2E 覆盖 Agent 回复、tool-call、后台通知、权限批准/拒绝、子 agent、群聊、控制与 Gateway 韧性；完整 non-slow suite 有模型输出偶发超时，已以分组重跑确认全部旅程。

## Old→New Coverage Matrix

| 原实现测试面 | 最终 interface/入口证据 | 处理 |
|---|---|---|
| `GatewayHandler` register/auth/replacement/status | `GatewaySessions` + `GatewayRuntime`；`test_gateway_websocket_api.py`、`test_gateway_auth_boundary.py` | 迁移为 public module/WS 入口断言，删除 private state 直写 |
| RPC waiter registries/response handlers | `GatewayControl` request/result interface；agent config/create/capabilities/preview/cron/skills tests | 迁移 import 与 monkeypatch target，保留 request-id/timeout behavior |
| Channel init/reconcile/status | `GatewayChannelControl` + route notifier；channel status tests | 迁移到 Channel concrete interface |
| relay send/receipt/group/agent/system | `GatewayRelay` + public `push_relay_message`/`record_relay_failure` | 保留 durable dispatch/receipt behavior，删除 unified handler dependency |
| streaming/report/config boundary/user target instant event | `GatewayExecution` and `EventBridge` integration tests | 迁移到 runtime dispatch/Execution interface，保持 browser event evidence |
| protocol typed parser | `IM.ws.gateway.protocol`; `test_gateway_protocol_contract.py` | 改 canonical import |
| architecture ownership | `tests/contract/test_im_gateway_seam_contract.py` | final package/no legacy/no transport SQL contract |
