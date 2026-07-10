# feat-340-M10: backend-status-broadcast — Tasks

> 对齐: ../design.md (Changelog 2026-05-11, 决策 11, §5 映射表, 风险 7)

## 目标

PA gateway 节点 register / heartbeat / disconnect / 心跳超时 任一事件触发后,
浏览器侧 owner 的 WebSocket(`/im/ws/user`)收到对应 `node.status_changed`
(并对该节点 agent 列表 emit `agent.status_changed`),跨 owner 隔离,
diff 不变不广播。

## 退出标准

- [x] `src/IM/ws/user_stream.py` 新增 `broadcast_to_user(user_id, frame_dict)` 便利函数。
- [x] `src/IM/api/ws/event_types.py` 新增 `build_node_status_changed_payload` / `build_agent_status_changed_payload`。
- [x] `GatewayHandler._handle_register`:diff 旧 status → 新 online,变化时发 owner-scoped node + agent 事件。
- [x] `GatewayHandler._handle_heartbeat`:diff status,仅状态翻转时广播。
- [x] `GatewayHandler.disconnect`(WS finally 路径):node 由 online→offline 时广播 offline 帧。
- [x] 新增 asyncio offline 守护任务(`run_offline_guard`),每 10s 扫 `nodes.last_heartbeat_at` 过期 60s,翻转为 offline 并广播,在 `IM/app.py` lifespan 启动 / 取消。
- [x] 单测覆盖:diff 不变不广播 / 跨 owner 隔离 / 首次 register 广播 online / disconnect 广播 offline / offline guard 翻转。
- [x] 集成测试:WS 端到端 — register WS gateway → owner WS 收 node.status_changed: online。

## 测试策略

按设计 §3.1 "测试必须证明产品能用"准则:

| 层级 | 文件 | 验证什么 |
|---|---|---|
| 单元 | `tests/im_service/unit/test_ws_event_types.py` (扩) | 两个 payload builder 字段稳定 |
| 单元 | `tests/im_service/unit/test_user_stream.py` (扩) | `broadcast_to_user` 单 user fan-out + 死连接清理 |
| 单元 | `tests/im_service/unit/test_gateway_status_broadcast.py` (新) | 四个触发点 + diff 不变不广播 + 跨 owner 隔离 |
| 单元 | `tests/im_service/unit/test_offline_guard.py` (新) | `run_offline_guard` 扫描超时并广播 |
| 集成 | `tests/im_service/integration/test_status_broadcast_e2e.py` (新) | 真起 FastAPI + TestClient,PA gateway WS 发 register,owner WS 收 online 帧;PA 断开收 offline |

## Roadpoints

### R1 — payload builders + broadcast_to_user 便利函数
- 步骤: 在 `event_types.py` 加两个 builder + 常量;在 `user_stream.py` `UserStreamRegistry` 加 `broadcast_to_user`。
- 验证: 新建 / 扩展单元测试,确认 payload 字段、broadcast 单 user 命中、死连接清理。

### R2 — GatewayHandler 注入 status diff + emit 路径(register / heartbeat / disconnect)
- 步骤: 给 `GatewayHandler` 注入 `user_stream_registry` + seq 计数器;在 `_handle_register` / `_handle_heartbeat` / `disconnect` 三处计算 node + agents diff 并 broadcast。
- 验证: `test_gateway_status_broadcast.py` 覆盖四个场景。

### R3 — Offline 守护任务
- 步骤: `user_stream.py` 加 `run_offline_guard(handler, registry, node_repo, interval=10, timeout=60)`;`app.py` lifespan 启动并 cancel。
- 验证: 单测,把"now" / 阈值参数化,模拟 stale 节点。

### R4 — 集成 e2e + 文档
- 步骤: `test_status_broadcast_e2e.py` 通过 FastAPI TestClient 真发 WS 帧。
- 验证: TestClient 收 `node.status_changed` 帧并断言字段;tasks.md + progress.md 写完。
