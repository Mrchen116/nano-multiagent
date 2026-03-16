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
  - 现有前端只会在 completion/delivery 阶段吞掉 suppressed receipt；如果 processing/report 先生成 synthetic agent message，即使后续 receipt 被忽略，用户也已经看到运行中/已完成气泡。
- Decision:
  - 待执行。
- Rationale:
  - 待执行。
- Evidence:
  - Tests: 待执行。
  - Entry: 待执行。
- Rollback:
  - 待执行。
- Commits: C1=待执行, C2=待执行, C3=待执行
- Next:
  - 安装前端依赖，补红测锁定 processing/report 泄漏，再以最小前端消费层实现收口。
