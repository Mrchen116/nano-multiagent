# M142 Acceptance Handoff

## Scope
- Milestone: M142 — 聊天工作区指定 Agent 直聊与 prompt 冻结
- Worktree: `/Users/czj/Repos/nano-multiagent/.worktrees/M142`
- Branch: `milestone/M142`
- Date: 2026-03-13

## What is closed in this pass
1. 聊天工作区现在存在真实 direct-chat 入口：`New direct chat`。
2. 用户可在 workspace 中看到 `Available agents`，并直接为指定 Agent 打开新的直聊。
3. IM relay payload 现在显式携带：
   - `agent_id`
   - `config_profile_version`
   - `system_prompt`
4. Gateway 新建 kernel session 时会透传上述 metadata。
5. runtime 会从 session metadata 恢复 frozen prompt，因此旧会话不会在后续 turn 中漂移到更新后的 prompt。

## Automated evidence
### Workspace direct-chat discoverability
- Test: `/Users/czj/Repos/nano-multiagent/.worktrees/M142/src/IM/frontend/src/features/chat/chat-workspace-page.test.ts`
- Key assertions:
  - conversation list 存在 `New direct chat`；
  - 点击后出现 `Available agents`；
  - 点击 `Chat with Agent New` 后会调用 `createDirectConversation({ agentId: "agent-new" })`；
  - 新直聊详情会以 `Agent New` 为目标渲染。

### Prompt snapshot propagation
- Test: `/Users/czj/Repos/nano-multiagent/.worktrees/M142/tests/im_service/integration/test_agent_create_flow.py`
- Key assertions:
  - relay payload 顶层包含 `agent_id`；
  - relay payload metadata 包含 `config_profile_version` 与 `system_prompt`。

### Gateway session metadata
- Test: `/Users/czj/Repos/nano-multiagent/.worktrees/M142/tests/unit/personal_assistant/test_gateway_pipeline.py`
- Key assertions:
  - 新 inbound 会话在 `create_session()` 时会写入 `agent_id`、`conversation_id`、`config_profile_version`、`system_prompt`。

### Old-session non-drift proof
- Test: `/Users/czj/Repos/nano-multiagent/.worktrees/M142/tests/unit/test_agent_runtime_hooks.py`
- Key assertions:
  - 同一个 session 连续两轮调用都使用 session metadata 中冻结的 `system_prompt`；
  - 这证明旧会话不随着后续 profile 变化而漂移。

## Commands run
- Python:
  - `pytest -q /Users/czj/Repos/nano-multiagent/.worktrees/M142/tests/unit/personal_assistant/test_kernel_api_client.py /Users/czj/Repos/nano-multiagent/.worktrees/M142/tests/unit/personal_assistant/test_gateway_pipeline.py /Users/czj/Repos/nano-multiagent/.worktrees/M142/tests/unit/test_agent_runtime_hooks.py /Users/czj/Repos/nano-multiagent/.worktrees/M142/tests/im_service/integration/test_agent_create_flow.py /Users/czj/Repos/nano-multiagent/.worktrees/M142/tests/im_service/integration/test_m103_im_gateway_e2e.py`
- Frontend:
  - `npm --prefix /Users/czj/Repos/nano-multiagent/.worktrees/M142/src/IM/frontend install`
  - `npm --prefix /Users/czj/Repos/nano-multiagent/.worktrees/M142/src/IM/frontend test -- --run src/features/chat/im-chat-api.test.ts src/features/chat/chat-workspace-page.test.ts`

## Current verdict
- Verdict: Ready for main agent acceptance
- Blocking issues in this pass: 0
- Notes:
  - 本次已完成自动化门禁与交付留痕。
  - 真实浏览器 / 真实进程下“旧会话不漂移，新会话吃新 prompt”的最终产品证据仍应由主 agent 在总验收环节补齐并留档，不在本次子任务里虚报完成。
