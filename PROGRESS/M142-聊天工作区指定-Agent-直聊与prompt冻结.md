# M142 聊天工作区指定 Agent 直聊与 prompt 冻结进展

## 2026-03-13
- Done:
  - 在 canonical worktree `/Users/czj/Repos/nano-multiagent/.worktrees/M142` 内完成 M142 的 red-green 收口，不改 `data/dev-tasks.json`。
  - 为聊天工作区补齐 direct-chat discoverability：conversation list 新增 `New direct chat`，workspace 可显示 `Available agents`，并可直接为指定 Agent 创建或打开直聊。
  - 为 relay -> gateway -> kernel -> runtime 链路补齐 prompt snapshot metadata：relay payload 携带 `agent_id`、`config_profile_version`、`system_prompt`，Gateway 建 session 时透传 metadata，runtime 从 session metadata 恢复 frozen prompt。
  - 补齐 canonical frontend test setup，使 M142 相关 vitest 能在当前 jsdom/React Router 环境稳定运行。
- Evidence:
  - 聊天工作区发现并打开指定 Agent 的新直聊：
    - `src/IM/frontend/src/features/chat/chat-workspace-page.test.ts` 中 `lets users discover an agent and open a fresh direct chat from the workspace` 断言：存在 `New direct chat`，点击后出现 `Available agents`，点击 `Chat with Agent New` 会调用 `createDirectConversation({ agentId: "agent-new" })`，并读取 `conv-agent-new` 对话详情。
  - 旧会话不漂移如何被证明：
    - `tests/unit/test_agent_runtime_hooks.py::test_session_metadata_system_prompt_is_used_for_every_turn` 明确创建带 `metadata={"system_prompt": ...}` 的 session，连续两轮 `runtime.run(...)` 都向 LLM 发送相同 frozen prompt，证明旧 session 不随外部配置漂移。
  - 新会话吃新 prompt 如何被证明：
    - `tests/unit/personal_assistant/test_gateway_pipeline.py::test_inbound_pipeline_passes_frozen_prompt_metadata_when_creating_new_kernel_sessions` 断言新的 inbound 会话在创建 kernel session 时写入 `agent_id`、`conversation_id`、`config_profile_version`、`system_prompt`。
    - `tests/im_service/integration/test_agent_create_flow.py` 断言 IM relay payload 已显式带出 `agent_id` 与 prompt snapshot metadata，证明新会话真实入口链路能把新 prompt 快照送入 Gateway。
  - Python 目标门禁：
    - `pytest -q /Users/czj/Repos/nano-multiagent/.worktrees/M142/tests/unit/personal_assistant/test_kernel_api_client.py /Users/czj/Repos/nano-multiagent/.worktrees/M142/tests/unit/personal_assistant/test_gateway_pipeline.py /Users/czj/Repos/nano-multiagent/.worktrees/M142/tests/unit/test_agent_runtime_hooks.py /Users/czj/Repos/nano-multiagent/.worktrees/M142/tests/im_service/integration/test_agent_create_flow.py /Users/czj/Repos/nano-multiagent/.worktrees/M142/tests/im_service/integration/test_m103_im_gateway_e2e.py` -> `25 passed in 0.55s`
  - Frontend 目标门禁：
    - `npm --prefix /Users/czj/Repos/nano-multiagent/.worktrees/M142/src/IM/frontend install` -> `added 253 packages, and audited 254 packages in 5s`
    - `npm --prefix /Users/czj/Repos/nano-multiagent/.worktrees/M142/src/IM/frontend test -- --run src/features/chat/im-chat-api.test.ts src/features/chat/chat-workspace-page.test.ts` -> `2 passed (2 files), 18 passed (18 tests)`
- Rollback:
  - 回退 direct-chat 入口、relay metadata、Gateway session metadata 与 runtime frozen-prompt rebuild，即可恢复到 M136 前的 starter-only chat + product default prompt 行为。
- Commits:
  - C1: `34c3915 test(M142): lock workspace direct chat and prompt snapshot path`
  - C2: `5685036 feat(M142): add workspace direct chats with frozen prompt sessions`
  - C3: `23c1e65 docs(M142): record direct-chat and frozen-prompt acceptance handoff`
- Next:
  - 交给主 agent 继续执行真实浏览器 / 真实进程 acceptance，验证“旧会话不漂移，新会话吃新 prompt”的产品证据。
