# TASKS: M246 — 群聊 buffer 消息结构化：分条 user message + sender 标识

## Milestone 目标

群聊 buffer 消息不再 join 为一条字符串，而是每条作为独立的 user message 进入 LLM 对话历史。
sender 前缀 `[sender_name]` 由 gateway 层拼接到 text 中，内核不感知 sender。
parts 含义扩展为多条 user message 的内容列表，runtime 将每个 part 作为独立 user message
追加到 history（而非 `\n` join）。Communication Context 中增加格式说明。

---

## R1 — GroupContextStore 存储 sender 字段

### Acceptance
1. `_SCHEMA` 增加 `sender TEXT NOT NULL DEFAULT ''` 列
2. `append(buf_key, text, sender)` 写入 sender（默认空字符串保持向后兼容）
3. `drain(buf_key)` 返回 `list[tuple[str, str]]`（`(sender, text)` 对）
4. 空 sender 时 drain 也返回 `("", text)` 格式
5. 旧 DB（缺 sender 列）通过 migration 兼容

### Tests Plan
- unit: 测试 append/drain 新签名，测试 sender 字段持久化，测试 migration
- 不选 contract/integration/e2e（内核层外不感知此字段）

### Expected Tests
- `tests/unit/personal_assistant/test_group_context_store_m246.py`
  - `test_append_and_drain_stores_sender`
  - `test_drain_returns_sender_text_tuples`
  - `test_append_default_sender_is_empty`

### DoD
- `test_command` 全绿 + C1/C2/C3

### Status: TODO

---

## R2 — InboundPipeline: drain 后格式化为独立 parts

### Acceptance
1. `_store_buffered_message(message, agent_id)` 使用 `message.external_user_id` 作为 sender 存入 store
2. `drain()` 后将每个 `(sender, text)` 格式化为 `f"[{sender}] {text}"` 当 sender 非空，否则直接 text
3. 多条 buffered 消息 + 当前消息组合为 `texts: list[str]`（每条独立，无 join）
4. 当前 mention 消息的 sender 也前缀化（`[external_user_id] text`）
5. 向后兼容：无 buffer 时 texts=[msg.text]（单条，行为不变）

### Tests Plan
- unit: 测试 buffer 消息带 sender 前缀，测试多条消息 texts 列表格式

### Expected Tests
- `tests/unit/personal_assistant/test_gateway_pipeline_no_fanout.py`（更新现有测试）
- 新增到 `test_group_context_store_m246.py` 或 `test_gateway_pipeline_m246.py`
  - `test_buffer_drain_formats_sender_prefix`
  - `test_mention_message_sender_prefixed`
  - `test_no_buffer_single_text_unchanged`

### DoD
- `test_command` 全绿 + C1/C2/C3

### Status: TODO

---

## R3 — Runtime: 将 parts 列表每个 part 作为独立 user message 注入 history

### Acceptance
1. `AgentRuntime.run()` 当 `parts` 长度 > 1 时，将每个 part 作为独立 user message 追加到 history
2. 单条 parts（长度=1）行为与之前完全一致（向后兼容）
3. 每个独立 user message 有独立 `message_id`，role="user"
4. LLM 收到 history 时每条 buffer 消息作为独立 `{"role":"user","content":"[sender] text"}` 条目

### Tests Plan
- unit: 测试多 parts → 多 user message in history
- unit: 测试单 part → 单 user message（backward compat）

### Expected Tests
- `tests/unit/test_agent_runtime_m246.py`（新建）
  - `test_multiple_parts_become_independent_user_messages`
  - `test_single_part_backward_compat`

### DoD
- `test_command` 全绿 + C1/C2/C3

### Status: TODO

---

## R4 — Communication Context 增加 message_format 说明

### Acceptance
1. `_build_communication_context_block` 增加 `message_format: [sender_id] message_text` 行
2. 仅群聊时显示此行（conversation_type="group"）
3. 直聊不显示 message_format 行

### Tests Plan
- unit: 更新 `test_before_agent_start_hook.py` 或新增测试

### Expected Tests
- `tests/unit/personal_assistant/test_communication_context_m246.py`
  - `test_group_context_block_includes_message_format`
  - `test_direct_context_block_no_message_format`

### DoD
- `test_command` 全绿 + C1/C2/C3

### Status: TODO
