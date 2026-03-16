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
- Commits: C1=`4dca7de`, C2=`d7d533e`, C3=`d9d4316`
- Next: 处理整套前端并发下暴露的测试超时与校验抖动。

## R3 agent 页面回归稳定性修复
- Status: DONE
- Context: rebase 后复跑全量门禁时，`agent-create` 与 `agent-edit` 在整套 Vitest 并发下暴露 5s timeout；create 页的 system prompt 必填断言也因长输入/异步默认值路径不稳定而丢失。
- Decision: 对 create/edit 回归把长文本输入从逐字 `user.type` 收敛为 `fireEvent.change`，保留 checkbox/select/button 的真实交互；同时为最重的两个 happy-path 用例显式设置 `10000ms` 超时，避免它们在整套并发下被默认 5s 误杀。
- Rationale: 问题在测试驱动方式而不是产品逻辑。把真正耗时的长输入改成同步表单赋值，既能保留关键行为断言，又能避免全套测试竞争 CPU 时的假超时与校验抖动。
- Evidence:
  - Tests: `cd /Users/czj/Repos/nano-multiagent/.worktrees/M222 && pytest tests/im_service/integration/test_agent_create_flow.py tests/im_service/integration/test_agent_config_api.py && npx pnpm --dir src/IM/frontend test -- agent-create agent-detail agents-list-mobile`
  - Entry: 同一轮全量门禁里 `agent-create` / `agent-edit` 已从 timeout 转为稳定通过，create 必填校验重新稳定命中 `System prompt is required.`。
- Rollback: `d9d4316`
- Commits: C1=`26cceab`, C2=`1340c1b`, C3=`this commit`
- Next: 进入 merge / dev-tasks 收尾。
