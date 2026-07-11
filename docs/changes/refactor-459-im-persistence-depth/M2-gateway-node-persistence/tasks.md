# refactor-459-M2: Gateway node persistence seam — Tasks

> 对齐: ../design.md v1

## 目标

把 Gateway register、heartbeat、disconnect、timeout 的 node/profile/user/stale 持久化顺序收进 concrete SQLite `GatewayNodePersistence`，让 Gateway handler 与 user-stream 只表达协议、连接和广播意图，并严格保持现有 durable failure state 与对外状态事件不变。

## 退出标准

- [ ] `GatewayNodePersistence` 的真实 SQLite interface 覆盖 first register、re-register、empty advertise、stale reconcile、heartbeat、disconnect/offline no-op/error 与 stale scan。
- [ ] register 不增加 operation-level transaction/lock；第 N 个 agent 失败时 node/profile/user/binding durable rows 与重构前基线逐表一致。
- [ ] Gateway handler 不再读取 node/profile/user raw connection，user-stream 整文件无 private connection/直接 SQL，M1 seam contract 临时例外删除。
- [ ] Gateway register、heartbeat、disconnect、timeout 后 Node/Agent 状态、错误与 owner-scoped 广播时机/shape 不变。
- [ ] 相关 unit/integration、完整 IM non-e2e 与 `ruff check` / `ruff format --check` 全绿。

## 测试策略

- 被测行为（来自退出标准）：first register/re-register 的 profile preserve 与 agent-user ensure；empty advertise/stale reconcile；真实 SQLite trigger 在第 N 个 agent 写入失败时的逐表 durable state；heartbeat 状态归一；disconnect 与 forced-offline 的 no-op/error；stale online node scan；Gateway WS ack 与 owner-scoped node/agent 广播不变；静态 seam 零 private connection/SQL。
- 已有测试在：`tests/im_service/unit/test_gateway_handler.py`、`test_gateway_status_broadcast.py`、`test_offline_guard.py`、`test_nodes_metrics_repositories.py`（扩展/改接线），`tests/im_service/integration/test_gateway_im_registration.py`、`test_gateway_websocket_api.py`（扩展/复用），`tests/contract/test_im_persistence_seam_contract.py`（扩展）；无合适的 caller-oriented module interface 文件，新建 `tests/im_service/unit/test_gateway_node_persistence.py`，理由：跨 node/profile/user 表的 concrete persistence interface 及 transaction failure compatibility 是新的独立行为面，现有 handler/repository 文件分别测协议或单实体且不应承载该 seam。
- 落层/目录/marker：`tests/im_service/unit/`、`tests/im_service/integration/`、`tests/contract/`，marker：无。
- 可选依赖 importorskip：无。
- 本 milestone 产生的一次性验收证据（收尾删除，不进套件）：`scripts/e2e-up.sh` 真 Gateway 进程 register/heartbeat，以及真实 Gateway WebSocket disconnect/timeout 的状态与广播检查；命令、durable rows 对照与结果写入 progress，不保留临时脚本。
- 前端 UI：N/A（无前端或视觉变化）。
- Prototype / Reference Contract：N/A。

## Roadpoints

### R1 — GatewayNodePersistence interface 与 durable failure compatibility

- 状态：DONE
- 步骤：用真实 SQLite 行为测试锁定 register/heartbeat/offline/stale interface；以 trigger 注入第 N 个 agent 失败并记录重构前 durable rows；实现 typed result 与 caller-oriented concrete module，复用既有 repository commit boundaries，不新增外层 transaction/lock。
- 验证：module interface 红转绿；first/re-register/empty/stale/no-op/error/failure injection 全部通过，逐表 durable rows 与 baseline 一致。

### R2 — Gateway handler node lifecycle 接线与广播不变

- 状态：DOING
- 步骤：GatewayHandler 显式接收 `GatewayNodePersistence`，register/heartbeat/disconnect/force-offline 只消费 typed outcome；保留 websocket connection 与广播编排；app composition 显式构造注入。
- 验证：handler/status broadcast 与 Gateway WS/registration integration 红转绿；ack、status、last_error、agent ids、owner 隔离和广播时机不变。

### R3 — Timeout scan 与 seam contract 收口

- 状态：TODO
- 步骤：user-stream offline guard 通过 `stale_online_node_ids` 查询；删除 M1 stale-node 临时例外，contract 升级为 handler/user-stream 整文件无 private connection/SQL；完成真入口与全量门禁。
- 验证：offline guard 与 seam contract 红转绿；真 Gateway/WS register、heartbeat、disconnect、timeout 状态和广播验证；完整 IM non-e2e、ruff check/format 全绿。
