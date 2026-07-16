# bugfix-465-M1: permission-watchdog-exemption — progress

## 状态

DONE（已提交代码、测试、文档，待合并到 unit/bugfix-465）。

## R1 — Verify/Red: 复现权限等待被误杀

- Context: bugfix-417-M3 R4 把心搏作为所有静默窗口的活性证据，去掉了 permission 特例。但权限等待时心搏链可能延迟或丢失，导致 120 秒后被误判 stalled。
- 测试：`tests/unit/personal_assistant/test_inbound_pipeline_permission_watchdog.py` 改写 `test_permission_pending_survives_without_heartbeat`：推送 `permission_request` 后停止 heartbeat 0.25s（超过 idle_timeout=0.1s），再 resolve。实现前该测试报 `TimeoutError`，即 C1 红测。
- Commit: 与 R2 同一提交。

## R2 — Green: 实现权限等待豁免与恢复

- Decision: 在 `inbound_pipeline.py` `_await_terminal_run_async` 内引入局部 `current_timeout` 变量：
  - 初始值 = `_run_idle_timeout_seconds`；
  - `permission_request` 事件到达时设为 `None`，完全暂停 idle 看门狗；
  - `permission_resolved` 到达时恢复 `_run_idle_timeout_seconds`，继续检测决策后卡死。
- Rationale: 这是 bugfix-417 设计文档里明确要求的语义（“等权限确认不被误杀”），且不依赖心搏链路在权限等待期间稳定到达。`timeout=None` 是“完全豁免”，不是有限兜底。
- Evidence:
  - 单元测试：`pytest -xvs tests/unit/personal_assistant/test_inbound_pipeline_permission_watchdog.py` → 10 passed。
  - 契约/全量：`pytest -m "not e2e" tests/unit/personal_assistant tests/contract` → 939 passed。
- Commit: `b8e3addfc` (`fix(bugfix-465/M1-fix): 权限等待期间完全豁免 idle 看门狗`)。

## R3 — Entry QA: 真 IM + 真 Gateway 端到端验证

- Context: 单元测试复现的是代码行为，必须证明用户在真实 IM 入口也能离开 120 秒后回来继续审批。
- Decision: 在 worktree 内用 `scripts/e2e-up.sh` 起真 IM + 真 Gateway；通过 IM WebSocket 等待 `permission.request`，等待 125 秒后提交 `allow_once`，观察 `permission.resolved` 与 `message.completed` 是否到达，并检查 `.gateway-workspace/default-agent/.gitconfig` 是否被写出。
- Rationale: 真实入口 = 浏览器/IM 等价路径；只有真 stack 能验证跨进程投递、observer、SSE/WebSocket 等集成缝。
- Evidence:
  - 命令：
    ```bash
    cd <worktree>
    bash scripts/e2e-up.sh --wt <worktree>
    source .e2e-ports.env
    export WT_DIR=<worktree>
    python verify_permission_watchdog.py
    bash scripts/e2e-down.sh --wt <worktree>
    ```
  - 输出：
    ```
    logged in user_id=...
    using agent_id=default-agent
    conversation_id=...
    sent trigger message, waiting for permission.request
    got permission.request request_id=... message_id=...
    pausing 125s to exceed idle timeout (120s)...
    resolving permission with allow_once
    got permission.resolved
    got message.completed
    PASS: run survived the parked wait; approved tool wrote .../.gateway-workspace/default-agent/.gitconfig
    ```
- 环境：本地 `:4000/health` 可达，主 config 已配置 `llm:` 段，`NANO_MULTIAGENT_RUN_LIVE_PROXY_E2E` 门控已满足。

## R4 — Docs: 回填 fix.md 与 milestone 文档

- 回填 `docs/changes/bugfix-465-permission-watchdog-exemption/fix.md` 的“修复”和“验证”两段。
- 创建本 `tasks.md` 与 `progress.md`。
- Commit: 待提交（C3）。

## Rollback

- 代码回退：`git revert b8e3addfc`。
- 行为回退：恢复 bugfix-417 的纯心搏活性检测，权限等待将不再被豁免。

## Next

- 将 `milestone/bugfix-465-M1` rebase 到 `origin/unit/bugfix-465`。
- 在 `unit/bugfix-465` worktree 内合并并 push。
- 清理 milestone worktree 与 branch，向 orchestrator 汇报 DONE。

## Env caveats

- 无阻塞；真实入口验证已通过。
