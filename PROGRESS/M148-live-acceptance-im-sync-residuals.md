# M148 修复 live acceptance 暴露的 IM 接口与动态同步残留问题

## 启动记录
- 已阅读：`LOGBOOK.md`、`COMMENTING_GUIDE.md`、`/Users/czj/.codex/skills/tdd-execution-worker/SKILL.md`。
- 已阅读强制材料：
  - `/Users/czj/Repos/nano-multiagent/.worktrees/M147/PROGRESS/M147-live-agent-dynamic-sync.md`
  - `/Users/czj/Repos/nano-multiagent/.worktrees/M147/TASKS/M147-live-agent-dynamic-sync.md`
  - `/Users/czj/Repos/nano-multiagent/.worktrees/M104/ACCEPTANCE/m104-runtime/gateway.log`
  - `/Users/czj/Repos/nano-multiagent/.worktrees/M104/ACCEPTANCE/m104-runtime/im.log`
- 当前处境：M148，`execution_mode=parallel`，`use_worktree=true`，worktree=`/Users/czj/Repos/nano-multiagent/.worktrees/M148`，branch=`milestone/M148`。
- 计划测试门禁：`PYTHONPATH=src pytest -q tests/im_service/unit/test_db_init.py tests/unit/personal_assistant/test_gateway_pipeline.py tests/unit/personal_assistant/test_main.py tests/unit/personal_assistant/test_m102_gateway_im_connection.py tests/im_service/integration/test_agent_create_flow.py tests/im_service/integration/test_m103_im_gateway_e2e.py`
- 基线结果：旧 M147 定向门禁 `39 passed in 0.57s`；真实 acceptance 证据显示 IM 共享 SQLite 连接在并发参数化查询上抖动，且动态同步路径对瞬时 config fetch 失败与既有 session prompt 刷新都没有兜住。

### R1 IM 并发读接口 sqlite 稳定性收口
- Context:
- Decision:
- Rationale:
- Evidence:
  - Tests:
  - Entry:
- Rollback:
- Commits: C1=, C2=, C3=
- Next:

### R2 动态同步残留：瞬时配置抖动重试 + 已有会话切换到新 profile
- Context:
- Decision:
- Rationale:
- Evidence:
  - Tests:
  - Entry:
- Rollback:
- Commits: C1=, C2=, C3=
- Next:

### R3 证据文档与 live acceptance 交接
- Context:
- Decision:
- Rationale:
- Evidence:
  - Tests:
  - Entry:
- Rollback:
- Commits: C1=, C2=, C3=
- Next:
