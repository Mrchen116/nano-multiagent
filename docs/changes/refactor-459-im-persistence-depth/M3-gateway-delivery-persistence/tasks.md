# refactor-459-M3: Gateway delivery persistence — Tasks

> 对齐: ../design.md

## 目标

在不改变 Gateway 投递、会话、过程事件和重启恢复行为的前提下，让 `GatewayConversationPersistence`
成为 delivery 路径唯一的 SQLite knowledge owner，`GatewayHandler` 只保留协议、连接和投递编排。

## 退出标准

- [ ] dispatch DDL 在 schema initialization 中幂等创建，列 shape 与已有数据不变。
- [ ] `GatewayConversationPersistence` 集中 target classification、canonical direct、group fanout、dispatch first-write-wins、missing-node、system user 和 usage scope 查询。
- [ ] `GatewayHandler` 不再访问 repository private connection 或执行 SQL；agent-message 显式向 `resolve_send_target` 传 `caller_owner_id=None`，不推断/修复 owner。
- [ ] 真进程证据覆盖 relay/group/agent-user-conversation target、过程事件和重启后 dispatch 重复抑制/恢复。
- [ ] `pytest -m "not e2e"`、`scripts/e2e-critical.sh -m "not slow"` 与 ruff 全绿。

## 测试策略

- 被测行为（来自退出标准）：schema shape/旧数据、target classification 与 caller owner input、canonical direct 复用、group fanout/missing node、dispatch first-write-wins、handler 协议结果与真进程重启恢复。
- 已有测试在：`tests/im_service/unit/test_db_init.py`、`tests/im_service/unit/test_gateway_handler.py`、`tests/im_service/integration/test_gateway_websocket_api.py`、`tests/contract/test_im_persistence_seam_contract.py`（扩展）；新建 `tests/im_service/unit/test_gateway_conversation_persistence.py`，理由：现有 node persistence 测试只覆盖 node lifecycle，delivery concrete module 需要独立真 SQLite interface surface。
- 落层/目录/marker：`tests/im_service/unit/` 与 `tests/contract/`，marker：无；真进程临时验收不进 pytest 套件。
- 可选依赖 importorskip：无。
- 本 milestone 产生的一次性验收证据（收尾删除，不进套件）：通过真 IM/Gateway 进程与同一 SQLite DB 重启执行的命令/日志/数据库摘要，结论持久记入 `progress.md`。
- 用户路径分类：N/A（非前端）。
- UI 状态矩阵：N/A。
- Prototype / Reference Contract：N/A。

## Roadpoints

### R1 — 建立 Gateway conversation persistence interface

- 状态: DONE
- 步骤: 先用真 SQLite 红测锁定 DDL shape、target/canonical direct、caller owner input、fanout/missing node、dispatch first-write-wins；再实现 typed results 与 concrete module。
- 验证: 新 module/schema 测试、ruff，并审计不冻结 issue #128 的 orphan-owner 行为。

### R2 — 收口 handler 并完成真栈恢复验收

- 状态: DOING
- 步骤: 用 contract/handler 红测驱动 composition 注入，删除 handler 内 private connection/SQL/persistence helpers；清理被 module interface 替代的 private-state 测试。
- 验证: 相关 unit/integration/contract、真 IM+Gateway 进程 relay/group/target/过程事件/同 DB 重启重复抑制，最终全量 non-e2e、e2e-critical not-slow、ruff。
