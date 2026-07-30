# M205 Acceptance Handoff

## Scope
- Milestone: M205 — 新建 Agent 首聊闭环、新会话产品路径、allowlist 普通用户收敛
- Worktree: `/Users/czj/Repos/nano-multiagent/.worktrees/M205`
- Branch: `milestone/M205`
- Date: 2026-03-16

## What is closed in this implementation pass
1. 新建 Agent 时允许把 Gateway 预注册的 ownerless runtime placeholder 升级为真实 profile，并在绑定节点时同步回填 node owner，避免创建后列表消失或首聊 `unknown agent_id`。
2. Direct chat 保持单 Agent 稳定复用入口，同时在聊天页中提供 `Start fresh session`，让新线程显式吃到新的 prompt/profile snapshot。
3. Agent create/edit allowlist UI 改为产品安全默认视图，内部/高级项折叠展示，并保留已保存高级项可见。
4. Gateway inbound pipeline 补齐 statusless run snapshot 回归修复：当 run snapshot 没有显式 `status` 但已有 `output_text` 时，按 `completed` 处理，避免 browserless roundtrip 集成测试卡住。

## Implementation self-proof

### R1 新建 Agent 首聊闭环与 runtime 可聊态
- Implementation entry:
  - `/Users/czj/Repos/nano-multiagent/.worktrees/M205/src/IM/application/config_service.py`
- Automated evidence:
  - `pytest tests/im_service/integration/test_agent_create_flow.py`
    - Result: `2 passed in 0.59s`
  - `pytest -q tests/im_service/integration/test_agent_create_flow.py tests/im_service/integration/test_agent_config_api.py tests/im_service/integration/test_m103_im_gateway_e2e.py::test_web_im_message_roundtrip_browserless tests/im_service/integration/test_m103_im_gateway_e2e.py::test_direct_chat_keeps_old_session_after_config_sync_while_new_conversation_gets_new_profile`
    - Result: `10 passed in 0.97s`
- Key assertions covered:
  - 创建后的 Agent 会出现在 `/im/v1/agents` runtime-selectable 列表中。
  - 创建后立即进入真实 `relay.message` 路径时，Gateway 能识别新 Agent，不再出现 `unknown agent_id`。
  - 新 Agent 绑定节点后的 relay task 会落到正确的 `target_node_id`。

### R2 每 Agent 单一入口下的 fresh session 路径
- Implementation entry:
  - `/Users/czj/Repos/nano-multiagent/.worktrees/M205/src/IM/frontend/src/features/chat/im-chat-api.ts`
  - `/Users/czj/Repos/nano-multiagent/.worktrees/M205/src/IM/frontend/src/features/chat/chat-api.ts`
  - `/Users/czj/Repos/nano-multiagent/.worktrees/M205/src/IM/frontend/src/features/chat/chat-workspace-page.tsx`
  - `/Users/czj/Repos/nano-multiagent/.worktrees/M205/src/IM/frontend/src/features/chat/components/message-pane.tsx`
  - `/Users/czj/Repos/nano-multiagent/.worktrees/M205/src/IM/frontend/src/features/chat/types.ts`
- Automated evidence:
  - `npm --prefix src/IM/frontend test src/features/chat/chat-workspace-page.test.ts src/features/settings/agents/agent-create.test.tsx src/features/settings/agents/agent-edit.test.tsx`
    - Result: `31 passed (31)`
  - `npm --prefix src/IM/frontend run build`
    - Result: passed
  - backend snapshot semantics spot-check included in:
    - `pytest -q tests/im_service/integration/test_agent_create_flow.py tests/im_service/integration/test_agent_config_api.py tests/im_service/integration/test_m103_im_gateway_e2e.py::test_web_im_message_roundtrip_browserless tests/im_service/integration/test_m103_im_gateway_e2e.py::test_direct_chat_keeps_old_session_after_config_sync_while_new_conversation_gets_new_profile`
    - Result: `10 passed in 0.97s`
- Key assertions covered:
  - 聊天页不恢复全局 `New direct chat`。
  - 直聊页可见 `Start fresh session` 并能导航到新线程。
  - 旧 direct conversation 保持旧 `config_profile_version`，新 direct conversation 读取新 `config_profile_version`。

### R3 Allowlist 面向普通用户的收敛与分组
- Implementation entry:
  - `/Users/czj/Repos/nano-multiagent/.worktrees/M205/src/IM/frontend/src/features/settings/agents/allowlist-selector.tsx`
  - `/Users/czj/Repos/nano-multiagent/.worktrees/M205/src/IM/frontend/src/features/settings/agents/agent-create-page.tsx`
  - `/Users/czj/Repos/nano-multiagent/.worktrees/M205/src/IM/frontend/src/features/settings/agents/agent-detail-page.tsx`
  - `/Users/czj/Repos/nano-multiagent/.worktrees/M205/src/IM/frontend/src/features/settings/agents/agent-create.test.tsx`
  - `/Users/czj/Repos/nano-multiagent/.worktrees/M205/src/IM/frontend/src/features/settings/agents/agent-edit.test.tsx`
- Automated evidence:
  - `npm --prefix src/IM/frontend test src/features/settings/agents/agent-create.test.tsx src/features/settings/agents/agent-edit.test.tsx`
    - Result: included in `31 passed (31)`
  - `npm --prefix src/IM/frontend run build`
    - Result: passed
- Key assertions covered:
  - 默认只展示 product-safe 推荐项。
  - 高级/内部项收敛到折叠区。
  - 已保存高级项在编辑页保持可见，不被静默吞掉。

### R4 Backend regression fix discovered during self-proof
- Implementation entry:
  - `/Users/czj/Repos/nano-multiagent/.worktrees/M205/src/personal_assistant/gateway/inbound_pipeline.py`
  - `/Users/czj/Repos/nano-multiagent/.worktrees/M205/tests/unit/personal_assistant/test_gateway_pipeline.py`
- Root cause:
  - Gateway pipeline 轮询 kernel run 时，只把显式 `status in {completed, failed, cancelled}` 视为终态。
  - 但 browserless fake kernel 的部分 run snapshot 只有 `output_text`，没有 `status`；于是 pipeline 无限轮询，导致 `test_web_im_message_roundtrip_browserless` 卡住。
- Fix:
  - `_run_status()` 新增 fallback：
    - 有显式 `status` 则沿用；
    - 无 `status` 但有非空 `output_text` 时视为 `completed`；
    - 无 `status` 但有 `error` 时视为 `failed`。
- Automated evidence:
  - `pytest tests/unit/personal_assistant/test_gateway_pipeline.py -k statusless_run_snapshot_with_output`
    - Result: `1 passed`
  - `pytest tests/im_service/integration/test_m103_im_gateway_e2e.py::test_web_im_message_roundtrip_browserless`
    - Result: `1 passed in 0.63s`

## Final targeted test summary
- Backend:
  - `pytest tests/im_service/integration/test_agent_create_flow.py` → `2 passed in 0.59s`
  - `pytest tests/im_service/integration/test_agent_config_api.py` → `6 passed in 0.65s`
  - `pytest tests/im_service/integration/test_m103_im_gateway_e2e.py::test_web_im_message_roundtrip_browserless` → `1 passed in 0.63s`
  - `pytest -q tests/im_service/integration/test_agent_create_flow.py tests/im_service/integration/test_agent_config_api.py tests/im_service/integration/test_m103_im_gateway_e2e.py::test_web_im_message_roundtrip_browserless tests/im_service/integration/test_m103_im_gateway_e2e.py::test_direct_chat_keeps_old_session_after_config_sync_while_new_conversation_gets_new_profile` → `10 passed in 0.97s`
- Frontend:
  - `npm --prefix src/IM/frontend test src/features/settings/agents/agent-create.test.tsx src/features/settings/agents/agent-edit.test.tsx src/features/chat/chat-workspace-page.test.ts` → `31 passed (31)`
  - `npm --prefix src/IM/frontend run build` → passed

## Final product acceptance still pending re-dispatch
The following items are not claimed as completed by this implementation subagent and still require orchestrator/main-agent product acceptance on the real stack:
1. 用真实 IM 前端浏览器创建新 Agent，并验证首条真实消息在在线 Gateway / real runtime 上成功往返。
2. 在真实聊天页里通过 `Start fresh session` 验证：旧 direct thread 保留旧 prompt snapshot，新线程吃到新 prompt 版本。
3. 在真实 Settings create/edit 页面确认 allowlist 默认信息层级、折叠区、已保存高级项展示符合产品预期。
4. 在真实 acceptance runtime 中确认无新的 Gateway 日志异常、无 `unknown agent_id` 回归、无 fresh-session 误导路径。

## Current verdict
- Verdict: M205 implementation-side exit criteria satisfied; ready for orchestrator to re-dispatch final product acceptance.
- Not completed in this pass:
  - Real browser / real runtime product acceptance
  - Merge to `main`
  - Worktree cleanup
- Current merge blocker:
  - Repo root `main` working tree is already dirty with unrelated local changes/untracked files outside M205 scope, so merging from this worktree is not currently safe without disturbing user state.
