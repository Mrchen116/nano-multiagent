# M232 群聊 system prompt 成员注入（before_agent_start hook）

## Milestone 目标

SPEC §7：每个 Agent 在 session 启动时，通过 `before_agent_start` hook 在系统提示词后追加通信上下文。

1. gateway 创建 kernel session 时，把群聊元信息写入 session metadata
2. products/personal_assistant 产品侧 `before_agent_start` hook 读取 metadata，追加上下文块

## Roadpoints

---

### R1 gateway session metadata 写入群聊元信息

**状态**: DONE

**目标**：在 `InboundPipeline._build_session_metadata` 中，写入 `conversation_type`、
`participant_agent_ids`、`external_chat_id`（当消息为群聊时）。

**Acceptance**（3 条）:
1. group chat 消息创建的 session metadata 含 `conversation_type: "group"`
2. group chat session metadata 含 `participant_agent_ids`（来自 `mentioned_agent_ids` 或空列表）
3. direct chat session metadata 含 `conversation_type: "direct"` 且无 `participant_agent_ids`

**Tests Plan**:
- unit：测试 `_build_session_metadata` 输出（group/direct 两种场景）
- contract：metadata dict 字段类型断言
- integration：不需要（已有 pipeline 集成测试覆盖 session 创建调用）
- e2e：不需要（此 milestone scope 内 kernel 不变）

**Expected Tests**:
- `tests/unit/personal_assistant/test_gateway_pipeline.py`：新增 `test_session_metadata_group_fields` 和 `test_session_metadata_direct_fields`

**DoD**: `test_command` 全绿 + C1/C2/C3

---

### R2 before_agent_start hook 追加通信上下文块

**状态**: DONE

**目标**：在 `src/agent/products/personal_assistant/hooks/__init__.py` 的 `setup()` 中注册
`before_agent_start` handler。handler 读取 `ctx.metadata` 中的 `conversation_type` 和
`participant_agent_ids`，在群聊时追加上下文块到 system_prompt；直聊追加简化版。

设计说明：
- 生产路径：runtime 目前不向 hook_ctx.metadata 注入 session metadata（core 层不在 M232 scope）。
  hook 从 `ctx.metadata` 读取 `conversation_type`，若字段缺失则不追加（安全降级）。
- 单测路径：测试直接用 `HookContext(session_id=..., metadata={"conversation_type":"group", ...})` 注入，
  验证群聊/直聊输出差异。

**Acceptance**（4 条）:
1. group chat 时 hook 返回包含 `system_prompt` 键且不为 None 的 dict
2. group chat system_prompt 末尾含 `[Communication Context]` 块，包含 agent_id 和 participant_agent_ids
3. direct chat（conversation_type="direct"）时追加简化版（仅 agent_id，无 participants）
4. 无 conversation_type 字段时 hook 返回 None（安全降级）

**Tests Plan**:
- unit：`tests/unit/personal_assistant/test_before_agent_start_hook.py`，覆盖 group/direct/缺字段 三场景
- contract：hook 函数签名为 `(payload, ctx) -> dict | None`；返回值符合 before_agent_start 契约
- integration：不需要（hook 是纯函数，无副作用，无外部依赖）
- e2e：不需要（scope 内不涉及真实 kernel 运行）

**Expected Tests**:
- `tests/unit/personal_assistant/test_before_agent_start_hook.py`

**DoD**: `test_command` 全绿 + C1/C2/C3
