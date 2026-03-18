# M231 群聊广播：IM relay 多 agent 广播 + gateway fan-out 撤销

## 目标

1. IM relay_service 群聊时为每个 participant agent 各创建一条独立 relay task
2. messages.py create_message 对每个 participant agent 各调一次 enqueue_relay + push_relay_message
3. inbound_pipeline.py 移除 for other_id 的 fan-out 广播 loop 和回复广播逻辑，保留 GroupContextStore buffer 逻辑

## Prevention Rules

- messages.py 循环中每条 relay 独立处理失败，一个 agent 节点离线不能阻断其他 agent 的 relay
- _resolve_agent_snapshot 返回类型从单值改为列表，调用方需同步调整

---

## R1: relay_service — 群聊多 agent broadcast

**状态：** DONE

### Acceptance

1. 群聊消息时 `enqueue_message_relay` 为每个 participant agent 创建独立 relay task，每条 relay 的 `payload.agent_id` 各不相同
2. 直聊消息保持原有单 relay 行为
3. `mentioned_agent_ids` 写入每条 relay 的 `metadata`（告知 gateway 由它判断执行还是缓存）
4. 各 agent relay 使用独立 idempotency_key（`{base_key}:{agent_id}`）
5. 返回 `list[RelayEnqueueResult]`（群聊多条，直聊单条列表）

### Tests Plan

- unit：核心逻辑，覆盖群聊多 relay、直聊单 relay、幂等性
- contract：不选（无 HTTP 边界）
- integration：不选（relay_service 自身无跨服务依赖）
- e2e：不选（由 R2 的路由层覆盖）

### Expected Tests

- `tests/unit/IM/test_relay_service_broadcast.py`
  - `test_group_chat_creates_one_relay_per_participant_agent`
  - `test_direct_chat_creates_single_relay`
  - `test_group_relay_each_carries_mentioned_agent_ids`
  - `test_group_relay_idempotency_is_per_agent`

### DoD

- `test_command` 全绿
- C1/C2/C3 提交齐全
- PROGRESS 写清决策/证据/哈希

---

## R2: messages.py — 群聊 per-agent relay loop

**状态：** TODO

### Acceptance

1. `create_message` 路由群聊时对每个 participant agent 调一次 enqueue_relay + push_relay_message
2. 单个 agent 节点离线（push 返回 False）只记录 failure，不 raise HTTP 503，继续其他 agent
3. 所有 agent 均离线时才返回 503
4. 直聊行为保持不变（单 relay 单 push）

### Tests Plan

- unit：mock gateway_handler，验证群聊多次 push 被调用
- contract：不选
- integration：不选（gateway 是外部）
- e2e：不选

### Expected Tests

- `tests/unit/IM/test_messages_broadcast.py`
  - `test_group_message_pushes_relay_to_each_agent`
  - `test_group_message_partial_push_failure_continues`
  - `test_group_message_all_push_failure_returns_503`

### DoD

- `test_command` 全绿
- C1/C2/C3 提交齐全
- PROGRESS 写清决策/证据/哈希

---

## R3: inbound_pipeline.py — 移除 gateway fan-out loop

**状态：** TODO

### Acceptance

1. `handle_inbound` 移除 `for other_id in self._agents:` 两个广播 loop（消息广播 + 回复广播）
2. 保留 `GroupContextStore`、`_group_buf_key_for_agent`、buffer drain 逻辑
3. 只针对本 relay 的 `agent_id` 判断执行/缓存
4. 现有测试全绿（不引入回归）

### Tests Plan

- unit：验证移除后单 agent 路径仍正确，group_context_store buffer/drain 仍正常
- contract：不选
- integration：不选
- e2e：不选

### Expected Tests

- `tests/unit/personal_assistant/test_gateway_pipeline.py`（现有测试保持全绿）
- 新增少量断言：fan-out loop 不再向其他 agent 追加 buffer

### DoD

- `test_command` 全绿
- C1/C2/C3 提交齐全
- PROGRESS 写清决策/证据/哈希
