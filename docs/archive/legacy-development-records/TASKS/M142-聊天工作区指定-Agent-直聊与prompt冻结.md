# M142 聊天工作区指定 Agent 直聊与 prompt 冻结

## [DONE] R142.1 red tests for direct-chat discoverability and frozen prompt
- Steps:
  - 先补前端红测，锁定聊天工作区必须出现 `New direct chat`，可列出 `Available agents`，并能从 workspace 为指定 Agent 打开新直聊。
  - 先补后端红测，锁定 relay payload 必须携带 `agent_id`、`config_profile_version`、`system_prompt`。
  - 先补 Gateway / kernel / runtime 红测，锁定 kernel `create_session(metadata=...)`、session metadata rebuild、以及旧会话 frozen prompt 跨 turn 生效。
- Expected Tests:
  - `/Users/czj/Repos/nano-multiagent/.worktrees/M142/src/IM/frontend/src/features/chat/chat-workspace-page.test.ts`
  - `/Users/czj/Repos/nano-multiagent/.worktrees/M142/tests/unit/personal_assistant/test_kernel_api_client.py`
  - `/Users/czj/Repos/nano-multiagent/.worktrees/M142/tests/unit/personal_assistant/test_gateway_pipeline.py`
  - `/Users/czj/Repos/nano-multiagent/.worktrees/M142/tests/unit/test_agent_runtime_hooks.py`
  - `/Users/czj/Repos/nano-multiagent/.worktrees/M142/tests/im_service/integration/test_agent_create_flow.py`
  - `/Users/czj/Repos/nano-multiagent/.worktrees/M142/tests/im_service/integration/test_m103_im_gateway_e2e.py`
- Rollback:
  - 删除新增红测与 direct-chat / frozen-prompt metadata 断言，恢复到 M136 之前的直聊与默认 prompt 行为。
- Commits:
  - `34c3915 test(M142): lock workspace direct chat and prompt snapshot path`
- Next:
  - R142.2 最小实现 discoverability、direct chat、relay metadata 与 session frozen prompt。

## [DONE] R142.2 minimal implementation for workspace direct chat and prompt snapshot
- Steps:
  - 在 Web IM workspace 中新增 direct-chat 入口、discoverable agent panel 与 direct conversation 创建逻辑。
  - 在 IM relay payload 中补 `agent_id`、`config_profile_version`、`system_prompt`。
  - 在 Gateway 建立 kernel session 时透传 metadata，并让 runtime 从 session metadata 恢复 frozen `system_prompt`，以保证旧会话不漂移、新会话吃新 prompt。
- Expected Tests:
  - `/Users/czj/Repos/nano-multiagent/.worktrees/M142/src/IM/frontend/src/features/chat/im-chat-api.test.ts`
  - `/Users/czj/Repos/nano-multiagent/.worktrees/M142/src/IM/frontend/src/features/chat/chat-workspace-page.test.ts`
  - `/Users/czj/Repos/nano-multiagent/.worktrees/M142/tests/unit/personal_assistant/test_kernel_api_client.py`
  - `/Users/czj/Repos/nano-multiagent/.worktrees/M142/tests/unit/personal_assistant/test_gateway_pipeline.py`
  - `/Users/czj/Repos/nano-multiagent/.worktrees/M142/tests/unit/test_agent_runtime_hooks.py`
  - `/Users/czj/Repos/nano-multiagent/.worktrees/M142/tests/im_service/integration/test_agent_create_flow.py`
  - `/Users/czj/Repos/nano-multiagent/.worktrees/M142/tests/im_service/integration/test_m103_im_gateway_e2e.py`
- Rollback:
  - 回退 `chat-workspace-page.tsx` / `conversation-list.tsx` / `im-chat-api.ts` / `mock-chat-api.ts` 的 direct-chat 入口与 API helper；回退 relay / gateway / runtime 的 session metadata 链路。
- Commits:
  - `5685036 feat(M142): add workspace direct chats with frozen prompt sessions`
- Next:
  - R142.3 文档化、门禁留痕与主 agent 验收交接。

## [DONE] R142.3 docs and acceptance handoff
- Steps:
  - 记录最小测试命令、结果、Roadpoints 与真实 commits。
  - 在 PROGRESS 中明确旧会话不漂移、新会话吃新 prompt、workspace 如何发现并打开指定 Agent 的证明方式。
  - 生成 M142 acceptance 留痕，明确当前自动化证据与后续主 agent 真实浏览器/真实进程验收边界。
- Expected Tests:
  - `pytest -q /Users/czj/Repos/nano-multiagent/.worktrees/M142/tests/unit/personal_assistant/test_kernel_api_client.py /Users/czj/Repos/nano-multiagent/.worktrees/M142/tests/unit/personal_assistant/test_gateway_pipeline.py /Users/czj/Repos/nano-multiagent/.worktrees/M142/tests/unit/test_agent_runtime_hooks.py /Users/czj/Repos/nano-multiagent/.worktrees/M142/tests/im_service/integration/test_agent_create_flow.py /Users/czj/Repos/nano-multiagent/.worktrees/M142/tests/im_service/integration/test_m103_im_gateway_e2e.py`
  - `npm --prefix /Users/czj/Repos/nano-multiagent/.worktrees/M142/src/IM/frontend test -- --run src/features/chat/im-chat-api.test.ts src/features/chat/chat-workspace-page.test.ts`
- Rollback:
  - 删除 M142 文档并回退到未留痕状态。
- Commits:
  - `23c1e65 docs(M142): record direct-chat and frozen-prompt acceptance handoff`
