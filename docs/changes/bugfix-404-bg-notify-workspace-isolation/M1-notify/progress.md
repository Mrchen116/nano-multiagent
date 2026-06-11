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
- Commits: C1=1dd6d4c, C2=1882aad, C3=95916f44

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
- Commits: C1=f8a4906, C2=4c34a85, C3=e11faf4d

## R3 — _deliver_notification 改造：删裸 except pass，显式判断子 session，透传 workspace_root

- Context: `_deliver_notification` 用 `except ValueError: pass` 静默吞掉所有投递失败（包括非 ValueError），子 session 跳过逻辑仅靠异常隐式实现；`runs_registry.submit` 不传 workspace_root 导致非默认 workspace 下 session 定位失败
- Decision:
  1. `_wire_notification_callbacks` 在 wire 时一次性从 `runs_registry` 取出 `_session_manager`，传入 `_deliver_notification`（避免每次调用刺探私有属性）
  2. `_deliver_notification` 从 `record.workspace_root` 构造 `Path`，传入 `session_manager.get_session(parent, workspace_root=workspace_root)` 显式检查 kind，跳过子 session
  3. `runs_registry.submit(...)` 补充 `workspace_root=workspace_root` 参数
  4. 原 `except ValueError: pass` 改为 `except Exception as exc: log_error(...)`，保留可观察性
- Rationale: 信息流闭合：注册捕获 → 投递透传；异常可见性：静默吞包比日志差；子 session 判断从隐式（靠 raise）改为显式（读 metadata），行为意图明确
- Evidence:
  - Tests: `pytest tests/ -m "not e2e"` on `unit/bugfix-404` — 2692 passed, 0 failed
  - Entry: N/A（内核内部投递路径，无独立入口）
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: e2e 端到端验证 — `e2e-up.sh` 起栈（worktree 内 ephemeral 端口，agent workspace_root 指向 `.gateway-workspace/default-agent`，`workspace_is_default=false`）；发消息让 default-agent 后台跑 `sleep 5 && echo BG404DONE`；session JSONL(`sess_43aebc488044f77c`) 证明：① bash tool 以 `run_in_background=true` 注册任务 `b99031c268e0dae7d`；② 任务完成后 `<task-notification>` 以 `role=user` 注入父 session（修前路径在非默认 workspace 下会 ValueError 静默失败，修后成功）；③ agent 读到输出文件内容 `BG404DONE` 并正常回复；修复路径全通。
  - Visual/Interaction: N/A
- Rollback: 回退到 4c34a85（R2 C2）
- Commits: C1=87fb7b4, C2=2f81f0a, C3=3c085d10
