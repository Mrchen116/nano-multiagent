# M222 - Agent 设置/新增页面产品收口

已在编码前阅读：`LOGBOOK.md`、`COMMENTING_GUIDE.md`。

- Milestone: M222 / 梳理并修复新增 Agent 页面关键产品问题
- Branch: `milestone/M222`
- Worktree: `/Users/czj/Repos/nano-multiagent/.worktrees/M222`
- Test Command: `cd /Users/czj/Repos/nano-multiagent/.worktrees/M222 && pytest tests/im_service/integration/test_agent_create_flow.py tests/im_service/integration/test_agent_config_api.py && pnpm --dir src/IM/frontend test -- agent-create agent-detail agents-list-mobile`
- Baseline:
  - Backend: `pytest tests/im_service/integration/test_agent_create_flow.py tests/im_service/integration/test_agent_config_api.py` 通过（8 passed）。
  - Frontend: `pnpm --dir src/IM/frontend test -- agent-create agent-detail agents-list-mobile` 当前因环境缺少 `pnpm` 失败，需在后续改用仓内可执行方式补跑前端门禁。

## R1 页面信息架构与 workspace 语义收口
- Status: TODO
- Context:
- Decision:
- Rationale:
- Evidence:
  - Tests: 待执行
  - Entry: 待执行
- Rollback:
- Commits: C1=, C2=, C3=
- Next: 收口 create/detail 的主次结构、workspace 语义与操作反馈。

## R2 allowlist / node / status 视觉交互收口与列表回归
- Status: TODO
- Context:
- Decision:
- Rationale:
- Evidence:
  - Tests: 待执行
  - Entry: 待执行
- Rollback:
- Commits: C1=, C2=, C3=
- Next: 收口 allowlist 与状态区噪音，并补齐 list/create/detail 回归。
