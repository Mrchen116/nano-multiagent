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

- Context: `BashTool._run_background`、`_run_foreground`（auto-background 路径）和 `AgentTool._run_background`、`_resume_subagent` 注册任务时没有传 workspace_root
- Decision: 四处注册调用均补 `workspace_root=str(ctx.repo_root)`（bash 两路径、agent background 路径、resume 路径）；resume 路径用传入的 workspace_root 参数
- Rationale: 产生点即捕获，与决策 1 一致；ctx.repo_root 即 session workspace（由 `_resolve_execution_context` 保证）
- Evidence:
  - Tests: `pytest tests/unit/agent/background_tasks/test_background_tasks.py` — 23 passed；`pytest tests/ -m "not e2e"` — 2682 passed
  - Entry: N/A（工具层修改，无独立 HTTP 入口）
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: N/A（R3 统一回归）
  - Visual/Interaction: N/A
- Rollback: 回退到 95916f4（R1 C3）
- Commits: C1=f8a4906, C2=4c34a85, C3=（本次）

## R3 — _deliver_notification 改造：删裸 except pass，显式判断子 session，透传 workspace_root

_待填_
