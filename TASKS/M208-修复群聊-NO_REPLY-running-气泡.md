# M208 Task — 修复群聊 NO_REPLY 仍显示运行中气泡

## 启动记录
- 已阅读：`/Users/czj/Repos/nano-multiagent/.worktrees/M208/LOGBOOK.md`、`/Users/czj/Repos/nano-multiagent/.worktrees/M208/COMMENTING_GUIDE.md`、`/Users/czj/.claude/skills/tdd-execution-worker/SKILL.md`。
- 注释承诺：后续改动继续遵守 Google 风格 docstring；注释只写意图、边界与约束，不复述代码。
- 当前处境：M208 / 修复群聊中 NO_REPLY 在前端仍渲染为可见 running 气泡；`execution_mode=parallel`；`use_worktree=true`；worktree=`/Users/czj/Repos/nano-multiagent/.worktrees/M208`；branch=`milestone/M208`。
- 测试门禁：`cd /Users/czj/Repos/nano-multiagent/.worktrees/M208/src/IM/frontend && npm test -- --runInBand src/features/chat/**/*.test.ts* && npm run build && pytest /Users/czj/Repos/nano-multiagent/.worktrees/M208/tests/im_service/integration/test_m103_im_gateway_e2e.py /Users/czj/Repos/nano-multiagent/.worktrees/M208/tests/im_service/unit/test_relay_service.py`
- 允许范围：
  - `/Users/czj/Repos/nano-multiagent/.worktrees/M208/src/IM/frontend/src/features/chat/**`
  - `/Users/czj/Repos/nano-multiagent/.worktrees/M208/src/IM/frontend/package.json`
  - `/Users/czj/Repos/nano-multiagent/.worktrees/M208/src/IM/frontend/dist/**`
  - `/Users/czj/Repos/nano-multiagent/.worktrees/M208/tests/im_service/integration/test_m103_im_gateway_e2e.py`
  - `/Users/czj/Repos/nano-multiagent/.worktrees/M208/tests/im_service/unit/test_relay_service.py`
  - `/Users/czj/Repos/nano-multiagent/.worktrees/M208/TASKS/**`
  - `/Users/czj/Repos/nano-multiagent/.worktrees/M208/PROGRESS/**`
  - `/Users/czj/Repos/nano-multiagent/.worktrees/M208/ACCEPTANCE/**`
- 禁止范围：
  - `/Users/czj/Repos/nano-multiagent/.worktrees/M208/src/IM/application/**`
  - `/Users/czj/Repos/nano-multiagent/.worktrees/M208/src/personal_assistant/**`
  - `/Users/czj/Repos/nano-multiagent/.worktrees/M208/scripts/acceptance/**`
- Fresh evidence：
  - 浏览器重现：`/Users/czj/Repos/nano-multiagent/src/IM/frontend/.playwright-cli/page-2026-03-16T03-13-50-289Z.yml`
  - 结构化后端证据：`/Users/czj/Repos/nano-multiagent/output/playwright/m170-no-reply-running-leak-20260316.json`
  - runtime DB：`/Users/czj/Repos/nano-multiagent/ACCEPTANCE/m170-runtime/im_service.sqlite3`
- Prevention rules:
  - 真实入口行为与源码矛盾时，先确认 fresh runtime 与前端 dist 一致，避免旧 dev server / 旧产物造成假象。
  - NO_REPLY 验收必须覆盖 processing/running 与 completed 阶段，不能让协议字符串或内部状态对普通用户可见。
  - 修复限定在前端消费层收口，不改后端 schema、路由或群聊 mention 语义。
  - M206 已吞掉 suppressed `relay.completed` / `message.delivered`；本次 blocker 是 `relay.processing` / `relay.report` 仍把 `NO_REPLY` 作为 synthetic agent bubble 暴露。
- 基线门禁：首次执行失败于 `npm test` 前置环境，worktree 前端未安装依赖，报错 `/bin/sh: vitest: command not found`；需先补齐依赖再继续红绿测试。

## Roadpoints

### R1. 在前端消费层静默吞掉 NO_REPLY 的 processing/report synthetic bubble
- Status: TODO
- Acceptance:
  - `relay.processing` / `relay.report` 若只携带 NO_REPLY 协议 token，不生成任何可见 agent bubble。
  - 群聊线程与会话列表都不显示 `NO_REPLY`、`suppressed_by=no_reply_token`、`Agent is working` 或 `Agent replied`。
  - 既有 typed mention、picker mention、双 Agent 同线程回复相关前端回归继续为绿。
  - 现有正常 agent processing / report 文案仍可见，不误伤真实回复流。
- Tests Plan:
  - unit: 在 `chat-workspace-page.test.ts` 为 `toRelayAgentMessage()` 增加 `relay.processing` / `relay.report` 的 NO_REPLY 红测，并补页面级 SSE 回归锁住“线程与列表都不泄漏”。
  - contract: 不新增；本次不改 payload shape，只改前端消费规则。
  - integration: 复用页面级 React Query + SSE 流测试，确认真实页面在历史加载/实时事件混合下也保持静默。
  - e2e: 不在本 worker 内重跑真实浏览器；通过自动化门禁、dist 构建与 ACCEPTANCE 证据为主 agent 复验提供入口。
- Expected Tests:
  - `src/IM/frontend/src/features/chat/chat-workspace-page.test.ts::keeps relay.processing NO_REPLY tokens out of visible agent messages`
  - `src/IM/frontend/src/features/chat/chat-workspace-page.test.ts::keeps relay.report NO_REPLY tokens out of visible agent messages`
  - `src/IM/frontend/src/features/chat/chat-workspace-page.test.ts::keeps NO_REPLY processing and report events out of the live group thread and conversation preview`
  - `cd /Users/czj/Repos/nano-multiagent/.worktrees/M208/src/IM/frontend && npm test -- --runInBand src/features/chat/**/*.test.ts*`
  - `cd /Users/czj/Repos/nano-multiagent/.worktrees/M208/src/IM/frontend && npm run build`
  - `pytest /Users/czj/Repos/nano-multiagent/.worktrees/M208/tests/im_service/integration/test_m103_im_gateway_e2e.py /Users/czj/Repos/nano-multiagent/.worktrees/M208/tests/im_service/unit/test_relay_service.py`
- DoD:
  - 红测先证明当前前端会把 `relay.processing` / `relay.report` 的 NO_REPLY token 渲染成 synthetic agent bubble 或列表预览。
  - 最小实现后执行 milestone test gate 全绿。
  - C1/C2/C3 齐全，`PROGRESS` / `ACCEPTANCE` 写清根因、证据、回滚点与后续 M170 复验入口。
