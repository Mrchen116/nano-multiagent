# bugfix-404-M2: workspace 隔离修复 — Progress

> 对齐: tasks.md

## 澄清记录

无

---

## R1 — node.register 带 agent_workspaces + _handle_register 种子落库

- Context: `node.register` 帧只含 agent id 列表，IM 首次见到 agent 时凭空填 managed default 路径，导致 worktree gateway 的本地 config workspace_root 无法传递给 IM。
- Decision: `send_register` 帧新增可选字段 `agent_workspaces: {agent_id: workspace_root}`；`_handle_register` 首见时优先用上报值，已存在则保持（"first seen wins" 幂等语义，与 feat-379-M6 同模式）；无字段退回旧逻辑（向后兼容）。
- Rationale: 决策 3——可选字段设计保新旧帧兼容；种子信息在注册时一次性传递，避免两步竞态窗口。
- Evidence:
  - Tests: `pytest tests/ -m "not e2e"` — 2681 passed, 1 skipped
  - Entry: N/A（纯后端协议层，无需 CLI/HTTP 入口额外验证）
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: N/A（单元测试覆盖三场景：首见种子/已存在不覆盖/无字段退回旧行为）
  - Visual/Interaction: N/A
- Rollback: `git revert 414e5cc`（C2），`git revert 555d600`（C1）
- Commits: C1=555d600, C2=414e5cc, C3=（本次）
- Next: R2 — sync_agent 不采用 mirror workspace_root

---

## R2 — sync_agent 不采用 mirror workspace_root

- Context: `sync_agent` 回拉 IM mirror 时，若 `payload["workspace_root"]` 非空就直接覆盖 runtime config，导致 worktree 正确配置的路径被 IM DB 里的旧 managed default 冲掉。
- Decision: `sync_agent` 优先查 `local_config.agents` 取该 agent 的 workspace_root；找不到（IM UI 新建的 agent 尚未写回 local_config）才用 factory。IM mirror 值完全不参与 runtime workspace 决策。
- Rationale: 决策 4——workspace_root 创建即定，本地 config 是唯一可信源；即使 IM DB 有脏值，runtime 也不受影响。
- Evidence:
  - Tests: `pytest tests/ -m "not e2e"` — 2682 passed, 1 skipped
  - Entry: N/A
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: 新增 test_sync_agent_ignores_mirror_workspace_root_and_uses_local_config；更新两个现有测试以反映修后正确语义
  - Visual/Interaction: N/A
- Rollback: `git revert b8e8e6f`（C2），`git revert a4b7fb4`（C1）
- Commits: C1=a4b7fb4, C2=b8e8e6f, C3=（本次）
- Next: R3 — update_profile 删除 workspace_root 参数，service 层封口

---

## R3 — update_profile 删除 workspace_root 参数，update 封口

（待补充）
