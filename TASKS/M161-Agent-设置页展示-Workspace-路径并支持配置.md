# M161 Task — Agent 设置页展示 Workspace 路径并支持配置

## 启动记录
- 已确认 worktree：`/Users/czj/Repos/nano-multiagent/.worktrees/M161`
- 已确认 branch：`milestone/M161`
- 已确认约束：仅在该 worktree 实施修复；不修改 `data/dev-tasks.json`
- 首轮阅读：
  - `src/IM/frontend/src/features/settings/agents/agents-list-page.tsx`
  - `src/IM/frontend/src/features/settings/agents/agent-detail-page.tsx`
  - `src/IM/frontend/src/features/settings/agents/agent-create-page.tsx`
  - `src/IM/frontend/src/features/settings/agents/im-agent-config-api.ts`
  - `src/IM/api/routes/agents.py`
  - `src/IM/application/config_service.py`
  - `src/IM/infra/repositories.py`
  - `src/personal_assistant/main.py`
  - 参考模板：`TASKS/M155-Agent-设置页商业化表单与反馈打磨.md`
  - 参考模板：`PROGRESS/M160-修复群聊创建参与者选择器显示与可操作性.md`

## 目标
在 IM 的 Agent 设置页中清楚展示每个 Agent 当前 workspace 路径，并提供清晰可操作的 workspace 设置入口，让用户既能看到当前工作目录，也能在设置页完成 workspace 路径配置。

## 明确问题
1. Agent 列表页当前只展示模型、节点与更新时间，没有 workspace 路径信息。
2. Agent 详情页当前只允许编辑 prompt / tools / model 等资料，没有 workspace 相关设置入口。
3. 现有 IM Agent 配置接口不返回也不接受 workspace 路径，gateway config sync 也无法消费来自 IM 的 workspace 变更。
4. 前后端测试尚未把 workspace 展示与设置链路纳入回归门禁。

## Scope
- 为 IM Agent 配置接口补充 workspace 路径读写能力，并返回可用于 UI 展示的当前路径与默认/自定义状态。
- 为 gateway config sync 消费 IM 下发的 workspace 路径，保证保存后在线节点能拿到更新后的工作目录。
- 为 Agent 列表页补充 workspace 路径展示与进入设置入口。
- 为 Agent 详情页与创建页补充 workspace 设置区，明确区分只读“当前路径”和可编辑“配置项”。
- 新增聚焦测试，覆盖后端接口、gateway sync、前端列表/详情/创建路径。
- 更新 `TASKS/M161-*.md` 与 `PROGRESS/M161-*.md`，记录 Roadpoints、验证命令、提交点与回滚边界。

## 非目标
- 不修改 `data/dev-tasks.json`。
- 不新增独立 Playwright 套件。
- 不改动与 workspace 设置无关的聊天流、节点管理或 data layer。

## Roadpoints

### R1. 打通 workspace 路径数据模型与接口
- Status: DONE
- Acceptance:
  - `/im/v1/agents` 与 `/im/v1/agents/{id}/config` 返回当前 workspace 路径。
  - create / patch 接口支持提交 workspace 路径配置，并区分默认路径与自定义路径。
  - config sync 拉取配置时可消费 workspace 路径而不是硬编码默认目录。
- Tests Plan:
  - IM contract / integration tests 覆盖 response shape、create、patch、sync 行为。
- DoD:
  - 后端与 gateway runtime 对 workspace 路径使用统一规则。

### R2. 设置页展示当前 workspace 并提供可编辑入口
- Status: DONE
- Acceptance:
  - Agent 列表页能直接看到每个 Agent 当前 workspace 路径。
  - Agent 详情页有清晰的 workspace 设置区，区分“当前路径（只读）”与“workspace 配置（可编辑）”。
  - 从列表进入详情后，用户可以修改并保存 workspace 设置。
- Tests Plan:
  - 前端列表/详情/创建页测试覆盖 workspace 展示、说明文案、保存 payload。
- DoD:
  - 用户不再需要猜测 Agent 实际工作目录，也能直接完成配置。

### R3. 聚焦验证、记录与收口
- Status: DONE
- Acceptance:
  - 跑完聚焦前后端验证命令并记录结果。
  - PROGRESS 写清根因、修复点、验证结果、提交点与回滚点。
- Tests Plan:
  - `pytest /Users/czj/Repos/nano-multiagent/.worktrees/M161/tests/im_service/contract/test_agent_config_contract.py /Users/czj/Repos/nano-multiagent/.worktrees/M161/tests/im_service/contract/test_agent_create_contract.py /Users/czj/Repos/nano-multiagent/.worktrees/M161/tests/im_service/integration/test_agent_config_api.py /Users/czj/Repos/nano-multiagent/.worktrees/M161/tests/im_service/integration/test_agent_create_flow.py /Users/czj/Repos/nano-multiagent/.worktrees/M161/tests/unit/personal_assistant/test_main.py`
  - `npm --prefix /Users/czj/Repos/nano-multiagent/.worktrees/M161/src/IM/frontend test -- --run src/features/settings/agents/agent-create.test.tsx src/features/settings/agents/agent-edit.test.tsx src/features/settings/agents/agents-list-mobile.test.tsx`
  - `npm --prefix /Users/czj/Repos/nano-multiagent/.worktrees/M161/src/IM/frontend run build`
- DoD:
  - 分支可提交，worktree 状态清晰可汇报。

## 提交计划
- C1: 文档化任务拆解与 Roadpoints
- C2: 后端 workspace 配置模型 / API / config sync
- C3: 前端设置页展示与编辑 + 聚焦验证收口
