# M232 Progress — 群聊 system prompt 成员注入（before_agent_start hook）

## 概述

实现 SPEC §7 要求的 before_agent_start hook，在 session 启动时向 system prompt 追加通信上下文。

---

### R1 gateway session metadata 写入群聊元信息

- Context: `_build_session_metadata` 负责构建传给 kernel 的 session metadata dict。需写入
  `conversation_type`（group/direct）、`participant_agent_ids`（群聊参与者 agent id 列表）、
  `external_chat_id`（群聊 ID）。participant_agent_ids 来自 message.metadata 的 mentioned_agent_ids。
- Decision: 在 `_build_session_metadata` 中根据 `message.is_group` 写入三个字段。
- Rationale: session metadata 是唯一能穿越 gateway→kernel HTTP 边界的持久化载体；字段命名与 SPEC §7 对齐。
- Evidence:
  - Tests: `python -m pytest tests/unit/personal_assistant/ tests/unit/ -x -q`
  - Entry: unit test 断言 create_session_calls[0]["metadata"]["conversation_type"] == "group"
- Rollback: 回退到 baseline（baseline 无此字段）
- Commits: C1=?, C2=?, C3=?
- Next: R2

---

### R2 before_agent_start hook 追加通信上下文块

- Context: hook 注册在 `src/agent/products/personal_assistant/hooks/__init__.py` 的 `setup()` 中。
  hook handler 读取 `ctx.metadata["conversation_type"]` 和 `ctx.metadata["participant_agent_ids"]`，
  群聊时追加完整上下文块，直聊时追加简化版。
  注：生产路径 core runtime 不注入 session metadata 到 hook_ctx.metadata（core 在 forbidden scope）；
  单测通过直接构造 HookContext 注入字段验证 hook 逻辑。
- Decision: hook 返回 `{"system_prompt": base_prompt + context_block}` 当 base_prompt 存在，
  或返回 `{"system_prompt": context_block}` 当 payload["system_prompt"] 为 None。
- Rationale: hook 应追加而不是覆盖，因此优先取 payload["system_prompt"] 作 base。
- Evidence:
  - Tests: `python -m pytest tests/unit/personal_assistant/ tests/unit/ -x -q`
  - Entry: unit test 断言群聊 system_prompt 含 `[Communication Context]` 块
- Rollback: 回退到 R1 C3
- Commits: C1=?, C2=?, C3=?
- Next: DONE
