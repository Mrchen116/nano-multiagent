# bugfix-404-M1 progress

## R1 — BackgroundTaskRecord 补 workspace_root 字段 + registry 签名

- Context: `BackgroundTaskRecord` 无 `workspace_root` 字段，注册时信息在产生点即丢失，投递时无从取
- Decision: 在 `BackgroundTaskRecord` 加 `workspace_root: str | None = None`；`register_bash`/`register_subagent` 加同名可选参数并落入 record
- Rationale: 信息在产生点（注册时，session 必然活跃）一次性捕获、显式落进数据流，与 #64 同构
- Evidence:
  - Tests: `pytest tests/unit/agent/background_tasks/test_background_tasks.py` — 21 passed
  - Entry: N/A（纯数据模型修改，无独立入口）
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: N/A（R3 统一回归）
  - Visual/Interaction: N/A
- Rollback: 回退到 c589f5f（plan commit）
- Commits: C1=1dd6d4c, C2=1882aad, C3=（本次）

## R2 — bash/agent 工具注册调用传 workspace_root

_待填_

## R3 — _deliver_notification 改造：删裸 except pass，显式判断子 session，透传 workspace_root

_待填_
