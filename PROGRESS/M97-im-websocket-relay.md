# M97 - IM WebSocket Server + 消息中继

已在编码前阅读：`SPEC.md`、`docs/IM-SPEC.md`、`docs/内核设计SPEC.md`、`LOGBOOK.md`、`ROADMAP.md`、`COMMENTING_GUIDE.md`。

## Baseline
- Tests: `cd /Users/czj/Repos/nano-multiagent/.worktrees/M97 && PYTHONPATH=src pytest -q tests/im_service`
- Result: 24 passed
- Notes:
  - `src/IM/ws/gateway_handler.py` 仍是占位，当前尚无 Gateway WebSocket 入口。
  - 现有 IM 测试只覆盖 HTTP + SSE，尚未覆盖 IM-SPEC §4 的 WebSocket 协议与 relay 幂等逻辑。

### R1 WebSocket 连接管理与协议骨架
- Context: 基线中 `src/IM/ws/gateway_handler.py` 只有占位类，IM 服务没有 Gateway WebSocket 入口，也没有 IM-SPEC §4 的协议处理。
- Decision: 实现 `GatewayHandler` 作为单例连接管理器，维护 `node_id -> websocket` 映射；在 `create_app()` 中挂载 `/im/ws/gateway`；支持 `node.register` / `node.heartbeat` / `node.report` / `node.delivery_receipt` 上行，以及 `relay.message` / `config.sync` / `heartbeat.trigger` 下推。
- Rationale: 先收口在 canonical `ws/gateway_handler.py` 中实现协议管理，避免把连接态散落到 route/app 逻辑里，便于后续 M99/M102 在同一协议层继续扩展。
- Evidence:
  - Tests: `PYTHONPATH=src pytest -q tests/im_service/unit/test_gateway_handler.py tests/im_service/integration/test_gateway_websocket_api.py tests/im_service/contract/test_gateway_protocol_contract.py`
  - Entry: `/Users/czj/Repos/nano-multiagent/.worktrees/M97/src/IM/ws/gateway_handler.py`、`/Users/czj/Repos/nano-multiagent/.worktrees/M97/src/IM/app.py`
- Rollback: working tree HEAD before commit
- Commits: C1=, C2=, C3=
- Next: 把 WebSocket 下推与消息创建接线到 relay 任务层，并补幂等状态测试。

### R2 RelayService + RelayTask 幂等中继
- Context: M94 只把 `RelayTask` 放进 domain，占位但未落库；消息创建仍是纯 HTTP/SSE 路径，没有中继和 `idempotency_key` 语义。
- Decision: 新增 `application/relay_service.py`，在 SQLite 中引入 `relay_tasks` 表；扩展 `RelayTask` 字段为 `relay_task_id/conversation_id/created_at/updated_at/receipt_*`；消息 API 增加可选 `target_node_id`，并通过 `Idempotency-Key` 或稳定默认键创建/复用 relay task，再由 `GatewayHandler` 下推 `relay.message`，delivery receipt 回写 sent/completed/failed。
- Rationale: 将幂等逻辑集中在 `RelayService`，HTTP route 只做编排，WebSocket handler 只做协议收发，保持 application/ws 边界清晰。
- Evidence:
  - Tests: `PYTHONPATH=src pytest -q tests/im_service/unit/test_relay_service.py tests/im_service/integration/test_gateway_websocket_api.py`
  - Entry: `/Users/czj/Repos/nano-multiagent/.worktrees/M97/src/IM/application/relay_service.py`、`/Users/czj/Repos/nano-multiagent/.worktrees/M97/src/IM/api/routes/messages.py`、`/Users/czj/Repos/nano-multiagent/.worktrees/M97/src/IM/infra/db.py`
- Rollback: working tree HEAD before commit
- Commits: C1=, C2=, C3=
- Next: 跑完整 IM 测试集，更新任务文档与 board 状态。

### R3 文档/任务收口与负向复查
- Context: 本次改动跨 app/api/application/domain/infra/ws/test，多处接线后需要复查同步/异步边界与 canonical imports，避免再留下 placeholder 或双路径实现。
- Decision: 将消息创建入口改为 async，直接 `await gateway_handler.push_relay_message(...)`，移除同步 route 中 `asyncio.run(...)` 的错误路径；补 TASKS/PROGRESS；全量执行 `tests/im_service` 复查回归。
- Rationale: 遵守“单一 canonical 结构”与负向复查规则，避免在 HTTP 入口里留下隐藏的 async 兼容分支。
- Evidence:
  - Tests: `cd /Users/czj/Repos/nano-multiagent/.worktrees/M97 && PYTHONPATH=src pytest -q tests/im_service`
  - Result: `33 passed`
  - Entry: `/Users/czj/Repos/nano-multiagent/.worktrees/M97/TASKS/M97-im-websocket-relay.md`、`/Users/czj/Repos/nano-multiagent/.worktrees/M97/PROGRESS/M97-im-websocket-relay.md`
- Rollback: working tree HEAD before commit
- Commits: C1=, C2=, C3=
- Next: 更新 `data/dev-tasks.json`，提交、合并到 local main，并清理 M97 worktree。

## Final Test Snapshot
- `cd /Users/czj/Repos/nano-multiagent/.worktrees/M97 && PYTHONPATH=src pytest -q tests/im_service`
- Result: 33 passed
- Scope Check:
  - 仅修改 IM websocket / relay 相关后端代码、对应 IM tests、TASKS/PROGRESS。
  - 未触碰 M95/M96/M100、gateway/personal_assistant、或 worktree 外其他源码。
