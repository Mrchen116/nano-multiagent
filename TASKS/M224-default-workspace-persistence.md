# M224 修复已有 Agent 默认 Workspace 未持久化导致 Bash cwd 回落仓库根

## Milestone Context
- Milestone: M224 / 修复已有 Agent 默认 Workspace 未持久化导致 Bash cwd 回落仓库根
- Execution: serial
- Worktree: `true`
- Worktree dir: `/Users/czj/Repos/nano-multiagent/.worktrees/M224`
- Branch: `milestone/M224`
- Test gate: `pytest tests/im_service/integration/test_agent_create_flow.py tests/im_service/integration/test_agent_config_api.py tests/personal_assistant/test_inbound_pipeline.py && npx pnpm --dir src/IM/frontend test -- --run agent-create agent-detail allowlist-selector`
- Allowed scope:
  - `src/IM/**`
  - `src/personal_assistant/**`
  - `src/agent/**`
  - `tests/**`
  - `TASKS/**`
  - `PROGRESS/**`
  - `ACCEPTANCE/**`
  - `data/dev-tasks.json`
- Forbidden scope:
  - 其他无关模块
  - 与 M224 无关的产品文案/视觉收口
- Prevention notes:
  - 根因不是 Bash 工具本身，而是 session/workspace_root 缺失后 runtime fallback 到 repo root。
  - 主运行态 `data/im_service.sqlite3` 里 agent `fuck` 的 `workspace_root` 当前为 `null`。
  - 旧直聊会话 `7947b93380fe43fd806c759ed1efccd9` 是真实问题现场。
  - 必须验证真实 direct chat/bash `pwd`，不能只看单元测试。
  - 不使用 isolation 参数。
  - 收尾需要合并 main、清理 worktree、更新 `data/dev-tasks.json`。
- Baseline:
  - 派工给定的 `tests/personal_assistant/test_inbound_pipeline.py` 在当前仓库不存在，原始门禁命令无法直接启动；本 milestone 以内会用现有对应测试 `tests/unit/personal_assistant/test_gateway_pipeline.py` 建立 red/green，并在收尾时同时报告这条门禁漂移。

## Roadpoints

### R1. 固化默认 workspace_root 未持久化与旧 profile 缺字段的红测
- Status: TODO
- Acceptance:
  - 红测证明 IM 创建 agent 未填写 workspace 时，数据库行仍写成 `NULL`，而不是默认 managed workspace。
  - 红测覆盖 gateway runtime 广播/注册创建出的 profile，防止只有 HTTP create path 被修。
  - 红测证明既有 `workspace_root IS NULL` 的旧 profile 需要迁移或读取兜底，而不能永远依赖 API 展示层临时回退。
  - 自动化覆盖创建、读取、会话复用三类场景的至少前两类。
- Tests Plan:
  - unit: 是；对 repository/config helper 的默认路径与迁移策略做快速边界覆盖。
  - contract: 否；本次不新增 HTTP 字段，只收紧持久化语义。
  - integration: 是；覆盖 create/list/get 以及 gateway register 路径的 DB 持久化行为。
  - e2e: 否；R2 做真实 direct chat 验证。
- Expected Tests:
  - `tests/im_service/integration/test_agent_config_api.py::*default*workspace*`
  - `tests/im_service/integration/test_agent_create_flow.py::*default*workspace*`
  - `tests/im_service/unit/test_repositories.py::*workspace*`
- DoD:
  - 红测先稳定失败并直指 `agent_profiles.workspace_root` 持久化缺口。
  - C1/C2/C3 齐全。
  - 最小相关测试集全绿。
  - `PROGRESS` 记录根因、迁移策略、回滚点。

### R2. 修复旧直聊 binding/session 刷新并完成真实 direct chat bash pwd 验证
- Status: TODO
- Acceptance:
  - 旧 profile `workspace_root` 缺失时，runtime/gateway 至少有迁移或读取兜底，agent `fuck` 可收敛到 `/Users/czj/nano-assistant/workspace/fuck`。
  - 旧 direct-chat binding 复用前会校验 kernel session metadata；缺少 `workspace_root` 时自动重建，不再冻结 repo-root 旧 session。
  - 对 agent `fuck` 的真实 direct chat 能证明 Bash `pwd` 落在 `/Users/czj/nano-assistant/workspace/fuck`。
  - 自动化覆盖创建与会话复用场景；收尾给出真实运行态证据。
- Tests Plan:
  - unit: 是；覆盖 gateway pipeline 对 legacy session metadata 缺失时的刷新策略。
  - contract: 是；复用现有 session contract，确认 `get_session` 返回 metadata 足以做复用判定。
  - integration: 是；覆盖 direct chat 复用旧 binding 时自动换新 session。
  - e2e: 是；真实 direct chat / bash `pwd` 验证。
- Expected Tests:
  - `tests/unit/personal_assistant/test_gateway_pipeline.py::*legacy*workspace*`
  - `tests/im_service/integration/test_m103_im_gateway_e2e.py::*legacy*kernel*session*`
  - `tests/contract/test_sessions_contract.py`
  - 真实运行态：agent `fuck` direct chat 执行 `pwd`
- DoD:
  - 代码、自动化和真实入口验证一致。
  - C1/C2/C3 齐全。
  - 记录测试结果、运行态证据、回滚点与 merge 结果。
