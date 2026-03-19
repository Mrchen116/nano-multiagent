# M247 群聊 sender 显示名：传递用户 display name 替代原始 ID

## Goal
群聊参与者（用户和 agent）都同时传递 id 和 display_name。id 用于 @mention，display_name 用于可读展示，两者都出现在 Communication Context 和消息前缀中。IM relay 层负责解析 display_name，gateway 透传，不做查询。

## Roadpoints

### R1 relay_service 添加 sender/participants 字段
**Acceptance:**
1. 群聊 relay payload 中 `sender` 字段包含 `{id, display_name, type}` （用户从 users 表解析，agent 从 agent_profiles 解析）
2. 群聊 relay payload 中 `participants` 字段是 `[{id, display_name, type}]` 列表
3. `display_name` fallback：users 表无记录时用 id，agent_profiles 无记录时用 agent_id
4. 直聊 relay payload 不受影响（向后兼容）
5. `type` 字段：用户为 `"user"`，agent 为 `"agent"`

**Tests Plan:**
- unit: `tests/im_service/unit/test_relay_service.py` — 新增函数测试 group relay payload sender/participants 字段
- contract: 不新增（现有 contract tests 覆盖 payload 结构）
- integration: 不新增（用 unit 足够）
- e2e: 不新增

**Expected Tests:**
- `test_group_relay_payload_includes_sender_display_name_and_participants()`
- `test_group_relay_payload_sender_fallback_to_id_when_no_profile()`
- `test_direct_relay_payload_does_not_include_sender_participants()`

**DoD:** test_command 全绿，C1/C2/C3 齐全，PROGRESS 写清决策/证据

**Status:** TODO

---

### R2 web_relay_adapter 解析 sender.display_name 和 participants
**Acceptance:**
1. `RelayEnvelope` 新增 `sender_display_name: str | None` 和 `participants: list[dict]`
2. `_build_inbound` 将 `sender_display_name` 注入 `InboundMessage.metadata["sender_display_name"]`
3. `participants` 注入 `InboundMessage.metadata["participants"]`
4. 向后兼容：payload 没有 `sender` 字段时 `sender_display_name=None`

**Tests Plan:**
- unit: `tests/personal_assistant/unit/test_web_relay_adapter.py` — 测试 parse 和 build_inbound

**Expected Tests:**
- `test_relay_adapter_parses_sender_display_name_from_payload()`
- `test_relay_adapter_builds_inbound_with_sender_display_name_in_metadata()`
- `test_relay_adapter_backward_compat_without_sender_field()`

**DoD:** test_command 全绿，C1/C2/C3 齐全

**Status:** TODO

---

### R3 inbound_pipeline 使用 display_name 替代 UUID 作为 sender 前缀
**Acceptance:**
1. `_format_sender_text` 接收 display_name 时用 display_name，否则 fallback 到 sender_id
2. 群聊 buffer append 时 sender 参数用 display_name（若有）
3. 当前消息的 sender 前缀使用 display_name（fallback UUID）
4. 直聊不受影响

**Tests Plan:**
- unit: `tests/personal_assistant/unit/test_inbound_pipeline_sender_display_name.py`

**Expected Tests:**
- `test_pipeline_uses_display_name_for_group_message_prefix()`
- `test_pipeline_falls_back_to_external_user_id_when_no_display_name()`
- `test_pipeline_buffered_messages_use_display_name_as_sender()`

**DoD:** test_command 全绿，C1/C2/C3 齐全

**Status:** TODO

---

### R4 communication_context hook 更新 participants 格式和 message_format
**Acceptance:**
1. `group_participants` 列出 `[{id, display_name, type}]` 格式（或中文描述）
2. `message_format` 说明：历史消息以 `[display_name]` 标识发言人，agent 回复无需加前缀，@mention 用 id
3. session_metadata 中传递 `participants` 列表（含 id/display_name/type）
4. 向后兼容：当 participants 不含 display_name 时 fallback 到 id

**Tests Plan:**
- unit: `tests/personal_assistant/unit/test_communication_context.py`

**Expected Tests:**
- `test_communication_context_group_participants_with_display_name()`
- `test_communication_context_message_format_says_display_name()`
- `test_communication_context_fallback_to_id_when_no_display_name()`

**DoD:** test_command 全绿，C1/C2/C3 齐全

**Status:** TODO
