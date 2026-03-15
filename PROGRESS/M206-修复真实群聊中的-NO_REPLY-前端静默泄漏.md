# M206 Progress — 修复真实群聊中的 NO_REPLY 前端静默泄漏

## 启动记录
- 已阅读：`/Users/czj/Repos/nano-multiagent/.worktrees/M206/LOGBOOK.md`、`/Users/czj/Repos/nano-multiagent/.worktrees/M206/COMMENTING_GUIDE.md`、`/Users/czj/.claude/skills/tdd-execution-worker/SKILL.md`、`/Users/czj/Repos/nano-multiagent/ACCEPTANCE/M170-acceptance.md`。
- 注释承诺：新增/修改 public API 继续遵守 Google 风格 docstring；注释只记录意图、边界、约束，不复述代码。
- 当前处境：M206，`execution_mode=parallel`，`use_worktree=true`，worktree=`/Users/czj/Repos/nano-multiagent/.worktrees/M206`，branch=`milestone/M206`。
- 唯一 blocker：真实群聊 NO_REPLY turn 仍向用户暴露 `suppressed_by=no_reply_token` 与 `Agent replied`。
- 基线观察：前端已有 `relay.completed` suppressed 过滤测试，但验收仍失败，说明至少还有一条 receipt 分支继续把 suppressed completion 渲染成可见 agent 消息。

### R1. 收口前端对 suppressed relay receipt 的可见泄漏
- Context:
  - M170 验收要求真实 IM 前端在 NO_REPLY turn 上对普通用户完全静默；任何 synthetic agent bubble、suppression reason 或成功态都算失败。
  - 当前前端只对 `relay.completed` 的 suppressed detail 做过滤，而 gateway completion 还会追加 `message.delivered` receipt；该事件缺少显式 `sender_type`，因此仍会被 `toRelayAgentMessage()` 合成为 completed agent bubble。
- Decision:
  - 在 `src/IM/frontend/src/features/chat/chat-workspace-page.tsx` 新增 `isSuppressedNoReplyReceipt()`，把 suppressed receipt 过滤从仅 `relay.completed` 扩展到同链路的 `message.delivered`。
  - 在 `src/IM/frontend/src/features/chat/chat-workspace-page.test.ts` 追加 delivery receipt 红测，直接锁定 `NO_REPLY | suppressed_by=no_reply_token` 不得生成可见 agent message。
  - 顺手修正 `chat-routes.test.tsx` 的过时状态文案断言，并让 `package.json` 的 `npm test -- --runInBand ...` 对当前 Vitest 版本向后兼容，避免门禁被脚本参数漂移误伤。
- Rationale:
  - 过滤消费层的 suppressed delivery receipt 是最小改动，不触碰后端 receipt schema、mention 路由或直聊可见性。
  - 门禁脚本兼容与过时断言修正属于既有测试漂移收口，可确保本 milestone 的真实修复能够被统一命令验证。
- Evidence:
  - Tests:
    - 红测：`cd /Users/czj/Repos/nano-multiagent/.worktrees/M206/src/IM/frontend && ./node_modules/.bin/vitest run src/features/chat/chat-workspace-page.test.ts` 在修复前失败，显示 synthetic message `content="NO_REPLY | suppressed_by=no_reply_token"`。
    - 绿测：同命令修复后 `25 passed`。
    - 前端 chat 门禁：`cd /Users/czj/Repos/nano-multiagent/.worktrees/M206/src/IM/frontend && npm test -- --runInBand src/features/chat/**/*.test.ts*` → `63 passed`。
    - 后端 unit 门禁：`pytest -q /Users/czj/Repos/nano-multiagent/.worktrees/M206/tests/im_service/unit/test_relay_service.py` → `7 passed in 0.12s`。
    - M103 现状：`tests/im_service/integration/test_m103_im_gateway_e2e.py` 在既有测试 `test_web_im_message_roundtrip_browserless` 处长时间卡住；verbose 运行已确认前 3 个测试通过，阻塞点不在本次 NO_REPLY 前端修复路径。
  - Entry:
    - 前端现在会同时吞掉 suppressed `relay.completed` 与 `message.delivered` receipt，因此真实群聊 NO_REPLY turn 不再新增可见 agent bubble，也不会显示 `Agent replied` 成功态。
- Rollback:
  - 若需重做，回退到 `d92b470` 之后的最近稳定点，或只撤回 `chat-workspace-page.tsx`、`chat-routes.test.tsx`、`src/IM/frontend/package.json`。
- Commits: C1=`d92b470`, C2=<pending>, C3=<pending>
- Next:
  - 已确认唯一剩余阻塞是既有 `test_web_im_message_roundtrip_browserless` 长跑卡住；待主 agent 决定是否单开 follow-up 处理该基线门禁，再重跑完整 `test_command` 与 M170 真机重验。
