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
  - 当前前端只对 `relay.completed` 的 suppressed detail 做过滤，而 gateway completion 还会追加 `message.delivered` receipt，极可能继续落成可见 agent 消息。
- Decision:
  - <pending>
- Rationale:
  - <pending>
- Evidence:
  - Tests: <pending>
  - Entry: <pending>
- Rollback:
  - <pending>
- Commits: C1=<pending>, C2=<pending>, C3=<pending>
- Next:
  - 先用前端红测锁定 `message.delivered` suppressed receipt 泄漏，再做最小实现并跑完整门禁。
