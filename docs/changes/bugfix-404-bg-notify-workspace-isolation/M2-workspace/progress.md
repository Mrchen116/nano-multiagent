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

（待补充）

---

## R3 — update_profile 删除 workspace_root 参数，update 封口

（待补充）
