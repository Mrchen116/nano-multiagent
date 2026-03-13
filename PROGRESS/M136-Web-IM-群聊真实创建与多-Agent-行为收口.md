# M136 Progress — Web IM 群聊真实创建与多 Agent 行为收口

## Startup
- Read:
  - `/Users/czj/.codex/skills/tdd-execution-worker/SKILL.md`
  - `/Users/czj/Repos/nano-multiagent/.worktrees/M136/LOGBOOK.md`
  - `/Users/czj/Repos/nano-multiagent/.worktrees/M136/COMMENTING_GUIDE.md`
  - `/Users/czj/Repos/nano-multiagent/docs/需求.md`
  - `/Users/czj/Repos/nano-multiagent/docs/IM-SPEC.md`
- Commenting commitment: 新增/修改 public API 遵守 Google 风格 docstring；注释只解释意图、边界、代价，不复述代码。
- Current situation:
  - Milestone: M136 / Web IM 群聊真实创建与多 Agent 行为收口
  - execution_mode=parallel
  - use_worktree=true（复用既有 worktree）
  - worktree_dir=`/Users/czj/Repos/nano-multiagent/.worktrees/M136`
  - branch=`milestone/M136`
- Test gate:
  - `PYTHONPATH=/Users/czj/Repos/nano-multiagent/.worktrees/M136/src pytest -q /Users/czj/Repos/nano-multiagent/.worktrees/M136/tests/im_service /Users/czj/Repos/nano-multiagent/.worktrees/M136/tests/unit/personal_assistant/test_m103_gateway_im_integration.py /Users/czj/Repos/nano-multiagent/.worktrees/M136/tests/acceptance/test_im_gateway_real_acceptance.py`
  - `npm --prefix /Users/czj/Repos/nano-multiagent/.worktrees/M136/src/IM/frontend test -- --run src/features/chat/im-chat-api.test.ts src/features/chat/chat-layout.test.tsx src/features/chat/chat-workspace-page.test.ts src/app/router.test.tsx`
- Prevention / notes:
  - 只在 canonical M136 worktree 内工作，不创建新 worktree。
  - 不修改 `data/dev-tasks.json`。
  - 主链路优先真实入口/真实 HTTP+WS+frontend 行为，不接受只做 isolated unit 冒充完成。
  - 若 NO_REPLY 协议当前并未真正产品化，必须在证据中明确记录缺口，不做虚假闭环。

## Baseline findings
- 现有后端 `/im/v1/conversations` 已支持通用会话创建，但前端默认路径仍围绕 starter direct chat，缺少“真实创建群聊”的产品入口。
- 现有前端已有 group chat / agent-to-agent 的 discoverability 文案与 mock 语义，但真实 `im-chat-api.ts` 仍主要围绕 starter conversation bootstrap，并未显式暴露群聊创建流。
- Gateway 已有 @提及门控 focused 证据（M103），但 M136 仍需把群聊入口、多 Agent 证据、以及 NO_REPLY 需求状态一起核对收口。

### R1 群聊创建/进入真实入口收口
- Context: 现有 Web IM 已有群聊 discoverability 文案与 mock 语义，但真实页面工作区没有显式“创建群聊”入口，导致用户仍主要沿 starter direct chat 路径使用产品，难以证明“可从真实产品入口创建/进入群聊”。
- Decision: 在 `ConversationList` 顶部加入 `Create group chat` 入口，并在 `ChatWorkspacePage` 内落一个最小群聊创建面板，先以真实产品入口和页面文案收口，不额外扩散复杂表单/导航逻辑。
- Rationale: M136 目标是补入口闭环与真实证据，先把缺失的产品前门补齐，比一次性做完整群组配置向导更小、更稳、更符合最小改动原则。
- Evidence:
  - Tests: `npm --prefix /Users/czj/Repos/nano-multiagent/.worktrees/M136/src/IM/frontend test -- --run src/features/chat/chat-workspace-page.test.ts src/features/chat/chat-layout.test.tsx src/app/router.test.tsx`
  - Entry: `chat-workspace-page.test.ts` 断言主工作区可见 `Create group chat`，点击后出现 `Select participants` 面板；证据落盘于 `ACCEPTANCE/M136-group-chat-evidence.md`。
- Rollback: 回退到加入群聊入口前的稳定点。
- Commits: C1=<pending>, C2=<pending>, C3=<pending>
- Next: 继续把真实后端群聊创建与多 Agent relay 证据串起来。

### R2 多 Agent 群聊 relay / metadata / 行为证据收口
- Context: 既有 Gateway mention gate 主要验证“该不该处理”，但 relay payload 没有稳定暴露群聊 conversation type 与 mentioned_agent_ids，导致多 Agent 群聊行为缺少真实 IM→Gateway 证据，实际路由也会优先落到默认 agent。
- Decision: 在 `RelayService` 为每条 relay 注入 `metadata.conversation_type` 与从文本解析出的 `mentioned_agent_ids`；在 `WebIMService` 传入 conversation type；在 `InboundPipeline._resolve_agent()` 优先消费 `mentioned_agent_ids`/`reply_to_agent_id`，使群聊显式提及可真正命中对应 agent。
- Rationale: 这是打通 M136 群聊闭环所需的最小 metadata 集合，既能保留现有 gateway 架构，也能让多 Agent 行为有可断言的真实 frame 证据。
- Evidence:
  - Tests: `PYTHONPATH=/Users/czj/Repos/nano-multiagent/.worktrees/M136/src pytest -q /Users/czj/Repos/nano-multiagent/.worktrees/M136/tests/im_service/integration/test_m136_group_chat_flow.py`
  - Entry: `test_group_conversation_creation_and_explicit_agent_mentions_roundtrip` 证明 `/im/v1/conversations` 创建 `type=group` 会话后，两个显式提及分别命中 `Agent-A` 与 `Agent-B`，且 relay frame metadata 包含 `conversation_type=group` 与 `mentioned_agent_ids`。
- Rollback: 回退到新增群聊入口但尚未改 relay metadata 的稳定点。
- Commits: C1=<pending>, C2=<pending>, C3=<pending>
- Next: 核对 mention gate 与 NO_REPLY 需求状态，并把证据写入 acceptance。

### R3 @提及门控、NO_REPLY/群聊行为说明与真实证据收口
- Context: M103 已有 mention gate focused 回归，但 M136 还需要把其与当前真实 relay/group 行为一起核对；同时需求要求群聊“无需回复”时输出固定字符串 `NO_REPLY`，但现有产品链路未见真实落地证据。
- Decision: 复用现有 mention gate regression 作为自动化证据，并在 `ACCEPTANCE/M136-group-chat-evidence.md` 明确标注：@提及门控已真实成立；`NO_REPLY` 固定字符串协议未在 Web IM/Gateway 主链路真实落地，本次只做如实审计留痕。
- Rationale: 用户要求核对是否满足需求；对已满足项给证据，对未满足项明确记账，比继续在同一 milestone 内冒进补一个未设计完整的协议实现更稳妥。
- Evidence:
  - Tests: `PYTHONPATH=/Users/czj/Repos/nano-multiagent/.worktrees/M136/src pytest -q /Users/czj/Repos/nano-multiagent/.worktrees/M136/tests/unit/personal_assistant/test_m103_gateway_im_integration.py /Users/czj/Repos/nano-multiagent/.worktrees/M136/tests/acceptance/test_im_gateway_real_acceptance.py`
  - Entry: `test_group_message_without_mention_is_ignored` / `test_group_message_with_mention_or_reply_runs` 继续证明 mention gate；`ACCEPTANCE/M136-group-chat-evidence.md` 明确记录 `NO_REPLY` 现状缺口。
- Rollback: 回退到完成 relay metadata 收口后的稳定点。
- Commits: C1=<pending>, C2=<pending>, C3=<pending>
- Next: 当前代码与证据已完成，剩余为提交与是否进一步补真实浏览器截图/录像。

## Final verification
- Python gate: `PYTHONPATH=/Users/czj/Repos/nano-multiagent/.worktrees/M136/src pytest -q /Users/czj/Repos/nano-multiagent/.worktrees/M136/tests/im_service /Users/czj/Repos/nano-multiagent/.worktrees/M136/tests/unit/personal_assistant/test_m103_gateway_im_integration.py /Users/czj/Repos/nano-multiagent/.worktrees/M136/tests/acceptance/test_im_gateway_real_acceptance.py` → `68 passed`
- Frontend gate: `npm --prefix /Users/czj/Repos/nano-multiagent/.worktrees/M136/src/IM/frontend test -- --run src/features/chat/im-chat-api.test.ts src/features/chat/chat-layout.test.tsx src/features/chat/chat-workspace-page.test.ts src/app/router.test.tsx` → `24 passed`

## Result summary
- 已补 Web IM 群聊真实创建入口（最小 UI 前门）、群聊 relay metadata（`conversation_type` / `mentioned_agent_ids`）与 Gateway 多 Agent 显式提及路由。
- 已形成自动化证据证明群聊会话可创建/进入、多个 Agent 行为成立、@提及门控成立。
- 已明确核对并记录：`NO_REPLY` 固定字符串协议尚未在真实产品链路中完成落地。
- 相关证据文件：`/Users/czj/Repos/nano-multiagent/.worktrees/M136/ACCEPTANCE/M136-group-chat-evidence.md`

## Relevant files
- `/Users/czj/Repos/nano-multiagent/.worktrees/M136/src/IM/frontend/src/features/chat/components/conversation-list.tsx`
- `/Users/czj/Repos/nano-multiagent/.worktrees/M136/src/IM/frontend/src/features/chat/chat-workspace-page.tsx`
- `/Users/czj/Repos/nano-multiagent/.worktrees/M136/src/IM/frontend/src/features/chat/chat-workspace-page.test.ts`
- `/Users/czj/Repos/nano-multiagent/.worktrees/M136/src/IM/application/web_im_service.py`
- `/Users/czj/Repos/nano-multiagent/.worktrees/M136/src/IM/application/relay_service.py`
- `/Users/czj/Repos/nano-multiagent/.worktrees/M136/src/personal_assistant/gateway/inbound_pipeline.py`
- `/Users/czj/Repos/nano-multiagent/.worktrees/M136/tests/im_service/integration/test_m136_group_chat_flow.py`
- `/Users/czj/Repos/nano-multiagent/.worktrees/M136/tests/im_service/integration/test_m103_im_gateway_e2e.py`
- `/Users/czj/Repos/nano-multiagent/.worktrees/M136/ACCEPTANCE/M136-group-chat-evidence.md`
- `/Users/czj/Repos/nano-multiagent/.worktrees/M136/TASKS/M136-Web-IM-群聊真实创建与多-Agent-行为收口.md`
- `/Users/czj/Repos/nano-multiagent/.worktrees/M136/PROGRESS/M136-Web-IM-群聊真实创建与多-Agent-行为收口.md`
