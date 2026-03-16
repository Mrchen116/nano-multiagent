# M222 - Agent 设置/新增页面产品收口

已在编码前阅读：`LOGBOOK.md`、`COMMENTING_GUIDE.md`。

- Milestone: M222 / 梳理并修复新增 Agent 页面关键产品问题
- Branch: `milestone/M222`
- Worktree: `/Users/czj/Repos/nano-multiagent/.worktrees/M222`
- Test Command: `cd /Users/czj/Repos/nano-multiagent/.worktrees/M222 && pytest tests/im_service/integration/test_agent_create_flow.py tests/im_service/integration/test_agent_config_api.py && pnpm --dir src/IM/frontend test -- agent-create agent-detail agents-list-mobile`
- Baseline:
  - Backend: `pytest tests/im_service/integration/test_agent_create_flow.py tests/im_service/integration/test_agent_config_api.py` 通过（8 passed）。
  - Frontend: 原始 `pnpm` 命令因环境缺少全局 `pnpm` 失败；后续改用 `npx pnpm --dir src/IM/frontend test -- agent-create agent-detail agents-list-mobile` 作为等价入口完成门禁。

## R1 页面信息架构与 workspace 语义收口
- Status: DONE
- Context: create/detail 页原先把 workspace 当前状态、workspace 设置、侧栏说明、底部反馈混成三套并行信息系统；用户指出的不只是单点文案，而是整体穿模、丑陋与层级混乱。
- Decision: 以 create/detail 共用的三层结构重排页面：`Basics` 承接身份字段，`Behavior` 承接 prompt/allowlist，`Runtime defaults` 承接 group/model/workspace；detail 页把 workspace 拆成“Workspace in use now”与“Saved workspace path for future runs”，create 页把 preview 改成“Workspace after creation”。
- Rationale: 先按“正在发生的状态”和“保存后才会生效的设置”切层，再决定每块放在哪里，能一次性解决 workspace 误导、侧栏堆叠和底部操作反馈抢戏的问题，而不是继续补碎片文案。
- Evidence:
  - Tests: `cd /Users/czj/Repos/nano-multiagent/.worktrees/M222 && pytest tests/im_service/integration/test_agent_create_flow.py tests/im_service/integration/test_agent_config_api.py && npx pnpm --dir src/IM/frontend test -- agent-create agent-detail agents-list-mobile`
  - Entry: create/detail 页面现在都能直接读出主表单、运行中状态与保存后语义，workspace 不再混淆“当前”与“设置”。
- Rollback: `4dca7de`
- Commits: C1=`4dca7de`, C2=`d7d533e`, C3=`this commit`
- Next: 继续记录 allowlist/node/status 收口与 list mobile 一致性证据。

## R2 allowlist / node / status 视觉交互收口与列表回归
- Status: DONE
- Context: allowlist 默认暴露 `Advanced`/`advanced/internal` 等内部概念，node/status 区既像说明栏又像操作栏，mobile list 仍沿用旧的 workspace 命名，容易让同一产品在不同页面说不同的话。
- Decision: allowlist 改成 `Recommended options`、`Saved choices outside the main list` 与 `Show more options`，去掉内部标签；detail 侧栏改成 `Runtime status` / `Direct chat` / `Node status` 三块；agents list mobile/desktop 统一改成 `Managed workspace` / `Custom workspace` 与 `Open workspace settings`。
- Rationale: 让默认路径只暴露产品语义，把少见能力折叠但仍保留已保存值，可同时降低噪音、保住可恢复性，并让列表页与详情页在 workspace 命名上保持一致。
- Evidence:
  - Tests: `cd /Users/czj/Repos/nano-multiagent/.worktrees/M222 && pytest tests/im_service/integration/test_agent_create_flow.py tests/im_service/integration/test_agent_config_api.py && npx pnpm --dir src/IM/frontend test -- agent-create agent-detail agents-list-mobile`
  - Entry: create/detail/list mobile 的 allowlist、workspace 和入口名称已一致；route 级 `agent-edit` 回归也覆盖了新结构与保存流。
- Rollback: `4dca7de`
- Commits: C1=`4dca7de`, C2=`d7d533e`, C3=`this commit`
- Next: Milestone 文档已齐，进入 rebase / merge / dev-tasks 收尾。
