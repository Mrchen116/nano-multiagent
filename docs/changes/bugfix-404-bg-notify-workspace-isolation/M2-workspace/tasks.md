# bugfix-404-M2: workspace 隔离修复 — Tasks

> 对齐: ../design.md（决策 3/4/5）

## 目标

worktree 内 `e2e-up.sh` 起的 gateway，IM 广播与 runtime 实际 workspace 均为 worktree 路径，而非主仓默认路径。UI 编辑 agent 其他配置后 workspace_root 保持不变。

## 退出标准

- [x] `node.register` 帧携带 `agent_workspaces: {agent_id: workspace_root}`（R1）
- [x] `_handle_register` 首见 agent 时用上报值落库；已存在则保持不动（R1）
- [x] `sync_agent` workspace_root 一律取本地 config，不采用 IM mirror 值（R2）
- [x] `ConfigService.update_profile` 删除 `workspace_root` 参数，update 后存量非默认值保持（R3）
- [x] `pytest tests/ -m "not e2e"` 全绿（各 R 完成后）

## 测试策略

- 被测行为：
  1. send_register 帧含 agent_workspaces 字段
  2. _handle_register 首见种子落库（上报值）、已存在保持、无字段退回旧行为
  3. sync_agent 不采用 mirror workspace_root（IM 给脏值，runtime 用本地值）
  4. update_profile 签名删 workspace_root，update 后非默认值保持
- 已有测试在：
  - `tests/unit/personal_assistant/test_gateway_upstream_reporter.py`（扩展 send_register 断言）
  - `tests/unit/personal_assistant/test_gateway_im_config_sync.py`（扩展 sync_agent 脏值测试）
  - `tests/im_service/integration/test_gateway_im_registration.py`（扩展 _handle_register 种子落库）
  - `tests/im_service/unit/test_repositories_agent_profile.py`（扩展 update 不写 workspace_root）
  - `tests/im_service/unit/test_gateway_handler.py`（补 _handle_register 三场景）
- 落层：单元/集成，无 e2e marker
- 可选依赖 importorskip：无
- 一次性验收证据：无（纯后端逻辑，单测覆盖）

## Roadpoints

### R1 — node.register 带 agent_workspaces + _handle_register 种子落库

- 步骤: 写失败测试 → 修 upstream_reporter.send_register + gateway_handler._handle_register
- 验证: 新增单测全红 → 实现后全绿

**状态: DONE** — C1=555d600, C2=414e5cc

### R2 — sync_agent 不采用 mirror workspace_root

- 步骤: 写失败测试（IM 给脏值，runtime 期望本地值）→ 修 main.py sync_agent
- 验证: 新增单测全红 → 实现后全绿

**状态: DONE** — C1=a4b7fb4, C2=b8e8e6f

### R3 — update_profile 删除 workspace_root 参数，update 封口

- 步骤: 写失败测试（update 后非默认值保持）→ 修 config_service、repositories、routes/agents
- 验证: 新增单测全红 → 实现后全绿

**状态: DONE**
