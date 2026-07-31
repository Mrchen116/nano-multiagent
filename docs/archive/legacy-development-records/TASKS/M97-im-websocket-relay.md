# M97 - IM WebSocket Server + 消息中继

已在编码前阅读：`SPEC.md`、`docs/IM-SPEC.md`、`docs/内核设计SPEC.md`、`LOGBOOK.md`、`ROADMAP.md`、`COMMENTING_GUIDE.md`。

- Milestone: M97 / IM WebSocket Server + 消息中继
- Branch: `milestone/M97`
- Worktree: `/Users/czj/Repos/nano-multiagent/.worktrees/M97`
- Test Command: `cd /Users/czj/Repos/nano-multiagent/.worktrees/M97 && PYTHONPATH=src pytest -q tests/im_service`
- Prevention Rules:
  1. 先跑真实基线测试，再开始编码。
  2. 大范围编辑后回查负向断言与 import path，避免遗留并行结构。
  3. 保持唯一 canonical 结构；兼容层必须最小且有理由。
  4. TASKS/PROGRESS 明确注明已先阅读 SPEC 与模块 SPEC。

## R1 WebSocket 连接管理与协议骨架
- Status: TODO
- Acceptance:
  - `src/IM/ws/gateway_handler.py` 不再是占位，实现 Gateway 连接注册、断开清理、消息分发。
  - 上行协议支持 `node.register` / `node.heartbeat` / `node.report` / `node.delivery_receipt`。
  - 下行协议支持 `relay.message` / `config.sync` / `heartbeat.trigger`。
  - FastAPI app 暴露 Gateway WebSocket 入口。
- Tests Plan:
  - unit: 覆盖 handler 协议校验、连接映射、断开清理。
  - integration: 通过 TestClient websocket 验证注册、下推、回执闭环。
  - contract: 稳定消息 envelope 结构与错误语义。
- Expected Tests:
  - `tests/im_service/unit/test_gateway_handler.py`
  - `tests/im_service/integration/test_gateway_websocket_api.py`
  - `tests/im_service/contract/test_gateway_protocol_contract.py`

## R2 RelayService + RelayTask 幂等中继
- Status: TODO
- Acceptance:
  - `src/IM/application/relay_service.py` 实现 RelayTask 创建、去重与状态推进。
  - 使用 `idempotency_key` 保证重复请求不产生重复 relay task。
  - 消息创建后可生成 relay task 并下推 `relay.message`。
  - 上行 delivery receipt 可回写 relay task 状态。
- Tests Plan:
  - unit: 验证同 idempotency_key 只生成一个任务，receipt 推进 sent/completed/failed。
  - integration: API 发消息后 Gateway 收到 `relay.message`。
  - contract: relay payload 字段和任务状态语义稳定。
- Expected Tests:
  - `tests/im_service/unit/test_relay_service.py`
  - `tests/im_service/integration/test_gateway_websocket_api.py`
  - `tests/im_service/contract/test_gateway_protocol_contract.py`

## R3 文档/任务收口与负向复查
- Status: TODO
- Acceptance:
  - TASKS/PROGRESS 记录 baseline、实现决策、证据、回滚点。
  - 复查 import path 与旧占位残留，保持 canonical 结构。
  - `PYTHONPATH=src pytest -q tests/im_service` 全绿。
  - 完成后更新 `data/dev-tasks.json` 为 DONE 并写入 result。
- Tests Plan:
  - full: `cd /Users/czj/Repos/nano-multiagent/.worktrees/M97 && PYTHONPATH=src pytest -q tests/im_service`
