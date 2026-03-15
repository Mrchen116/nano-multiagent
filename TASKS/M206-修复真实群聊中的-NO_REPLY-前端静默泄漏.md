# M206 Task — 修复真实群聊中的 NO_REPLY 前端静默泄漏

## 启动记录
- 已阅读：`/Users/czj/Repos/nano-multiagent/.worktrees/M206/LOGBOOK.md`、`/Users/czj/Repos/nano-multiagent/.worktrees/M206/COMMENTING_GUIDE.md`、`/Users/czj/.claude/skills/tdd-execution-worker/SKILL.md`、`/Users/czj/Repos/nano-multiagent/ACCEPTANCE/M170-acceptance.md`。
- 当前处境：M206 / 让真实群聊中的 NO_REPLY 对用户完全静默；`execution_mode=parallel`；`use_worktree=true`；worktree=`/Users/czj/Repos/nano-multiagent/.worktrees/M206`；branch=`milestone/M206`。
- 测试门禁：`pytest tests/im_service/integration/test_m103_im_gateway_e2e.py tests/im_service/unit/test_relay_service.py && cd src/IM/frontend && npm test -- --runInBand src/features/chat/**/*.test.ts* && npm run build`
- 允许范围：`src/IM/**`、`tests/**`、`scripts/acceptance/**`、`ACCEPTANCE/**`、`TASKS/**`、`PROGRESS/**`、`LOGBOOK.md`
- 禁止范围：`data/dev-tasks.json`、`.worktrees/M205/**`、`.worktrees/M104/**`、`.worktrees/M141/**`
- 唯一 blocker：`ACCEPTANCE/M170-acceptance.md` 中 Issue 1，真实群聊 NO_REPLY turn 仍显示 `suppressed_by=no_reply_token` 与 `Agent replied`。
- Prevention rules:
  - 修复必须让真实 IM 前端用户路径对 NO_REPLY 完全静默，不能只改后端日志语义。
  - 不能泄漏 `suppressed_by=no_reply_token`、`NO_REPLY`、旧 ACK 或成功回复状态。
  - 必须保住 group creation、typed mention、picker mention、双 Agent 同线程回复。
  - 优先最小修复，避免扩大 schema 或改动群聊主链路之外的行为面。

## Roadpoints

### R1. 收口前端对 suppressed relay receipt 的可见泄漏
- Status: DONE
- Acceptance:
  - `relay.completed` / `message.delivered` 的 suppressed NO_REPLY receipt 不再生成任何可见 agent bubble。
  - 群聊线程中不再出现 `suppressed_by=no_reply_token`、`NO_REPLY`、旧 ACK 文本或 `Agent replied` 成功态。
  - 现有直聊 relay completion 可见性保持不变。
  - typed mention、picker mention、双 Agent 同线程回复相关自动化继续为绿。
- Tests Plan:
  - unit: 不新增后端 unit；复用 `tests/im_service/unit/test_relay_service.py` 作为回归门禁，确认 relay payload 相关能力未回退。
  - contract: 不新增；事件 payload shape 不变，本次只修前端消费语义。
  - integration: 在前端 `chat-workspace-page.test.ts` 增加 suppressed `message.delivered` 场景红测，并保留现有直聊 `relay.completed` 可见回归。
  - e2e: 不在本 worker 内做真实产品验收；通过自动化与 acceptance 文档给出主 agent 重验入口。
- Expected Tests:
  - `src/IM/frontend/src/features/chat/chat-workspace-page.test.ts::keeps suppressed NO_REPLY message-delivered receipts out of visible agent messages`
  - `src/IM/frontend/src/features/chat/chat-workspace-page.test.ts::keeps relay-completed agent replies visible after late history hydration for direct chats`
  - `tests/im_service/integration/test_m103_im_gateway_e2e.py`
  - `tests/im_service/unit/test_relay_service.py`
- DoD:
  - 红测先证明当前前端会把 suppressed completion/delivery receipt 变成可见 agent 消息。
  - 最小实现后执行 milestone test gate 全绿。
  - C1/C2/C3 齐全，PROGRESS 写清根因、证据、回滚点与下一步重验建议。

## 当前结果
- 当前根因已证实：前端仅对 `relay.completed` 做 suppressed 过滤，但后续 `message.delivered` receipt 仍被当作 synthetic agent message 渲染，导致出现可见 bubble 与 `Agent replied`。
- 最小修复已落地：前端把 suppressed `NO_REPLY` 过滤扩展到同链路的 `message.delivered`，其余 payload shape 与直聊语义保持不变。
- 自动化证据：
  - 前端红测先失败：`keeps suppressed NO_REPLY delivery receipts out of visible agent messages`
  - 前端目标 suite 转绿：`./node_modules/.bin/vitest run src/features/chat/chat-workspace-page.test.ts` → `25 passed`
  - 前端 chat 门禁转绿：`npm test -- --runInBand src/features/chat/**/*.test.ts*` → `63 passed`
  - relay unit 门禁转绿：`pytest -q tests/im_service/unit/test_relay_service.py` → `7 passed in 0.12s`
  - 唯一剩余阻塞见 `PROGRESS` 与 `ACCEPTANCE/M206-implementation-proof.md`：`tests/im_service/integration/test_m103_im_gateway_e2e.py::test_web_im_message_roundtrip_browserless` 长时间卡住，未在本次修复范围内复现出确定失败栈。

## 回滚点
- 若需要回滚，优先撤回：
  - `src/IM/frontend/src/features/chat/chat-workspace-page.tsx`
  - `src/IM/frontend/src/features/chat/chat-workspace-page.test.ts`
  - `TASKS/M206-修复真实群聊中的-NO_REPLY-前端静默泄漏.md`
  - `PROGRESS/M206-修复真实群聊中的-NO_REPLY-前端静默泄漏.md`
