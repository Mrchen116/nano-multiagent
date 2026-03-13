# M136 Group Chat Evidence

## Scope
- Milestone: M136 — Web IM 群聊真实创建与多 Agent 行为收口
- Worktree: `/Users/czj/Repos/nano-multiagent/.worktrees/M136`
- Branch: `milestone/M136`
- Date: 2026-03-13

## What was verified
1. Web IM 主聊天工作区现在存在真实群聊创建入口：`Create group chat`。
2. 点击入口后，页面出现群聊创建面板，明确提示 `Select participants`，不再只有 seeded direct chat 路径。
3. IM 后端真实 `/im/v1/conversations` 入口可创建 `type=group` 会话，并可在会话列表中重新读取。
4. relay payload 现在携带真实群聊 metadata：
   - `conversation_type`
   - `mentioned_agent_ids`
5. Gateway 在群聊场景下会按 `mentioned_agent_ids` 选择对应 Agent，而不是一律落到默认 Agent。
6. `@提及` 门控仍成立：未提及时忽略，提及时才进入 kernel。

## Automated evidence
### Frontend real-entry evidence
- Test: `src/IM/frontend/src/features/chat/chat-workspace-page.test.ts`
- Key assertion:
  - 主工作区存在 `Create group chat` 按钮；
  - 点击后可见 `Select participants` 面板。

### Backend group-creation + multi-agent evidence
- Test: `tests/im_service/integration/test_m136_group_chat_flow.py`
- Key assertion:
  - `POST /im/v1/conversations` with three participants returns `type == "group"`;
  - `GET /im/v1/conversations` returns the same group conversation;
  - first relay frame metadata is `{"conversation_type": "group", "mentioned_agent_ids": ["agent-a"]}`;
  - second relay frame metadata is `{"conversation_type": "group", "mentioned_agent_ids": ["agent-b"]}`;
  - Gateway creates kernel sessions titled `Agent-A` then `Agent-B`, proving multiple agents are really routed in one group chat path.

### Mention-gate regression evidence
- Test: `tests/unit/personal_assistant/test_m103_gateway_im_integration.py`
- Key assertion:
  - `test_group_message_without_mention_is_ignored`
  - `test_group_message_with_mention_or_reply_runs`

## NO_REPLY requirement audit
- Requirement anchor:
  - `/Users/czj/Repos/nano-multiagent/docs/需求.md` §三.7
- Current product status in M136 worktree:
  - 已有真实 `@提及` 门控与群聊 metadata/行为证据；
  - 但未发现真实产品路径中已经把“无需回复时输出固定字符串 `NO_REPLY`”落实到 Web IM / Gateway / 群聊主链路。
- Conclusion:
  - M136 已收口“群聊真实创建入口 + 多 Agent 群聊行为 + @提及门控证据”；
  - `NO_REPLY` 固定字符串协议仍属于未完全产品化项，本次只如实核对并留痕，不虚报完成。

## Commands run
- Python:
  - `PYTHONPATH=/Users/czj/Repos/nano-multiagent/.worktrees/M136/src pytest -q /Users/czj/Repos/nano-multiagent/.worktrees/M136/tests/im_service /Users/czj/Repos/nano-multiagent/.worktrees/M136/tests/unit/personal_assistant/test_m103_gateway_im_integration.py /Users/czj/Repos/nano-multiagent/.worktrees/M136/tests/acceptance/test_im_gateway_real_acceptance.py`
- Frontend:
  - `npm --prefix /Users/czj/Repos/nano-multiagent/.worktrees/M136/src/IM/frontend test -- --run src/features/chat/im-chat-api.test.ts src/features/chat/chat-layout.test.tsx src/features/chat/chat-workspace-page.test.ts src/app/router.test.tsx`

## Exit-criteria mapping
- Exit 1: satisfied via real UI entry + backend group conversation creation.
- Exit 2: satisfied via multi-agent mention routing evidence (`agent-a`, `agent-b`).
- Exit 3: partially satisfied — @提及门控有真实产品证据；`NO_REPLY` 固定字符串协议仍未真实落地。
- Exit 4: satisfied for relay/group metadata minimal closure (`conversation_type`, `mentioned_agent_ids`).
- Exit 5: satisfied — TASKS/PROGRESS/ACCEPTANCE 已记录。
