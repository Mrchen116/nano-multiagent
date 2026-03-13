# M138 主 Agent 与 Heartbeat 汇报链路产品化

## Scope
- Milestone: M138
- Branch: `milestone/M138`
- Canonical worktree: `/Users/czj/Repos/nano-multiagent/.worktrees/M138`

## Startup
- 已阅读：
  - `/Users/czj/.codex/skills/tdd-execution-worker/SKILL.md`
  - `/Users/czj/Repos/nano-multiagent/.worktrees/M138/LOGBOOK.md`
  - `/Users/czj/Repos/nano-multiagent/.worktrees/M138/COMMENTING_GUIDE.md`
  - `/Users/czj/Repos/nano-multiagent/docs/需求.md`
  - `/Users/czj/Repos/nano-multiagent/docs/IM-SPEC.md`
- 注释规范承诺：后续新增 public module/class/function/method 均按 Google 风格 docstring 写契约；注释只解释意图、边界、代价，不复述代码。
- 当前处境：M138，复用既有 milestone worktree `/Users/czj/Repos/nano-multiagent/.worktrees/M138`，分支 `milestone/M138`。
- 测试门禁：`cd /Users/czj/Repos/nano-multiagent/.worktrees/M138 && pytest -q`
- 基线结果：`768 passed, 4 skipped`。
- 注意事项：
  - 只做主 Agent 可识别性与 heartbeat IM 回流闭环，不扩散为无关重构。
  - 必须保留真实产品入口视角，不接受只在 mock/内部对象里“概念存在”。
  - 维持单一主链路，避免为 heartbeat 另造旁路通知系统。

## Roadpoint Records

### R1 主 Agent 入口语义产品化
- Context: 默认 starter 与会话头部仅展示通用 Agent 文案，用户无法在真实产品入口直接识别“这是主 Agent / 你的默认替身入口”。
- Decision: 将默认 starter 标题、描述、ownership 与会话 detail/list 语义统一收口到“主 Agent”语义，同时保持现有 conversation/send 行为不变。
- Rationale: M138 的第一出口条件是“用户可识别主 Agent 的真实产品入口或会话语义”；最小达成方式是复用现有 Web IM 入口与现有字段，不引入新的页面或路由。
- Evidence:
  - Tests:
    - `cd /Users/czj/Repos/nano-multiagent/.worktrees/M138/src/IM/frontend && npm test -- --run src/features/chat/im-chat-api.test.ts src/features/chat/components/message-pane.test.tsx src/features/chat/chat-workspace-page.test.ts`
  - Entry:
    - 默认入口标题改为 `主 Agent · <name>`；会话头部出现 `主 Agent 会话` 与 `这是你与主 Agent 的默认产品入口。`。
- Rollback: 仅回退 `/src/IM/frontend/src/features/chat/im-chat-api.ts` 与对应前端测试文件即可恢复旧文案，不影响后端协议。
- Commits: C1=, C2=, C3=
- Next: 继续把 heartbeat 结果接入 IM 可见 report 事件流。

### R2 Heartbeat 结果 IM 回流产品化
- Context: scheduler 已能触发 HEARTBEAT.md 执行，但产物停留在本地 kernel run；IM 侧虽已有 `node.report -> relay.report` 持久化能力，却没有 heartbeat 专用 payload 生产与转发桥。
- Decision: 在 `PollingHeartbeatRunner` 中把 tick summary 映射为 heartbeat product reports，再由 `GatewayRuntime` 在 IM 连通后/关停前通过现有 `node.report` 通道转发。
- Rationale: 这样改动最小，复用现有 IM 持久化与 conversation event 语义，不新增 heartbeat 专用 API 或第二套回流协议。
- Evidence:
  - Tests:
    - `cd /Users/czj/Repos/nano-multiagent/.worktrees/M138 && pytest -q tests/unit/personal_assistant/test_main.py`
    - `cd /Users/czj/Repos/nano-multiagent/.worktrees/M138 && pytest -q tests/im_service/integration/test_gateway_websocket_api.py -k heartbeat_report_into_conversation_events`
  - Entry:
    - heartbeat run 被映射为 `node.report` payload，包含 `agent_id/session_key/conversation_id/message_id/summary/guidance`；IM 事件流能看到 `relay.report` 与 `agent_run_completed`。
- Rollback: 回退 `/src/personal_assistant/main.py` 与新增测试即可；IM 侧既有 report/receipt 路径不需要回退。
- Commits: C1=, C2=, C3=
- Next: 收口真实入口证据、整体验证、判断是否需要补真实进程 acceptance。

### R3 真实入口证据与收口
- Context: R1/R2 已分别覆盖入口语义与 IM 回流桥，但仍需把可复述的“真实入口证据”整理为对验收者可消费的结论，并明确提交前是否仍有 blocker。
- Decision: 以现有 Web IM 前端产品文案测试 + IM websocket/integration 事件落库测试作为当前证据；本轮先跑 targeted tests，不扩展到新的长链路 acceptance，也暂不先跑全量 `pytest -q`。
- Rationale: 本 milestone 的产品闭环核心是“用户可识别主 Agent”与“heartbeat 结果可通过 IM 回流可见”；现有证据已打到真实产品入口字段与真实 IM websocket/event persistence，且 targeted tests 已覆盖当前改动面。
- Evidence:
  - Tests:
    - `npm --prefix /Users/czj/Repos/nano-multiagent/.worktrees/M138/src/IM/frontend test -- --run src/features/chat/im-chat-api.test.ts src/features/chat/components/message-pane.test.tsx src/features/chat/chat-workspace-page.test.ts` -> 3 files, 20 tests passed.
    - `cd /Users/czj/Repos/nano-multiagent/.worktrees/M138 && pytest -q tests/unit/personal_assistant/test_main.py` -> 24 passed.
    - `cd /Users/czj/Repos/nano-multiagent/.worktrees/M138 && pytest -q tests/im_service/integration/test_gateway_websocket_api.py -k heartbeat_report_into_conversation_events` -> 1 passed, 5 deselected.
  - Entry:
    - 主 Agent 真实入口证据位于 `/Users/czj/Repos/nano-multiagent/.worktrees/M138/src/IM/frontend/src/features/chat/im-chat-api.ts:215`、`:238`、`:328`，以及对应测试 `/Users/czj/Repos/nano-multiagent/.worktrees/M138/src/IM/frontend/src/features/chat/components/message-pane.test.tsx:40`、`/Users/czj/Repos/nano-multiagent/.worktrees/M138/src/IM/frontend/src/features/chat/chat-workspace-page.test.ts:76`；默认 starter/title/detail 明确显示 `主 Agent`、`主 Agent 会话`、`这是你与主 Agent 的默认产品入口。`。
    - Heartbeat 回流证据位于 `/Users/czj/Repos/nano-multiagent/.worktrees/M138/src/personal_assistant/main.py:402`、`:641`、`:987`，以及测试 `/Users/czj/Repos/nano-multiagent/.worktrees/M138/tests/unit/personal_assistant/test_main.py:512`、`:545`、`/Users/czj/Repos/nano-multiagent/.worktrees/M138/tests/im_service/integration/test_gateway_websocket_api.py:241`；真实 websocket `node.report` 进入 IM conversation events，事件文本包含 `relay.report`、`agent_run_completed` 与指导文案 `Open your main agent thread in Web IM to review the latest heartbeat result.`
  - Red Test:
    - 本轮未新增红测执行记录；当前 worktree 中针对 R1/R2/R3 的改动已存在且 targeted tests 直接为绿，未复现到独立 failing snapshot。
  - Merge Main:
    - 未 merge `main`；`git merge-base --is-ancestor main HEAD` 返回非零，`git rev-list --left-right --count main...HEAD` 为 `13 0`，说明当前分支落后 `main` 13 个提交。
- Rollback: 同上，分别回退前端文案映射与 runtime heartbeat report bridge。
- Commits: C1=, C2=, C3=
- Next: 若要提交前进一步降风险，可补跑 `cd /Users/czj/Repos/nano-multiagent/.worktrees/M138 && pytest -q` 作为全量回归；除此之外暂无代码级 blocker。
