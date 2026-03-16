# M208 Progress — 修复群聊 NO_REPLY 仍显示运行中气泡

## 启动记录
- 已阅读：`/Users/czj/Repos/nano-multiagent/.worktrees/M208/LOGBOOK.md`、`/Users/czj/Repos/nano-multiagent/.worktrees/M208/COMMENTING_GUIDE.md`、`/Users/czj/.claude/skills/tdd-execution-worker/SKILL.md`。
- 注释承诺：新增/修改 public API 继续遵守 Google 风格 docstring；注释只记录意图、边界、约束，不复述代码。
- 当前处境：M208，`execution_mode=parallel`，`use_worktree=true`，worktree=`/Users/czj/Repos/nano-multiagent/.worktrees/M208`，branch=`milestone/M208`。
- 基线观察：fresh acceptance 证据显示当前前端虽然已吞掉 suppressed completion / delivery receipt，但 `relay.processing` 与 `relay.report` 仍把 `summary=NO_REPLY` 渲染成 synthetic agent bubble，并同步污染会话列表预览。
- 基线门禁：首次执行卡在 worktree 前端依赖缺失，`npm test` 报 `/bin/sh: vitest: command not found`；后续先补齐依赖，再进入红绿验证。

## Roadpoint 记录

### R1. 在前端消费层静默吞掉 NO_REPLY 的 processing/report synthetic bubble
- Context:
  - M170 fresh browser 复验里，群聊 NO_REPLY turn 仍出现 `NO_REPLY` + `Agent is working`；结构化事件明确显示 `relay.processing.summary="NO_REPLY"`、`relay.report.summary="NO_REPLY"`，随后 completion/delivery 才带 `suppressed_by=no_reply_token`。
  - 现有前端只会在 completion/delivery 阶段吞掉 suppressed receipt；如果 processing/report 先生成 synthetic agent message，即使后续 receipt 被忽略，用户也已经看到运行中/已完成气泡，并污染会话列表预览。
- Decision:
  - 在 `src/IM/frontend/src/features/chat/chat-workspace-page.tsx` 新增精确 `NO_REPLY` token 判定，并在 `toRelayAgentMessage()` 收口：只要 relay synthetic message 的最终 content 是精确 `NO_REPLY`，就直接返回 `null`。
  - 在 `src/IM/frontend/src/features/chat/chat-workspace-page.test.ts` 增加 processing/report 的映射红测与群聊页面级 SSE 回归，锁定线程正文、状态文案和列表预览都不泄漏。
- Rationale:
  - 把 NO_REPLY 静默收口放在前端消费层，是最小改动，既不碰后端 schema，也不影响 mention 路由和真实 agent 文案。
  - 仅匹配精确 token，可避免误吞正常回复里提到 `NO_REPLY` 的真实文本。
- Evidence:
  - Tests:
    - 红测：`cd /Users/czj/Repos/nano-multiagent/.worktrees/M208/src/IM/frontend && ./node_modules/.bin/vitest run src/features/chat/chat-workspace-page.test.ts` 在修复前失败，新增两个 mapping 用例都收到 synthetic agent message `content="NO_REPLY"`。
    - 前端目标 suite：同命令修复后 `29 passed`。
    - 前端 chat 门禁：`cd /Users/czj/Repos/nano-multiagent/.worktrees/M208/src/IM/frontend && npm test -- --runInBand src/features/chat/**/*.test.ts*` → `67 passed`。
    - 前端 build：`cd /Users/czj/Repos/nano-multiagent/.worktrees/M208/src/IM/frontend && npm run build` → `built in 727ms`。
    - 后端门禁：`pytest /Users/czj/Repos/nano-multiagent/.worktrees/M208/tests/im_service/integration/test_m103_im_gateway_e2e.py /Users/czj/Repos/nano-multiagent/.worktrees/M208/tests/im_service/unit/test_relay_service.py` → `17 passed in 0.81s`。
  - Entry:
    - 前端现在会在 processing/report 阶段就静默吞掉精确 `NO_REPLY` token，因此真实群聊不会再出现 running/completed agent bubble，也不会让会话列表最后预览被 NO_REPLY 覆盖。
- Rollback:
  - 若需重做，回退到 C1 `303219d`，或只撤回 `src/IM/frontend/src/features/chat/chat-workspace-page.tsx` 与相关测试/证据文档。
- Commits: C1=`303219d`, C2=`da64475`, C3=待执行
- Next:
  - 文档提交后即可交给主 agent 重派 M170 真实验收。
