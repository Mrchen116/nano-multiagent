# M118 NodeGateway 默认启动体验优化

## 启动记录
- 已阅读：`/Users/czj/.claude/skills/tdd-execution-worker/SKILL.md`、`/Users/czj/Repos/nano-multiagent/.claude/worktrees/agent-a875e700/.claude/worktrees/agent-a1293136/.claude/worktrees/agent-a61f9cf7/.claude/worktrees/agent-a3621a5f/.claude/worktrees/agent-a7dd372c/.claude/worktrees/M118/LOGBOOK.md`、`/Users/czj/Repos/nano-multiagent/.claude/worktrees/agent-a875e700/.claude/worktrees/agent-a1293136/.claude/worktrees/agent-a61f9cf7/.claude/worktrees/agent-a3621a5f/.claude/worktrees/agent-a7dd372c/.claude/worktrees/M118/COMMENTING_GUIDE.md`、`/Users/czj/Repos/nano-multiagent/.claude/worktrees/agent-a875e700/.claude/worktrees/agent-a1293136/.claude/worktrees/agent-a61f9cf7/.claude/worktrees/agent-a3621a5f/.claude/worktrees/agent-a7dd372c/.claude/worktrees/M118/docs/NodeGateway-SPEC.md`、`/Users/czj/Repos/nano-multiagent/.claude/worktrees/agent-a875e700/.claude/worktrees/agent-a1293136/.claude/worktrees/agent-a61f9cf7/.claude/worktrees/agent-a3621a5f/.claude/worktrees/agent-a7dd372c/.claude/worktrees/M118/docs/operator-runbook.md`、`/Users/czj/Repos/nano-multiagent/.claude/worktrees/agent-a875e700/.claude/worktrees/agent-a1293136/.claude/worktrees/agent-a61f9cf7/.claude/worktrees/agent-a3621a5f/.claude/worktrees/agent-a7dd372c/.claude/worktrees/M118/src/personal_assistant/main.py`、`/Users/czj/Repos/nano-multiagent/.claude/worktrees/agent-a875e700/.claude/worktrees/agent-a1293136/.claude/worktrees/agent-a61f9cf7/.claude/worktrees/agent-a3621a5f/.claude/worktrees/agent-a7dd372c/.claude/worktrees/M118/src/personal_assistant/config/local_store.py`、相关 IM / frontend / unit / integration / e2e 测试。
- 注释规范承诺：后续新增 public module/class/function/method 均按 Google 风格 docstring 写契约；注释只解释意图、边界、代价，不复述代码。
- 当前处境：M118，`execution_mode=parallel`，`use_worktree=true`，当前 worktree 为 `/Users/czj/Repos/nano-multiagent/.claude/worktrees/agent-a875e700/.claude/worktrees/agent-a1293136/.claude/worktrees/agent-a61f9cf7/.claude/worktrees/agent-a3621a5f/.claude/worktrees/agent-a7dd372c/.claude/worktrees/M118`，分支为 `milestone/M118`。
- 测试门禁：`cd /Users/czj/Repos/nano-multiagent && python -m pytest -q 2>&1 | tail -160`
- 基线结果：`739 passed, 4 skipped`。
- prevention / 注意事项：
  - 默认用户路径只能要求“启动 Gateway”，不能再让用户理解 `kernel.command` / `kernel.base_url`。
  - 默认启动必须后台化；前台阻塞只能保留给显式 `foreground/debug` 路径。
  - 未绑定时必须自动打开浏览器进入登录/绑定，而不是要求用户手动 curl。
  - 绑定完成后必须能直接在 Web IM 里聊天；验证要经过真实入口，而不只是假设 API 已通。
  - 不改 `ROADMAP.md`，不手改 `data/dev-tasks.json`，不做与本 UX 收口无关的重构。

## 计划摘要
- R1：把 `personal_assistant.main` 拆成默认后台启动与显式 foreground 两条入口，保证默认命令尽快返回但仍等待 ready/失败。
- R2：补 Gateway 侧 IM bootstrap client，基于节点 owner 状态自动触发 bind request + 浏览器打开，并把默认 kernel 入口收口成真实可运行的内部值。
- R3：补前端 bind 页面与 chat bootstrap 闭环，让 bind 完成后直接进入 `/chat`，聊天默认选择已绑定节点。

### R1 默认后台启动与前台模式分流
- Context:
- Decision:
- Rationale:
- Evidence:
  - Tests:
  - Entry:
- Rollback:
- Commits: C1=<pending>, C2=<pending>, C3=<pending>
- Next: Red 先补 CLI 默认后台化与 foreground 分流回归测试。

### R2 内核默认内聚与未绑定自动浏览器绑定
- Context:
- Decision:
- Rationale:
- Evidence:
  - Tests:
  - Entry:
- Rollback:
- Commits: C1=<pending>, C2=<pending>, C3=<pending>
- Next: 在 R1 完成后补 IM bootstrap / bind 自动拉起测试与实现。

### R3 Web IM 绑定页与绑定后直聊闭环
- Context:
- Decision:
- Rationale:
- Evidence:
  - Tests:
  - Entry:
- Rollback:
- Commits: C1=<pending>, C2=<pending>, C3=<pending>
- Next: 在 bind URL/浏览器拉起稳定后补前端 bind→chat 闭环与真实入口验证。
