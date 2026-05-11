# feat-340-M10 — Progress

## 触发点 diagram(对齐风险 7 要求)

```
PA gateway WS  ──▶  _handle_register   ┐
                                       │
PA gateway WS  ──▶  _handle_heartbeat  ┼─▶ diff(prior.status vs current.status)
                                       │      │
WS finally     ──▶  disconnect()       ┘      ▼
                                          status 翻转?
                                            ├─ 否 → 不广播 (重要,避免风暴)
                                            └─ 是 → build_node_status_changed_payload
                                                    + broadcast_to_user(owner_id, frame)
                                                    + 每个 agent_profiles(node_id=...)
                                                      emit agent.status_changed
                                                       (折叠为与 node.status 同步,见决策)

asyncio task run_offline_guard:
  every 10s:
    for each row where status='online' AND last_heartbeat_at < now-60s:
      ⤷ mark_disconnected → 同上路径 emit offline
```

## 钉死的决策(超出 design 决策 11 的部分留给 worker)

1. **offline timeout**: 60 秒(= heartbeat_interval 15s × 4)。理由:Gateway 默认 heartbeat 15s
   一次,4 个间隔后仍无心跳是合理 unreachable 判定阈值;避免太短导致 flapping。
2. **scan interval**: 10 秒。理由:守护任务粒度 ≤ timeout/6,保证翻转延迟最坏不超过
   ~70s,实现成本低。
3. **seq 号策略**: owner-scoped 单调递增,由 `GatewayHandler` 维护一个 `dict[owner_id, int]`
   计数器(per-owner,而非全局,避免不同 owner 看到稀疏序列)。`message.*` / `tool_call.*`
   原 conversation-scoped seq 不受影响。
4. **agent.status 派生**: design 决策 11 显式说"agent.status 字段语义若不明,折叠 follow
   node.status"。本 milestone 采用最小决策:`agent_profiles` 表里所有 `node_id = <该 node>`
   的 agent,在 node 翻转时统一 emit 同 status 的 `agent.status_changed`。后续 M6 / M5
   消费时仅消费此事件即可。
5. **frame 编码**: `json.dumps(..., ensure_ascii=True, separators=(",", ":"))`,与
   `encode_user_stream_event_frame` 一致;最外层用 `op="event"` + `event_type` 包,
   payload 由 builder 产出 — 让前端解析器复用同一条 reducer。

## R1 — payload builders + broadcast_to_user

- Context: 决策 11 要求 owner-scoped 单 user 广播;现有 `broadcast_to_users` 接 Iterable[str],
  调用方写一个 frozenset 包装就够用。但 design 明确说"加便利函数"——这里加单 user 薄包装,
  内部直接 delegate 到 `broadcast_to_users({user_id}, text)`,不引新索引,不破坏死连接清理路径。
- Decision:
  - `event_types.py` 增 `build_node_status_changed_payload` / `build_agent_status_changed_payload`,
    payload 字段对齐 design §4。
  - `user_stream.py` 加 `UserStreamRegistry.broadcast_to_user(user_id, text)` —
    单参数,内部委托 `broadcast_to_users` 既有路径。
- Rationale: 复用既有 fan-out + 死连接清理路径,符合决策 11 "不引入新索引"。
- Evidence: `pytest tests/im_service/unit/test_ws_event_types.py tests/im_service/unit/test_user_stream.py` → 14 passed。
  `pytest tests/im_service/unit` → 93 passed,无回归。
- Rollback: revert C1+C2 commit。
- Commits: C1=54cd9184, C2=b0259e21, C3=R1-doc

## R2 — GatewayHandler 状态 diff + emit

- Context: 三个 producer 点 register / heartbeat / disconnect 都已经写 DB,只需在写 DB 前后
  各取一次 status 快照,翻转时 broadcast。
- Decision:
  - `GatewayHandler.__init__` 增 `user_stream_registry: UserStreamRegistry | None = None`。None 时
    所有 broadcast 调用是 no-op(保持单元测试 + 既有调用兼容)。
  - 维护 `self._status_seq_by_owner: dict[str, int]`,加锁递增。
  - `_handle_register`:`prior = node_repo.get_node(node_id)`(可能 None);`record_gateway_registration`
    后必为 online。`prior is None or prior.status != "online"` → emit online。
  - `_handle_heartbeat`:`prior = node_repo.get_node(node_id)`,`record_heartbeat` 后取 next;
    `prior.status != next.status` → emit。
  - `disconnect`:`prior = node_repo.get_node`;`mark_disconnected`;若 `prior is not None and prior.status != "offline"` → emit offline。
- Rationale: status 由 NodeRepository 内 `_normalize_node_status` 派生,直接在 record_xx 前后取
  before/after 是最简单 truthful 的 diff 方式。
- Evidence: `test_gateway_status_broadcast.py` 覆盖单 owner 翻转 + 跨 owner 隔离 +
  diff 不变不广播。
- Rollback: revert 该 R 的 C2 即可。
- Commits: C1=<填>, C2=<填>, C3=<填>

## R3 — offline guard 异步任务

- Decision: `user_stream.py` 内新增 async def `run_offline_guard(*, handler, node_repository,
  interval_seconds=10, timeout_seconds=60)`,扫 `nodes` 表 `status='online' AND
  last_heartbeat_at < cutoff` 行,逐一调用 `handler.force_mark_offline(node_id=..., reason="heartbeat_timeout")`。
  `force_mark_offline` 内部复用 R2 的 emit 路径(等价于 disconnect,但不影响 in-memory
  `_connections`——心跳超时 worker 之所以会发生,往往是连接已经物理失效但 finally 还没跑,
  所以两条路径都覆盖一次,接受幂等)。
- Rationale: design 风险 1 明确要求"asyncio task 每 10s 扫一次",参数提取出来便于单测。
- Evidence: `test_offline_guard.py` 直接构造一次扫描,断言 broadcast 调用 + DB 翻转。
- Commits: C1=<填>, C2=<填>, C3=<填>

## R4 — e2e + 文档收尾

- Decision: `tests/im_service/integration/test_status_broadcast_e2e.py` 用 FastAPI TestClient
  起 app,两个 owner 的 token 各开一条 `/im/ws/user`,PA 在 `/im/ws/gateway` 发 register,断言
  正确 owner 收到帧、另一个 owner 没收到。
- Evidence: 集成测试绿,acceptance 命令通过。
- Commits: C1=<填>, C2=<填>, C3=<填>
